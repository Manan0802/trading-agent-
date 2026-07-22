import pytest

from app.services.advisor.fund_catalogue import (
    BROWSABLE_CATEGORIES,
    CatalogueFund,
    codes_for_category,
    funds_in_category,
    is_browsable,
)


def test_the_categories_a_retail_investor_needs_are_all_present():
    for category in (
        "Equity Scheme - Large Cap Fund",
        "Equity Scheme - Mid Cap Fund",
        "Equity Scheme - Small Cap Fund",
        "Equity Scheme - Flexi Cap Fund",
        "Equity Scheme - ELSS",
        "Debt Scheme - Corporate Bond Fund",
        "Debt Scheme - Liquid Fund",
    ):
        assert category in BROWSABLE_CATEGORIES, category


def test_legacy_closed_ended_categories_are_not_offered():
    """The feed carries pre-2018 labels like 'Income', 'Growth', 'IDF' and
    '1099 Days'. They are wound-up or closed-ended schemes, not something a
    retail investor can act on, and 'Growth' as a category is meaningless
    alongside a Growth plan."""
    for junk in ("Income", "Growth", "IDF", "1099 Days"):
        assert junk not in BROWSABLE_CATEGORIES


def test_every_browsable_category_has_enough_funds_to_rank():
    """A percentile rank across two funds is not a ranking."""
    for category in BROWSABLE_CATEGORIES:
        assert len(codes_for_category(category)) >= 5, category


def test_categories_are_sorted_for_a_stable_filter_control():
    assert BROWSABLE_CATEGORIES == sorted(BROWSABLE_CATEGORIES)


def test_flexi_cap_now_holds_far_more_than_the_nine_hand_picked_funds():
    assert len(codes_for_category("Equity Scheme - Flexi Cap Fund")) > 30


def test_the_previously_hand_verified_codes_survive():
    """These were each checked against AMFI by hand, so their absence would
    mean the catalogue lost real funds."""
    assert "122639" in codes_for_category("Equity Scheme - Flexi Cap Fund")
    assert "118955" in codes_for_category("Equity Scheme - Flexi Cap Fund")
    assert "118814" in codes_for_category("Debt Scheme - Corporate Bond Fund")


def test_codes_are_strings_because_scheme_codes_have_leading_zeros_upstream():
    codes = codes_for_category("Equity Scheme - Flexi Cap Fund")
    assert all(isinstance(c, str) for c in codes)


def test_funds_carry_the_name_and_house_for_display():
    funds = funds_in_category("Equity Scheme - Flexi Cap Fund")
    assert all(isinstance(f, CatalogueFund) for f in funds)
    ppfas = next(f for f in funds if f.code == "122639")
    assert "Parag Parikh" in ppfas.name
    assert ppfas.fund_house


def test_an_unknown_category_yields_nothing_rather_than_raising():
    assert codes_for_category("Equity Scheme - Unicorn Fund") == []


def test_is_browsable_gates_the_api():
    assert is_browsable("Equity Scheme - Flexi Cap Fund")
    assert not is_browsable("Income")


def test_results_are_stable_across_calls():
    assert codes_for_category("Equity Scheme - ELSS") == codes_for_category(
        "Equity Scheme - ELSS"
    )
