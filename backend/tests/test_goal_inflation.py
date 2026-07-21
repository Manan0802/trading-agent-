import pytest

from app.services.advisor.goal_inflation import (
    GENERAL_INFLATION,
    inflation_for_goal,
    inflation_note,
)
from app.services.advisor.sip_calculator import calculate_required_sip


def test_education_inflates_faster_than_general_prices():
    """Indian private education has run well above CPI for two decades."""
    assert inflation_for_goal("education") > GENERAL_INFLATION


def test_healthcare_is_the_fastest_inflating_goal():
    rates = {g: inflation_for_goal(g) for g in ("education", "home", "retirement", "car")}
    assert inflation_for_goal("healthcare") > max(rates.values())


def test_unknown_goal_type_falls_back_to_general_inflation():
    assert inflation_for_goal("sabbatical-in-goa") == GENERAL_INFLATION


def test_goal_type_matching_is_case_and_whitespace_insensitive():
    assert inflation_for_goal("  Education ") == inflation_for_goal("education")


def test_every_goal_type_has_a_note_explaining_its_rate():
    """A number the user cannot interrogate is a number they cannot trust."""
    for goal in ("education", "healthcare", "home", "retirement", "car", "unknown"):
        note = inflation_note(goal)
        assert note
        assert f"{inflation_for_goal(goal):.0%}" in note


def test_education_goal_needs_a_materially_larger_sip_than_the_flat_6_percent():
    """This is the defect: a 15-year education goal was under-funded by the
    difference between 6% and 10% compounded — not a rounding error."""
    flat = calculate_required_sip(2_000_000, 15, 0.12, inflation_rate=0.06)
    real = calculate_required_sip(
        2_000_000, 15, 0.12, inflation_rate=inflation_for_goal("education")
    )
    assert real["required_monthly_sip"] > flat["required_monthly_sip"] * 1.5


def test_sip_calculator_still_accepts_an_explicit_rate():
    """The rate stays overridable — the table is a default, not a policy."""
    r = calculate_required_sip(1_000_000, 10, 0.12, inflation_rate=0.0)
    assert r["inflation_adjusted_target"] == pytest.approx(1_000_000)
