"""The portfolio optimiser Bachatt builds its MAXX and Balanced baskets with.

Ported from `sip-optimizer`:
    services/optimizer.py        -- the SLSQP solve, the softmin constraint, the
                                    momentum/drawdown tactical overlay
    config/portfolio_baskets.py  -- basket definitions and per-slot weight bounds
    config/settings.py           -- STRATEGY_BOUNDS, RISK_FREE_RATE

Every constant below carries the name it has in their code so the two files can
be diffed by eye. `tests/test_basket_parity.py` does better than eye: it
executes their real source as an oracle and asserts this module returns the same
weights.

**The shape of the optimisation, in one block:**

    minimise   -metric(w) + penalty(w)      over w, subject to Σw = 1 and bounds
      metric   = Σ(w·score) - 0.05 · annualised_volatility(w)      [objective 'bachatt']
      penalty  = λ · max(0, max_loss_threshold - rolling_30d_min(w))
      λ        = 1.0 for 'bachatt', 1000.0 for 'sharpe' / 'sortino'
      threshold= STRATEGY_BOUNDS[strategy]['max_loss'], ×1.5 bullish, ×0.5 bearish

    then a tactical overlay multiplies each weight by a bucket factor keyed on
    the fund's 14-day momentum/drawdown class, and renormalises.

**Why the metric is a difference and not a ratio.** Sharpe and Sortino divide by
a risk number. An arbitrage or liquid fund's denominator collapses toward zero,
so score/vol runs to infinity and the solver puts everything in it. The linear
form survives that, which is the whole reason the 'bachatt' objective exists.
`test_basket_parity.py` holds a near-zero-variance fund for exactly this case.

**Purity.** No database, no network, no clock, no logging. Returns arrive as a
DataFrame of daily log returns with fund codes as columns; scores arrive as a
plain dict. Their `optimize_portfolio` also takes `precomputed`,
`injected_raw_weights`, `freq`, `current_weights` and `silent` -- a cache path, a
warm start and a log-level switch, none of which change the arithmetic. Dropped,
so this function is a function.

─────────────────────────────────────────────────────────────────────────────
Three things deliberately NOT ported
─────────────────────────────────────────────────────────────────────────────

1. **`PREFERRED_AMCS` / `PREFERRED_AMC_SCORE_DELTA`.** Upstream's
   `pick_fund_for_slot` takes the top-ranked fund, and if its fund house is not
   one of six favoured ones, swaps it for the best fund from those six that is
   within 0.03 score of the leader. That is distribution economics executing
   inside a quality ranking, and a screen that ranked on merit and then quietly
   substituted a house would be lying about what the number means. Not imported,
   not referenced; `test_preferred_amc_logic_is_absent` asserts that nothing
   executable in this module names them -- the only mentions permitted are the
   backticked ones in this paragraph, saying why they are gone.

2. **`min_lumpsum` pre-filtering (`PRE_FILTER_RATIO`, `PREFILTER_MIN_BUCKETS`).**
   Upstream drops any fund whose minimum investment exceeds 10% of the amount
   being invested (or the whole amount, for a daily SIP), reading `min_lumpsum`
   from a distributor feed. traa has no equivalent feed -- `serve.MISSING_COLUMNS`
   already names "Minimum investment" as a column we cannot build. **So the slot
   pools here are unfiltered by minimum investment: a fund can rank first in a
   slot and still be unbuyable at the user's amount, and the screen has to say
   so** rather than presenting the pick as actionable.

3. **`fixed_isins` (the INSTA_FD basket).** Two hardcoded ISINs at 0.5 each, no
   optimisation involved. `get_basket("INSTA_FD")` round-trips it so the
   definition is not lost, but nothing here optimises it and
   `basket_cat_composition` returns [] for it, exactly as upstream does.

─────────────────────────────────────────────────────────────────────────────
Which MAXX
─────────────────────────────────────────────────────────────────────────────

There are two incompatible definitions of "MAXX BASKET" in the reference, and
they disagree about more than one thing:

    backend  config/portfolio_baskets.py  5 slots, Commodity capped at 0.15,
                                          Debt and Flexi floored at 0.10
    frontend smart-sip/app/basket-builder 6 slots (adds a bare "Equity Scheme",
             + lib/basket-builder/        and uses bare "Flexi / Multi"),
               allocationBounds.ts        Commodity capped at 0.20, no floors

Their "Balanced" differs too: the frontend template has 5 slots including a
Large Cap slot the backend basket does not have, and no Flexi slot.

**The backend definition is the one ported here**, because it is the one the
optimiser actually enforces -- `weight_bounds_for_slot` is what feeds
`bounds_list`, and the frontend numbers only ever decorate a slider. If the two
are ever reconciled upstream, this file is where the disagreement is recorded.

─────────────────────────────────────────────────────────────────────────────
The slot keys do not exist in traa's taxonomy -- read this before using it
─────────────────────────────────────────────────────────────────────────────

Upstream stores its own category vocabulary: "Equity Index Fund",
"Sectoral/ Thematic", "Flexi / Multi" and "Commodity" are *categories* there.
traa derives categories from AMFI and `inputs.SEBI_SCHEME_TYPES` allows exactly
five: Equity Scheme, Debt Scheme, Hybrid Scheme, Other Scheme, Solution Oriented
Scheme. Measured against `app/data/fund_catalogue.json`:

    Equity Index Fund             no such category (nearest: Other Scheme /
                                  Index Funds, 364 funds)
    Sectoral/ Thematic            a *sub_category* of Equity Scheme, 246 funds
    Flexi / Multi::Flexi Cap Fund no such category (nearest: Equity Scheme /
                                  Flexi Cap Fund, 44 funds)
    Commodity::Gold, ::Silver     no Commodity category at all -- AMFI has
                                  none. Gold (23 funds) and silver (19) sit
                                  inside Other Scheme / FoF Domestic, next to
                                  Nasdaq trackers, separated only by name.
    Equity Scheme::Large & Mid Cap Fund   exists, 36 funds
    Debt Scheme::Liquid Fund              exists, 51 funds

So matched literally, every MAXX slot and two of BALANCED's four come back
empty. **That is a naming mismatch, not a missing universe** -- every fund
exists. The translation lives in `basket_slots.py`, deliberately in one place,
and it reuses `advisor/fund_universe.gold_funds()` for the commodity slots
rather than inventing a second definition of which funds are gold. This module
stays in upstream's vocabulary so it can be diffed against upstream's source.

Two of the mapped slots carry a caveat the screen has to repeat: Index Funds
(364 tracking wildly different indices) and Sectoral/ Thematic (246 betting on
different sectors) are not peer groups in any useful sense, so filling a slot
from either ranks which segment ran rather than which fund is better run. The
fund screen already says this about the same two groups.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.optimize import minimize

# ── Strategy bounds (config/settings.py) ─────────────────────────────────────
# `default_bounds` is carried for completeness; the basket path always builds
# bounds per slot instead, via `weight_bounds_for_slot`.
RISK_FREE_RATE = 0.04
STRATEGY_BOUNDS = {
    "conservative": {"max_loss": 0,      "default_bounds": (0.0, 0.40)},
    "balanced":     {"max_loss": -0.005, "default_bounds": (0.0, 0.40)},
    "aggressive":   {"max_loss": -0.01,  "default_bounds": (0.0, 0.40)},
}

# Conservative's threshold is 0, not a small negative -- so `0 * 1.5` and
# `0 * 0.5` are both 0 and the regime has no effect on it, while the penalty is
# live on essentially every portfolio (any negative 30-day window violates it).
REGIME_LOSS_MULTIPLIER = {"bullish": 1.5, "bearish": 0.5}


# ─────────────────────────────────────────────────────────────────────────────
# Basket definitions (config/portfolio_baskets.py)
# ─────────────────────────────────────────────────────────────────────────────

PORTFOLIO_BASKETS: dict[str, dict] = {
    "MAXX": {
        "name": "MAXX BASKET",
        "strategy": "aggressive",
        "slots": {
            "Equity Index Fund": 1,
            "Sectoral/ Thematic": 1,
            "Flexi / Multi::Flexi Cap Fund": 1,
            "Commodity::Gold": 1,
            "Commodity::Silver": 1,
        },
    },
    "BALANCED": {
        "name": "Balanced",
        "strategy": "balanced",
        "slots": {
            "Equity Scheme::Large & Mid Cap Fund": 1,
            "Flexi / Multi::Flexi Cap Fund": 1,
            "Commodity::Gold": 1,
            "Debt Scheme::Liquid Fund": 1,
        },
    },
    # No slots and no optimisation -- see point 3 of the docstring.
    "INSTA_FD": {
        "name": "Insta FD",
        "strategy": "conservative",
        "slots": {},
        "fixed_isins": [
            {"isin": "INF846K01412", "weight": 0.5},
            {"isin": "INF209K01RU9", "weight": 0.5},
        ],
    },
}

MAX_WEIGHT_DEFAULT = 0.40
MAX_WEIGHT_COMMODITY = 0.15
MIN_WEIGHT_DEBT = 0.10
MIN_WEIGHT_FLEXI = 0.10
MIN_BASKET_SIZE = 2
RANK_POOL_LIMIT = 50


def parse_slot_key(slot_key: str) -> tuple[str, str | None]:
    """`"Commodity::Gold"` -> `("Commodity", "Gold")`; a bare key -> `(key, None)`."""
    if "::" in slot_key:
        category, sub_category = slot_key.split("::", 1)
        return category, sub_category
    return slot_key, None


def weight_bounds_for_slot(slot_key: str) -> tuple[float, float]:
    """Per-slot `(min_weight, max_weight)`.

    Keyed on the CATEGORY half only -- every Commodity slot gets the same cap
    whether it is Gold or Silver. An unknown slot falls through to the default
    `(0.0, 0.40)` rather than raising, so a slot key that has drifted quietly
    loses its floor and its tighter cap instead of failing loudly. Theirs;
    reproduced.
    """
    cat = slot_key.split("::", 1)[0]
    if cat == "Commodity":
        return (0.0, MAX_WEIGHT_COMMODITY)
    if cat == "Debt Scheme":
        return (MIN_WEIGHT_DEBT, MAX_WEIGHT_DEFAULT)
    if cat == "Flexi / Multi":
        return (MIN_WEIGHT_FLEXI, MAX_WEIGHT_DEFAULT)
    return (0.0, MAX_WEIGHT_DEFAULT)


def max_weight_for_slot(slot_key: str) -> float:
    return weight_bounds_for_slot(slot_key)[1]


def get_basket(basket_id: str) -> dict | None:
    """Case- and whitespace-insensitive lookup; None for an unknown id."""
    return PORTFOLIO_BASKETS.get((basket_id or "").strip().upper())


def basket_cat_composition(basket_id: str) -> list[dict]:
    """One `{category, sub_category, count}` per slot. `[]` for an unknown basket.

    Also `[]` for INSTA_FD, which has no slots -- so an empty list means either
    "no such basket" or "a fixed-ISIN basket", and a caller that needs to tell
    them apart has to ask `get_basket` too. Theirs. (Their docstring's worked
    example is stale, incidentally: it shows MAXX producing an
    `{"category": "Equity Scheme"}` entry, and MAXX has no Equity Scheme slot.)
    """
    basket = get_basket(basket_id)
    if not basket:
        return []
    composition: list[dict] = []
    for slot_key, count in basket.get("slots", {}).items():
        category, sub_category = parse_slot_key(slot_key)
        composition.append(
            {"category": category, "sub_category": sub_category, "count": count}
        )
    return composition


# ─────────────────────────────────────────────────────────────────────────────
# Momentum / drawdown over the last fourteen days (services/optimizer.py)
# ─────────────────────────────────────────────────────────────────────────────

LOOKBACK = 14
WARMUP = 7
LINEAR_WEIGHTS = np.arange(1, LOOKBACK + 1, dtype=float)   # [1, 2, ..., 14]
TOTAL_WEIGHT = LINEAR_WEIGHTS.sum()                        # 105.0
MOMENTUM_MAX_SCALE = 1.25
DRAWDOWN_MAX_SCALE = 0.75
MOMENTUM_MAGNITUDE_CAP = 1.5   # max excess ratio above trigger
DRAWDOWN_MAGNITUDE_CAP = 2.0   # max depth ratio below threshold
DRAWDOWN_THRESHOLD = np.log(1 - 0.01)                      # ≈ -0.01005

# Tactical overlay buckets: [from_ratio, to_ratio, factor], where ratio is the
# fund's current weight divided by the weight the optimiser suggested. Below its
# suggested weight a momentum fund is topped up hard (3.0x at ratio < 0.5); above
# it, trimmed (0.8x past 3.0). Drawdown funds get the mirror image.
MOMENTUM_BUCKETS = [
    (3.0, np.inf, 0.8),
    (2.0, 3.0, 1.0),
    (1.5, 2.0, 1.1),
    (1.1, 1.5, 1.2),
    (0.75, 1.1, 1.5),
    (0.5, 0.75, 2.0),
    (0.0, 0.5, 3.0),
]

DRAWDOWN_BUCKETS = [
    (3.0, np.inf, 0.1),
    (2.0, 3.0, 0.2),
    (1.5, 2.0, 0.4),
    (1.1, 1.5, 0.6),
    (0.75, 1.1, 0.8),
    (0.5, 0.75, 0.9),
    (0.0, 0.5, 1.0),
]

NEUTRAL_BUCKETS = [
    (3.0, np.inf, 0.7),
    (2.0, 3.0, 0.75),
    (1.5, 2.0, 0.8),
    (1.1, 1.5, 0.9),
    (0.75, 1.1, 1.3),
    (0.5, 0.75, 1.4),
    (0.0, 0.5, 1.6),
]


def bucket_factor(ratio: float, buckets) -> float:
    """First bucket whose half-open `[low, high)` contains `ratio`, else 1.0.

    The fallthrough covers two live cases and neither is theoretical: a negative
    ratio matches nothing, and `np.inf` matches nothing either because the last
    bucket's test is `3.0 <= inf < inf`. Both come back 1.0, i.e. "leave the
    weight alone".
    """
    for low, high, factor in buckets:
        if low <= ratio < high:
            return factor
    return 1.0


def detect_momentum_drawdown(returns: pd.DataFrame, lookback: int = LOOKBACK, warmup: int = WARMUP):
    """Classify every column as momentum, drawdown or neutral over 14 days.

    Returns `(momentum_funds, drawdown_funds, momentum_scores, drawdown_scores,
    net_scores)`; the three score maps are keyed by fund code, the two sets hold
    codes. `net = momentum - drawdown`, positive means momentum, exactly zero
    means neutral.

    **Different from `scoring.momentum_drawdown`, on purpose.** That one is the
    fund-scorer's version out of `fill_metrics.py` and its trigger is a *rolling*
    7-day mean, recomputed for each of the 14 days. This one takes the mean of
    those rolling means -- one scalar per fund for the whole window -- so a fund
    accelerating late in the window is judged against its own average pace
    rather than against last week's. Same constants, different denominators, and
    the two genuinely disagree on real funds. Both are reproduced as written.

    Also unlike the scorer's version, this one has **no minimum history check**:
    with five rows of returns it happily scores five days and calls it fourteen,
    because `LINEAR_WEIGHTS[-len(recent):]` silently shortens the weight vector.
    The pool rule at the bottom of this module is what keeps such funds out.
    """
    recent_extended = returns.tail(lookback + warmup)

    rolling_7d = recent_extended.rolling(window=warmup).mean()
    avg_rolling_7d = rolling_7d.mean()
    momentum_trigger = np.maximum(1.5 * avg_rolling_7d.values, 0)

    recent = recent_extended.tail(lookback)
    fund_codes = recent.columns.tolist()

    weights = LINEAR_WEIGHTS[-len(recent):]

    # Momentum: how far above the trigger, not merely whether above it. With a
    # non-positive trigger the magnitude has nothing to divide by, so it falls
    # back to binary 1/0 -- `trigger_safe` exists only to keep numpy quiet in
    # the branch that is then discarded.
    trigger_safe = np.where(momentum_trigger > 0, momentum_trigger, 1e-8)
    mom_magnitude = np.where(
        (recent.values > momentum_trigger) & (momentum_trigger > 0),
        np.clip(recent.values / trigger_safe, 1.0, 1.0 + MOMENTUM_MAGNITUDE_CAP),
        np.where(recent.values > momentum_trigger, 1.0, 0.0),
    )
    momentum_scores_arr = (mom_magnitude * weights[:, None]).sum(axis=0) / (
        TOTAL_WEIGHT * (1.0 + MOMENTUM_MAGNITUDE_CAP)
    )

    # Drawdown: how far below a fixed -1% day, capped at three times it.
    threshold_abs = abs(DRAWDOWN_THRESHOLD)
    dd_magnitude = np.where(
        recent.values < DRAWDOWN_THRESHOLD,
        np.clip(
            (DRAWDOWN_THRESHOLD - recent.values) / threshold_abs + 1.0,
            1.0,
            1.0 + DRAWDOWN_MAGNITUDE_CAP,
        ),
        0.0,
    )
    drawdown_scores_arr = (dd_magnitude * weights[:, None]).sum(axis=0) / (
        TOTAL_WEIGHT * (1.0 + DRAWDOWN_MAGNITUDE_CAP)
    )

    net_scores_arr = momentum_scores_arr - drawdown_scores_arr

    momentum_scores = dict(zip(fund_codes, momentum_scores_arr))
    drawdown_scores = dict(zip(fund_codes, drawdown_scores_arr))
    net_scores = dict(zip(fund_codes, net_scores_arr))

    momentum_funds = set()
    drawdown_funds = set()
    for fund in fund_codes:
        ns = net_scores[fund]
        if ns > 0:
            momentum_funds.add(fund)
        elif ns < 0:
            drawdown_funds.add(fund)

    return momentum_funds, drawdown_funds, momentum_scores, drawdown_scores, net_scores


# ─────────────────────────────────────────────────────────────────────────────
# The optimiser (services/optimizer.py optimize_portfolio)
# ─────────────────────────────────────────────────────────────────────────────

ANNUALIZATION_FACTOR = 252

# A small diagonal nudge so the covariance matrix is strictly positive-definite
# whatever BLAS is underneath -- Accelerate on macOS, OpenBLAS on Linux. Without
# it a fund whose returns are constant (an overnight fund with a flat NAV, or a
# column of zeros from a backfill hole) makes the matrix singular, and the two
# backends then disagree about the weights. This is why results are stable
# across machines; `test_the_covariance_nudge_makes_a_singular_matrix_solvable`
# pins it.
COVARIANCE_RIDGE = 1e-8

ROLLING_WINDOW_DAYS = 30
ROLLING_KERNEL = np.ones(ROLLING_WINDOW_DAYS)

# Softmin sharpness. `np.min` is what the constraint means, but its gradient is
# discontinuous: the moment the argmin jumps to a different 30-day window SLSQP
# sees the objective kink and stalls. `-log(Σ exp(-α·x))/α` is smooth and
# converges to the true min as α grows. Their comment says "α=50 is accurate for
# return values in [-0.5, 0.5]"; measured, it is not especially accurate -- see
# `softmin` below -- but it is smooth, which is what the solver needs.
SOFTMIN_ALPHA = 50.0

RISK_AVERSION = 0.05
PENALTY_LAMBDA_BACHATT = 1.0
PENALTY_LAMBDA_OTHER = 1000.0

# Their second starting point perturbs the midpoint of the bounds with noise
# from a fixed-seed legacy RandomState, precisely so repeated calls agree.
PERTURBATION_SEED = 42
PERTURBATION_RANGE = 0.05

SLSQP_OPTIONS = {"maxiter": 1000, "ftol": 1e-8}
TRUST_CONSTR_OPTIONS = {"maxiter": 1000}


def covariance(returns: pd.DataFrame) -> np.ndarray:
    """Sample covariance of the daily log returns, plus the ridge."""
    return returns.cov().values + np.eye(returns.shape[1]) * COVARIANCE_RIDGE


def loss_threshold(strategy: str, regime: str) -> float:
    """The 30-day loss floor the penalty measures against, scaled by regime.

    Bullish *loosens* the floor (1.5 × a negative number is more negative) and
    bearish tightens it. Getting the two the wrong way round is silent -- the
    optimiser still solves, it just protects the portfolio hardest in the regime
    that needs it least.
    """
    threshold = STRATEGY_BOUNDS[strategy]["max_loss"]
    return threshold * REGIME_LOSS_MULTIPLIER.get(regime, 1.0)


def normalised_scores(
    fund_codes: Sequence[str], scores: dict | None, mean_returns: np.ndarray
) -> np.ndarray:
    """Fund scores min-maxed to [0, 1], with two fallbacks.

    Upstream calls this `score_array` and builds it inline. Three paths:

      * `raw.sum() == 0`  -- fall back to mean daily returns, shifted to
        non-negative. Note the test is on the SUM, not on "all missing": a pool
        whose scores happened to cancel to zero would take this branch too, and
        a universe of genuinely zero scores is indistinguishable from a universe
        where the caller passed no scores at all.
      * `max > min` -- ordinary min-max, so the best fund in the pool scores 1.0
        and the worst 0.0 *regardless of how close together they are*. Two funds
        0.001 apart become 1.0 and 0.0, and the optimiser treats that as the
        widest possible quality gap. Theirs.
      * otherwise -- a uniform `1/n`. Because the score enters the objective
        linearly and the weights sum to 1, a uniform array contributes the same
        constant for every allocation, so the solve collapses to
        minimum-variance. That is the right answer when nothing separates the
        funds; it is worth knowing it is what happens.
    """
    raw = np.array(
        [scores.get(code, 0.0) if scores else 0.0 for code in fund_codes], dtype=float
    )
    if raw.sum() == 0:
        raw = np.asarray(mean_returns, dtype=float).copy()
        raw -= raw.min()
    s_min, s_max = raw.min(), raw.max()
    if s_max > s_min:
        return (raw - s_min) / (s_max - s_min)
    return np.ones(len(fund_codes), dtype=float) / len(fund_codes)


def softmin(values: np.ndarray, alpha: float = SOFTMIN_ALPHA) -> float:
    """`-log(Σ exp(-α·x))/α` -- a smooth, always-pessimistic stand-in for min.

    Bounded: `min - log(k)/α <= softmin <= min` over k values. The lower end is
    reached when every value ties, and k here is the number of 30-day windows,
    which for a year of NAVs is around 170 -- so at α=50 the guaranteed slack is
    up to `log(170)/50 ≈ 0.103`, ten percentage points of return.

    Measured on a realistic 200-day series (171 windows, true min -12.6%) the
    softmin returns **-18.1%**: 5.5 percentage points more pessimistic than the
    worst month that actually happened. That is not a rounding difference. It
    means the loss constraint bites well before the stated `max_loss` threshold
    is really breached, and the effective threshold moves with how many windows
    the caller passed in. Reproduced as theirs, and named here so nobody reads
    `max_loss = -0.01` as a promise about a real month.
    """
    return -np.log(np.sum(np.exp(-alpha * np.asarray(values, dtype=float)))) / alpha


def rolling_30d_min_return(returns_values: np.ndarray, weights: np.ndarray) -> float:
    """Softmin over every 30-day cumulative simple return of the weighted book.

    Log returns are additive over time, so a 30-day sum is a convolution;
    `expm1` turns the cumulative log return back into a simple one.

    **The short-history guard does not do what it looks like it does.**
    `np.convolve(x, ones(30), mode="valid")` does not return an empty array when
    `x` is shorter than the kernel -- numpy slides the *shorter* array and hands
    back `30 - len(x) + 1` values, every one of them the sum of the whole
    history. So a fund with 20 days of NAV produces eleven identical "30-day
    windows", each of which is really its entire 20-day record, and the
    `len(rolling_cum) == 0` branch below is unreachable dead code for any
    non-empty input. The constraint does not switch off; it silently starts
    measuring something else. Ported as written, and it is the sharpest reason
    the pool rule at the bottom of this module insists on 210 NAV rows.
    """
    portfolio_log_returns = np.sum(returns_values * weights, axis=1)
    rolling_log_sum = np.convolve(portfolio_log_returns, ROLLING_KERNEL, mode="valid")
    rolling_cum = np.expm1(rolling_log_sum)
    if len(rolling_cum) == 0:
        return 0.0
    return softmin(rolling_cum)


def feasible_bounds(bounds_list) -> list[tuple[float, float]]:
    """Rescale bounds that cannot coexist with `Σw = 1`, rather than failing.

    With the equality constraint, `Σ lower <= 1 <= Σ upper` has to hold or SLSQP
    reports "Inequality constraints incompatible" on every attempt. Upstream's
    fix is proportional rescaling -- lowers to sum 0.999, uppers to sum 1.001 --
    which keeps a solve possible but **silently moves the caps the caller
    asked for**. The live trigger is a basket of commodity slots: two Gold slots
    at (0.0, 0.15) cap out at 0.30 together, so the uppers get multiplied by
    3.34 and the 15% commodity limit becomes 50%. It logs a warning upstream and
    that is all; here it returns quietly, so a caller that cares must compare
    what it passed with what came back.
    """
    lowers = np.array([b[0] for b in bounds_list], dtype=float)
    uppers = np.array([b[1] for b in bounds_list], dtype=float)
    if lowers.sum() > 1.0:
        lowers = lowers / lowers.sum() * 0.999
    if uppers.sum() < 1.0:
        uppers = uppers / uppers.sum() * 1.001
    return [(lowers[i], uppers[i]) for i in range(len(bounds_list))]


def starting_points(bounds_list, regime: str) -> list[np.ndarray]:
    """Three starting weight vectors, tried in order until one converges.

    The first is regime-shaped -- bullish starts almost everything off the FIRST
    column and bearish puts half of it there, which is positional, not a
    statement about that fund. The second is the midpoint of the bounds plus
    fixed-seed noise. The third reverses the first. All three are clipped into
    the bounds and renormalised, and renormalising after clipping can push a
    weight back outside its bounds; SLSQP treats them as hints, not as feasible
    points, so it does not matter. Note the first two divide by `n - 1`, so a
    one-fund call raises ZeroDivisionError in a non-neutral regime. Theirs.
    """
    num_assets = len(bounds_list)
    if regime == "bullish":
        init_weights = np.array([0.05] + [0.95 / (num_assets - 1)] * (num_assets - 1))
    elif regime == "bearish":
        init_weights = np.array([0.50] + [0.50 / (num_assets - 1)] * (num_assets - 1))
    else:
        init_weights = np.array([1 / num_assets] * num_assets)

    for i, (low, high) in enumerate(bounds_list):
        init_weights[i] = np.clip(init_weights[i], low, high)
    init_weights = init_weights / init_weights.sum()

    candidates = [init_weights]

    rng = np.random.RandomState(PERTURBATION_SEED)
    mid_weights = np.array([(low + high) / 2 for low, high in bounds_list])
    noise = rng.uniform(-PERTURBATION_RANGE, PERTURBATION_RANGE, num_assets)
    perturbed = np.clip(
        mid_weights + noise,
        [b[0] for b in bounds_list],
        [b[1] for b in bounds_list],
    )
    candidates.append(perturbed / perturbed.sum())

    rev_weights = init_weights[::-1].copy()
    for i, (low, high) in enumerate(bounds_list):
        rev_weights[i] = np.clip(rev_weights[i], low, high)
    candidates.append(rev_weights / rev_weights.sum())

    return candidates


def optimize_portfolio(
    returns: pd.DataFrame,
    bounds_list,
    strategy: str,
    regime: str,
    objective: str,
    scores: dict | None = None,
    current_portfolio: dict | None = None,
    return_raw: bool = False,
):
    """Weights for one basket. `(adjusted, success)`, or `(adjusted, success, raw)`.

    `returns` is daily log returns, funds as columns. `bounds_list` is one
    `(min, max)` per column, in column order -- normally from
    `weight_bounds_for_slot`. `objective` is 'bachatt', 'sharpe', or anything
    else, which means Sortino. `scores` is their `bachatt_scores`: a
    `{code: score}` map, missing codes read as 0.0. `current_portfolio` is a
    `{code: amount}` map of what is already held, used only by the tactical
    overlay.

    **`success=False` does not mean no weights.** Every SLSQP start and the
    trust-constr fallback can fail, and the function then returns clipped equal
    weights with `success=False` -- and skips the tactical overlay entirely, so
    a failed solve and a successful one do not even go through the same code
    path. A caller that ignores the flag ships an equal-weight portfolio as
    though it were optimised.

    **The returned weights can sit outside `bounds_list`.** SLSQP respects the
    bounds; the tactical overlay that runs afterwards multiplies each weight by
    a bucket factor between 0.1 and 3.0 and renormalises, and nothing re-checks
    the caps. A Commodity slot bounded at 0.15 can come back above it. The raw,
    in-bounds weights are available via `return_raw=True`, which is what a
    caller enforcing a mandate should be looking at.
    """
    fund_codes = returns.columns.tolist()
    (
        momentum_funds,
        drawdown_funds,
        momentum_scores,
        drawdown_scores,
        net_scores,
    ) = detect_momentum_drawdown(returns)
    cov_matrix = covariance(returns)
    returns_values = returns.values
    mean_returns_cached = returns.mean().values

    num_assets = len(fund_codes)
    max_loss_threshold = loss_threshold(strategy, regime)

    if objective == "bachatt":
        score_array = normalised_scores(fund_codes, scores, mean_returns_cached)
    else:
        score_array = None

    # A far lighter hand on the constraint for the bachatt objective, because
    # that score already carries risk inside it (sortino and drawdown are ~60%
    # of it). At 1000 the penalty swamps the score signal, most visibly in a
    # bearish regime where the threshold halves and near-zero-volatility funds
    # would take the whole book.
    penalty_lambda = PENALTY_LAMBDA_BACHATT if objective == "bachatt" else PENALTY_LAMBDA_OTHER

    def objective_function(weights):
        portfolio_return = np.dot(weights.T, mean_returns_cached)
        ann_return = portfolio_return * ANNUALIZATION_FACTOR

        if objective == "bachatt" and score_array is not None:
            portfolio_score_return = np.dot(weights, score_array)
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            ann_volatility = np.sqrt(portfolio_variance) * np.sqrt(ANNUALIZATION_FACTOR)
            metric_val = portfolio_score_return - RISK_AVERSION * ann_volatility
        elif objective == "sharpe":
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            portfolio_std = np.sqrt(portfolio_variance)
            ann_volatility = portfolio_std * np.sqrt(ANNUALIZATION_FACTOR)
            if ann_volatility == 0:
                metric_val = 0.0
            else:
                metric_val = (ann_return - RISK_FREE_RATE) / ann_volatility
        else:
            portfolio_daily_returns = np.sum(returns_values * weights, axis=1)
            downside_returns = portfolio_daily_returns[portfolio_daily_returns < 0]
            # 0.001 when nothing was ever negative -- a denominator, not a
            # measurement, and it makes the Sortino of a never-down book ~1000x
            # any real one.
            downside_dev = (
                np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(ANNUALIZATION_FACTOR)
                if len(downside_returns) > 0
                else 0.001
            )
            metric_val = (ann_return - RISK_FREE_RATE) / downside_dev

        # Soft, not hard: the solver is allowed to breach the loss floor and pay
        # for it. A hard constraint would make an infeasible request return
        # nothing at all.
        current_rolling_min = rolling_30d_min_return(returns_values, weights)
        violation = max(0, max_loss_threshold - current_rolling_min)
        return -metric_val + penalty_lambda * violation

    bounds_list = feasible_bounds(bounds_list)
    candidates = starting_points(bounds_list, regime)
    constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]

    result = None
    for w0 in candidates:
        try:
            res = minimize(
                objective_function,
                w0,
                method="SLSQP",
                bounds=bounds_list,
                constraints=constraints,
                options=SLSQP_OPTIONS,
            )
            if res.success:
                result = res
                break
        except Exception:
            continue

    if result is None:
        try:
            from scipy.optimize import LinearConstraint

            lc = LinearConstraint(np.ones(num_assets), 1.0, 1.0)
            res = minimize(
                objective_function,
                candidates[1],
                method="trust-constr",
                bounds=bounds_list,
                constraints=lc,
                options=TRUST_CONSTR_OPTIONS,
            )
            if res.success:
                result = res
        except Exception:
            result = None

    if result is None or not result.success:
        safe_weights = np.array([1 / num_assets] * num_assets)
        for i, (low, high) in enumerate(bounds_list):
            safe_weights[i] = np.clip(safe_weights[i], low, high)
        safe_weights = safe_weights / safe_weights.sum()
        if return_raw:
            return safe_weights, False, safe_weights
        return safe_weights, False

    raw_weights = result.x

    # ── Tactical overlay ────────────────────────────────────────────────────
    # This runs on every successful solve, including when nothing is currently
    # held. With no current portfolio every ratio is 1.0, which lands in the
    # 0.75-1.1 bucket, which is 1.5x for a momentum fund, 0.8x for a drawdown
    # fund and 1.3x for a neutral one -- so the optimiser's answer is
    # systematically tilted toward whatever ran in the last fortnight before
    # anyone sees it. It is not a rebalancing adjustment; it is a momentum tilt
    # wearing a rebalancing adjustment's clothes.
    if current_portfolio is not None:
        total_p = sum(current_portfolio.values())
        if total_p > 0:
            current_weights = (
                np.array([current_portfolio.get(code, 0.0) for code in fund_codes]) / total_p
            )
        else:
            current_weights = np.zeros_like(raw_weights)
    else:
        current_weights = np.zeros_like(raw_weights)

    safe_raw_weights = np.where(raw_weights == 0, 1.0, raw_weights)
    ratios = np.where(
        raw_weights == 0,
        1.0,
        np.where(current_weights == 0, 1.0, current_weights / safe_raw_weights),
    )

    adjusted_weights = np.zeros_like(raw_weights)
    for i, fund in enumerate(fund_codes):
        ratio = ratios[i]
        intensity = abs(net_scores.get(fund, 0.0))
        if fund in momentum_funds:
            final_factor = bucket_factor(ratio, MOMENTUM_BUCKETS) * (
                1 + (MOMENTUM_MAX_SCALE - 1.0) * intensity
            )
        elif fund in drawdown_funds:
            final_factor = bucket_factor(ratio, DRAWDOWN_BUCKETS) * (
                1 + (DRAWDOWN_MAX_SCALE - 1.0) * intensity
            )
        else:
            final_factor = bucket_factor(ratio, NEUTRAL_BUCKETS)
        adjusted_weights[i] = raw_weights[i] * final_factor

    adjusted_weights = adjusted_weights / adjusted_weights.sum()

    if return_raw:
        return adjusted_weights, True, raw_weights
    return adjusted_weights, True


# ─────────────────────────────────────────────────────────────────────────────
# NOT part of the port. The candidate pool, defined by rule instead of by hand.
# ─────────────────────────────────────────────────────────────────────────────
#
# Upstream fills a slot from `optimizer_include = 2`: a hand-curated column of
# roughly 180 funds, maintained by scripts like `include_amc.py` and
# `exclude_non_whitelisted_amcs.py`. We have no such column, and we must not
# create one. A curated list is the same discretion `PREFERRED_AMCS` was
# rejected for, only harder to see -- a fund house that is simply absent from
# the list never has to be swapped for, because it was never in the running.
#
# So the pool is a rule, and this is the whole of it:
#
#     A fund is in a slot's pool when
#       (a) its category equals the slot's category, and its sub_category equals
#           the slot's sub_category when the slot names one (a bare slot key
#           accepts every sub_category in that category, as upstream's SQL does);
#       (b) peer_size >= MIN_PEER_SIZE_FOR_POOL (8);
#       (c) nav_fresh is true;
#       (d) nav_rows >= MIN_NAV_ROWS_FOR_POOL (210).
#     Pools are sorted by score descending, then code ascending, and cut to
#     SLOT_POOL_LIMIT. The slot's pick is pool[0].
#
# Why each clause:
#
#   (b) 8 is `serve.MIN_PEERS_TO_RANK`, the floor the fund screen already uses
#       before it will publish a category's leaders, and it is there for a
#       reason that applies with more force here: a score is a percentile
#       statement about a peer group, so "best in category" across four funds is
#       the category with three funds left out. Contra Fund has 4 members and
#       Balanced Hybrid 4. Using one number in both places means the screen and
#       the basket can never disagree about whether a group is rankable.
#   (c) and (d) are upstream's own NAV gate, `_nav_eligible_fund_ids(min_rows=210,
#       fresh_days=30)`, kept at their numbers. 210 NAV rows is about ten months
#       of trading days -- comfortably past the 30 rows `rolling_30d_min_return`
#       needs before the loss constraint exists at all, and past the 21 that
#       `detect_momentum_drawdown` quietly does without. Freshness arrives as a
#       boolean rather than being computed, because this module has no clock.
#       Both are re-asserted here even though `universe.is_scoreable` already
#       enforces them, because a pool that ranks money should not depend on the
#       caller having remembered to run the other filter first.
#
# What the rule deliberately does NOT do: no fund house preference, no minimum
# investment, no AUM floor, no expense ratio screen, no hand-maintained list.
# Every fund that clears the four clauses competes, and the only thing that then
# separates them is the score.
#
# The tie-break is `code` ascending, where upstream's is 1-month return
# descending and then scheme code. `ScoredFund` does not carry a 1-month return,
# and reaching for one would drag a metrics lookup into a pure module; code
# ascending is arbitrary but stable, and it only ever decides between funds whose
# scores are equal to four decimal places.


@dataclass(frozen=True)
class PoolFund:
    """One candidate, carrying exactly the fields the pool rule reads.

    `code`, `category`, `sub_category`, `score` and `peer_size` all come
    straight off `universe.ScoredFund`. `nav_fresh` and `nav_rows` do not --
    they live on `FundInputs` / `FundMetrics` -- so a caller assembling these
    has to join the two, which is deliberate: it is the join that makes the
    freshness claim someone's responsibility rather than an assumption.
    """

    code: str
    category: str | None
    sub_category: str | None
    score: float
    peer_size: int | None
    nav_fresh: bool
    nav_rows: int


SLOT_POOL_LIMIT = RANK_POOL_LIMIT   # N. Their pool depth, so it is not a new opinion.
MIN_PEER_SIZE_FOR_POOL = 8          # == serve.MIN_PEERS_TO_RANK
MIN_NAV_ROWS_FOR_POOL = 210         # == their _nav_eligible_fund_ids(min_rows=210)


def pool_eligibility(fund: PoolFund) -> tuple[bool, str]:
    """Whether a fund may compete for a slot, and why not if it may not.

    A reason string rather than a bare False, same as `universe.is_scoreable`
    and for the same reason: a basket that silently drops candidates is
    indistinguishable from one that never had them.
    """
    if (fund.peer_size or 0) < MIN_PEER_SIZE_FOR_POOL:
        return False, (
            f"peer group of {fund.peer_size or 0}, under {MIN_PEER_SIZE_FOR_POOL} -- "
            "a score is a statement about peers and this group has too few"
        )
    if not fund.nav_fresh:
        return False, "no NAV published recently, so the fund looks wound up"
    if fund.nav_rows < MIN_NAV_ROWS_FOR_POOL:
        return False, (
            f"{fund.nav_rows} NAVs, under {MIN_NAV_ROWS_FOR_POOL} -- too little "
            "history for a 30-day loss constraint to mean anything"
        )
    return True, ""


def slot_matches(slot_key: str, fund: PoolFund) -> bool:
    """Category must match; sub_category must match only when the slot names one."""
    category, sub_category = parse_slot_key(slot_key)
    if fund.category != category:
        return False
    return sub_category is None or fund.sub_category == sub_category


def slot_pool(
    slot_key: str, funds: Sequence[PoolFund], limit: int = SLOT_POOL_LIMIT
) -> list[PoolFund]:
    """The ranked candidates for one slot. Empty when nothing qualifies."""
    eligible = [
        f for f in funds if slot_matches(slot_key, f) and pool_eligibility(f)[0]
    ]
    eligible.sort(key=lambda f: (-f.score, f.code))
    return eligible[:limit]


def basket_slot_pools(
    basket_id: str, funds: Sequence[PoolFund], limit: int = SLOT_POOL_LIMIT
) -> dict[str, list[PoolFund]]:
    """One pool per slot of a basket, empty lists included.

    Included rather than omitted so a caller can see which slots came up empty
    and say so -- with `MIN_BASKET_SIZE` at 2, a basket that filled one slot is
    not a basket. Every slot in both ported baskets asks for exactly one fund,
    so the slot's count is not used here; if a count above 1 ever appears it
    means "take that many off the top of this pool".
    """
    basket = get_basket(basket_id)
    if not basket:
        return {}
    return {
        slot_key: slot_pool(slot_key, funds, limit)
        for slot_key in basket.get("slots", {})
    }
