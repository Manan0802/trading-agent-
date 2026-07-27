import pytest

from app.services.portfolio.holding_cost import (
    PlanType,
    classify_plan,
    cost_review,
)


def test_a_direct_plan_is_recognised_from_its_name():
    assert classify_plan("Parag Parikh Flexi Cap Fund - Direct Plan - Growth") == "direct"


def test_a_regular_plan_is_recognised_from_its_name():
    assert classify_plan("SBI Balanced Advantage Fund - Regular Plan - Growth") == "regular"


def test_a_name_with_neither_word_is_not_guessed():
    """Older schemes predate the direct/regular split and simply do not say.
    Guessing would put a warning on a fund that may not deserve one."""
    assert classify_plan("Invesco India Infrastructure Fund - Growth") is None


def test_classification_ignores_case_and_spacing():
    assert classify_plan("HDFC  FLEXI CAP FUND -  DIRECT  PLAN") == "direct"


def test_a_regular_holding_is_priced_over_the_years_left():
    """0.65pp sounds small. What it takes out of a real balance over a real
    horizon does not."""
    review = cost_review(
        holdings=[{"name": "X Fund - Regular Plan - Growth", "value": 500000, "ter_gap": 0.0065}],
        years_remaining=15,
    )
    assert review.annual_cost == pytest.approx(3250, abs=1)
    assert review.lifetime_cost > review.annual_cost * 15


def test_a_direct_holding_costs_nothing_extra():
    review = cost_review(
        holdings=[{"name": "X Fund - Direct Plan - Growth", "value": 500000, "ter_gap": 0.0065}],
        years_remaining=15,
    )
    assert review.annual_cost == 0
    assert not review.flagged


def test_only_the_regular_holdings_are_flagged():
    review = cost_review(
        holdings=[
            {"name": "A - Direct Plan - Growth", "value": 300000, "ter_gap": 0.006},
            {"name": "B - Regular Plan - Growth", "value": 200000, "ter_gap": 0.009},
            {"name": "C Fund - Growth", "value": 100000, "ter_gap": 0.007},
        ],
        years_remaining=10,
    )
    assert [f.name for f in review.flagged] == ["B - Regular Plan - Growth"]


def test_a_holding_without_a_published_gap_is_not_priced():
    """AMFI does not file a TER for every scheme. An unpriced holding is
    reported as unknown rather than assigned an average."""
    review = cost_review(
        holdings=[{"name": "B - Regular Plan - Growth", "value": 200000, "ter_gap": None}],
        years_remaining=10,
    )
    assert review.annual_cost == 0
    assert review.unpriced == ["B - Regular Plan - Growth"]


def test_the_lifetime_figure_compounds_rather_than_multiplying():
    """The fee comes out of a balance that would otherwise have grown, so the
    cost of paying it compounds too."""
    review = cost_review(
        holdings=[{"name": "B - Regular Plan", "value": 1000000, "ter_gap": 0.01}],
        years_remaining=20,
        assumed_return=0.12,
    )
    naive = 0.01 * 1000000 * 20
    assert review.lifetime_cost > naive * 1.5


def test_zero_years_remaining_has_no_lifetime_cost():
    review = cost_review(
        holdings=[{"name": "B - Regular Plan", "value": 100000, "ter_gap": 0.01}],
        years_remaining=0,
    )
    assert review.lifetime_cost == 0


def test_an_empty_portfolio_reviews_cleanly():
    review = cost_review(holdings=[], years_remaining=10)
    assert review.annual_cost == 0 and not review.flagged and not review.unpriced


def test_the_summary_says_what_to_do_and_names_the_catch():
    """Switching is a redemption, so it is a taxable event. Telling someone to
    switch without saying that is bad advice."""
    review = cost_review(
        holdings=[{"name": "B - Regular Plan - Growth", "value": 400000, "ter_gap": 0.008}],
        years_remaining=12,
    )
    assert "₹" in review.summary
    assert "tax" in review.summary.lower() or "capital gain" in review.summary.lower()


def test_the_summary_reads_correctly_for_one_fund_and_for_several():
    one = cost_review(
        holdings=[{"name": "A - Regular Plan", "value": 100000, "ter_gap": 0.006}],
        years_remaining=10,
    )
    many = cost_review(
        holdings=[
            {"name": "A - Regular Plan", "value": 100000, "ter_gap": 0.006},
            {"name": "B - Regular Plan", "value": 100000, "ter_gap": 0.006},
        ],
        years_remaining=10,
    )
    assert "1 fund here is a regular plan" in one.summary
    assert "2 funds here are regular plans" in many.summary
