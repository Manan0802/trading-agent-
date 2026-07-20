from datetime import date

import pytest

from app.services.portfolio.fifo import TxnInput, apply_fifo


def buy(d: date, units: float, price: float) -> TxnInput:
    return TxnInput(txn_date=d, txn_type="BUY", units=units, price=price)


def sell(d: date, units: float, price: float) -> TxnInput:
    return TxnInput(txn_date=d, txn_type="SELL", units=units, price=price)


def test_buys_only_leaves_everything_open():
    result = apply_fifo(
        [
            buy(date(2024, 1, 5), 100, 50.0),
            buy(date(2024, 2, 5), 90, 55.0),
        ]
    )
    assert result.units_held == pytest.approx(190)
    assert result.cost_basis == pytest.approx(100 * 50 + 90 * 55)
    assert result.realised_gains == []
    assert len(result.open_lots) == 2


def test_partial_sell_consumes_the_oldest_lot_first():
    result = apply_fifo(
        [
            buy(date(2024, 1, 5), 100, 50.0),
            buy(date(2024, 2, 5), 100, 60.0),
            sell(date(2024, 6, 5), 40, 70.0),
        ]
    )
    assert len(result.realised_gains) == 1
    gain = result.realised_gains[0]
    # Sold units must be costed at the January price, not the February one.
    assert gain.buy_date == date(2024, 1, 5)
    assert gain.buy_price == pytest.approx(50.0)
    assert gain.units == pytest.approx(40)
    assert gain.gain == pytest.approx(40 * (70.0 - 50.0))

    assert result.units_held == pytest.approx(160)
    assert result.cost_basis == pytest.approx(60 * 50 + 100 * 60)


def test_sell_spanning_two_lots_splits_the_gain():
    result = apply_fifo(
        [
            buy(date(2024, 1, 5), 100, 50.0),
            buy(date(2024, 2, 5), 100, 60.0),
            sell(date(2024, 6, 5), 150, 70.0),
        ]
    )
    assert len(result.realised_gains) == 2
    first, second = result.realised_gains
    assert first.units == pytest.approx(100) and first.buy_price == pytest.approx(50.0)
    assert second.units == pytest.approx(50) and second.buy_price == pytest.approx(60.0)
    assert result.total_realised_gain == pytest.approx(
        100 * (70 - 50) + 50 * (70 - 60)
    )
    assert result.units_held == pytest.approx(50)


def test_holding_period_classifies_long_vs_short_term_equity():
    result = apply_fifo(
        [
            buy(date(2023, 1, 10), 10, 100.0),  # held > 12 months
            buy(date(2024, 6, 1), 10, 100.0),  # held < 12 months
            sell(date(2024, 8, 1), 20, 120.0),
        ]
    )
    long_leg, short_leg = result.realised_gains
    assert long_leg.holding_days > 365 and long_leg.is_long_term_equity is True
    assert short_leg.holding_days < 365 and short_leg.is_long_term_equity is False


def test_selling_more_units_than_held_is_rejected():
    with pytest.raises(ValueError, match="more units than held"):
        apply_fifo(
            [
                buy(date(2024, 1, 5), 10, 50.0),
                sell(date(2024, 2, 5), 25, 60.0),
            ]
        )


def test_transactions_are_processed_in_date_order_regardless_of_input_order():
    unordered = [
        sell(date(2024, 6, 5), 40, 70.0),
        buy(date(2024, 1, 5), 100, 50.0),
    ]
    result = apply_fifo(unordered)
    assert result.units_held == pytest.approx(60)
    assert result.realised_gains[0].buy_date == date(2024, 1, 5)


def test_full_exit_leaves_no_open_units():
    result = apply_fifo(
        [
            buy(date(2024, 1, 5), 100, 50.0),
            sell(date(2024, 9, 5), 100, 80.0),
        ]
    )
    assert result.units_held == pytest.approx(0)
    assert result.cost_basis == pytest.approx(0)
    assert result.open_lots == []
    assert result.total_realised_gain == pytest.approx(3000)
