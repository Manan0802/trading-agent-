"""Tax-saving actions, filtered by which regime the user should actually be in.

The previous version recommended ELSS to everyone using old-regime slabs. Since
FY 2023-24 the new regime is the default and Chapter VI-A deductions do not
exist inside it, so for most salaried users that advice was not merely
suboptimal — it told them to lock ₹1.5 lakh into a three-year product for a tax
benefit they could not claim.
"""

from app.services.advisor.money import inr
from app.services.advisor.tax_regime import Regime, compare_regimes, compute_tax

SECTION_80C_CAP = 150_000
SECTION_80D_SELF_CAP = 25_000
SECTION_80CCD_1B_CAP = 50_000

# Employer NPS: the one deduction that survives into the new regime, capped at a
# percentage of basic salary (not CTC) and higher in the new regime.
EMPLOYER_NPS_CAP_NEW = 0.14
EMPLOYER_NPS_CAP_OLD = 0.10


def _saving_from_reducing_income(
    annual_income: float,
    amount: float,
    regime: Regime,
    is_salaried: bool,
    claimed: float,
) -> float:
    """Tax saved by an employer contribution that never enters taxable salary."""
    before = compute_tax(
        annual_income, regime, is_salaried=is_salaried, deductions=claimed
    )
    after = compute_tax(
        annual_income - amount, regime, is_salaried=is_salaried, deductions=claimed
    )
    return round(before - after, 2)


def _saving_from_deduction(
    annual_income: float,
    amount: float,
    regime: Regime,
    is_salaried: bool,
    claimed: float,
) -> float:
    """Tax saved by claiming `amount` on top of `claimed`.

    Recomputed rather than multiplied by a single marginal rate: a deduction
    that straddles a slab boundary is relieved partly at the lower rate, and
    the flat-rate shortcut overstated the benefit for anyone sitting just
    above a slab edge.
    """
    before = compute_tax(
        annual_income, regime, is_salaried=is_salaried, deductions=claimed
    )
    after = compute_tax(
        annual_income, regime, is_salaried=is_salaried, deductions=claimed + amount
    )
    return round(before - after, 2)


def generate_tax_saving_plan(
    annual_income: float,
    existing_80c: float = 0,
    existing_80d: float = 0,
    has_nps: bool = False,
    *,
    is_salaried: bool = True,
    other_deductions: float = 0,
    basic_salary: float | None = None,
    force_regime: Regime | None = None,
) -> dict:
    """Which regime to pick, and only the actions that pay off inside it.

    `other_deductions` is everything outside 80C/80D/80CCD(1B) — HRA, home loan
    interest, 80E, 80G. Without it the old regime looks worse than it is for
    anyone paying rent or a mortgage.
    """
    claimed = existing_80c + existing_80d + other_deductions
    comparison = compare_regimes(
        annual_income, is_salaried=is_salaried, deductions=claimed
    )
    regime: Regime = force_regime or comparison.recommended
    old_regime_only = regime == "old"

    actions: list[dict] = []

    # --- Employer NPS, 80CCD(2): valid in both regimes, so it leads. ---
    nps_cap_rate = EMPLOYER_NPS_CAP_NEW if regime == "new" else EMPLOYER_NPS_CAP_OLD
    if basic_salary is None:
        employer_nps_amount = None
        employer_nps_saving = 0.0
        employer_nps_note = (
            f"Worth up to {nps_cap_rate:.0%} of your basic salary and it is the "
            "only deduction that still works in the new regime. Enter your basic "
            "(not CTC) to see the rupee figure, guessing it would be inventing "
            "a number. Ask HR whether they can route part of your CTC here."
        )
    else:
        employer_nps_amount = round(basic_salary * nps_cap_rate)
        employer_nps_saving = _saving_from_reducing_income(
            annual_income, employer_nps_amount, regime, is_salaried, claimed
        )
        employer_nps_note = (
            f"{nps_cap_rate:.0%} of your {inr(basic_salary)} basic. This is a "
            "CTC restructure, not extra money out of your pocket, but it is "
            "locked until 60, so only take it if you would have invested it anyway."
        )

    actions.append(
        {
            "name": "Employer NPS contribution",
            "section": "80CCD(2)",
            "amount": employer_nps_amount,
            "tax_saved": employer_nps_saving,
            "applicable": True,
            "note": employer_nps_note,
        }
    )

    running = claimed
    if employer_nps_amount:
        # Already reflected as an income reduction; nothing to add to `running`.
        pass

    def _add(name: str, section: str, gap: float, note: str) -> None:
        nonlocal running
        if not old_regime_only or gap <= 0:
            actions.append(
                {
                    "name": name,
                    "section": section,
                    "amount": 0,
                    "tax_saved": 0,
                    "applicable": old_regime_only,
                    "note": note
                    if old_regime_only
                    else f"Not claimable in the new regime, which is cheaper for you. {note}",
                }
            )
            return
        saved = _saving_from_deduction(
            annual_income, gap, regime, is_salaried, running
        )
        running += gap
        actions.append(
            {
                "name": name,
                "section": section,
                "amount": round(gap),
                "tax_saved": saved,
                "applicable": True,
                "note": note,
            }
        )

    _add(
        "ELSS / PPF / EPF top-up",
        "80C",
        max(0.0, SECTION_80C_CAP - existing_80c),
        "ELSS has the shortest lock-in at three years, but it is equity, do not "
        "use it for money you need inside five.",
    )
    _add(
        "Health insurance premium",
        "80D",
        max(0.0, SECTION_80D_SELF_CAP - existing_80d),
        "Buy this for the cover, not the deduction. A hospitalisation without "
        "insurance is the single most common reason a goal portfolio gets liquidated.",
    )
    _add(
        "Additional NPS contribution",
        "80CCD(1B)",
        0.0 if has_nps else SECTION_80CCD_1B_CAP,
        "Locked until 60 with only partial withdrawal allowed. The deduction is "
        "real; the illiquidity is also real.",
    )

    return {
        "regime": {
            "recommended": comparison.recommended,
            "new_regime_tax": comparison.new_regime_tax,
            "old_regime_tax": comparison.old_regime_tax,
            "saving": comparison.saving,
            "breakeven_deductions": comparison.breakeven_deductions,
            "rationale": comparison.rationale,
        },
        "evaluated_under": regime,
        "actions": actions,
        "total_potential_tax_saving": round(sum(a["tax_saved"] for a in actions), 2),
    }
