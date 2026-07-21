from app.services.advisor.tax_advisor import generate_tax_saving_plan


def _action(plan: dict, section: str) -> dict:
    return next(a for a in plan["actions"] if a["section"] == section)


def test_typical_salaried_earner_is_told_to_stay_in_the_new_regime():
    """The old advisor pushed ELSS at everyone. For this user that is wrong."""
    plan = generate_tax_saving_plan(1_500_000)
    assert plan["regime"]["recommended"] == "new"

    elss = _action(plan, "80C")
    assert elss["applicable"] is False
    assert elss["tax_saved"] == 0
    assert elss["amount"] == 0


def test_deduction_heavy_high_earner_is_told_to_stay_in_the_old_regime():
    plan = generate_tax_saving_plan(
        2_500_000, existing_80c=150_000, existing_80d=25_000, other_deductions=675_000
    )
    assert plan["regime"]["recommended"] == "old"


def test_80c_gap_is_only_offered_when_the_old_regime_wins():
    plan = generate_tax_saving_plan(
        2_500_000, existing_80c=50_000, other_deductions=800_000
    )
    assert plan["regime"]["recommended"] == "old"

    elss = _action(plan, "80C")
    assert elss["applicable"] is True
    assert elss["amount"] == 100_000  # 1.5L cap minus the 50k already claimed
    assert elss["tax_saved"] > 0


def test_tax_saved_is_recomputed_not_multiplied_by_a_flat_rate():
    """A deduction that straddles a slab boundary saves less than top-rate x amount.

    The old code multiplied by a single rate and overstated the benefit for
    anyone sitting just above a slab edge.
    """
    # Old-regime taxable lands at 10.5L, so a 1.5L 80C deduction crosses the
    # 30% -> 20% boundary: only 50k of it is relieved at 30%.
    plan = generate_tax_saving_plan(1_100_000, other_deductions=0, force_regime="old")
    elss = _action(plan, "80C")
    naive = 150_000 * 0.30 * 1.04
    assert elss["tax_saved"] < naive
    assert elss["tax_saved"] > 0


def test_employer_nps_is_offered_in_both_regimes():
    """80CCD(2) is the one deduction that survives into the new regime."""
    for income in (1_500_000, 3_000_000):
        plan = generate_tax_saving_plan(income, basic_salary=income * 0.4)
        nps = _action(plan, "80CCD(2)")
        assert nps["applicable"] is True
        assert nps["amount"] > 0


def test_employer_nps_cap_is_14_percent_of_basic_in_the_new_regime():
    plan = generate_tax_saving_plan(2_000_000, basic_salary=1_000_000)
    assert plan["regime"]["recommended"] == "new"
    assert _action(plan, "80CCD(2)")["amount"] == 140_000


def test_employer_nps_has_no_rupee_figure_without_a_basic_salary():
    """Guessing basic as a fraction of CTC would be inventing a number."""
    plan = generate_tax_saving_plan(1_500_000)
    nps = _action(plan, "80CCD(2)")
    assert nps["amount"] is None
    assert "basic" in nps["note"].lower()


def test_existing_claims_are_subtracted_not_ignored():
    plan = generate_tax_saving_plan(
        2_500_000, existing_80c=150_000, existing_80d=25_000, other_deductions=700_000
    )
    assert _action(plan, "80C")["amount"] == 0
    assert _action(plan, "80D")["amount"] == 0


def test_nps_1b_is_skipped_when_the_user_already_has_it():
    plan = generate_tax_saving_plan(
        2_500_000, has_nps=True, existing_80c=150_000, other_deductions=700_000
    )
    assert _action(plan, "80CCD(1B)")["amount"] == 0


def test_total_saving_never_exceeds_the_bill_itself():
    plan = generate_tax_saving_plan(600_000)
    assert plan["total_potential_tax_saving"] <= max(
        plan["regime"]["new_regime_tax"], plan["regime"]["old_regime_tax"]
    )


def test_zero_income_produces_no_actions_and_no_tax():
    plan = generate_tax_saving_plan(0)
    assert plan["total_potential_tax_saving"] == 0
    assert plan["regime"]["new_regime_tax"] == 0
