import pytest

from app.services.advisor.levers import Lever, rank_levers


def test_the_levers_come_back_ordered_by_what_they_are_worth():
    """The whole point: an advisor's job is to tell you which decision matters,
    and most people spend their attention on the one that matters least."""
    levers = rank_levers(
        portfolio_value=2_000_000,
        annual_income=1_500_000,
        monthly_sip=25_000,
        years_remaining=15,
        regular_plan_cost_gap=0.0064,
        tax_saving=159_900,
    )
    values = [lever.lifetime_value for lever in levers]
    assert values == sorted(values, reverse=True)


def test_fund_selection_is_included_and_valued_at_nothing():
    """Measured over sixty windows and it does not work. Leaving it off the
    list would hide the finding; putting it on at zero is the finding."""
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    )
    picking = next(lever for lever in levers if lever.key == "fund_selection")
    assert picking.lifetime_value == 0
    assert "does not" in picking.detail.lower()


def test_switching_to_direct_beats_fund_picking_by_a_wide_margin():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    )
    by_key = {lever.key: lever for lever in levers}
    assert by_key["plan_switch"].lifetime_value > by_key["fund_selection"].lifetime_value


def test_a_portfolio_already_in_direct_plans_shows_no_switch_lever():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=None, tax_saving=159_900,
    )
    assert not any(lever.key == "plan_switch" for lever in levers)


def test_the_tax_lever_is_a_one_off_not_compounded_forever():
    """A regime choice saves that tax every year it applies, but it is not
    invested and compounding unless the user actually invests it, so claiming
    a compounded figure would be inventing a behaviour."""
    levers = rank_levers(
        portfolio_value=100_000, annual_income=1_500_000, monthly_sip=5_000,
        years_remaining=15, regular_plan_cost_gap=None, tax_saving=159_900,
    )
    tax = next(lever for lever in levers if lever.key == "tax_regime")
    assert tax.annual_value == pytest.approx(159_900)
    assert tax.lifetime_value == pytest.approx(159_900 * 15)


def test_no_tax_lever_when_the_regimes_cost_the_same():
    levers = rank_levers(
        portfolio_value=100_000, annual_income=400_000, monthly_sip=5_000,
        years_remaining=15, regular_plan_cost_gap=None, tax_saving=0,
    )
    assert not any(lever.key == "tax_regime" for lever in levers)


def test_every_lever_says_what_to_do_about_it():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    )
    for lever in levers:
        assert lever.title and lever.detail
        assert lever.action


def test_the_switch_lever_names_the_tax_cost_of_switching():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=0,
    )
    switch = next(lever for lever in levers if lever.key == "plan_switch")
    assert "capital gain" in switch.action.lower() or "tax" in switch.action.lower()


def test_an_empty_situation_still_returns_the_selection_finding():
    """Even a user with nothing invested deserves to know what does not work
    before they start."""
    levers = rank_levers(
        portfolio_value=0, annual_income=0, monthly_sip=0,
        years_remaining=0, regular_plan_cost_gap=None, tax_saving=0,
    )
    assert [lever.key for lever in levers] == ["fund_selection"]


def test_values_are_rupees_not_percentages():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    )
    switch = next(lever for lever in levers if lever.key == "plan_switch")
    assert switch.annual_value > 1000
