"""Turning one fund's NAV series into the numbers the scorer ranks on.

Pure over a NAV series. No database, no network, and no clock -- the clock
enters as an `as_of` argument. That is what makes this exhaustively testable,
and, more importantly, what makes it *comparable*: the reference implementation's
`calculate_performance_metrics` lifts cleanly out of its source through
`reference.read_source()` + AST, so every number here is held against theirs to
1e-12 in `tests/test_screener_metrics.py`.

Read this before changing anything: eight of the definitions below are odd, and
all eight are odd *upstream*. They are reproduced deliberately and each one is
commented where it lives. Fixing one silently would move every rank in the
product and no test outside this file would notice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from app.services.screener import scoring

# The single most consequential undocumented constant in the port.
#
# `get_nav_data_dynamic(fund_id, amfi_code, years=4)` cuts at
# `pd.Timestamp.now() - pd.DateOffset(years=4)`. Not `max(nav_date) - 4y`, and
# not the fund's full history. Every roll* and ret* number the scorer sees is
# computed inside that window: on a fund with 3,253 NAVs since 2013 the window
# is 981 rows, and its roll1y over four years is a different number from its
# roll1y over eleven. Nothing upstream documents this.
METRICS_WINDOW_YEARS = 4

TRADING_DAYS = 252
DAYS_PER_YEAR = 365.25

# Confirmed in the reference's own `config/settings.py`, not guessed.
RISK_FREE_RATE = 0.04

# A fund that has not published in ten days is treated as not live. Note this
# disagrees with `advisor/category_ranking._CLOSED_AFTER_DAYS`, which uses
# thirty. Both are deliberate -- upstream uses ten and traa's own screen uses
# thirty -- so the same fund can be rankable on one screen and wound-up on the
# other. `scripts/consistency.py` names the divergence rather than hiding it.
NAV_FRESH_DAYS = 10

# 22 NAVs -> 21 returns -> 14 scoring days after a 7-day warm-up.
MOMENTUM_NAV_ROWS = scoring.NAV_ROWS_NEEDED

# Below this, upstream returns a dict of zeros. See `_EMPTY` for the one place
# we knowingly diverge from it.
MIN_RETURNS_FOR_METRICS = 2

# Rolling windows, in calendar days, exactly as upstream names them. The 1y and
# 3y windows are annualised; the shorter three are not -- see `_rolling`.
ROLLING_WINDOWS = (
    ("rolling_1m", 30, None),
    ("rolling_3m", 91, None),
    ("rolling_6m", 182, None),
    ("rolling_1y", 365, 365),
    ("rolling_3y", 1095, 1095),
)

TRAILING_WINDOWS = (
    ("returns_1m", 1),
    ("returns_3m", 3),
    ("returns_6m", 6),
    ("returns_1y", 12),
    ("returns_3y", 36),
)


@dataclass(frozen=True)
class FundMetrics:
    """One fund's metrics.

    UNITS, because this is where the bug will be: every `returns_*`,
    `rolling_*`, `volatility`, `max_drawdown`, `worst_30d` and `best_30d` is a
    PERCENT (12.6 means 12.6%), because that is what upstream stores and what
    the scorer's normalisation was tuned against. `sortino` is a bare ratio.
    `momentum` and `drawdown` are 0-1 signals.

    The API layer converts to fractions at its own boundary -- `formatPercent()`
    in the frontend takes a fraction and would render 12.6 as "+1260.0%". A
    uniform unit slip is invisible to the scorer, because `minmax` and
    `rank(pct=True)` are both scale-invariant, so only an absolute-range test
    catches it. There is one.
    """

    annualized_return: float
    returns_1m: float
    returns_3m: float
    returns_6m: float
    returns_1y: float
    returns_3y: float
    rolling_1m: float
    rolling_3m: float
    rolling_6m: float
    rolling_1y: float
    rolling_3y: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    best_30d: float
    worst_30d: float
    negative_days_pct: float
    # Not scored. Stored so a screen can disclose them and so a rank change is
    # attributable next month.
    momentum: float | None
    drawdown: float | None
    history_years: float
    nav_rows: int
    capped_days: int
    first_nav_date: date | None
    last_nav_date: date | None
    nav_fresh: bool


def window_start(as_of: date, years: int = METRICS_WINDOW_YEARS) -> date:
    """The cutoff upstream uses: `now() - DateOffset(years=4)`, taken from the
    wall clock rather than from the fund's own last NAV.

    A fund that stopped publishing two years ago therefore gets a two-year
    window, not four years of its own history. Reproduced -- but through
    `as_of` rather than `now()`, which is the one improvement here: a run for a
    past date is repeatable, and theirs is not.
    """
    return (pd.Timestamp(as_of) - pd.DateOffset(years=years)).date()


def nav_to_log_returns(navs: list[tuple[date, float]]) -> pd.Series:
    """NAV levels to log returns, dropping non-positive NAVs first.

    Dropping *before* differencing is upstream's behaviour and it matters: a
    zero-NAV placeholder day in the middle of a series does not produce two
    broken returns, it produces one return spanning the gap. AMFI serves those
    placeholders for dates before a scheme launched.
    """
    if not navs:
        return pd.Series(dtype=float)
    index = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in navs])
    series = pd.Series([float(n) for _, n in navs], index=index).sort_index()
    clean = series[series > 0]
    if len(clean) < 2:
        return pd.Series(dtype=float)
    return np.log(clean / clean.shift(1)).dropna()


def _finite(value: float) -> float:
    """NaN and Inf become 0.0, as upstream does to every float it returns."""
    v = float(value)
    return 0.0 if (np.isnan(v) or np.isinf(v)) else v


def _trailing(simple: pd.Series, months: int) -> float:
    """One trailing return, as a percent.

    Two upstream behaviours reproduced here that both flatter young funds:

    1. If the fund is younger than the requested period, the whole available
       window is used instead -- so a two-year-old fund's `returns_3y` is its
       two-year CAGR, competing against genuine three-year numbers. We store
       `history_years` alongside so a screen can disclose it.
    2. The result is only annualised when the period actually spans a year or
       more; below that it is the raw cumulative return. So `returns_3m` is a
       three-month number, not an annualised one, and `returns_3y` is annualised.
       The scorer blends them as if they were commensurable.
    """
    if len(simple) == 0:
        return 0.0
    end = simple.index[-1]
    target_start = end - pd.DateOffset(months=months)
    period = simple if target_start < simple.index[0] else simple.loc[target_start:]
    if len(period) < 2:
        return 0.0
    cum = float(np.prod(1 + period) - 1)
    years = (period.index[-1] - period.index[0]).days / DAYS_PER_YEAR
    if years <= 0:
        return 0.0
    value = ((1 + cum) ** (1 / years) - 1) if years >= 1 else cum
    return _finite(value * 100)


def _rolling(log_ret: pd.Series, offset_days: int, annualize_days: int | None) -> float:
    """Mean of every overlapping calendar window, as a percent.

    Transcribed, not re-derived. Three details are load-bearing:

    * `searchsorted(..., side='right')` puts a window's first return strictly
      after `t - offset`. `'left'` would include one extra day per window.
    * `valid_mask` drops the leading windows that are not yet a full `offset`
      long, so a young fund is not credited with a short window's return.
    * The annualisation exponent is `365.25 / annualize_days`, not
      `1 / annualize_years`. Those differ, and the difference is real money.

    Prefix-sum plus searchsorted makes this O(n), not O(n x window) -- which is
    why the nightly pass over 4,957 funds is fifteen seconds and not worth
    parallelising.
    """
    idx = log_ret.index
    arr = log_ret.to_numpy(dtype=float)
    n = len(arr)
    if n == 0:
        return 0.0
    window_starts = idx - pd.Timedelta(days=offset_days)
    start_positions = idx.searchsorted(window_starts, side="right")
    valid_mask = idx >= idx[0] + pd.Timedelta(days=offset_days)
    cum = np.concatenate([[0.0], np.cumsum(arr)])
    window_sums = cum[np.arange(n) + 1] - cum[start_positions]
    values = np.expm1(window_sums[valid_mask])
    if len(values) == 0:
        return 0.0
    mean_cum = float(values.mean())
    if annualize_days:
        value = ((1 + mean_cum) ** (DAYS_PER_YEAR / annualize_days) - 1) * 100
    else:
        value = mean_cum * 100
    return _finite(value)


def _empty(navs: list[tuple[date, float]], as_of: date) -> FundMetrics:
    """What a series too short to measure produces.

    **A deliberate divergence, and the only one in this module.** Upstream's
    early return for `len(series) < 2` hands back a dict of eight keys -- it is
    missing `returns_1y`, `rolling_1y` and the rest entirely, so any caller that
    reads one gets a KeyError rather than a zero. Reproducing a KeyError would
    be reproducing a crash, so this returns a complete record of zeros instead.
    Every scored field is identical to upstream's for the keys upstream has.
    """
    dates = sorted(d for d, _ in navs)
    first = dates[0] if dates else None
    last = dates[-1] if dates else None
    return FundMetrics(
        annualized_return=0.0,
        returns_1m=0.0, returns_3m=0.0, returns_6m=0.0, returns_1y=0.0, returns_3y=0.0,
        rolling_1m=0.0, rolling_3m=0.0, rolling_6m=0.0, rolling_1y=0.0, rolling_3y=0.0,
        volatility=0.0, sharpe=0.0, sortino=0.0, max_drawdown=0.0,
        best_30d=0.0, worst_30d=0.0, negative_days_pct=0.0,
        momentum=None, drawdown=None,
        history_years=0.0, nav_rows=len(navs), capped_days=0,
        first_nav_date=first, last_nav_date=last,
        nav_fresh=is_fresh(last, as_of),
    )


def is_fresh(last_nav_date: date | None, as_of: date) -> bool:
    if last_nav_date is None:
        return False
    return (as_of - last_nav_date).days <= NAV_FRESH_DAYS


def compute(
    navs: list[tuple[date, float]],
    as_of: date,
    momentum_navs: list[tuple[date, float]] | None = None,
) -> FundMetrics:
    """Every metric for one fund, from NAVs already narrowed to the window.

    `navs` must already be the four-year slice -- `window_start()` gives the
    cutoff, and the caller reads it out of the store, because this function
    holds no clock beyond `as_of`.

    `momentum_navs` is the last 22 NAVs over the fund's **entire** history, not
    a tail of `navs`. Upstream's `compute_momentum_drawdown` runs
    `ORDER BY nav_date DESC LIMIT 22` with no window cutoff at all. For a fund
    with 22 NAVs inside the window the two are provably identical; for a
    rarely-publishing one they are not. Passing None falls back to `navs`, which
    is right for tests and wrong for a sparse fund in production.
    """
    log_ret = nav_to_log_returns(navs)
    if len(log_ret) < MIN_RETURNS_FOR_METRICS:
        return _empty(navs, as_of)

    # Applied here, not by the caller: upstream caps inside
    # `calculate_performance_metrics`, so a caller handing in a pre-capped
    # series would double-apply it. Reuses the ported function rather than
    # re-implementing the 25% rule, which now exists in exactly one place.
    log_ret, capped_days = scoring.cap_log_returns(log_ret)
    simple = np.exp(log_ret) - 1

    total_cum = float(np.prod(1 + simple) - 1)
    span_days = (log_ret.index[-1] - log_ret.index[0]).days
    years = span_days / DAYS_PER_YEAR
    cagr = ((1 + total_cum) ** (1 / years) - 1) if years >= 1 else total_cum

    # pandas' default ddof=1. Not a detail: ddof=0 moves every volatility and
    # therefore every risk tier.
    ann_vol = float(log_ret.std()) * np.sqrt(TRADING_DAYS)
    sharpe = 0.0 if (ann_vol == 0 or np.isnan(ann_vol)) else (cagr - RISK_FREE_RATE) / ann_vol

    # Non-standard, and reproduced verbatim: this is the standard deviation of
    # the negative returns about *their own mean*, not the root-mean-square
    # shortfall below a minimum acceptable return. It then divides an annual
    # CAGR by a deviation derived from daily data. This is exactly why
    # `scoring.risk_score` uses sortino rank-only -- overnight funds produce
    # values around 200 and a magnitude term would be meaningless.
    negatives = log_ret[log_ret < 0]
    downside_dev = 0.0001 if len(negatives) == 0 else float(negatives.std()) * np.sqrt(TRADING_DAYS)
    sortino = (
        0.0
        if (downside_dev == 0 or np.isnan(downside_dev))
        else (cagr - RISK_FREE_RATE) / downside_dev
    )

    cumulative = (1 + simple).cumprod()
    peak = cumulative.expanding(min_periods=1).max()
    max_dd = float(((cumulative - peak) / peak).min())

    # Thirty *rows*, not thirty calendar days -- while `rolling_1m` above is
    # thirty calendar days. Inconsistent upstream; both reproduced.
    #
    # And a second, sharper quirk: below thirty returns, `np.convolve` silently
    # swaps its arguments so the longer `ones(30)` becomes the sliding window.
    # Every output is then the sum of the *entire* series, so a fund with three
    # returns has its whole lifetime return reported as both its best and its
    # worst thirty-day move. That is what upstream ships. Guarding against it
    # here would break parity, so it is reproduced and named instead -- and it
    # is one more reason `history_years` is stored and disclosed.
    log_arr = log_ret.to_numpy(dtype=float)
    rolling_30d = np.expm1(np.convolve(log_arr, np.ones(30), mode="valid"))
    best_30d = float(rolling_30d.max()) if len(rolling_30d) > 0 else 0.0
    worst_30d = float(rolling_30d.min()) if len(rolling_30d) > 0 else 0.0

    trailing = {name: _trailing(simple, months) for name, months in TRAILING_WINDOWS}
    rollings = {name: _rolling(log_ret, days, ann) for name, days, ann in ROLLING_WINDOWS}

    momentum_source = momentum_navs if momentum_navs is not None else navs
    momentum, drawdown = scoring.momentum_drawdown(nav_to_log_returns(momentum_source))

    # From the sorted dates, not from the caller's list order. The store always
    # returns rows ordered, but this function is pure and public, and a reversed
    # list must not silently produce a fund whose history "starts" at its end.
    dates = sorted(d for d, _ in navs)
    first_nav_date = dates[0]
    last_nav_date = dates[-1]

    return FundMetrics(
        annualized_return=_finite(cagr * 100),
        **trailing,
        **rollings,
        volatility=_finite(ann_vol * 100),
        sharpe=_finite(sharpe),
        sortino=_finite(sortino),
        max_drawdown=_finite(max_dd * 100),
        best_30d=_finite(best_30d * 100),
        worst_30d=_finite(worst_30d * 100),
        negative_days_pct=_finite(float((log_ret < 0).mean()) * 100),
        momentum=momentum,
        drawdown=drawdown,
        history_years=round(years, 4),
        nav_rows=len(navs),
        capped_days=capped_days,
        first_nav_date=first_nav_date,
        last_nav_date=last_nav_date,
        nav_fresh=is_fresh(last_nav_date, as_of),
    )
