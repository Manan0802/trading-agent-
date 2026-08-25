"""Which decisions are worth money, ranked.

`rank_levers` returns a `LeverSet`, not a list: gates (do these first),
levers (then these, biggest first), trades (bought with risk, never sorted
in among the levers) and unpriced (what we know matters and cannot value).
Tests that only care about the ranked list read `.levers`.
"""

import pytest

from app.services.advisor import levers as levers_mod
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
    ).levers
    values = [lever.lifetime_value for lever in levers]
    assert values == sorted(values, reverse=True)


def test_fund_selection_is_included_and_valued_at_nothing():
    """Measured over sixty windows and it does not work. Leaving it off the
    list would hide the finding; putting it on at zero is the finding."""
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    ).levers
    picking = next(lever for lever in levers if lever.key == "fund_selection")
    assert picking.lifetime_value == 0
    assert "does not" in picking.detail.lower()


def test_switching_to_direct_beats_fund_picking_by_a_wide_margin():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    ).levers
    by_key = {lever.key: lever for lever in levers}
    assert by_key["plan_switch"].lifetime_value > by_key["fund_selection"].lifetime_value


def test_a_portfolio_already_in_direct_plans_shows_no_switch_lever():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=None, tax_saving=159_900,
    ).levers
    assert not any(lever.key == "plan_switch" for lever in levers)


def test_the_tax_lever_is_a_one_off_not_compounded_forever():
    """A regime choice saves that tax every year it applies, but it is not
    invested and compounding unless the user actually invests it, so claiming
    a compounded figure would be inventing a behaviour."""
    levers = rank_levers(
        portfolio_value=100_000, annual_income=1_500_000, monthly_sip=5_000,
        years_remaining=15, regular_plan_cost_gap=None, tax_saving=159_900,
    ).levers
    tax = next(lever for lever in levers if lever.key == "tax_regime")
    assert tax.annual_value == pytest.approx(159_900)
    assert tax.lifetime_value == pytest.approx(159_900 * 15)


def test_no_tax_lever_when_the_regimes_cost_the_same():
    levers = rank_levers(
        portfolio_value=100_000, annual_income=400_000, monthly_sip=5_000,
        years_remaining=15, regular_plan_cost_gap=None, tax_saving=0,
    ).levers
    assert not any(lever.key == "tax_regime" for lever in levers)


def test_every_lever_says_what_to_do_about_it():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    ).levers
    for lever in levers:
        assert lever.title and lever.detail
        assert lever.action


def test_the_switch_lever_names_the_tax_cost_of_switching():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=0,
    ).levers
    switch = next(lever for lever in levers if lever.key == "plan_switch")
    assert "capital gain" in switch.action.lower() or "tax" in switch.action.lower()


def test_an_empty_situation_still_returns_the_selection_finding():
    """Even a user with nothing invested deserves to know what does not work
    before they start."""
    levers = rank_levers(
        portfolio_value=0, annual_income=0, monthly_sip=0,
        years_remaining=0, regular_plan_cost_gap=None, tax_saving=0,
    ).levers
    assert [lever.key for lever in levers] == ["fund_selection"]


def test_values_are_rupees_not_percentages():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=159_900,
    ).levers
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
    ).levers
    tax = next(lever for lever in levers if lever.key == "tax_regime")
    assert tax.lifetime_value == 0
    assert "already" in tax.detail.lower()
    # And it must not outrank a lever that is actually worth money. Asserted
    # against the intent rather than against a named winner: `save_more` now
    # legitimately beats `plan_switch` for this user, and pinning the winner
    # made this test fail on a change it was never about.
    assert levers[0].key != "tax_regime"
    assert levers[0].lifetime_value > 0


def test_the_already_done_lever_still_appears_so_the_check_is_visible():
    """Silently dropping it reads as though tax was never looked at."""
    levers = rank_levers(
        portfolio_value=0, annual_income=2_400_000, monthly_sip=0,
        years_remaining=10, regular_plan_cost_gap=None,
        tax_saving=0, tax_regime_gap=245_700, current_regime="new",
    ).levers
    assert any(lever.key == "tax_regime" for lever in levers)


def test_no_tax_lever_at_all_when_there_is_no_decision_to_make():
    """Below the rebate threshold both regimes cost nothing, so there is no
    choice to congratulate the user on having made."""
    levers = rank_levers(
        portfolio_value=100_000, annual_income=400_000, monthly_sip=5_000,
        years_remaining=15, regular_plan_cost_gap=None,
        tax_saving=0, tax_regime_gap=0, current_regime="new",
    ).levers
    assert not any(lever.key == "tax_regime" for lever in levers)


