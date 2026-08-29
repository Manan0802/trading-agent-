"""The switch badge: four numbers, and the two ways of getting them wrong.

The first draft of this arithmetic charged the whole capital-gains bill against
a switch and concluded "two-year payback". Both halves of that were wrong in the
same direction -- toward telling someone to leave money in an expensive fund --
in the one place §1.1 says this app has a measured signal.
"""

import pytest

from app.services.advisor.switch_badge import (
    BADGE_MAX_CHARS,
    LTCG_RATE,
    STCG_RATE,
    switch_math,
)
from app.services.llm.grounding import Claim, check_all

# The worked example in §11.7, kept as a regression pin.
_WORKED = dict(
    balance=500_000.0,
    ter_gap_pp=1.0,
    unrealised_gain=200_000.0,
    long_term=True,
    exit_load=0.0,
    horizon_years=12.0,
    assumed_return=0.12,
    exemption_available=125_000.0,
)


def test_the_documented_example_reproduces_number_for_number():
    m = switch_math(**_WORKED, kind="plan")
    assert round(m.annual_saving) == 5_000
    assert round(m.tax_brought_forward) == 9_375
    assert round(m.tax_carry_per_year) == 1_125
    assert m.pays_back
    assert m.badge == "Direct saves ₹5,000/yr"


class TestTheTaxLineIsADeferralNotACost:
    def test_it_says_so_in_words(self):
        detail = switch_math(**_WORKED).detail
        assert "not a cost" in detail
        assert "basis resets" in detail
        assert "return forgone" in detail

    def test_charging_the_gross_bill_would_flip_the_verdict(self):
        """The whole reason the distinction is in the code rather than the prose.

        Same fund, an exit load, and a horizon: treating the ₹9,375 as spent
        turns a switch that pays back into one that does not.
        """
        args = {**_WORKED, "exit_load": 4_000.0, "horizon_years": 2.0}
        honest = switch_math(**args)
        assert honest.pays_back, "₹4,000 against ₹3,875/yr net pays back in ~1 year"

        gross_cost = args["exit_load"] + honest.tax_brought_forward
        as_if_sunk = gross_cost / honest.annual_saving
        assert as_if_sunk > args["horizon_years"], (
            "charging the deferral as a cost puts breakeven at "
            f"{as_if_sunk:.1f} years against a {args['horizon_years']:.0f}-year "
            "horizon, so the badge reads 'leave it' on a switch that pays back"
        )

    def test_only_the_exit_load_has_to_be_paid_back(self):
        no_load = switch_math(**{**_WORKED, "exit_load": 0.0})
        assert no_load.breakeven_years == 0.0, (
            "nothing left the account, so there is nothing to earn back"
        )


class TestTheExemptionIsNeverAssumed:
    def test_a_holding_allocated_none_of_it_is_taxed_on_the_whole_gain(self):
        """It is annual and shared, so ten rows claiming it overstate ten times."""
        none = switch_math(**{**_WORKED, "exemption_available": 0.0})
        assert round(none.tax_brought_forward) == round(200_000 * LTCG_RATE) == 25_000
        some = switch_math(**_WORKED)
        assert some.tax_brought_forward < none.tax_brought_forward

    def test_a_non_equity_fund_gets_no_exemption_at_all(self):
        """Section 112A covers equity and equity-oriented funds. Gold and debt
        sit under Section 112, which has no threshold."""
        gold = switch_math(**{**_WORKED, "equity": False})
        assert round(gold.tax_brought_forward) == 25_000, (
            "applying an equity exemption to a gold fund understates its bill"
        )

    def test_a_short_term_holding_is_taxed_at_the_short_term_rate(self):
        short = switch_math(**{**_WORKED, "long_term": False})
        assert round(short.tax_brought_forward) == round(200_000 * STCG_RATE)
        assert STCG_RATE > LTCG_RATE

    def test_a_loss_is_not_a_tax_bill(self):
        loss = switch_math(**{**_WORKED, "unrealised_gain": -50_000.0})
        assert loss.tax_brought_forward == 0.0
        assert loss.tax_carry_per_year == 0.0


class TestTheBadgeFitsItsColumn:
    @pytest.mark.parametrize("balance", [10_000, 500_000, 50_00_000, 5_00_00_000])
    @pytest.mark.parametrize("kind", ["plan", "peer"])
    def test_every_magnitude_fits(self, balance, kind):
        m = switch_math(**{**_WORKED, "balance": float(balance)}, kind=kind)
        assert len(m.badge) <= BADGE_MAX_CHARS, f"{m.badge!r} is {len(m.badge)}"

    def test_a_switch_that_does_not_pay_back_says_so_rather_than_softening(self):
        m = switch_math(**{**_WORKED, "exit_load": 90_000.0, "horizon_years": 2.0})
        assert not m.pays_back
        assert m.badge == "Cheaper option won't pay back"
        assert len(m.badge) <= BADGE_MAX_CHARS
        assert "saves" not in m.badge.lower(), (
            "recommending a switch that does not pay back inside the user's own "
            "horizon is the behaviour §1.2 says destroys returns"
        )

    def test_a_gap_that_saves_nothing_produces_no_breakeven(self):
        m = switch_math(**{**_WORKED, "ter_gap_pp": 0.0})
        assert m.breakeven_years is None
        assert not m.pays_back


class TestGroundingActuallyGuardsThis:
    """§9.1's open item: grounding.py is 792 lines, 50 tests, zero callers.

    A guard with no caller is a guard nothing is behind, so these tests check
    the wiring and then show the guard failing -- the acceptance slice 3.1 was
    written to, applied here because 1.4 is its first caller.
    """

    def test_every_printed_figure_passes_check_all(self):
        m = switch_math(**_WORKED)
        result = m.verify()
        assert result.ok, result.why()

    def test_the_guard_rejects_a_figure_the_payload_does_not_contain(self):
        m = switch_math(**_WORKED)
        fabricated = m.detail.replace("₹5,000", "₹50,000")
        result = check_all(fabricated, list(m.claims), m.source)
        assert not result.ok, (
            "a tenfold overstatement of the saving reached the screen unchecked"
        )
        # Reported without the separator: the checker normalises before
        # comparing, so ₹50,000 and 50000 are the same claim to it.
        assert "50000" in result.why()

    def test_the_guard_rejects_a_claim_citing_a_field_that_is_not_there(self):
        m = switch_math(**_WORKED)
        result = check_all(m.detail, [Claim("5000", "made_up_field")], m.source)
        assert not result.ok

    @pytest.mark.parametrize("kind", ["plan", "peer"])
    def test_the_badge_itself_is_covered_not_just_the_detail(self, kind):
        m = switch_math(**_WORKED, kind=kind)
        assert str(round(m.annual_saving)) in str(m.source["annual_saving"])
        assert m.verify().ok
