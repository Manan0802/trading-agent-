from datetime import date

import pytest

from app.services.portfolio.returns import Cashflow, absolute_return, compute_xirr


def test_lump_sum_over_one_year():
    # 10,000 out, 11,000 back exactly 365 days later -> 10%
    r = compute_xirr(
        [
            Cashflow(date(2023, 1, 1), -10000),
            Cashflow(date(2024, 1, 1), 11000),
        ]
    )
    assert r == pytest.approx(0.10, abs=1e-4)


def test_monthly_sip_annualises_above_absolute_return():
    # 12 x 1,000 invested through the year, worth 13,000 at the end.
    # Absolute return is 8.3%, but most of that money was invested for far
    # less than a year, so the annualised (XIRR) figure must be higher.
    cashflows = [Cashflow(date(2024, m, 1), -1000.0) for m in range(1, 13)]
    cashflows.append(Cashflow(date(2025, 1, 1), 13000.0))
    r = compute_xirr(cashflows)
    assert r > absolute_return(invested=12000, current_value=13000)
    assert r == pytest.approx(0.1566, abs=1e-3)


def test_loss_gives_negative_xirr():
    r = compute_xirr(
        [
            Cashflow(date(2023, 1, 1), -10000),
            Cashflow(date(2024, 1, 1), 9000),
        ]
    )
    assert r is not None and r < 0


def test_returns_none_instead_of_crashing_on_unsolvable_input():
    # Only purchases and no current value -> no rate can balance the equation.
    assert compute_xirr([Cashflow(date(2024, 1, 1), -1000)]) is None
    assert (
        compute_xirr(
            [Cashflow(date(2024, 1, 1), -1000), Cashflow(date(2024, 2, 1), -1000)]
        )
        is None
    )
    assert compute_xirr([]) is None


def test_portfolio_xirr_pools_cashflows_rather_than_averaging():
    """Pooling is the mathematically correct aggregation.

    Both funds are held for the same year: a small one doubles (100%), a large
    one is flat (0%). Averaging the two rates says the portfolio made 50%, but
    only 10,000 of the 100,000 invested actually grew — the true portfolio
    return is 10%. Only pooling the cashflows gets that right.
    """
    fund_a = [Cashflow(date(2023, 1, 1), -10000), Cashflow(date(2024, 1, 1), 20000)]
    fund_b = [Cashflow(date(2023, 1, 1), -90000), Cashflow(date(2024, 1, 1), 90000)]

    xirr_a = compute_xirr(fund_a)
    xirr_b = compute_xirr(fund_b)
    pooled = compute_xirr(fund_a + fund_b)

    assert xirr_a == pytest.approx(1.0, abs=1e-3)  # doubled
    assert xirr_b == pytest.approx(0.0, abs=1e-3)  # flat
    naive_average = (xirr_a + xirr_b) / 2
    assert naive_average == pytest.approx(0.5, abs=1e-3)
    assert pooled == pytest.approx(0.10, abs=1e-3)


def test_absolute_return_counts_realised_proceeds():
    assert absolute_return(invested=10000, current_value=11000) == pytest.approx(0.10)
    assert absolute_return(
        invested=10000, current_value=6000, realised=6000
    ) == pytest.approx(0.20)
    assert absolute_return(invested=0, current_value=0) == 0.0
