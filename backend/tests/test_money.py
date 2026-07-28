import pytest

from app.services.advisor.money import inr


@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, "₹0"),
        (999, "₹999"),
        (1_000, "₹1,000"),
        (99_999, "₹99,999"),
        (1_00_000, "₹1,00,000"),
        (2_45_700, "₹2,45,700"),
        (1_54_083, "₹1,54,083"),
        (1_23_45_678, "₹1,23,45,678"),
        (1_00_00_00_000, "₹1,00,00,00,000"),
        (-2_45_700, "-₹2,45,700"),
        (1234.7, "₹1,235"),
    ],
)
def test_rupees_group_the_indian_way(amount, expected):
    """245,700 reads as a typo to anyone in India. The grouping goes in twos
    after the first thousand, and the commas are how the eye finds the lakh."""
    assert inr(amount) == expected


def test_the_backend_sentences_that_carry_rupees_all_use_it():
    """These strings are sent to the browser as prose, so the frontend's own
    formatter never sees them. Each was grouped in thousands until this."""
    from app.services.advisor.goal_commitment import GoalDemand, assess_commitment
    from app.services.advisor.tax_regime import compare_regimes

    commitment = assess_commitment(
        [GoalDemand("a", "Retirement", 1_54_083, 25)],
        annual_income=18_00_000,
        monthly_expenses=85_000,
    )
    assert "₹1,54,083" in commitment.verdict
    assert "154,083" not in commitment.verdict

    tax = compare_regimes(24_00_000, is_salaried=True, deductions=0)
    assert "₹2,45,700" in tax.rationale
