import pytest

from app.services.advisor.goal_commitment import GoalDemand, assess_commitment


def _goal(name: str, sip: float, years: float = 15) -> GoalDemand:
    return GoalDemand(goal_id=name.lower(), goal_name=name, monthly_sip=sip, years=years)


class TestGoalsAreAddedUp:
    """The failure this exists to catch. A planner computes three tidy ₹15,000
    plans and never mentions that they come to ₹45,000."""

    def test_three_affordable_looking_goals_can_be_unaffordable_together(self):
        result = assess_commitment(
            [_goal("Retirement", 15_000), _goal("House", 15_000), _goal("Car", 15_000)],
            annual_income=1_200_000,
            monthly_expenses=55_000,
        )
        assert result.total_monthly == 45_000
        # 1L income, 55k expenses, 45k surplus, less a tenth held back = 40.5k
        assert result.affordable_monthly == pytest.approx(40_500)
        assert result.shortfall == pytest.approx(4_500)
        assert "short" in result.verdict

    def test_goals_that_fit_are_told_they_fit_with_the_headroom_named(self):
        result = assess_commitment(
            [_goal("Retirement", 20_000)],
            annual_income=1_800_000,
            monthly_expenses=70_000,
        )
        assert result.shortfall == 0
        assert "fit" in result.verdict
        assert result.affordable_monthly is not None
        assert result.affordable_monthly > result.total_monthly

    def test_a_buffer_is_held_back_before_anything_is_called_spare(self):
        """A plan that commits every spare rupee is the plan a single bad month
        breaks."""
        result = assess_commitment(
            [_goal("X", 1)], annual_income=1_200_000, monthly_expenses=50_000
        )
        surplus = 100_000 - 50_000
        assert result.affordable_monthly == pytest.approx(surplus * 0.9)
        assert result.affordable_monthly < surplus


class TestItRefusesToInventTheAnswer:
    def test_without_income_it_reports_the_total_and_says_what_is_missing(self):
        result = assess_commitment(
            [_goal("Retirement", 15_000)],
            annual_income=None,
            monthly_expenses=None,
        )
        assert result.total_monthly == 15_000
        assert result.affordable_monthly is None
        assert result.shortfall is None
        assert "income" in result.verdict

    def test_income_without_expenses_is_still_not_enough_to_judge(self):
        result = assess_commitment(
            [_goal("Retirement", 15_000)],
            annual_income=1_200_000,
            monthly_expenses=None,
        )
        assert result.shortfall is None

    def test_expenses_above_income_leave_nothing_rather_than_a_negative(self):
        result = assess_commitment(
            [_goal("Retirement", 15_000)],
            annual_income=600_000,
            monthly_expenses=80_000,
        )
        assert result.affordable_monthly == 0
        assert result.shortfall == 15_000


class TestWhatItSays:
    def test_the_largest_goal_is_named_because_that_is_where_a_choice_starts(self):
        result = assess_commitment(
            [_goal("Car", 8_000), _goal("Daughter's college", 30_000)],
            annual_income=900_000,
            monthly_expenses=50_000,
        )
        assert "Daughter's college" in result.verdict

    def test_it_suggests_moving_a_date_rather_than_choosing_for_the_user(self):
        """Cutting a retirement target and delaying a house are not comparable
        in a way a formula can settle."""
        result = assess_commitment(
            [_goal("Retirement", 40_000)],
            annual_income=900_000,
            monthly_expenses=50_000,
        )
        assert "date" in result.verdict
        assert "compound" in result.verdict

    def test_goals_come_back_largest_first(self):
        result = assess_commitment(
            [_goal("Small", 2_000), _goal("Big", 30_000), _goal("Middle", 9_000)],
            annual_income=1_200_000,
            monthly_expenses=40_000,
        )
        assert [g.goal_name for g in result.goals] == ["Big", "Middle", "Small"]

    def test_no_goals_says_so_rather_than_reporting_a_zero(self):
        result = assess_commitment([], annual_income=1_200_000, monthly_expenses=40_000)
        assert result.total_monthly == 0
        assert "No goals yet" in result.verdict
