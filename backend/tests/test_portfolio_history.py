from datetime import date

import pytest

from app.services.marketdata.mutual_fund import NavPoint
from app.services.portfolio.fifo import TxnInput
from app.services.portfolio.history import HoldingSeries, build_history


def _navs(start: date, months: int, first: float, step: float) -> list[NavPoint]:
    points = []
    for i in range(months * 31):
        d = date.fromordinal(start.toordinal() + i)
        points.append(NavPoint(date=d, nav=first + step * i))
    return points


NAVS = _navs(date(2024, 1, 1), 24, 100.0, 0.1)
BENCH = _navs(date(2024, 1, 1), 24, 200.0, 0.1)


def _series(txns: list[TxnInput]) -> list[HoldingSeries]:
    return [HoldingSeries(key="fund", transactions=txns, navs=NAVS)]


def test_no_transactions_produces_no_history():
    assert build_history([], BENCH, date(2025, 1, 1)) == []


def test_history_starts_at_the_first_purchase_not_before():
    txns = [TxnInput(date(2024, 6, 10), "BUY", 100, 116.0)]
    points = build_history(_series(txns), BENCH, date(2024, 12, 31))
    assert points[0].date >= date(2024, 6, 10)


def test_history_ends_exactly_on_the_valuation_date():
    """The chart's last point must equal the headline number, or the page
    contradicts itself."""
    txns = [TxnInput(date(2024, 2, 1), "BUY", 100, 103.1)]
    points = build_history(_series(txns), BENCH, date(2024, 11, 17))
    assert points[-1].date == date(2024, 11, 17)


def test_value_tracks_the_price_upward():
    txns = [TxnInput(date(2024, 2, 1), "BUY", 100, 103.1)]
    points = build_history(_series(txns), BENCH, date(2024, 12, 1))
    values = [p.portfolio_value for p in points]
    assert values == sorted(values)
    assert values[-1] > values[0]


def test_invested_is_cumulative_and_steps_at_each_purchase():
    txns = [
        TxnInput(date(2024, 2, 1), "BUY", 100, 100.0),
        TxnInput(date(2024, 8, 1), "BUY", 100, 100.0),
    ]
    points = build_history(_series(txns), BENCH, date(2024, 12, 1))
    assert points[0].invested == pytest.approx(10_000)
    assert points[-1].invested == pytest.approx(20_000)


def test_a_sale_reduces_both_units_and_invested():
    txns = [
        TxnInput(date(2024, 2, 1), "BUY", 100, 100.0),
        TxnInput(date(2024, 8, 1), "SELL", 60, 120.0),
    ]
    points = build_history(_series(txns), BENCH, date(2024, 12, 1))
    assert points[-1].invested < points[0].invested
    assert points[-1].portfolio_value < points[0].portfolio_value * 1.5


def test_benchmark_follows_the_same_cashflows():
    txns = [TxnInput(date(2024, 2, 1), "BUY", 100, 103.1)]
    points = build_history(_series(txns), BENCH, date(2024, 12, 1))
    assert all(p.benchmark_value is not None for p in points)
    # Same rupees, a cheaper-growing index: the benchmark ends lower.
    assert points[-1].benchmark_value < points[-1].portfolio_value


def test_missing_benchmark_history_leaves_the_series_null_not_zero():
    """A zero would draw a line at the bottom of the chart and read as a total
    loss rather than as missing data."""
    txns = [TxnInput(date(2024, 2, 1), "BUY", 100, 103.1)]
    points = build_history(_series(txns), [], date(2024, 12, 1))
    assert all(p.benchmark_value is None for p in points)
    assert all(p.portfolio_value > 0 for p in points)


def test_long_horizons_stay_bounded_in_point_count():
    """Ten years of daily points would be 3,650 numbers over the wire for a
    chart 800 pixels wide."""
    txns = [TxnInput(date(2024, 1, 2), "BUY", 100, 100.1)]
    points = build_history(_series(txns), BENCH, date(2025, 12, 1))
    assert len(points) <= 130


def test_two_holdings_are_summed():
    txns_a = [TxnInput(date(2024, 2, 1), "BUY", 100, 100.0)]
    txns_b = [TxnInput(date(2024, 2, 1), "BUY", 50, 100.0)]
    series = [
        HoldingSeries(key="a", transactions=txns_a, navs=NAVS),
        HoldingSeries(key="b", transactions=txns_b, navs=NAVS),
    ]
    combined = build_history(series, BENCH, date(2024, 12, 1))
    just_a = build_history(_series(txns_a), BENCH, date(2024, 12, 1))
    assert combined[-1].portfolio_value == pytest.approx(
        just_a[-1].portfolio_value * 1.5
    )
