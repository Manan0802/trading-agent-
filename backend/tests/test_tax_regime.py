import pytest

from app.services.advisor import tax_regime
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


def test_the_stated_financial_year_still_covers_today():
    """Tax is the largest number this app reports, and slabs change by Budget.

    The module names the years its constants are current for. This fails the
    moment the Indian financial year moves past the last one named, which is
    the prompt to re-check against the Budget rather than a claim that anything
    is wrong. Verified once by hand for FY 2026-27 — Budget 2026-27 changed no
    personal income tax value — and this makes the next check unmissable.
    """
    import re
    from datetime import date
    from pathlib import Path

    from app.services.advisor import tax_regime

    # The FIRST line only. A wider window picks up years from the prose below
    # it — which is how the first version of this test passed a mutation that
    # backdated the declaration, on pass 125.
    headline = Path(tax_regime.__file__).read_text().split("\n", 1)[0]
    years = re.findall(r"FY (\d{4})-(\d{2})", headline)
    assert years, f"tax_regime.py's first line no longer states its years: {headline!r}"
    latest_start = max(int(y[0]) for y in years)

    today = date.today()
    current_fy_start = today.year if today.month >= 4 else today.year - 1
    assert latest_start >= current_fy_start, (
        f"tax_regime.py states FY {latest_start}-{str(latest_start + 1)[2:]} but "
        f"it is now FY {current_fy_start}-{str(current_fy_start + 1)[2:]}. "
        "Re-check the slabs, 87A rebate, standard deduction and cess against the "
        "latest Budget, then extend the docstring."
    )


class TestSurchargeAndMarginalRelief:
    """The largest number this app shows, and it was absent entirely.

    Surcharge is levied on the TAX, not the income, and its bands are cliffs:
    at 50,00,001 the whole bill takes 10%, not just the rupee above. Without
    relief, earning one more rupee at 50 lakh costs about 1.4 lakh. Section
    113's proviso caps the surcharge at the income above the threshold, and
    that cap is what this class exists to hold.
    """

    THRESHOLDS = (5_000_000, 10_000_000, 20_000_000, 50_000_000)

    @pytest.mark.parametrize("threshold", THRESHOLDS)
    @pytest.mark.parametrize("regime", ("new", "old"))
    def test_one_rupee_more_income_costs_at_most_one_rupee_more_tax(
        self, threshold, regime
    ):
        """Measured BEFORE cess, which is where the law applies the relief.

        Cess is levied on the relieved total, so the figure a person actually
        pays rises by 1 x 1.04 = 1.04. BUILD.md's acceptance said "at most one
        rupee" and that is only true pre-cess; building it is what surfaced the
        difference.
        """
        below = tax_regime.compute_tax(threshold, regime)
        above = tax_regime.compute_tax(threshold + 1, regime)
        pre_cess = (above - below) / (1 + tax_regime.CESS_RATE)
        assert 0 <= pre_cess <= 1.0001, (
            f"{regime} regime at {threshold:,}: one more rupee of income costs "
            f"{pre_cess:,.2f} more tax before cess. Marginal relief is missing "
            "or wrong, and the error is in lakhs."
        )

    @pytest.mark.parametrize("threshold", THRESHOLDS)
    @pytest.mark.parametrize("regime", ("new", "old"))
    def test_the_bill_never_goes_down_when_income_goes_up(self, threshold, regime):
        """Relief must not over-correct into a discount."""
        assert tax_regime.compute_tax(threshold + 1, regime) >= tax_regime.compute_tax(
            threshold, regime
        )

    def test_the_new_regime_surcharge_is_capped_at_25_percent(self):
        """The 37% top band applies to the old regime only."""
        assert tax_regime.surcharge_rate(60_000_000, "new") == 0.25
        assert tax_regime.surcharge_rate(60_000_000, "old") == 0.37

    @pytest.mark.parametrize(
        "income,expected",
        [(4_000_000, 0.00), (6_000_000, 0.10), (15_000_000, 0.15), (30_000_000, 0.25)],
    )
    def test_the_bands_are_the_filed_ones(self, income, expected):
        assert tax_regime.surcharge_rate(income, "old") == expected

    def test_capital_gains_surcharge_stops_at_15_percent(self):
        """A separate rule, and the one this app actually shows.

        Gains under 111A, 112A and 112 carry surcharge at no more than 15%
        however high total income goes. Someone with 6 crore of salary pays
        37% on the salary tax and 15% on the gains tax -- conflating the two
        overstates a redemption's cost by a fifth of the gains bill.
        """
        assert tax_regime.surcharge_rate_for_gains(60_000_000, "old") == 0.15
        assert tax_regime.surcharge_rate_for_gains(30_000_000, "old") == 0.15
        assert tax_regime.surcharge_rate_for_gains(6_000_000, "old") == 0.10
        assert tax_regime.surcharge_rate_for_gains(4_000_000, "old") == 0.00

    def test_below_fifty_lakh_nothing_changed(self):
        """Surcharge starts above 50 lakh; every smaller bill must be untouched."""
        for income in (500_000, 1_200_000, 2_400_000, 4_999_999):
            assert tax_regime.surcharge_rate(income, "new") == 0.0
            assert tax_regime.surcharge_rate(income, "old") == 0.0
