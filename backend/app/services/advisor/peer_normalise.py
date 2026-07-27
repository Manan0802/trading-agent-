"""Turning a raw metric into a comparable 0-1 score against a peer group.

Two obvious approaches, each broken on its own:

*Percentile rank* is stable and outlier-proof, but throws away magnitude. The
best fund in a category scores 1.0 whether it beat second place by 0.1pp or by
8pp, which is exactly the information a user is asking for.

*Min-max* keeps magnitude but hands the whole scale to the extremes. One fund
with a freak number squashes every ordinary fund towards zero.

So blend them, and shift the blend by horizon: over three years a return gap is
signal and magnitude deserves weight, while over one month it is mostly noise
and only the ordering is worth trusting. Callers pass `w_rank` accordingly.
"""

from dataclasses import dataclass

import numpy as np

# The magnitude component is scaled between these percentiles of the peer
# group rather than between its min and max. Raw min-max hands the whole scale
# to the two most extreme funds: put one fund returning 300% into a category
# where everyone else sits between 10% and 14%, and every ordinary fund is
# compressed into the bottom hundredth of the range. Clipping the *output* at
# 0.95 does not help, because the damage is to the middle of the field, not the
# top. Scaling between the 10th and 90th percentile instead means a fund has to
# be genuinely unusual across a tenth of its peer group before it moves the
# scale at all.
_MAGNITUDE_LOW_PCTL = 10.0
_MAGNITUDE_HIGH_PCTL = 90.0

# One fund ranked against itself has proved nothing.
_NEUTRAL = 0.5

Value = float | None


def _clean(values: list[Value]) -> np.ndarray:
    return np.array([v for v in values if v is not None], dtype=float)


def hybrid(
    values: list[Value],
    w_rank: float,
    *,
    lower_is_better: bool = False,
) -> list[Value]:
    """Score each value against the others. `None` in, `None` out.

    Funds missing the metric are excluded from the scale entirely rather than
    counted as zero, which would drag the whole peer distribution down and
    quietly reward everyone else for another fund's missing data.
    """
    present = _clean(values)
    if present.size == 0:
        return [None] * len(values)
    if present.size == 1:
        return [None if v is None else _NEUTRAL for v in values]

    sign = -1.0 if lower_is_better else 1.0
    scale = PeerScale.fit(list(present * sign), w_rank=w_rank)
    return [None if v is None else scale.score(v * sign) for v in values]


@dataclass(frozen=True)
class PeerScale:
    """A fixed scale fitted to one peer group.

    Scoring a fund through it never mutates it, so a fund shown for information
    — one the user already holds, say — cannot shift the percentiles of the
    funds actually being ranked for a recommendation.
    """

    sorted_reference: np.ndarray
    low: float
    high: float
    w_rank: float

    @classmethod
    def fit(cls, reference: list[float], w_rank: float) -> "PeerScale":
        arr = np.sort(np.array(reference, dtype=float)) if reference else np.array([])
        if arr.size == 0:
            return cls(sorted_reference=arr, low=0.0, high=0.0, w_rank=w_rank)
        low = float(np.percentile(arr, _MAGNITUDE_LOW_PCTL))
        high = float(np.percentile(arr, _MAGNITUDE_HIGH_PCTL))
        if high <= low:
            # A peer group where 80% of funds share one value: fall back to the
            # full range so the few that differ are still separated.
            low, high = float(arr[0]), float(arr[-1])
        return cls(sorted_reference=arr, low=low, high=high, w_rank=w_rank)

    def score(self, value: float) -> float:
        n = self.sorted_reference.size
        if n == 0:
            return _NEUTRAL

        rank = float(np.searchsorted(self.sorted_reference, value, side="right")) / n

        spread = self.high - self.low
        if spread <= 0:
            magnitude = 0.0
        else:
            # Clamped rather than extrapolated: beyond the 10th-90th band we
            # are off the end of a scale there is no evidence for, and a fund
            # 5x past the 90th percentile is not 5x better than one just past it.
            magnitude = min(max((value - self.low) / spread, 0.0), 1.0)

        return self.w_rank * rank + (1.0 - self.w_rank) * magnitude
