"""Answers "would I have done better just buying the index?".

The comparison mirrors the user's real cashflows — the same rupees on the same
dates — into the benchmark, then values that hypothetical holding today. Both
sides therefore share an identical cashflow timeline, which is what makes the
two XIRRs comparable: any difference is fund selection, not timing.
"""

from dataclasses import dataclass
from datetime import date

from app.services.marketdata.mutual_fund import NavPoint, nav_on_or_before
from app.services.portfolio.fifo import TxnInput
from app.services.portfolio.returns import Cashflow, compute_xirr


@dataclass(frozen=True)
class BenchmarkComparison:
    comparable: bool
    portfolio_value: float
    benchmark_value: float | None
    benchmark_units: float | None
    portfolio_xirr: float | None
    benchmark_xirr: float | None
    reason: str | None = None

    @property
    def outperformance(self) -> float | None:
        """Portfolio XIRR minus benchmark XIRR, in percentage points."""
        if self.portfolio_xirr is None or self.benchmark_xirr is None:
            return None
        return self.portfolio_xirr - self.benchmark_xirr


def _cashflows(
    transactions: list[TxnInput], terminal_value: float | None, valuation_date: date
) -> list[Cashflow]:
    flows = [
        Cashflow(
            date=t.txn_date,
            amount=-(t.units * t.price) if t.txn_type == "BUY" else t.units * t.price,
        )
        for t in transactions
    ]
    if terminal_value:
        flows.append(Cashflow(date=valuation_date, amount=terminal_value))
    return flows


def compare_to_benchmark(
    transactions: list[TxnInput],
    benchmark_navs: list[NavPoint],
    portfolio_current_value: float,
    valuation_date: date,
) -> BenchmarkComparison:
    def not_comparable(reason: str) -> BenchmarkComparison:
        return BenchmarkComparison(
            comparable=False,
            portfolio_value=portfolio_current_value,
            benchmark_value=None,
            benchmark_units=None,
            portfolio_xirr=compute_xirr(
                _cashflows(transactions, portfolio_current_value, valuation_date)
            ),
            benchmark_xirr=None,
            reason=reason,
        )

    if not transactions:
        return not_comparable("No transactions to compare")
    if not benchmark_navs:
        return not_comparable("No benchmark data available")

    units = 0.0
    for txn in sorted(transactions, key=lambda t: t.txn_date):
        nav = nav_on_or_before(benchmark_navs, txn.txn_date)
        if nav is None:
            # The benchmark series starts after this investment was made, so
            # there is no honest like-for-like to compute.
            return not_comparable(
                f"Benchmark history starts after {txn.txn_date}, so the periods do not match"
            )
        amount = txn.units * txn.price
        units += amount / nav.nav if txn.txn_type == "BUY" else -amount / nav.nav

    final_nav = nav_on_or_before(benchmark_navs, valuation_date)
    if final_nav is None:
        return not_comparable("No benchmark price on the valuation date")

    benchmark_value = units * final_nav.nav

    return BenchmarkComparison(
        comparable=True,
        portfolio_value=portfolio_current_value,
        benchmark_value=benchmark_value,
        benchmark_units=units,
        portfolio_xirr=compute_xirr(
            _cashflows(transactions, portfolio_current_value, valuation_date)
        ),
        benchmark_xirr=compute_xirr(
            _cashflows(transactions, benchmark_value, valuation_date)
        ),
    )
