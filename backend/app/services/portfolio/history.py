"""Portfolio value over time, alongside the same money in the index.

A portfolio page without a trajectory only answers "what is it worth now". The
question the user actually has is whether the line is going anywhere, and
whether it is going there faster than the index would have. Both series are
rebuilt from the transaction ledger at each sampled date rather than stored, so
they can never drift out of agreement with the headline figures.
"""

from dataclasses import dataclass
from datetime import date

from app.services.marketdata.mutual_fund import NavPoint, nav_on_or_before
from app.services.portfolio.fifo import TxnInput, apply_fifo

# Roughly ten years of month-ends. A chart is around 800 pixels wide, so daily
# sampling would send thousands of numbers to draw the same line.
MAX_POINTS = 130


@dataclass(frozen=True)
class HoldingSeries:
    key: str
    transactions: list[TxnInput]
    navs: list[NavPoint]


@dataclass(frozen=True)
class HistoryPoint:
    date: date
    invested: float
    portfolio_value: float
    # None, never zero: a zero would draw the line along the bottom of the
    # chart and read as a total loss rather than as missing data.
    benchmark_value: float | None


def _month_ends(start: date, end: date) -> list[date]:
    """Month-end dates from the month of `start` up to but excluding `end`."""
    dates: list[date] = []
    year, month = start.year, start.month
    while True:
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        last_day = date(next_year, next_month, 1).toordinal() - 1
        month_end = date.fromordinal(last_day)
        if month_end >= end:
            break
        if month_end >= start:
            dates.append(month_end)
        year, month = next_year, next_month
    return dates


def _sample_dates(first_txn: date, valuation_date: date) -> list[date]:
    dates = _month_ends(first_txn, valuation_date)
    if len(dates) > MAX_POINTS - 1:
        # Keep the endpoints and thin the middle, so a long history still
        # renders the same shape with fewer points.
        stride = len(dates) // (MAX_POINTS - 1) + 1
        dates = dates[::stride]
    return [*dates, valuation_date]


def _units_and_invested(
    transactions: list[TxnInput], as_of: date
) -> tuple[float, float]:
    """Units held on a date, and the FIFO cost basis of exactly those units.

    The cost basis has to be FIFO, not buys-minus-sale-proceeds, because the
    headline "Invested" on the same page is FIFO and the two were 30% apart
    after any partial sale. Buy 100 at 100 and sell 60 at 120: net cash says
    2,800, the 40 units still held cost 4,000. Both are true statements about
    different quantities, and both were labelled "Invested" one above the other.

    This is the module's own promise -- rebuilt from the ledger so they "can
    never drift out of agreement with the headline figures" -- which was not
    kept until the two used the same definition.
    """
    upto = [t for t in transactions if t.txn_date <= as_of]
    if not upto:
        return 0.0, 0.0
    lots = apply_fifo(upto)
    return lots.units_held, lots.cost_basis


def _benchmark_units(
    transactions: list[TxnInput], benchmark_navs: list[NavPoint], as_of: date
) -> float | None:
    units = 0.0
    for txn in sorted(transactions, key=lambda t: t.txn_date):
        if txn.txn_date > as_of:
            continue
        nav = nav_on_or_before(benchmark_navs, txn.txn_date)
        if nav is None:
            # The index series starts after this investment, so there is no
            # honest like-for-like to draw.
            return None
        amount = txn.units * txn.price
        units += amount / nav.nav if txn.txn_type == "BUY" else -amount / nav.nav
    return units


def build_history(
    series: list[HoldingSeries],
    benchmark_navs: list[NavPoint],
    valuation_date: date,
) -> list[HistoryPoint]:
    all_txns = [t for s in series for t in s.transactions]
    if not all_txns:
        return []

    first = min(t.txn_date for t in all_txns)
    points: list[HistoryPoint] = []

    for as_of in _sample_dates(first, valuation_date):
        value = 0.0
        invested = 0.0
        for holding in series:
            units, spent = _units_and_invested(holding.transactions, as_of)
            invested += spent
            if units <= 0:
                continue
            nav = nav_on_or_before(holding.navs, as_of)
            if nav is not None:
                value += units * nav.nav

        bench_units = _benchmark_units(all_txns, benchmark_navs, as_of)
        bench_nav = nav_on_or_before(benchmark_navs, as_of)
        benchmark_value = (
            bench_units * bench_nav.nav
            if bench_units is not None and bench_nav is not None
            else None
        )

        points.append(
            HistoryPoint(
                date=as_of,
                invested=round(invested, 2),
                portfolio_value=round(value, 2),
                benchmark_value=(
                    round(benchmark_value, 2) if benchmark_value is not None else None
                ),
            )
        )

    return points
