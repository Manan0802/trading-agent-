import pytest

from app.services.advisor.levers import Lever, _inr, rank_levers


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


def test_a_user_already_on_the_cheaper_regime_is_not_credited_with_the_saving():
    """The defect this replaced: the page quoted every user the full
    new-versus-old gap as the biggest number on it, including the majority who
    are on the new regime by default and banked that saving years ago."""
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=2_400_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064,
        tax_saving=0, tax_regime_gap=245_700, current_regime="new",
    )
    tax = next(lever for lever in levers if lever.key == "tax_regime")
    assert tax.lifetime_value == 0
    assert "already" in tax.detail.lower()
    # And it must not outrank a lever that is actually worth money.
    assert levers[0].key == "plan_switch"


def test_the_already_done_lever_still_appears_so_the_check_is_visible():
    """Silently dropping it reads as though tax was never looked at."""
    levers = rank_levers(
        portfolio_value=0, annual_income=2_400_000, monthly_sip=0,
        years_remaining=10, regular_plan_cost_gap=None,
        tax_saving=0, tax_regime_gap=245_700, current_regime="new",
    )
    assert any(lever.key == "tax_regime" for lever in levers)


def test_no_tax_lever_at_all_when_there_is_no_decision_to_make():
    """Below the rebate threshold both regimes cost nothing, so there is no
    choice to congratulate the user on having made."""
    levers = rank_levers(
        portfolio_value=100_000, annual_income=400_000, monthly_sip=5_000,
        years_remaining=15, regular_plan_cost_gap=None,
        tax_saving=0, tax_regime_gap=0, current_regime="new",
    )
    assert not any(lever.key == "tax_regime" for lever in levers)


def test_a_user_on_the_dearer_regime_is_told_which_way_to_move():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=2_400_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064,
        tax_saving=245_700, tax_regime_gap=245_700, current_regime="old",
    )
    tax = next(lever for lever in levers if lever.key == "tax_regime")
    assert tax.lifetime_value > 0
    assert "new" in tax.title.lower()
    assert "new" in tax.action.lower()


@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, "₹0"),
        (999, "₹999"),
        (1_000, "₹1,000"),
        (99_999, "₹99,999"),
        (1_00_000, "₹1,00,000"),
        (2_45_700, "₹2,45,700"),
        (1_23_45_678, "₹1,23,45,678"),
        (-2_45_700, "-₹2,45,700"),
    ],
)
def test_rupees_are_grouped_the_indian_way(amount, expected):
    """245,700 reads as a typo to anyone in India. Lakhs and crores group in
    twos after the first thousand."""
    assert _inr(amount) == expected
