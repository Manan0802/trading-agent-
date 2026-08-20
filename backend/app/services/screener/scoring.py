"""The exact arithmetic Bachatt ranks funds on, transcribed from their source.

Ported from `sip-optimizer` at commit 43a8bb9 (19 Aug 2026):
    server/scripts/fill_metrics.py      -- quality pillars, momentum/drawdown, grades
    server/scripts/fill_risk_scores.py  -- risk composite and tier
    server/services/performance.py      -- the outlier cap applied before metrics

Every constant below carries the name it has in their code so the two files can
be diffed by eye. `tests/test_scoring_parity.py` does better than eye: it
executes their real source as an oracle and asserts this module returns the
same numbers.

**The shape of the score, in one block:**

    quality = 0.45*consistency + 0.40*performance + 0.15*(1 - norm(vol))
       consistency = 0.50*roll1y + 0.25*roll6m + 0.15*roll3m + 0.10*roll1m
       performance = 0.55*ret3y  + 0.30*ret1y  + 0.15*ret3m

    score   = 0.73*quality + 0.15*momentum + 0.12*(1 - drawdown)

Roughly 85% of that is a trailing record and 27% of the final number is a
fourteen-day window. traa measured ranking-on-past-record three separate times
(50%, 38%) and cost at 87%. This module makes no claim either way -- it
reproduces their method faithfully so the two can finally be compared on one
universe. The judgement belongs on the screen, not in the arithmetic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ── Outlier neutralisation (performance.py) ──────────────────────────────────
# A single bad NAV, a split, or a restatement can move a day by more than any
# real fund does. Those days are zeroed rather than dropped, so calendar windows
# stay aligned and a 14-day lookback still covers 14 days.
MAX_DAILY_SIMPLE_FOR_METRICS = 0.25

# ── Momentum / drawdown (fill_metrics.py) ────────────────────────────────────
LOOKBACK = 14
WARMUP = 7
LINEAR_WEIGHTS = np.arange(1, LOOKBACK + 1, dtype=float)   # [1, 2, ..., 14]
TOTAL_WEIGHT = float(LINEAR_WEIGHTS.sum())                 # 105.0
DRAWDOWN_THRESHOLD = float(np.log(1 - 0.01))               # ≈ -0.01005
MOMENTUM_MAGNITUDE_CAP = 1.5
DRAWDOWN_MAGNITUDE_CAP = 2.0
NAV_ROWS_NEEDED = LOOKBACK + WARMUP + 1                    # 22 NAVs -> 21 returns

# ── Quality pillars (fill_metrics.py _compute_quality) ───────────────────────
PILLAR_WEIGHTS = {"consistency": 0.45, "performance": 0.40, "risk": 0.15}
# (column, w_rank, w_mag, weight-within-pillar)
CONSISTENCY_TERMS = (
    ("roll1y", 0.70, 0.30, 0.50),
    ("roll6m", 0.75, 0.25, 0.25),
    ("roll3m", 0.80, 0.20, 0.15),
    ("roll1m", 0.90, 0.10, 0.10),
)
PERFORMANCE_TERMS = (
    ("ret3y", 0.70, 0.30, 0.55),
    ("ret1y", 0.75, 0.25, 0.30),
    ("ret3m", 0.85, 0.15, 0.15),
)
RISK_TERM = ("vol", 0.75, 0.25)

# ── Final blend (fill_metrics.py _build_score_updates) ───────────────────────
W_QUALITY = 0.73
W_MOMENTUM = 0.15
W_DRAWDOWN = 0.12

# ── Grading (fill_metrics.py calculate_grades) ───────────────────────────────
GRADE_PCTL_VERY_GOOD = 90
GRADE_PCTL_GOOD = 65
GRADE_PCTL_AVG = 30
# Added by upstream on 2026-08-19 (commit 3a09adc). Tight clusters -- Liquid and
# Overnight debt especially -- produced p90/p65/p30 cutoffs sitting 0.001 apart,
# which split near-identical scores across Bad and Good. A floor widens the
# bands so close scores get close grades.
MIN_GRADE_CUTOFF_GAP = 0.02
# Graded within (category, sub_category) for these; within category for the rest.
SUB_CATEGORY_GRADE_CATEGORIES = frozenset({"Debt Scheme", "Commodity"})

# ── Risk composite (fill_risk_scores.py) ─────────────────────────────────────
W_RISK_VOLATILITY = 0.55
W_RISK_DRAWDOWN = 0.25
W_RISK_SORTINO = 0.15
W_RISK_MOMENTUM = 0.05
RISK_PCTL = (15, 30, 50, 70, 85)
RISK_TIERS = (
    "Low", "Low to Moderate", "Moderate",
    "Moderately High", "High", "Very High",
)


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation
# ─────────────────────────────────────────────────────────────────────────────

def minmax(series: pd.Series) -> pd.Series:
    """Scale to [0, 1] against the peer group, capped at 0.95.

    The cap is theirs and it is load-bearing: without it a single freak fund
    owns the top of the scale and compresses everyone ordinary underneath.
    (traa's own `peer_normalise` solves the same problem differently, by
    scaling between the 10th and 90th percentile. Do not mix the two.)
    """
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series([0.0] * len(series), index=series.index, dtype=float)
    return ((series - lo) / (hi - lo)).clip(upper=0.95)


def hybrid(series: pd.Series, w_rank: float, w_mag: float) -> pd.Series:
    """Percentile rank for stability, min-max for magnitude, blended.

    Rank weight rises as the horizon shortens: over three years a gap in
    returns carries information, over one month it is mostly noise and only the
    ordering is worth trusting.
    """
    rank_part = series.rank(method="average", pct=True)
    mag_part = minmax(series)
    return (w_rank * rank_part) + (w_mag * mag_part)


def make_oos_hybrid(ref_df: pd.DataFrame):
    """A `hybrid` that scores against a fixed reference distribution.

    Used for funds outside the eligible peer group: they get a comparable score
    for display without shifting the percentiles of the funds actually being
    ranked. Scoring a fund never mutates the scale it is measured against.
    """
    def hyb(series: pd.Series, w_rank: float, w_mag: float) -> pd.Series:
        ref = np.sort(ref_df[series.name].to_numpy())
        n = len(ref)
        lo, hi = (float(ref[0]), float(ref[-1])) if n else (0.0, 0.0)
        rng = hi - lo

        def one(x: float) -> float:
            rank = (np.searchsorted(ref, x, side="right") / n) if n else 0.0
            mag = 0.0 if rng == 0 else min(max((x - lo) / rng, 0.0), 0.95)
            return (w_rank * rank) + (w_mag * mag)

        return series.apply(one)

    return hyb


# ─────────────────────────────────────────────────────────────────────────────
# Quality + final score
# ─────────────────────────────────────────────────────────────────────────────

def compute_quality(df: pd.DataFrame, hyb=hybrid) -> pd.Series:
    """Three pillars over a peer group.

    `df` needs columns: roll1y roll6m roll3m roll1m ret3y ret1y ret3m vol.
    Pass `make_oos_hybrid(ref)` as `hyb` to score against another distribution.
    """
    consistency = sum(
        weight * hyb(df[col], w_rank, w_mag)
        for col, w_rank, w_mag, weight in CONSISTENCY_TERMS
    )
    performance = sum(
        weight * hyb(df[col], w_rank, w_mag)
        for col, w_rank, w_mag, weight in PERFORMANCE_TERMS
    )
    col, w_rank, w_mag = RISK_TERM
    risk = 1 - hyb(df[col], w_rank, w_mag)
    return (
        PILLAR_WEIGHTS["consistency"] * consistency
        + PILLAR_WEIGHTS["performance"] * performance
        + PILLAR_WEIGHTS["risk"] * risk
    )


def final_score(quality: float, momentum: float, drawdown: float) -> float:
    """Blend quality with the two fourteen-day signals."""
    return (W_QUALITY * quality) + (W_MOMENTUM * momentum) + (W_DRAWDOWN * (1 - drawdown))


# ─────────────────────────────────────────────────────────────────────────────
# Momentum / drawdown from a NAV series
# ─────────────────────────────────────────────────────────────────────────────

def cap_log_returns(log_ret: pd.Series, max_abs_simple: float = MAX_DAILY_SIMPLE_FOR_METRICS):
    """Zero out days whose simple move exceeds the cap. Returns (series, n_capped)."""
    if log_ret is None or len(log_ret) == 0:
        return log_ret, 0
    simple = np.exp(log_ret.to_numpy(dtype=float)) - 1.0
    over = np.abs(simple) > max_abs_simple
    n = int(over.sum())
    if n == 0:
        return log_ret, 0
    capped = pd.Series(np.log1p(np.where(over, 0.0, simple)), index=log_ret.index)
    return capped, n


def momentum_drawdown(log_ret: pd.Series) -> tuple[float | None, float | None]:
    """Recency-weighted momentum and drawdown over the last fourteen days.

    Both are magnitude-weighted, not binary: *how far* above the trigger (or
    below the threshold) a day ran is what counts, capped so one violent day
    cannot own the score. The seven-day warm-up exists so `rolling(7)` has no
    NaN anywhere in the scoring window -- without it momentum would be measured
    over fewer effective days than drawdown.

    Returns (None, None) when there is not enough history.
    """
    if log_ret is None or len(log_ret) < LOOKBACK + WARMUP:
        return None, None

    log_ret, _ = cap_log_returns(log_ret)
    if len(log_ret) < LOOKBACK + WARMUP:
        return None, None

    recent_extended = log_ret.tail(LOOKBACK + WARMUP)
    rolling_7d = recent_extended.rolling(window=WARMUP).mean()

    recent = recent_extended.tail(LOOKBACK).to_numpy(dtype=float)
    rolling_recent = rolling_7d.tail(LOOKBACK).to_numpy(dtype=float)

    # Adaptive trigger: 1.5x the fund's own recent average, floored at zero, so
    # "accelerating" is judged against the fund rather than a global constant.
    daily_trigger = np.where(rolling_recent > 0, 1.5 * rolling_recent, 0.0)
    weights = LINEAR_WEIGHTS[-len(recent):]

    trigger_safe = np.where(daily_trigger > 0, daily_trigger, 1e-8)
    mom_magnitude = np.where(
        (recent > daily_trigger) & (daily_trigger > 0),
        np.clip(recent / trigger_safe, 1.0, 1.0 + MOMENTUM_MAGNITUDE_CAP),
        np.where(recent > daily_trigger, 1.0, 0.0),
    )
    momentum = float(
        (mom_magnitude * weights).sum() / (TOTAL_WEIGHT * (1.0 + MOMENTUM_MAGNITUDE_CAP))
    )

    threshold_abs = abs(DRAWDOWN_THRESHOLD)
    dd_magnitude = np.where(
        recent < DRAWDOWN_THRESHOLD,
        np.clip((DRAWDOWN_THRESHOLD - recent) / threshold_abs + 1.0, 1.0, 1.0 + DRAWDOWN_MAGNITUDE_CAP),
        0.0,
    )
    drawdown = float(
        (dd_magnitude * weights).sum() / (TOTAL_WEIGHT * (1.0 + DRAWDOWN_MAGNITUDE_CAP))
    )
    return momentum, drawdown


# ─────────────────────────────────────────────────────────────────────────────
# Grading
# ─────────────────────────────────────────────────────────────────────────────

def grade_cutoffs(scores: np.ndarray) -> tuple[float, float, float]:
    """Percentile cutoffs with a minimum gap between band boundaries."""
    t_vg = float(np.percentile(scores, GRADE_PCTL_VERY_GOOD))
    t_g = float(np.percentile(scores, GRADE_PCTL_GOOD))
    t_a = float(np.percentile(scores, GRADE_PCTL_AVG))
    gap = MIN_GRADE_CUTOFF_GAP
    if t_vg - t_g < gap:
        t_g = t_vg - gap
    if t_g - t_a < gap:
        t_a = t_g - gap
    return t_vg, t_g, t_a


def grade_from_cutoffs(score: float, t_vg: float, t_g: float, t_a: float) -> str:
    """Graded by value, not rank position, so identical scores never split."""
    if score >= t_vg:
        return "Very Good"
    if score >= t_g:
        return "Good"
    if score >= t_a:
        return "Avg"
    return "Bad"


def grade_peer_key(category: str | None, sub_category: str | None) -> tuple:
    """Debt and Commodity grade within their sub-category; everything else within category."""
    if category in SUB_CATEGORY_GRADE_CATEGORIES:
        return (category, sub_category)
    return (category, None)


# ─────────────────────────────────────────────────────────────────────────────
# Risk composite
# ─────────────────────────────────────────────────────────────────────────────

def risk_score(df: pd.DataFrame) -> pd.Series:
    """Cross-category risk, 0-1, higher is riskier.

    Exists because SEBI's riskometer marks every equity scheme "Very High" --
    no separation between a large cap at ~12.6 volatility and a small cap at
    ~15.9, let alone a 30-volatility thematic. Sortino is rank-only on purpose:
    near-zero-volatility overnight funds produce values around 200, which would
    wreck any magnitude blend.

    `df` needs columns: volatility, drawdown_score, sortino, momentum_score.
    """
    vol_c = hybrid(df["volatility"], 0.60, 0.40)
    dd_c = hybrid(df["drawdown_score"], 0.70, 0.30)
    srt_c = 1 - hybrid(df["sortino"], 1.00, 0.00)
    mom_c = hybrid(df["momentum_score"], 0.70, 0.30)
    return (
        W_RISK_VOLATILITY * vol_c
        + W_RISK_DRAWDOWN * dd_c
        + W_RISK_SORTINO * srt_c
        + W_RISK_MOMENTUM * mom_c
    )


def risk_tier_cutoffs(scores: np.ndarray) -> tuple[float, ...]:
    return tuple(float(v) for v in np.percentile(scores, list(RISK_PCTL)))


def risk_tier_for(score: float, cutoffs: tuple[float, ...]) -> str:
    """Tiered by value ascending -- a HIGHER score is worse here."""
    for tier, cutoff in zip(RISK_TIERS, cutoffs):
        if score <= cutoff:
            return tier
    return RISK_TIERS[-1]
