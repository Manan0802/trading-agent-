"""Indian income tax under both regimes, FY 2025-26 (AY 2026-27).

The new regime is the default since FY 2023-24 and most salaried people are
better off in it, because its slabs are wide enough that the deductions the old
regime allows rarely make up the difference. The advisor used to assume the old
regime and push 80C products at everyone, which is wrong advice for the common
case, so regime choice is computed here rather than assumed.
"""

from dataclasses import dataclass
from typing import Literal

Regime = Literal["new", "old"]

# (upper bound of slab, marginal rate). The final slab is unbounded.
_NEW_SLABS: list[tuple[float, float]] = [
    (400_000, 0.00),
    (800_000, 0.05),
    (1_200_000, 0.10),
    (1_600_000, 0.15),
    (2_000_000, 0.20),
    (2_400_000, 0.25),
    (float("inf"), 0.30),
]

_OLD_SLABS: list[tuple[float, float]] = [
    (250_000, 0.00),
    (500_000, 0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

NEW_REGIME_STANDARD_DEDUCTION = 75_000
OLD_REGIME_STANDARD_DEDUCTION = 50_000

# Section 87A: full rebate of the tax payable, capped, if taxable income is at
# or below the limit. In the new regime this is what makes 12L effectively free.
NEW_REGIME_REBATE_LIMIT = 1_200_000
NEW_REGIME_REBATE_CAP = 60_000
OLD_REGIME_REBATE_LIMIT = 500_000
OLD_REGIME_REBATE_CAP = 12_500

CESS_RATE = 0.04


def _slab_tax(taxable: float, slabs: list[tuple[float, float]]) -> float:
    tax = 0.0
    lower = 0.0
    for upper, rate in slabs:
        if taxable <= lower:
            break
        tax += (min(taxable, upper) - lower) * rate
        lower = upper
    return tax


def compute_tax(
    annual_income: float,
    regime: Regime,
    *,
    is_salaried: bool = False,
    deductions: float = 0.0,
) -> float:
    """Total tax including cess.

    `deductions` covers everything claimed beyond the standard deduction — 80C,
    80D, 80CCD(1B), home loan interest, HRA. It is silently ignored under the
    new regime, which is the point: passing it in and seeing no change is the
    honest answer, not an error.
    """
    if annual_income <= 0:
        return 0.0

    if regime == "new":
        slabs = _NEW_SLABS
        standard = NEW_REGIME_STANDARD_DEDUCTION if is_salaried else 0.0
        claimed = 0.0
        rebate_limit, rebate_cap = NEW_REGIME_REBATE_LIMIT, NEW_REGIME_REBATE_CAP
    else:
        slabs = _OLD_SLABS
        standard = OLD_REGIME_STANDARD_DEDUCTION if is_salaried else 0.0
        claimed = deductions
        rebate_limit, rebate_cap = OLD_REGIME_REBATE_LIMIT, OLD_REGIME_REBATE_CAP

    taxable = max(0.0, annual_income - standard - claimed)
    tax = _slab_tax(taxable, slabs)

    if taxable <= rebate_limit:
        tax = max(0.0, tax - rebate_cap)

    return tax * (1 + CESS_RATE)


@dataclass(frozen=True)
class RegimeComparison:
    recommended: Regime
    new_regime_tax: float
    old_regime_tax: float
    saving: float
    rationale: str
    breakeven_deductions: float | None


def _breakeven_deductions(
    annual_income: float, is_salaried: bool, new_tax: float
) -> float | None:
    """Deductions at which the old regime's bill matches the new regime's.

    Solved by bisection rather than algebra because the rebate makes the old
    regime's tax a piecewise function with a discontinuity in its derivative.
    """
    lo, hi = 0.0, annual_income
    if compute_tax(annual_income, "old", is_salaried=is_salaried, deductions=hi) >= new_tax:
        # Even wiping out the entire income under the old regime does not beat
        # the new one — which happens whenever the new regime's tax is already 0.
        return None

    for _ in range(60):
        mid = (lo + hi) / 2
        if compute_tax(annual_income, "old", is_salaried=is_salaried, deductions=mid) > new_tax:
            lo = mid
        else:
            hi = mid
    return round(hi)


def compare_regimes(
    annual_income: float,
    *,
    is_salaried: bool = False,
    deductions: float = 0.0,
) -> RegimeComparison:
    """Which regime costs less, by how much, and what would change the answer."""
    new_tax = compute_tax(annual_income, "new", is_salaried=is_salaried)
    old_tax = compute_tax(
        annual_income, "old", is_salaried=is_salaried, deductions=deductions
    )

    recommended: Regime = "new" if new_tax <= old_tax else "old"
    saving = abs(new_tax - old_tax)
    breakeven = _breakeven_deductions(annual_income, is_salaried, new_tax)

    if recommended == "new":
        if breakeven is None:
            rationale = (
                "The new regime costs you nothing here, so no amount of "
                "deductions can make the old regime cheaper. Any 80C investment "
                "you make should be made because you want the asset, not for tax."
            )
        else:
            shortfall = max(0.0, breakeven - deductions)
            rationale = (
                f"The new regime is cheaper by ₹{saving:,.0f}. You are "
                f"claiming ₹{deductions:,.0f} of deductions; the old regime "
                f"would only catch up at ₹{breakeven:,.0f}, which is "
                f"₹{shortfall:,.0f} more than you have. Locking money into "
                "80C products to chase that is usually the tail wagging the dog."
            )
    else:
        rationale = (
            f"The old regime is cheaper by ₹{saving:,.0f} because your "
            f"₹{deductions:,.0f} of deductions exceed the "
            f"₹{breakeven:,.0f} breakeven. Keep claiming them — but check "
            "each one is an investment you would hold anyway."
            if breakeven is not None
            else f"The old regime is cheaper by ₹{saving:,.0f}."
        )

    return RegimeComparison(
        recommended=recommended,
        new_regime_tax=round(new_tax, 2),
        old_regime_tax=round(old_tax, 2),
        saving=round(saving, 2),
        rationale=rationale,
        breakeven_deductions=breakeven,
    )