def test_a_user_on_the_dearer_regime_is_told_which_way_to_move():
    levers = rank_levers(
        portfolio_value=2_000_000, annual_income=2_400_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064,
        tax_saving=245_700, tax_regime_gap=245_700, current_regime="old",
    ).levers
    tax = next(lever for lever in levers if lever.key == "tax_regime")
    assert tax.lifetime_value > 0
    assert "new" in tax.title.lower()
    assert "new" in tax.action.lower()


# ---------------------------------------------------------------------------
# The levers that were missing, and the four rules that keep them honest.
# ---------------------------------------------------------------------------

FULL = dict(
    portfolio_value=800_000, annual_income=1_500_000, monthly_sip=25_000,
    years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=184_000,
    tax_regime_gap=184_000, current_regime="old",
    monthly_expenses=60_000, liquid_savings=150_000,
    high_interest_debt=100_000, equity_share=0.6,
)


def full(**over):
    return rank_levers(**{**FULL, **over})


def test_saving_more_is_on_the_list_at_all():
    """The largest lever for almost everybody and it was on no screen in this
    app, while the one measured at zero had four."""
    keys = [lever.key for lever in full().levers]
    assert "save_more" in keys
    assert "ltcg_harvest" in keys
    assert "stay_invested" in keys


def test_saving_more_is_quoted_as_a_range_because_it_moves_with_the_assumption():
    """A cost gap compares two paths and the return assumption largely cancels.
    This one scales with it: +₹5,000/month over fifteen years is ₹14.6L at 6%
    and ₹30.6L at 14%. A single number would be false precision."""
    lever = next(l for l in full().levers if l.key == "save_more")
    assert lever.low is not None and lever.high is not None
    assert lever.low < lever.lifetime_value < lever.high
    assert lever.high > lever.low * 1.5, "the band is too narrow to be the real one"


def test_the_direction_of_saving_more_never_changes_across_the_band():
    for rate in (0.04, 0.06, 0.10, 0.14, 0.18):
        gain = (
            levers_mod._sip_future_value(30_000, 15, rate)
            - levers_mod._sip_future_value(25_000, 15, rate)
        )
        assert gain > 0, rate


def test_the_suggested_step_is_a_round_number_a_person_would_act_on():
    """"Put ₹5,000 more in" is a decision. "Put ₹4,873 more in" is a
    calculation result, and nobody acts on one."""
    for sip in (3_000, 12_000, 25_000, 90_000):
        step = levers_mod._saving_step(sip)
        assert step % 500 == 0, (sip, step)
        assert step >= 500


# ------------------------------------------------ contested magnitude, no number


def test_staying_invested_carries_no_figure_because_the_figure_is_contested():
    """Morningstar says 1.2 points a year, DALBAR said 0.72 in 2025 and 8.48 in
    2024, and a 2026 Financial Analysts Journal paper argues the headline is
    overstated. A number that swings twelvefold is not one to put on a screen —
    but the finding is real, so the lever stays and says why."""
    lever = next(l for l in full().levers if l.key == "stay_invested")
    assert lever.lifetime_value == 0
    assert lever.low is None and lever.high is None
    assert "not putting a number" in lever.detail
    assert "contested" in lever.evidence or "disagree" in lever.detail


# ------------------------------------------------------- gates are not levers


def test_expensive_debt_is_a_gate_not_a_lever():
    """Its value is per YEAR CARRIED. Sorted into a list of fifteen-year figures
    it ranked a guaranteed 42% return below a tax exemption — you do not weigh
    clearing a credit card against harvesting an allowance."""
    got = full()
    assert "high_interest_debt" not in [l.key for l in got.levers]
    assert "high_interest_debt" in [g.key for g in got.gates]


def test_the_debt_figure_is_per_year_not_over_the_whole_horizon():
    """₹1 lakh at 42% "costs" ₹1.87 crore against investing it over fifteen
    years. That is arithmetically right and rhetorically dishonest: nobody
    carries a card for fifteen years."""
    gate = next(g for g in full().gates if g.key == "high_interest_debt")
    assert gate.lifetime_value == gate.annual_value
    assert 20_000 < gate.lifetime_value < 40_000, gate.lifetime_value


