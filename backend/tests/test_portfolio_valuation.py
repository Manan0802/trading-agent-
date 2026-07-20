from datetime import date

import pytest

from app.services.portfolio.fifo import TxnInput
from app.services.portfolio.valuation import (
    HoldingInput,
    value_holding,
    value_portfolio,
)

VALUATION_DATE = date(2025, 1, 1)


def _prices(mapping: dict[str, float]):
    def lookup(asset_type: str, identifier: str) -> float:
        return mapping[identifier]

    return lookup


def _mf(identifier: str, txns: list[TxnInput], name: str = "Some Fund") -> HoldingInput:
    return HoldingInput(
        holding_id=identifier,
        name=name,
        asset_type="MF",
        identifier=identifier,
        category="Flexi Cap",
        transactions=txns,
    )


def test_single_lump_sum_holding_valuation():
    holding = _mf(
        "F1",
        [TxnInput(date(2024, 1, 1), "BUY", units=100, price=100.0)],
    )
    s = value_holding(holding, _prices({"F1": 130.0}), VALUATION_DATE)

    assert s.units_held == pytest.approx(100)
    assert s.invested == pytest.approx(10000)
    assert s.current_value == pytest.approx(13000)
    assert s.unrealised_gain == pytest.approx(3000)
    assert s.realised_gain == pytest.approx(0)
    assert s.absolute_return == pytest.approx(0.30)
    # Held slightly over a year, so annualised sits just under the absolute 30%.
    assert s.xirr == pytest.approx(0.2989, abs=1e-3)


def test_partial_sell_splits_realised_and_unrealised_gain():
    holding = _mf(
        "F1",
        [
            TxnInput(date(2024, 1, 1), "BUY", units=100, price=100.0),
            TxnInput(date(2024, 7, 1), "SELL", units=40, price=120.0),
        ],
    )
    s = value_holding(holding, _prices({"F1": 130.0}), VALUATION_DATE)

    assert s.units_held == pytest.approx(60)
    assert s.invested == pytest.approx(6000)  # cost basis of the 60 units still held
    assert s.current_value == pytest.approx(7800)
    assert s.realised_gain == pytest.approx(40 * (120 - 100))
    assert s.unrealised_gain == pytest.approx(1800)


def test_fully_exited_holding_has_no_current_value_but_keeps_its_return():
    holding = _mf(
        "F1",
        [
            TxnInput(date(2024, 1, 1), "BUY", units=100, price=100.0),
            TxnInput(date(2024, 12, 31), "SELL", units=100, price=120.0),
        ],
    )
    s = value_holding(holding, _prices({"F1": 130.0}), VALUATION_DATE)

    assert s.units_held == pytest.approx(0)
    assert s.current_value == pytest.approx(0)
    assert s.realised_gain == pytest.approx(2000)
    assert s.xirr is not None and s.xirr > 0


def test_sip_holding_uses_every_instalment_as_its_own_cashflow():
    txns = [
        TxnInput(date(2024, m, 1), "BUY", units=10, price=100.0) for m in range(1, 13)
    ]
    holding = _mf("F1", txns)
    s = value_holding(holding, _prices({"F1": 110.0}), VALUATION_DATE)

    assert s.units_held == pytest.approx(120)
    assert s.invested == pytest.approx(12000)
    assert s.current_value == pytest.approx(13200)
    assert s.absolute_return == pytest.approx(0.10)
    # Most instalments were invested for well under a year, so the annualised
    # figure has to exceed the flat 10%.
    assert s.xirr > s.absolute_return


def test_portfolio_totals_and_pooled_xirr():
    winner = _mf("F1", [TxnInput(date(2024, 1, 1), "BUY", units=100, price=100.0)])
    laggard = _mf("F2", [TxnInput(date(2024, 1, 1), "BUY", units=900, price=100.0)])
    lookup = _prices({"F1": 200.0, "F2": 100.0})

    p = value_portfolio([winner, laggard], lookup, VALUATION_DATE)

    assert p.total_invested == pytest.approx(100000)
    assert p.total_current_value == pytest.approx(110000)
    assert p.absolute_return == pytest.approx(0.10)
    # Pooled, not the average of 100% and 0%.
    assert p.xirr == pytest.approx(0.0997, abs=1e-3)
    assert len(p.holdings) == 2


def test_stock_and_mutual_fund_holdings_priced_through_the_same_path():
    mf_holding = _mf("F1", [TxnInput(date(2024, 1, 1), "BUY", units=10, price=100.0)])
    stock_holding = HoldingInput(
        holding_id="H2",
        name="Reliance Industries",
        asset_type="STOCK",
        identifier="RELIANCE.NS",
        category=None,
        transactions=[TxnInput(date(2024, 1, 1), "BUY", units=5, price=1000.0)],
    )
    lookup = _prices({"F1": 150.0, "RELIANCE.NS": 1300.0})

    p = value_portfolio([mf_holding, stock_holding], lookup, VALUATION_DATE)

    assert p.total_invested == pytest.approx(1000 + 5000)
    assert p.total_current_value == pytest.approx(1500 + 6500)


def test_unpriceable_holding_is_reported_not_fatal():
    """A delisted stock or a bad scheme code must not break the whole portfolio."""

    def failing_lookup(asset_type: str, identifier: str) -> float:
        raise ValueError("no price")

    holding = _mf("F1", [TxnInput(date(2024, 1, 1), "BUY", units=10, price=100.0)])
    s = value_holding(holding, failing_lookup, VALUATION_DATE)

    assert s.current_price is None
    assert s.current_value is None
    assert s.invested == pytest.approx(1000)
    assert s.xirr is None
    assert s.price_error is not None


def test_portfolio_returns_exclude_unpriceable_holdings_but_still_disclose_them():
    """Counting an unpriced holding's cost without its value would fake a loss.

    So the return figures cover only priced holdings, and the money we could
    not value is surfaced separately rather than silently dropped.
    """
    good = _mf("F1", [TxnInput(date(2024, 1, 1), "BUY", units=10, price=100.0)])
    bad = _mf("F2", [TxnInput(date(2024, 1, 1), "BUY", units=10, price=100.0)])

    def lookup(asset_type: str, identifier: str) -> float:
        if identifier == "F2":
            raise ValueError("no price")
        return 150.0

    p = value_portfolio([good, bad], lookup, VALUATION_DATE)

    assert p.total_invested == pytest.approx(1000)
    assert p.total_current_value == pytest.approx(1500)
    assert p.absolute_return == pytest.approx(0.50)  # not dragged down to -25%
    assert p.unpriced_invested == pytest.approx(1000)
    assert p.has_pricing_errors is True
    assert len(p.holdings) == 2  # both still listed for the user to see
