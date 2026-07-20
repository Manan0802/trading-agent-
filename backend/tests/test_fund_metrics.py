from datetime import date

import pytest

from app.services.advisor import fund_metrics as fm
from app.services.marketdata.mutual_fund import NavPoint

# Day 28 so stepping a month never overflows a short February.
START = date(2019, 1, 28)


def _next_month(d: date) -> date:
    return date(d.year + d.month // 12, d.month % 12 + 1, d.day)


def series_from_monthly_returns(returns: list[float], start_nav: float = 100.0):
    """Build a NAV series, one point per calendar month, realising these returns."""
    points = [NavPoint(date=START, nav=start_nav)]
    nav, when = start_nav, START
    for r in returns:
        nav *= 1 + r
        when = _next_month(when)
        points.append(NavPoint(date=when, nav=nav))
    return points


def steady_series(monthly_return: float, months: int, start_nav: float = 100.0):
    return series_from_monthly_returns([monthly_return] * months, start_nav)


def test_cagr_of_a_steadily_compounding_fund():
    # 1% a month for 5 years -> (1.01^12 - 1) = 12.68% a year
    navs = steady_series(0.01, months=60)
    assert fm.cagr(navs, years=3) == pytest.approx(0.1268, abs=2e-3)
    assert fm.cagr(navs, years=5) == pytest.approx(0.1268, abs=2e-3)


def test_cagr_is_none_when_history_is_too_short():
    navs = steady_series(0.01, months=12)
    assert fm.cagr(navs, years=1) is not None
    assert fm.cagr(navs, years=5) is None


def test_a_perfectly_steady_fund_has_no_volatility():
    navs = steady_series(0.01, months=36)
    assert fm.annualised_volatility(navs) == pytest.approx(0.0, abs=1e-9)


def test_volatility_rises_with_swings():
    calm = series_from_monthly_returns([0.01, 0.01] * 18)
    wild = series_from_monthly_returns([0.10, -0.08] * 18)
    assert fm.annualised_volatility(wild) > fm.annualised_volatility(calm)


def test_max_drawdown_measures_the_worst_peak_to_trough_fall():
    # Up to 120, down to 60 (a 50% fall), then partial recovery.
    navs = series_from_monthly_returns([0.20, -0.50, 0.30])
    assert fm.max_drawdown(navs) == pytest.approx(-0.50, abs=1e-9)


def test_max_drawdown_of_a_fund_that_only_rises_is_zero():
    assert fm.max_drawdown(steady_series(0.01, months=24)) == pytest.approx(0.0)


def test_sortino_ignores_upside_volatility():
    """Two funds with the same average return: one only jumps up, the other
    swings both ways. Sortino must prefer the one with no downside."""
    upside_only = series_from_monthly_returns([0.0, 0.04] * 18)
    two_sided = series_from_monthly_returns([-0.04, 0.08] * 18)

    assert fm.sortino(upside_only) > fm.sortino(two_sided)


def test_sortino_is_none_without_enough_history():
    assert fm.sortino(steady_series(0.01, months=2)) is None


def test_alpha_is_zero_when_a_fund_simply_tracks_its_benchmark():
    benchmark = series_from_monthly_returns([0.02, -0.01, 0.03, 0.00] * 9)
    tracker = series_from_monthly_returns([0.02, -0.01, 0.03, 0.00] * 9)
    assert fm.alpha(tracker, benchmark) == pytest.approx(0.0, abs=1e-6)


def test_alpha_is_positive_when_a_fund_consistently_adds_return():
    market = [0.02, -0.01, 0.03, 0.00] * 9
    benchmark = series_from_monthly_returns(market)
    outperformer = series_from_monthly_returns([r + 0.005 for r in market])
    assert fm.alpha(outperformer, benchmark) > 0


def test_downside_capture_below_one_means_the_fund_falls_less():
    market = [-0.10, 0.05, -0.06, 0.04] * 9
    benchmark = series_from_monthly_returns(market)
    # Halves every market fall, matches every rise.
    defensive = series_from_monthly_returns([r / 2 if r < 0 else r for r in market])

    assert fm.downside_capture(defensive, benchmark) == pytest.approx(0.5, abs=1e-6)


def test_downside_capture_above_one_means_the_fund_falls_harder():
    market = [-0.10, 0.05, -0.06, 0.04] * 9
    benchmark = series_from_monthly_returns(market)
    fragile = series_from_monthly_returns([r * 1.5 if r < 0 else r for r in market])

    assert fm.downside_capture(fragile, benchmark) == pytest.approx(1.5, abs=1e-6)


def test_consistency_is_one_when_a_fund_always_beats_its_benchmark():
    market = [0.01] * 84
    benchmark = series_from_monthly_returns(market)
    winner = series_from_monthly_returns([0.015] * 84)

    assert fm.rolling_consistency(winner, benchmark, window_years=3) == pytest.approx(1.0)


def test_consistency_is_zero_when_a_fund_always_lags():
    benchmark = series_from_monthly_returns([0.015] * 84)
    laggard = series_from_monthly_returns([0.01] * 84)

    assert fm.rolling_consistency(laggard, benchmark, window_years=3) == pytest.approx(0.0)


def test_consistency_is_none_without_a_full_window():
    benchmark = steady_series(0.01, months=20)
    fund = steady_series(0.012, months=20)
    assert fm.rolling_consistency(fund, benchmark, window_years=3) is None


def test_compute_metrics_bundles_everything_available():
    market = [0.01, -0.005, 0.02, 0.00] * 21  # 84 months
    benchmark = series_from_monthly_returns(market)
    fund = series_from_monthly_returns([r + 0.003 for r in market])

    m = fm.compute_metrics(fund, benchmark)

    assert m.cagr_3y is not None and m.cagr_5y is not None
    assert m.sortino is not None
    assert m.alpha is not None and m.alpha > 0
    assert m.downside_capture is not None
    assert m.consistency == pytest.approx(1.0)
    assert m.max_drawdown is not None and m.max_drawdown <= 0


def test_compute_metrics_without_a_benchmark_leaves_relative_metrics_unset():
    # Real funds always have losing months, which is what Sortino needs.
    navs = series_from_monthly_returns([0.02, -0.01, 0.015, 0.005] * 15)
    m = fm.compute_metrics(navs, benchmark=None)
    assert m.cagr_3y is not None
    assert m.sortino is not None
    assert m.alpha is None
    assert m.downside_capture is None
    assert m.consistency is None


def test_sortino_is_undefined_for_a_fund_that_never_fell_short():
    """No downside means the ratio has no denominator. Callers get None and
    treat it as a missing metric rather than a zero score."""
    assert fm.sortino(steady_series(0.01, months=36)) is None