def test_debt_is_cleared_before_the_emergency_fund():
    """42% interest before an account earning nothing."""
    keys = [g.key for g in full().gates]
    assert keys == ["high_interest_debt", "emergency_fund"]


def test_a_funded_emergency_fund_produces_no_gate():
    got = full(liquid_savings=600_000)
    assert "emergency_fund" not in [g.key for g in got.gates]


# --------------------------------------------- a trade is never sorted as a lever


def test_equity_share_is_kept_out_of_the_ranked_levers():
    """"Full equity is worth ₹34.8L more than 60%" is arithmetically true and is
    not free money — it is the price of holding through the fall that buys it.
    Sorted in among the fee savings it would top the list."""
    got = full()
    assert "equity_share" not in [l.key for l in got.levers]
    trade = next(t for t in got.trades if t.key == "equity_share")
    assert trade.kind == "trade"
    # And it would have topped the list, which is exactly why it is not on it.
    assert trade.lifetime_value > max(l.lifetime_value for l in got.levers)


def test_the_equity_trade_states_the_fall_it_is_paying_for():
    trade = next(t for t in full().trades if t.key == "equity_share")
    assert "not free money" in trade.detail
    assert "%" in trade.detail and "fall" in trade.detail
    assert "40%" in trade.action


def test_a_fully_invested_person_is_offered_no_equity_trade():
    assert full(equity_share=1.0).trades == []


# ------------------------------------------------- what we could not price


def test_what_we_cannot_price_is_named_rather_than_dropped():
    """A list containing only what we happened to be able to compute reads as a
    complete list of what matters."""
    got = rank_levers(
        portfolio_value=800_000, annual_income=1_500_000, monthly_sip=25_000,
        years_remaining=15, regular_plan_cost_gap=0.0064, tax_saving=0,
    )
    keys = {u.key for u in got.unpriced}
    assert keys == {"high_interest_debt", "emergency_fund", "equity_share"}
    for gap in got.unpriced:
        assert gap.why and gap.what_we_need
        assert gap.key not in [l.key for l in got.levers]


def test_knowing_the_spending_but_not_the_savings_asks_for_the_savings():
    got = full(liquid_savings=None)
    gap = next(u for u in got.unpriced if u.key == "emergency_fund")
    assert "₹" in gap.why, "it should say how much would be needed"


# ------------------------------------------------------ every lever is complete


def test_every_lever_says_how_we_know_and_when_to_come_back():
    """A number with no provenance is indistinguishable from one we made up,
    and nothing else on the Indian market tells a reader when to revisit."""
    got = full()
    for lever in got.levers + got.trades + got.gates:
        assert lever.evidence, lever.key
        assert lever.revisit, lever.key
        assert lever.action, lever.key
        assert lever.kind in {"certain", "behaviour", "trade", "gate"}, lever.kind


def test_certain_and_behaviour_levers_are_distinguished():
    """A slab calculation and "if you actually do it" are not the same kind of
    claim, and one list would present them as though they were."""
    by_key = {l.key: l for l in full().levers}
    assert by_key["tax_regime"].kind == "certain"
    assert by_key["plan_switch"].kind == "certain"
    assert by_key["ltcg_harvest"].kind == "certain"
    assert by_key["save_more"].kind == "behaviour"
    assert by_key["stay_invested"].kind == "behaviour"


def test_being_fully_in_direct_plans_does_not_zero_the_other_portfolio_levers():
    """One parameter served two meanings and quietly broke.

    `portfolio_value` was the money in REGULAR plans, because the only lever
    using it was the switch to direct. Then the LTCG exemption and the equity
    trade started using it too — and for anyone already fully in direct plans
    that value is zero, so both silently vanished. Their whole portfolio still
    has a gain to harvest.
    """
    got = rank_levers(
        portfolio_value=2_000_000,
        regular_plan_value=0.0,
        annual_income=1_500_000,
        monthly_sip=25_000,
        years_remaining=15,
        regular_plan_cost_gap=None,
        tax_saving=0,
    )
    keys = [lever.key for lever in got.levers]
    assert "ltcg_harvest" in keys, "the exemption applies to the whole portfolio"
    assert "plan_switch" not in keys, "there is nothing to switch"


