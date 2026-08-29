"""Indian income tax under both regimes, FY 2025-26 and FY 2026-27.

Budget 2026-27 (1 Feb 2026) made no change to personal income tax, so every
constant below is current for FY 2026-27 (AY 2027-28) as well. Re-confirm
after the next Budget: `tests/test_tax_regime.py` fails once the stated year
falls behind the current financial year, which is the prompt to check.

The new regime is the default since FY 2023-24 and most salaried people are
better off in it, because its slabs are wide enough that the deductions the old
regime allows rarely make up the difference. The advisor used to assume the old
regime and push 80C products at everyone, which is wrong advice for the common
case, so regime choice is computed here rather than assumed.
"""

from app.services.advisor.money import inr
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

# Surcharge on the TAX, not on the income, once taxable income passes a
# threshold. Slab-wise and cliff-edged: at 50,00,001 the whole bill takes 10%,
# not just the rupee above. That cliff is why marginal relief exists.
#
# The new regime caps surcharge at 25%; the old regime's top band is 37%. The
# 15% ceiling that applies to capital gains under 111A/112A/112 is a separate
# rule and is NOT this -- see `surcharge_rate_for_gains`.
_SURCHARGE_BANDS: list[tuple[float, float]] = [
    (5_000_000, 0.00),
    (10_000_000, 0.10),
    (20_000_000, 0.15),
    (50_000_000, 0.25),
    (float("inf"), 0.37),
]
_NEW_REGIME_MAX_SURCHARGE = 0.25

# Capital gains taxed under 111A (STCG), 112A and 112 (LTCG) carry surcharge at
# no more than 15% however high the total income goes. A person with 6 crore of
# salary pays 37% surcharge on the salary tax and 15% on the gains tax.
GAINS_SURCHARGE_CAP = 0.15


def surcharge_rate(taxable: float, regime: Regime) -> float:
    """The surcharge rate on ordinary income at this taxable income."""
    rate = 0.0
    for threshold, band in _SURCHARGE_BANDS:
        if taxable > threshold:
            continue
        rate = band
        break
    else:  # pragma: no cover - the final band is unbounded
        rate = _SURCHARGE_BANDS[-1][1]
    if regime == "new":
        return min(rate, _NEW_REGIME_MAX_SURCHARGE)
    return rate


def surcharge_rate_for_gains(taxable: float, regime: Regime) -> float:
    """Same bands, capped at 15% -- the rule for 111A / 112A / 112 income."""
    return min(surcharge_rate(taxable, regime), GAINS_SURCHARGE_CAP)


def _band_floor(taxable: float) -> float | None:
    """The threshold this income just crossed, or None below the first band."""
    crossed = [t for t, _ in _SURCHARGE_BANDS if taxable > t and t != float("inf")]
    return max(crossed) if crossed else None


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

    tax += _surcharge_with_relief(taxable, tax, regime, slabs, rebate_limit, rebate_cap)
    return tax * (1 + CESS_RATE)


def _surcharge_with_relief(
    taxable: float,
    base_tax: float,
    regime: Regime,
    slabs: list[tuple[float, float]],
    rebate_limit: float,
    rebate_cap: float,
) -> float:
    """Surcharge, reduced so crossing a threshold never costs more than it earns.

    The bands are cliffs: at 50,00,001 the whole bill takes 10% surcharge, not
    just the rupee above it. Without relief, earning one more rupee at 50 lakh
    costs about 1.4 lakh in tax -- so section 113's proviso caps the surcharge
    at the income above the threshold.

    Stated as a test rather than as a formula: the total tax on one rupee above
    a threshold may exceed the total tax below it by at most one rupee. That is
    the definition of marginal relief, and it is the thing the app must not get
    wrong, because a wrong answer here is wrong by lakhs.
    """
    rate = surcharge_rate(taxable, regime)
    if rate == 0.0:
        return 0.0

    surcharge = base_tax * rate
    threshold = _band_floor(taxable)
    if threshold is None:  # pragma: no cover - rate>0 implies a crossed band
        return surcharge

    # What someone exactly at the threshold pays, with no surcharge on it.
    at_threshold = _slab_tax(threshold, slabs)
    if threshold <= rebate_limit:
        at_threshold = max(0.0, at_threshold - rebate_cap)
    below_rate = surcharge_rate(threshold, regime)
    at_threshold += at_threshold * below_rate

    excess_income = taxable - threshold
    relief = max(0.0, (base_tax + surcharge) - at_threshold - excess_income)
    return surcharge - relief


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
                f"The new regime is cheaper by {inr(saving)}. You are "
                f"claiming {inr(deductions)} of deductions; the old regime "
                f"would only catch up at {inr(breakeven)}, which is "
                f"{inr(shortfall)} more than you have. Locking money into "
                "80C products to chase that is usually the tail wagging the dog."
            )
    else:
        rationale = (
            f"The old regime is cheaper by {inr(saving)} because your "
            f"{inr(deductions)} of deductions exceed the "
            f"{inr(breakeven)} breakeven. Keep claiming them, but check "
            "each one is an investment you would hold anyway."
            if breakeven is not None
            else f"The old regime is cheaper by {inr(saving)}."
        )

    return RegimeComparison(
        recommended=recommended,
        new_regime_tax=round(new_tax, 2),
        old_regime_tax=round(old_tax, 2),
        saving=round(saving, 2),
        rationale=rationale,
        breakeven_deductions=breakeven,
    )


def regime_switch_saving(
    annual_income: float,
    current: Regime,
    *,
    is_salaried: bool = False,
    deductions: float = 0.0,
) -> float:
    """What changing regime is worth *from where the taxpayer already is*.

    Zero when they are already in the cheaper one, and that is the common case
    rather than the exception: the new regime has been the statutory default
    since FY2023-24, so anyone who never filed a declaration is in it. Quoting
    them the full new-versus-old gap would bill them for a saving they have had
    all along, which is the difference between an advisor and a brochure.
    """
    comparison = compare_regimes(
        annual_income, is_salaried=is_salaried, deductions=deductions
    )
    return 0.0 if comparison.recommended == current else comparison.saving
