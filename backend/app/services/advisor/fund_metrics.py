"""Fund performance metrics computed from NAV history alone.

Licensed ratings (Value Research, CRISIL, Morningstar) have no free feed, so
NexTrade derives its own view from public NAV data. Everything here is a
standard, published measure — nothing invented — so a recommendation can be
explained and defended.

Returns are measured monthly, which is the convention for alpha, downside
capture and rolling-window comparisons.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from app.services.marketdata.mutual_fund import NavPoint, nav_on_or_before

DEFAULT_RISK_FREE_RATE = 0.06  # ~Indian 10-year G-sec
_MONTHS_PER_YEAR = 12
_DAYS_PER_YEAR = 365.25
_MIN_MONTHS = 6
# NAVs are not published on weekends or holidays, and a fund with exactly N
# years of history would otherwise miss its own N-year window by a fraction of
# a day. The elapsed period is measured from real dates regardless.
_WINDOW_GRACE_DAYS = 7


@dataclass(frozen=True)
class FundMetrics:
    cagr_1y: float | None = None
    cagr_3y: float | None = None
    cagr_5y: float | None = None
    volatility: float | None = None
    sortino: float | None = None
    max_drawdown: float | None = None
    # Only computable against a benchmark series.
    alpha: float | None = None
    downside_capture: float | None = None
    consistency: float | None = None


def cagr(navs: list[NavPoint], years: float) -> float | None:
    """Annualised growth over the trailing window, or None if history is short."""
    if len(navs) < 2:
        return None
    end = navs[-1]
    target = end.date - timedelta(days=years * _DAYS_PER_YEAR)
    if navs[0].date > target + timedelta(days=_WINDOW_GRACE_DAYS):
        return None
    start = nav_on_or_before(navs, target) or navs[0]
    if start.nav <= 0:
        return None
    elapsed_years = (end.date - start.date).days / _DAYS_PER_YEAR
    if elapsed_years <= 0:
        return None
    return (end.nav / start.nav) ** (1 / elapsed_years) - 1


def _monthly_navs(navs: list[NavPoint]) -> list[NavPoint]:
    """One NAV per calendar month (the last available in each)."""
    by_month: dict[tuple[int, int], NavPoint] = {}
    for point in navs:
        by_month[(point.date.year, point.date.month)] = point
    return [by_month[key] for key in sorted(by_month)]


def monthly_returns(navs: list[NavPoint]) -> np.ndarray:
    values = np.array([p.nav for p in _monthly_navs(navs)], dtype=float)
    if values.size < 2:
        return np.array([])
    return values[1:] / values[:-1] - 1


def annualised_volatility(navs: list[NavPoint]) -> float | None:
    returns = monthly_returns(navs)
    if returns.size < _MIN_MONTHS:
        return None
    return float(np.std(returns, ddof=1) * np.sqrt(_MONTHS_PER_YEAR))


def max_drawdown(navs: list[NavPoint]) -> float | None:
    """Worst peak-to-trough fall, as a negative fraction."""
    if len(navs) < 2:
        return None
    values = np.array([p.nav for p in navs], dtype=float)
    peaks = np.maximum.accumulate(values)
    return float(np.min(values / peaks - 1))


def sortino(
    navs: list[NavPoint], risk_free_rate: float = DEFAULT_RISK_FREE_RATE
) -> float | None:
    """Return per unit of *downside* risk.

    Preferred over Sharpe because Sharpe penalises upside swings just as hard
    as losses, which misjudges funds that are volatile in the right direction.
    """
    returns = monthly_returns(navs)
    if returns.size < _MIN_MONTHS:
        return None

    monthly_rf = (1 + risk_free_rate) ** (1 / _MONTHS_PER_YEAR) - 1
    excess = returns - monthly_rf
    shortfall = np.minimum(excess, 0.0)
    # Divided by the full period count, per Sortino's original definition.
    downside_deviation = float(np.sqrt(np.mean(shortfall**2)) * np.sqrt(_MONTHS_PER_YEAR))
    if downside_deviation == 0:
        return None
    return float(np.mean(excess) * _MONTHS_PER_YEAR / downside_deviation)


def _aligned_returns(
    fund: list[NavPoint], benchmark: list[NavPoint]
) -> tuple[np.ndarray, np.ndarray]:
    """Monthly returns for the months both series cover."""
    fund_by_month = {(p.date.year, p.date.month): p.nav for p in _monthly_navs(fund)}
    bench_by_month = {
        (p.date.year, p.date.month): p.nav for p in _monthly_navs(benchmark)
    }
    months = sorted(set(fund_by_month) & set(bench_by_month))
    if len(months) < 2:
        return np.array([]), np.array([])

    f = np.array([fund_by_month[m] for m in months], dtype=float)
    b = np.array([bench_by_month[m] for m in months], dtype=float)
    return f[1:] / f[:-1] - 1, b[1:] / b[:-1] - 1


def alpha(
    fund: list[NavPoint],
    benchmark: list[NavPoint],
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float | None:
    """Annualised CAPM alpha — return beyond what the fund's market exposure explains."""
    f, b = _aligned_returns(fund, benchmark)
    if f.size < _MIN_MONTHS:
        return None

    monthly_rf = (1 + risk_free_rate) ** (1 / _MONTHS_PER_YEAR) - 1
    f_excess, b_excess = f - monthly_rf, b - monthly_rf
    variance = float(np.var(b_excess, ddof=1))
    if variance == 0:
        return None
    beta = float(np.cov(f_excess, b_excess, ddof=1)[0][1] / variance)
    return float((np.mean(f_excess) - beta * np.mean(b_excess)) * _MONTHS_PER_YEAR)


