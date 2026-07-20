"""FIFO lot accounting for holdings.

Indian tax law deems the earliest-purchased units sold first, so gains must be
matched lot by lot rather than against an average cost. The same lot ledger
drives both the portfolio's cost basis and the capital-gains figures the tax
advisor needs.
"""

from dataclasses import dataclass, field
from datetime import date

LONG_TERM_EQUITY_DAYS = 365


@dataclass(frozen=True)
class TxnInput:
    txn_date: date
    txn_type: str  # "BUY" | "SELL"
    units: float
    price: float


@dataclass(frozen=True)
class Lot:
    """Units still held from one purchase."""

    date: date
    units: float
    price: float

    @property
    def cost(self) -> float:
        return self.units * self.price


@dataclass(frozen=True)
class RealisedGain:
    buy_date: date
    sell_date: date
    units: float
    buy_price: float
    sell_price: float

    @property
    def gain(self) -> float:
        return self.units * (self.sell_price - self.buy_price)

    @property
    def holding_days(self) -> int:
        return (self.sell_date - self.buy_date).days

    @property
    def is_long_term_equity(self) -> bool:
        """Equity/equity-MF long-term threshold.

        Debt and gold follow different rules, so callers must not reuse this
        flag for those asset classes.
        """
        return self.holding_days > LONG_TERM_EQUITY_DAYS


@dataclass
class FifoResult:
    open_lots: list[Lot] = field(default_factory=list)
    realised_gains: list[RealisedGain] = field(default_factory=list)

    @property
    def units_held(self) -> float:
        return sum(lot.units for lot in self.open_lots)

    @property
    def cost_basis(self) -> float:
        return sum(lot.cost for lot in self.open_lots)

    @property
    def total_realised_gain(self) -> float:
        return sum(g.gain for g in self.realised_gains)


def apply_fifo(transactions: list[TxnInput]) -> FifoResult:
    result = FifoResult()
    open_lots: list[Lot] = []

    for txn in sorted(transactions, key=lambda t: t.txn_date):
        if txn.txn_type == "BUY":
            open_lots.append(Lot(date=txn.txn_date, units=txn.units, price=txn.price))
            continue

        remaining = txn.units
        while remaining > 1e-9:
            if not open_lots:
                raise ValueError(
                    f"Cannot sell more units than held on {txn.txn_date}: "
                    f"{txn.units} requested"
                )
            lot = open_lots[0]
            consumed = min(lot.units, remaining)
            result.realised_gains.append(
                RealisedGain(
                    buy_date=lot.date,
                    sell_date=txn.txn_date,
                    units=consumed,
                    buy_price=lot.price,
                    sell_price=txn.price,
                )
            )
            remaining -= consumed
            if consumed >= lot.units - 1e-9:
                open_lots.pop(0)
            else:
                open_lots[0] = Lot(
                    date=lot.date, units=lot.units - consumed, price=lot.price
                )

    result.open_lots = open_lots
    return result
