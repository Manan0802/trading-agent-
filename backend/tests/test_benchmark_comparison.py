from datetime import date

import pytest

from app.services.marketdata.mutual_fund import NavPoint
from app.services.portfolio.benchmark import compare_to_benchmark
from app.services.portfolio.fifo import TxnInput

VALUATION_DATE = date(2025, 1, 1)


def flat_benchmark(nav: float = 100.0):
    """A benchmark that never moves, so any portfolio gain is pure outperformance."""
    return [
        NavPoint(date=date(2023, 1, 1), nav=nav),
        NavPoint(date=date(2024, 1, 1), nav=nav),
        NavPoint(date=VALUATION_DATE, nav=nav),
    ]


def doubling_benchmark():
    return [
        NavPoint(date=date(2024, 1, 1), nav=100.0),
        NavPoint(date=VALUATION_DATE, nav=200.0),
    ]


def test_benchmark_value_mirrors_the_same_rupees_on_the_same_dates():
    txns = [TxnInput(date(2024, 1, 1), "BUY", units=50, price=200.0)]  # 10,000
    result = compare_to_benchmark(
        txns, doubling_benchmark(), portfolio_current_value=11000, valuation_date=VALUATION_DATE
    )
    # 10,000 into a benchmark that doubled would be worth 20,000.
    assert result.benchmark_value == pytest.approx(20000)
    assert result.portfolio_value == pytest.approx(11000)


def test_beating_a_flat_benchmark_shows_positive_outperformance():
    txns = [TxnInput(date(2024, 1, 1), "BUY", units=100, price=100.0)]  # 10,000
    result = compare_to_benchmark(
        txns, flat_benchmark(), portfolio_current_value=13000, valuation_date=VALUATION_DATE
    )
    assert result.benchmark_value == pytest.approx(10000)
    assert result.portfolio_xirr > result.benchmark_xirr
    assert result.outperformance > 0


def test_lagging_the_benchmark_shows_negative_outperformance():
    txns = [TxnInput(date(2024, 1, 1), "BUY", units=100, price=100.0)]
    result = compare_to_benchmark(
        txns, doubling_benchmark(), portfolio_current_value=11000, valuation_date=VALUATION_DATE
    )
    assert result.outperformance < 0
    assert result.benchmark_xirr > result.portfolio_xirr


def test_sip_cashflows_are_mirrored_instalment_by_instalment():
    """Each instalment buys benchmark units at that month's level, so a rising
    benchmark means later instalments buy fewer units."""
    navs = [
        NavPoint(date=date(2024, 1, 1), nav=100.0),
        NavPoint(date=date(2024, 7, 1), nav=200.0),
        NavPoint(date=VALUATION_DATE, nav=200.0),
    ]
    txns = [
        TxnInput(date(2024, 1, 1), "BUY", units=10, price=100.0),  # 1,000 -> 10 units
        TxnInput(date(2024, 7, 1), "BUY", units=10, price=100.0),  # 1,000 -> 5 units
    ]
    result = compare_to_benchmark(
        txns, navs, portfolio_current_value=2000, valuation_date=VALUATION_DATE
    )
    assert result.benchmark_units == pytest.approx(15)
    assert result.benchmark_value == pytest.approx(3000)


def test_a_sell_withdraws_from_the_benchmark_too():
    navs = [
        NavPoint(date=date(2024, 1, 1), nav=100.0),
        NavPoint(date=date(2024, 7, 1), nav=100.0),
        NavPoint(date=VALUATION_DATE, nav=100.0),
    ]
    txns = [
        TxnInput(date(2024, 1, 1), "BUY", units=100, price=100.0),  # 10,000 -> 100 units
        TxnInput(date(2024, 7, 1), "SELL", units=40, price=100.0),  # 4,000 -> -40 units
    ]
    result = compare_to_benchmark(
        txns, navs, portfolio_current_value=6000, valuation_date=VALUATION_DATE
    )
    assert result.benchmark_units == pytest.approx(60)
    assert result.benchmark_value == pytest.approx(6000)


def test_a_transaction_on_a_market_holiday_uses_the_previous_published_nav():
    navs = [
        NavPoint(date=date(2024, 1, 1), nav=100.0),
        # No NAV on the 2nd — a holiday.
        NavPoint(date=date(2024, 1, 3), nav=150.0),
        NavPoint(date=VALUATION_DATE, nav=150.0),
    ]
    txns = [TxnInput(date(2024, 1, 2), "BUY", units=10, price=100.0)]  # 1,000
    result = compare_to_benchmark(
        txns, navs, portfolio_current_value=1000, valuation_date=VALUATION_DATE
    )
    # Priced at the 1st's NAV of 100, not the 3rd's 150.
    assert result.benchmark_units == pytest.approx(10)


def test_investing_before_the_benchmark_existed_is_reported_not_guessed():
    navs = [
        NavPoint(date=date(2024, 6, 1), nav=100.0),
        NavPoint(date=VALUATION_DATE, nav=110.0),
    ]
    txns = [TxnInput(date(2020, 1, 1), "BUY", units=10, price=100.0)]
    result = compare_to_benchmark(
        txns, navs, portfolio_current_value=1500, valuation_date=VALUATION_DATE
    )
    assert result.comparable is False
    assert result.benchmark_xirr is None


def test_no_transactions_gives_nothing_to_compare():
    result = compare_to_benchmark(
        [], flat_benchmark(), portfolio_current_value=0, valuation_date=VALUATION_DATE
    )
    assert result.comparable is False