def downside_capture(
    fund: list[NavPoint], benchmark: list[NavPoint]
) -> float | None:
    """How much of the market's falls the fund takes. Below 1.0 is protective."""
    f, b = _aligned_returns(fund, benchmark)
    if f.size < _MIN_MONTHS:
        return None

    down = b < 0
    if not down.any():
        return None
    benchmark_fall = float(np.mean(b[down]))
    if benchmark_fall == 0:
        return None
    return float(np.mean(f[down]) / benchmark_fall)


def rolling_consistency(
    fund: list[NavPoint], benchmark: list[NavPoint], window_years: float = 3
) -> float | None:
    """Share of rolling windows in which the fund beat its benchmark.

    A fund that wins on one lucky stretch scores badly here; one that keeps
    winning across many overlapping windows scores well. This is the guard
    against recommending whoever happens to top the recent-returns table.
    """
    fund_months = _monthly_navs(fund)
    bench_months = _monthly_navs(benchmark)
    if len(fund_months) < 2 or len(bench_months) < 2:
        return None

    window_days = window_years * _DAYS_PER_YEAR
    wins = comparisons = 0

    for start in fund_months:
        window_end = start.date + timedelta(days=window_days)
        if window_end > fund_months[-1].date:
            break
        fund_end = nav_on_or_before(fund_months, window_end)
        bench_start = nav_on_or_before(bench_months, start.date)
        bench_end = nav_on_or_before(bench_months, window_end)
        if not (fund_end and bench_start and bench_end):
            continue
        if start.nav <= 0 or bench_start.nav <= 0:
            continue
        comparisons += 1
        if fund_end.nav / start.nav > bench_end.nav / bench_start.nav:
            wins += 1

    if comparisons == 0:
        return None
    return wins / comparisons


def compute_metrics(
    navs: list[NavPoint],
    benchmark: list[NavPoint] | None = None,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> FundMetrics:
    return FundMetrics(
        cagr_1y=cagr(navs, 1),
        cagr_3y=cagr(navs, 3),
        cagr_5y=cagr(navs, 5),
        volatility=annualised_volatility(navs),
        sortino=sortino(navs, risk_free_rate),
        max_drawdown=max_drawdown(navs),
        alpha=alpha(navs, benchmark, risk_free_rate) if benchmark else None,
        downside_capture=downside_capture(navs, benchmark) if benchmark else None,
        consistency=rolling_consistency(navs, benchmark) if benchmark else None,
    )
