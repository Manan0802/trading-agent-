"""Turns a holding's raw transaction ledger into the numbers a user reads.

Brings together FIFO lot accounting (what is still held, and at what cost),
live prices, and money-weighted returns.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from app.services.portfolio.fifo import TxnInput, apply_fifo
from app.services.portfolio.returns import Cashflow, absolute_return, compute_xirr

PriceLookup = Callable[[str, str], float]


@dataclass(frozen=True)
class HoldingInput:
    holding_id: str
    name: str
    asset_type: str
    identifier: str
    category: str | None
    transactions: list[TxnInput]


@dataclass(frozen=True)
class HoldingSummary:
    holding_id: str
    name: str
    asset_type: str
    identifier: str
    category: str | None
    units_held: float
    invested: float  # cost basis of units still held
    current_price: float | None
    current_value: float | None
    realised_gain: float
    xirr: float | None
    price_error: str | None = None

    @property
    def unrealised_gain(self) -> float | None:
        if self.current_value is None:
            return None
        return self.current_value - self.invested

    @property
    def absolute_return(self) -> float | None:
        """Gain on the position still held. Realised gains are reported separately
        so a partial exit does not quietly inflate the number shown against
        current holdings."""
        if self.current_value is None:
            return None
        return absolute_return(invested=self.invested, current_value=self.current_value)


@dataclass
class PortfolioSummary:
    holdings: list[HoldingSummary] = field(default_factory=list)
    total_invested: float = 0.0
    total_current_value: float = 0.0
    total_realised_gain: float = 0.0
    unpriced_invested: float = 0.0
    xirr: float | None = None

    @property
    def total_unrealised_gain(self) -> float:
        return self.total_current_value - self.total_invested

    @property
    def absolute_return(self) -> float:
        return absolute_return(
            invested=self.total_invested, current_value=self.total_current_value
        )

    @property
    def has_pricing_errors(self) -> bool:
        return any(h.price_error for h in self.holdings)


def _cashflows(
    transactions: list[TxnInput],
    current_value: float | None,
    valuation_date: date,
) -> list[Cashflow]:
    flows = [
        Cashflow(
            date=t.txn_date,
            amount=-(t.units * t.price) if t.txn_type == "BUY" else t.units * t.price,
        )
        for t in transactions
    ]
    if current_value:
        flows.append(Cashflow(date=valuation_date, amount=current_value))
    return flows


def value_holding(
    holding: HoldingInput,
    price_lookup: PriceLookup,
    valuation_date: date,
) -> HoldingSummary:
    lots = apply_fifo(holding.transactions)

    current_price: float | None = None
    price_error: str | None = None
    try:
        current_price = price_lookup(holding.asset_type, holding.identifier)
    except Exception as exc:  # any data-source failure, not just our own errors
        price_error = str(exc)

    current_value = (
        lots.units_held * current_price if current_price is not None else None
    )

    return HoldingSummary(
        holding_id=holding.holding_id,
        name=holding.name,
        asset_type=holding.asset_type,
        identifier=holding.identifier,
        category=holding.category,
        units_held=lots.units_held,
        invested=lots.cost_basis,
        current_price=current_price,
        current_value=current_value,
        realised_gain=lots.total_realised_gain,
        xirr=(
            compute_xirr(
                _cashflows(holding.transactions, current_value, valuation_date)
            )
            if price_error is None
            else None
        ),
        price_error=price_error,
    )


def value_portfolio(
    holdings: list[HoldingInput],
    price_lookup: PriceLookup,
    valuation_date: date,
) -> PortfolioSummary:
    summary = PortfolioSummary()
    pooled: list[Cashflow] = []

    for holding in holdings:
        held = value_holding(holding, price_lookup, valuation_date)
        summary.holdings.append(held)

        if held.price_error is not None:
            # Counting its cost without its value would invent a paper loss.
            summary.unpriced_invested += held.invested
            continue

        summary.total_invested += held.invested
        summary.total_current_value += held.current_value or 0.0
        summary.total_realised_gain += held.realised_gain
        pooled.extend(
            _cashflows(holding.transactions, held.current_value, valuation_date)
        )

    summary.xirr = compute_xirr(pooled)
    return summary
