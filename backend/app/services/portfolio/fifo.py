"""FIFO lot accounting for holdings.

Indian tax law deems the earliest-purchased units sold first, so gains must be
matched lot by lot rather than against an average cost. The same lot ledger
drives both the portfolio's cost basis and the capital-gains figures the tax
advisor needs.
"""

from dataclasses import dataclass, field
from datetime import date

LONG_TERM_EQUITY_MONTHS = 12
# Kept because callers import it and because the number is still the right
# ROUGH answer for display. It is NOT what decides the rate -- see
# `is_long_term_equity`, which counts months.
LONG_TERM_EQUITY_DAYS = 365


def _months_after(start: date, months: int) -> date:
    """The same day-of-month, `months` later, clamped for short months.

    29 Feb + 12 months is 28 Feb, which is the reading that keeps a leap-day
    purchase from getting a free extra day.
    """
    total = start.month - 1 + months
    year, month = start.year + total // 12, total % 12 + 1
    last = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(start.day, last))


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
        """Equity/equity-MF long-term threshold, counted in MONTHS.

        Section 2(42A) makes a listed equity share or equity-oriented fund
        short-term when held for **not more than twelve months** -- calendar
        months, not 365 days. The day count is a proxy, and it breaks every
        time the holding spans a 29 February. Measured on the five boundary
        cases in the plan's section 10, three of five disagreed and **all three
        ran the same way**: `> 365 days` said long-term where the statute says
        short, so the app reported 12.5% where 20% was owed -- understating the
        tax by 7.5pp of the gain, on precisely the day it told the holder the
        wait was over.

        `366` would be the same mistake with a different constant; it breaks
        the non-leap years instead. Only calendar arithmetic matches the words.

        Debt and gold follow different rules, so callers must not reuse this
        flag for those asset classes.
        """
        return self.sell_date > _months_after(self.buy_date, LONG_TERM_EQUITY_MONTHS)


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
