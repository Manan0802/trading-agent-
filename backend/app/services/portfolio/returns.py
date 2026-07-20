"""Money-weighted portfolio returns.

XIRR is the right metric here because a real portfolio is built from irregular
cashflows — monthly SIPs, ad-hoc top-ups, partial redemptions. Time-weighted
return (what most portfolio trackers show) deliberately strips out the effect
of *when* money went in, which answers a different question than "what did my
money actually earn".
"""

from dataclasses import dataclass
from datetime import date

import pyxirr


@dataclass(frozen=True)
class Cashflow:
    """One movement of money. Negative = invested, positive = received back.

    A holding's current market value is modelled as a positive cashflow on the
    valuation date, as if the position were liquidated that day.
    """

    date: date
    amount: float


def compute_xirr(cashflows: list[Cashflow]) -> float | None:
    """Annualised money-weighted return, or None when it is undefined.

    Undefined happens routinely in real use — a brand-new holding with a single
    purchase and no valuation yet has no rate that balances the equation — so
    callers get None rather than an exception to handle.
    """
    if not cashflows:
        return None
    try:
        return pyxirr.xirr(
            [cf.date for cf in cashflows], [cf.amount for cf in cashflows]
        )
    except pyxirr.InvalidPaymentsError:
        return None


def absolute_return(
    invested: float, current_value: float, realised: float = 0.0
) -> float:
    """Simple gain over cost, ignoring time. Shown alongside XIRR, never instead of it."""
    if invested <= 0:
        return 0.0
    return (current_value + realised - invested) / invested
