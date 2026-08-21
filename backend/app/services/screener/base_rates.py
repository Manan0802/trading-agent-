"""What this kind of fund has done to people before, in rupees.

The reference class, and it goes *before* the specific fund's story rather than
beside it. That ordering is not a style choice: Kahneman and Lovallo's work on
the planning fallacy, and Flyvbjerg's reference-class forecasting built on it,
both find that a base rate presented alongside a vivid individual case gets
ignored in favour of the case. The outside view has to land first.

Built by `scripts/build_base_rates.py` from 5.18M NAV rows and committed as
JSON, because a twenty-year base rate does not move between deploys and
recomputing it takes minutes.

## The one thing this file is for

Fifteen Indian investing apps were surveyed while designing this and **not one
turns volatility into a loss a reader can picture**. "Standard deviation 14.2"
and even "−43% worst year" are not answers to "what could happen to my money".
`₹4,56,000 of your ₹8,00,000` is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "base_rates.json"

# The horizons a person actually thinks in, in the order they should be read.
HORIZON_ORDER = ("1y", "3y", "5y", "7y", "10y")

HORIZON_WORDS = {
    "1y": "one year",
    "3y": "three years",
    "5y": "five years",
    "7y": "seven years",
    "10y": "ten years",
}


@dataclass(frozen=True)
class Horizon:
    key: str
    words: str
    windows: int
    loss_share: float
    worst: float
    p05: float
    median: float
    p95: float


@dataclass(frozen=True)
class BaseRate:
    category: str
    sub_category: str
    funds: int
    funds_wound_up: int
    horizons: tuple[Horizon, ...]
    worst_fall: float | None
    median_recovery_days: int | None
    worst_recovery_days: int | None
    never_recovered: int
    as_of: str

    def horizon(self, key: str) -> Horizon | None:
        return next((h for h in self.horizons if h.key == key), None)

    @property
    def shortest(self) -> Horizon | None:
        return self.horizons[0] if self.horizons else None

    @property
    def longest(self) -> Horizon | None:
        return self.horizons[-1] if self.horizons else None

    @property
    def first_safe_horizon(self) -> Horizon | None:
        """The shortest horizon at which fewer than one window in fifty lost money.

        This is the finding the whole table exists to deliver: across every
        equity category the loss share collapses from 16-22% at one year to
        0-2% at five. Holding period decides whether you lose money; which fund
        you picked does not.
        """
        return next((h for h in self.horizons if h.loss_share <= 0.02), None)


@lru_cache(maxsize=1)
def _payload() -> dict:
    return json.loads(_DATA.read_text())


@lru_cache(maxsize=1)
def _index() -> dict[tuple[str, str], BaseRate]:
    payload = _payload()
    out: dict[tuple[str, str], BaseRate] = {}
    for record in payload["categories"]:
        horizons = tuple(
            Horizon(
                key=key,
                words=HORIZON_WORDS[key],
                windows=values["windows"],
                loss_share=values["loss_share"],
                worst=values["worst"],
                p05=values["p05"],
                median=values["median"],
                p95=values["p95"],
            )
            for key in HORIZON_ORDER
            if key in record["horizons"]
            for values in [record["horizons"][key]]
        )
        out[(record["category"], record["sub_category"])] = BaseRate(
            category=record["category"],
            sub_category=record["sub_category"],
            funds=record["funds"],
            funds_wound_up=record.get("funds_wound_up", 0),
            horizons=horizons,
            worst_fall=record.get("worst_fall"),
            median_recovery_days=record.get("median_recovery_days"),
            worst_recovery_days=record.get("worst_recovery_days"),
            never_recovered=record.get("never_recovered", 0),
            as_of=payload["as_of"],
        )
    return out


def for_category(category: str, sub_category: str | None) -> BaseRate | None:
    """The reference class for a fund, or None when we have no honest one.

    Returns None rather than falling back to a broader class. "Equity funds
    have lost money in 18% of years" is a different claim from "Small Cap funds
    have", and quietly substituting one for the other is exactly the kind of
    silent widening this project reports rather than performs.
    """
    return _index().get((category, sub_category or ""))


def split_category(joined: str) -> tuple[str, str]:
    """`"Equity Scheme - Small Cap Fund"` into its two halves."""
    return tuple(joined.split(" - ", 1)) if " - " in joined else (joined, "")


def for_joined(joined: str) -> BaseRate | None:
    top, sub = split_category(joined)
    return for_category(top, sub)


def rupees_at_risk(rate: BaseRate, amount: float) -> float | None:
    """The worst peak-to-trough fall this category has had, on this amount.

    Deliberately the worst *fall*, not the worst annual return: a fall is what a
    person watches happen to a number on a screen, and it is the thing that
    makes them sell. The annual figure is milder and describes something nobody
    experiences directly.
    """
    if rate.worst_fall is None or amount <= 0:
        return None
    return round(amount * abs(rate.worst_fall), 2)


def coverage() -> dict:
    return dict(_payload()["coverage"], as_of=_payload()["as_of"])


def all_rates() -> list[BaseRate]:
    return sorted(
        _index().values(),
        key=lambda r: (r.category, r.sub_category),
    )
