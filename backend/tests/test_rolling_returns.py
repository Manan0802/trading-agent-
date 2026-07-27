from datetime import date, timedelta

import pytest

from app.services.advisor.rolling_returns import (
    RollingStats,
    neutralise_nav_artefacts,
    rolling_return_stats,
)
from app.services.marketdata.mutual_fund import NavPoint


def _navs(days: int, daily_rate: float, start_nav: float = 100.0) -> list[NavPoint]:
    """A fund compounding at a fixed daily rate — every window returns the same."""
    start = date(2015, 1, 1)
    return [
        NavPoint(date=start + timedelta(days=i), nav=start_nav * (1 + daily_rate) ** i)
        for i in range(days)
    ]


def test_a_steady_fund_has_zero_dispersion_across_windows():
    """Every 1-year window of a constant-growth fund is identical, so the
    spread between best and worst must be nil."""
    stats = rolling_return_stats(_navs(1500, 0.0004), window_days=365)
    assert stats is not None
    assert stats.best == pytest.approx(stats.worst, abs=0.001)
    assert stats.share_positive == 1.0


def test_the_mean_is_taken_over_every_overlapping_window_not_the_endpoints():
    """This is the whole point: a fund that ended its last window on a good day
    cannot buy its way to the top."""
    navs = _navs(800, 0.0003)
    # A final-day spike moves point-to-point CAGR far more than the rolling mean.
    spiked = navs[:-1] + [NavPoint(date=navs[-1].date, nav=navs[-1].nav * 1.15)]
    plain = rolling_return_stats(navs, window_days=365)
    spike = rolling_return_stats(spiked, window_days=365)
    assert spike.mean > plain.mean
    # One day out of ~435 windows: the mean should barely move.
    assert spike.mean - plain.mean < 0.02


def test_a_fund_with_losing_windows_reports_them():
    """A fund can have a fine average and still have lost money over a full
    year at some point. That is the number a goal-based investor needs."""
    start = date(2015, 1, 1)
    navs = []
    nav = 100.0
    for i in range(1000):
        # Falls for the first 400 days, then recovers strongly.
        nav *= 0.9993 if i < 400 else 1.0012
        navs.append(NavPoint(date=start + timedelta(days=i), nav=nav))

    stats = rolling_return_stats(navs, window_days=365)
    assert stats.worst < 0
    assert 0 < stats.share_positive < 1


def test_too_little_history_returns_none_rather_than_a_partial_window():
    """A 6-month-old fund has no 1-year window. Scaling one up would be
    inventing a number."""
    assert rolling_return_stats(_navs(180, 0.0004), window_days=365) is None


def test_exactly_one_window_is_still_reported():
    stats = rolling_return_stats(_navs(400, 0.0004), window_days=365)
    assert stats is not None
    assert stats.count >= 1


def test_annualisation_applies_only_beyond_a_year():
    """A 3-year window is annualised; a 3-month window is left cumulative,
    because compounding a quarter to a year overstates it."""
    navs = _navs(1600, 0.0004)
    three_year = rolling_return_stats(navs, window_days=1095)
    three_month = rolling_return_stats(navs, window_days=91)
    one_year = rolling_return_stats(navs, window_days=365)
    # Annualised 3y should sit near the annualised 1y for a constant grower.
    assert three_year.mean == pytest.approx(one_year.mean, abs=0.01)
    # The 3-month figure is a quarter's worth, so materially smaller.
    assert three_month.mean < one_year.mean / 2


def test_windows_are_measured_on_calendar_dates_not_row_counts():
    """NAVs skip weekends and holidays, so counting rows would make a
    "1-year" window drift by weeks."""
    start = date(2015, 1, 1)
    navs = [
        NavPoint(date=start + timedelta(days=i), nav=100.0 * (1.0004**i))
        for i in range(900)
        if (start + timedelta(days=i)).weekday() < 5
    ]
    stats = rolling_return_stats(navs, window_days=365)
    assert stats is not None
    assert stats.mean == pytest.approx(0.1566, abs=0.02)


# --- artefact neutralisation -------------------------------------------------


def test_a_split_day_is_neutralised_before_metrics():
    """A 40% one-day move is a split or a restatement, not a return. Left in,
    it corrupts volatility, drawdown and every window that contains it."""
    navs = _navs(500, 0.0004)
    broken = list(navs)
    broken[250] = NavPoint(date=broken[250].date, nav=broken[250].nav * 0.55)

    cleaned, n = neutralise_nav_artefacts(broken)
    assert n >= 1
    clean_stats = rolling_return_stats(cleaned, window_days=365)
    plain_stats = rolling_return_stats(navs, window_days=365)
    assert clean_stats.worst == pytest.approx(plain_stats.worst, abs=0.03)


def test_a_clean_series_is_returned_untouched():
    navs = _navs(500, 0.0004)
    cleaned, n = neutralise_nav_artefacts(navs)
    assert n == 0
    assert [p.nav for p in cleaned] == [p.nav for p in navs]


def test_a_genuine_large_move_below_the_threshold_survives():
    """Indian equity funds really do move 8% in a day. Only the impossible
    moves are neutralised."""
    navs = _navs(300, 0.0004)
    real = list(navs)
    real[150] = NavPoint(date=real[150].date, nav=real[150].nav * 0.92)
    _, n = neutralise_nav_artefacts(real)
    assert n == 0


def test_neutralising_preserves_the_dates_so_windows_stay_aligned():
    navs = _navs(300, 0.0004)
    broken = list(navs)
    broken[100] = NavPoint(date=broken[100].date, nav=broken[100].nav * 2.0)
    cleaned, _ = neutralise_nav_artefacts(broken)
    assert [p.date for p in cleaned] == [p.date for p in navs]