def test_the_switch_is_valued_only_on_the_money_in_regular_plans():
    """The mirror of the above: a mostly-direct portfolio must not be billed a
    switch saving on all of it."""
    mostly_direct = rank_levers(
        portfolio_value=2_000_000, regular_plan_value=100_000,
        annual_income=1_500_000, monthly_sip=0, years_remaining=15,
        regular_plan_cost_gap=0.0064, tax_saving=0,
    )
    all_regular = rank_levers(
        portfolio_value=2_000_000, regular_plan_value=2_000_000,
        annual_income=1_500_000, monthly_sip=0, years_remaining=15,
        regular_plan_cost_gap=0.0064, tax_saving=0,
    )
    small = next(l for l in mostly_direct.levers if l.key == "plan_switch")
    large = next(l for l in all_regular.levers if l.key == "plan_switch")
    assert large.lifetime_value > small.lifetime_value * 5


# ---------------------------------------------------------------------------
# The reader can move the assumption, within bounds.
#
# Dietvorst, Simmons & Massey (Management Science 2018): people who can adjust
# an algorithm's output — even slightly, even within a restricted range — rely
# on it more and end up better off. His 2015 paper is the other half: an
# unalterable verdict gets abandoned the first time it errs.
# ---------------------------------------------------------------------------


def test_the_assumption_is_the_readers_to_move():
    low = full(assumed_return=0.06)
    high = full(assumed_return=0.16)
    a = next(l for l in low.levers if l.key == "save_more").lifetime_value
    b = next(l for l in high.levers if l.key == "save_more").lifetime_value
    assert b > a * 1.5, "moving the assumption changed nothing"


def test_an_absurd_assumption_is_clamped_not_obeyed():
    """An unbounded box lets someone type 40% and be told to do something
    absurd with real money. The bounds are the feature, not a limitation."""
    assert levers_mod.clamp_return(0.40) == levers_mod.RETURN_BOUNDS[1]
    assert levers_mod.clamp_return(-1.0) == levers_mod.RETURN_BOUNDS[0]
    assert levers_mod.clamp_return(None) == levers_mod._ASSUMED_RETURN
    absurd = next(l for l in full(assumed_return=5.0).levers if l.key == "save_more")
    capped = next(l for l in full(assumed_return=0.16).levers if l.key == "save_more")
    assert absurd.lifetime_value == capped.lifetime_value


def test_every_lever_that_depends_on_growth_carries_a_range():
    """I originally gave a range only to `save_more`, on the premise that a cost
    gap compares two paths so the assumption largely cancels. **Measuring it
    disproved that.** Over fifteen years the direct-plan switch moves 3.2x
    across the band and save-more moves 2.6x — the switch moves MORE, because a
    fee saving is a slice of a balance that is itself compounding.
    """
    for lever in full().levers:
        if lever.lifetime_value <= 0 or lever.key in NOT_COMPOUNDED:
            continue
        assert lever.low is not None, f"{lever.key} has no range"
        assert lever.low < lever.lifetime_value < lever.high, lever.key


# The one rupee figure here that does NOT move with the assumption, on purpose.
# `tax_regime` is `saving × years`, uncompounded: the money only grows if the
# person actually invests it, and assuming they do would be inventing a
# behaviour. So it correctly has no range, and this set records why rather than
# letting the test above quietly skip it.
NOT_COMPOUNDED = {"tax_regime"}


def test_the_tax_saving_is_deliberately_not_compounded():
    """It is the only rupee figure here that does not move when the reader
    changes the growth assumption — because it is not invested unless they
    invest it, and the engine will not assume that on their behalf."""
    at_low = next(l for l in full(assumed_return=0.04).levers if l.key == "tax_regime")
    at_high = next(l for l in full(assumed_return=0.16).levers if l.key == "tax_regime")
    assert at_low.lifetime_value == at_high.lifetime_value
    assert at_low.low is None


def test_a_lever_worth_nothing_gets_no_range():
    """A range around zero would imply the answer might not be zero."""
    for lever in full().levers:
        if lever.lifetime_value == 0:
            assert lever.low is None and lever.high is None, lever.key


def test_the_direction_of_every_lever_survives_the_whole_band():
    """The point of the bounds: a reader who disagrees with 12% should find the
    ranking still holds, not that it inverts."""
    for rate in (0.04, 0.08, 0.12, 0.16):
        got = full(assumed_return=rate)
        picking = next(l for l in got.levers if l.key == "fund_selection")
        assert picking.lifetime_value == 0, rate
        for lever in got.levers:
            assert lever.lifetime_value >= 0, (lever.key, rate)
