import pytest

from app.services.advisor.tax_regime import (
    NEW_REGIME_REBATE_LIMIT,
    compare_regimes,
    compute_tax,
    regime_switch_saving,
)


def test_new_regime_is_free_up_to_twelve_lakh_taxable():
    """The 87A rebate wipes out tax entirely up to 12L taxable income."""
    assert compute_tax(NEW_REGIME_REBATE_LIMIT, regime="new") == 0
    assert compute_tax(1_200_001, regime="new") > 0


def test_salaried_person_at_12_75_lakh_pays_nothing():
    # 75,000 standard deduction brings 12.75L down to the 12L rebate limit.
    assert compute_tax(1_275_000, regime="new", is_salaried=True) == 0


def test_new_regime_slabs_are_applied_progressively():
    # 20L salaried: 75k standard deduction -> 19.25L taxable.
    # 4L nil + 4L@5% + 4L@10% + 4L@15% + 3.25L@20% = 20k+40k+60k+65k = 1,85,000
    # No rebate above 12L. Plus 4% cess.
    tax = compute_tax(2_000_000, regime="new", is_salaried=True)
    assert tax == pytest.approx(185_000 * 1.04, abs=1)


def test_old_regime_allows_deductions_new_regime_does_not():
    gross = 1_500_000
    without = compute_tax(gross, regime="old", is_salaried=True)
    with_80c = compute_tax(gross, regime="old", is_salaried=True, deductions=150_000)
    assert with_80c < without

    # The same deduction is simply ignored under the new regime.
    assert compute_tax(gross, regime="new", is_salaried=True, deductions=150_000) == (
        compute_tax(gross, regime="new", is_salaried=True)
    )


def test_cess_is_included():
    """Health and education cess is 4% on tax — a real part of the bill."""
    tax = compute_tax(1_300_000, regime="new", is_salaried=True)
    assert tax % 1 == pytest.approx(0, abs=0.01) or tax > 0
    # 13L - 75k = 12.25L taxable: 4L nil + 4L@5% + 4L@10% + 0.25L@15% = 63,750
    assert tax == pytest.approx(63_750 * 1.04, abs=1)


def test_no_tax_on_zero_income():
    assert compute_tax(0, regime="new") == 0
    assert compute_tax(0, regime="old") == 0


def test_comparison_picks_new_regime_when_deductions_are_small():
    """This is the common case, and the one the old code got wrong."""
    result = compare_regimes(annual_income=1_200_000, is_salaried=True, deductions=150_000)
    assert result.recommended == "new"
    assert result.saving > 0
    assert "80C" in result.rationale or "deduction" in result.rationale.lower()


def test_comparison_picks_old_regime_when_deductions_are_large():
    """High earners with a home loan, HRA and full 80C can still win on old."""
    result = compare_regimes(
        annual_income=2_500_000, is_salaried=True, deductions=850_000
    )
    assert result.recommended == "old"
    assert result.saving > 0


def test_comparison_reports_both_bills_so_the_user_can_check():
    result = compare_regimes(annual_income=1_500_000, is_salaried=True, deductions=200_000)
    assert result.new_regime_tax > 0
    assert result.old_regime_tax > 0
    assert result.saving == pytest.approx(
        abs(result.new_regime_tax - result.old_regime_tax)
    )


def test_breakeven_deduction_is_reported():
    """How much more the user would need to deduct for old to win — actionable."""
    result = compare_regimes(annual_income=1_500_000, is_salaried=True, deductions=0)
    assert result.recommended == "new"
    assert result.breakeven_deductions is not None
    assert result.breakeven_deductions > 0

    # At exactly the breakeven, the two bills should be near-identical.
    at_breakeven = compare_regimes(
        annual_income=1_500_000,
        is_salaried=True,
        deductions=result.breakeven_deductions,
    )
    assert at_breakeven.saving < 1000


def test_someone_already_on_the_cheaper_regime_is_told_the_switch_is_worth_nothing():
    """The whole reason this function exists. The new regime is the statutory
    default, so most users are already in it and the full new-versus-old gap is
    a saving they have had for years — not one we can offer them."""
    saving = regime_switch_saving(
        2_400_000, current="new", is_salaried=True, deductions=0
    )
    assert saving == 0.0

    # And the gap itself is real, which is what makes the zero meaningful
    # rather than an artefact of the two bills being equal.
    assert compare_regimes(2_400_000, is_salaried=True, deductions=0).saving > 200_000


def test_someone_stuck_on_the_dearer_regime_is_quoted_the_real_gap():
    comparison = compare_regimes(2_400_000, is_salaried=True, deductions=0)
    saving = regime_switch_saving(
        2_400_000, current="old", is_salaried=True, deductions=0
    )
    assert saving == pytest.approx(comparison.saving)
    assert saving > 0


def test_heavy_deductions_flip_which_direction_the_switch_pays():
    """A big home loan and full 80C can make the old regime the right one, and
    then it is the person on the new regime who is leaving money behind."""
    assert regime_switch_saving(
        2_500_000, current="old", is_salaried=True, deductions=850_000
    ) == 0.0
    assert regime_switch_saving(
        2_500_000, current="new", is_salaried=True, deductions=850_000
    ) > 0
