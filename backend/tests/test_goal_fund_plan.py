import pytest

from app.services.advisor.fund_score import FundEvidence, WindowEvidence
from app.services.advisor.goal_fund_plan import (
    MIN_MONTHLY_SIP,
    build_fund_plan,
)


def _ev(code: str, *, worst=0.02, ter=0.007, span=12.0) -> FundEvidence:
    return FundEvidence(
        scheme_code=code,
        scheme_name=f"Fund {code}",
        category="Equity Scheme - Flexi Cap Fund",
        windows={
            "3y": WindowEvidence(mean=0.17, worst=worst, share_positive=1.0, count=900),
            "1y": WindowEvidence(mean=0.19, worst=-0.09, share_positive=0.9, count=1600),
        },
        volatility=0.14,
        max_drawdown=-0.24,
        direct_ter=ter,
        regular_ter=ter + 0.007,
        history_years=span,
    )


def _fake_ranker(_category, **_kw):
    from app.services.advisor.category_ranking import CategoryRanking, RankedFund
    from app.services.advisor.fund_score import score_peer_group_v2
    from app.services.advisor.fund_verdict import build_verdict

    scored = score_peer_group_v2(
        [_ev("a", worst=0.05, ter=0.005), _ev("b", worst=0.01, ter=0.012), _ev("c", worst=-0.04)]
    )
    return CategoryRanking(
        category=_category,
        ranked=[
            RankedFund(rank=i, fund=f, verdict=build_verdict(f.evidence, i, 3))
            for i, f in enumerate(scored.ranked, 1)
        ],
        unscorable=scored.unscorable,
        priced=3,
    )


def test_the_plan_names_funds_and_rupee_amounts_not_percentages():
    """"Put 65% in equity" is not something anyone can act on."""
    plan = build_fund_plan({"equity": 100}, monthly_sip=10000, ranker=_fake_ranker)
    assert plan.picks
    assert all(p.monthly_amount > 0 for p in plan.picks)
    assert sum(p.monthly_amount for p in plan.picks) == pytest.approx(10000)


def test_the_split_adds_back_to_the_sip_exactly():
    for sip in (5000, 7777, 25000):
        plan = build_fund_plan({"equity": 60, "debt": 40}, monthly_sip=sip, ranker=_fake_ranker)
        assert sum(p.monthly_amount for p in plan.picks) == pytest.approx(sip, abs=1)


def test_an_asset_class_too_small_to_place_is_skipped_with_the_reason():
    plan = build_fund_plan({"equity": 99, "gold": 1}, monthly_sip=10000, ranker=_fake_ranker)
    assert any(s.asset_class == "gold" for s in plan.skipped)
    assert "500" in plan.skipped[0].reason


def test_the_basket_narrows_rather_than_recommending_unplaceable_instalments():
    """Two funds at ₹300 each is worse than one at ₹600: most funds will not
    accept the ₹300."""
    plan = build_fund_plan({"equity": 100}, monthly_sip=800, ranker=_fake_ranker)
    assert len(plan.picks) == 1
    assert plan.picks[0].monthly_amount == pytest.approx(800)


def test_each_pick_carries_the_same_verdict_the_ranking_gives_it():
    """A goal and the Research page must not judge the same fund differently."""
    plan = build_fund_plan({"equity": 100}, monthly_sip=10000, ranker=_fake_ranker)
    assert plan.picks[0].verdict.headline
    assert plan.picks[0].rank == 1


def test_the_annual_commission_saved_is_totalled_across_the_plan():
    """Every pick is a direct plan. What that is worth is worth stating once."""
    plan = build_fund_plan({"equity": 100}, monthly_sip=12000, ranker=_fake_ranker)
    assert plan.annual_commission_avoided is not None
    assert plan.annual_commission_avoided > 0


def test_no_commission_total_when_no_pick_publishes_both_plans():
    def ranker(category, **kw):
        result = _fake_ranker(category, **kw)
        for r in result.ranked:
            object.__setattr__(r.fund.evidence, "regular_ter", None)
        return result

    plan = build_fund_plan({"equity": 100}, monthly_sip=12000, ranker=ranker)
    assert plan.annual_commission_avoided is None


def test_a_zero_weight_class_is_ignored_entirely():
    plan = build_fund_plan({"equity": 100, "gold": 0}, monthly_sip=10000, ranker=_fake_ranker)
    assert not any(s.asset_class == "gold" for s in plan.skipped)
    assert all(p.asset_class == "equity" for p in plan.picks)


def test_an_empty_category_is_skipped_with_a_reason_rather_than_dropped_silently():
    from app.services.advisor.category_ranking import CategoryRanking

    def empty(category, **_kw):
        return CategoryRanking(category=category, ranked=[], unscorable=[], priced=0)

    plan = build_fund_plan({"equity": 100}, monthly_sip=10000, ranker=empty)
    assert not plan.picks
    assert plan.skipped and plan.skipped[0].reason


def test_the_minimum_is_stated_where_it_bites():
    assert MIN_MONTHLY_SIP >= 500


class TestEveryInstalmentCanActuallyBePlaced:
    """A plan is only advice if the user can carry it out. Two ways it could
    produce an instalment no fund would accept, and one way it could quietly
    stop investing part of the SIP."""

    def test_the_weighted_split_never_drops_a_fund_below_the_minimum(self):
        """The guard checked an even split and the code then applied 60/40. A
        ₹1,000 sleeve became ₹600 and ₹400, and the ₹400 SIP was rejected at
        the counter."""
        plan = build_fund_plan(
            {"equity": 100.0}, monthly_sip=1000.0, ranker=_fake_ranker
        )
        assert len(plan.picks) == 2
        for pick in plan.picks:
            assert pick.monthly_amount >= MIN_MONTHLY_SIP, pick
        assert sum(p.monthly_amount for p in plan.picks) == pytest.approx(1000.0)

    @pytest.mark.parametrize("sip", [1000.0, 1100.0, 1200.0, 1249.0, 2000.0, 7333.0])
    def test_no_instalment_anywhere_is_below_what_a_fund_accepts(self, sip):
        plan = build_fund_plan(
            {"equity": 65.0, "debt": 25.0, "gold": 10.0},
            monthly_sip=sip,
            ranker=_fake_ranker,
        )
        for pick in plan.picks:
            assert pick.monthly_amount >= MIN_MONTHLY_SIP, (sip, pick)

    def test_a_sleeve_too_small_to_buy_hands_its_money_to_the_rest(self):
        """10% of a ₹4,000 SIP is ₹400 of gold, which no fund will take. Leaving
        gold out is right; leaving the ₹400 uninvested is not, and that is what
        used to happen."""
        plan = build_fund_plan(
            {"equity": 65.0, "debt": 25.0, "gold": 10.0},
            monthly_sip=4000.0,
            ranker=_fake_ranker,
        )
        assert sum(p.monthly_amount for p in plan.picks) == pytest.approx(4000.0)
        assert not any(p.asset_class == "gold" for p in plan.picks)

        move = next(m for m in plan.reallocations if m.asset_class == "gold")
        assert move.amount == pytest.approx(400.0)
        assert sum(move.moved_to.values()) == pytest.approx(400.0)

    def test_the_survivors_keep_their_weights_relative_to_each_other(self):
        """65/25 stays 65/25 after gold leaves, rather than drifting toward
        whichever sleeve happened to be bigger."""
        plan = build_fund_plan(
            {"equity": 65.0, "debt": 25.0, "gold": 10.0},
            monthly_sip=4000.0,
            ranker=_fake_ranker,
        )
        assert plan.actual_mix["equity"] == pytest.approx(65 / 90 * 100, abs=0.2)
        assert plan.actual_mix["debt"] == pytest.approx(25 / 90 * 100, abs=0.2)

    def test_the_departure_from_target_is_reported_not_hidden(self):
        plan = build_fund_plan(
            {"equity": 65.0, "debt": 25.0, "gold": 10.0},
            monthly_sip=4000.0,
            ranker=_fake_ranker,
        )
        assert plan.reallocations
        assert "gold" in plan.skipped[0].reason
        assert "differs from the target" in plan.reallocations[0].note

    def test_dropping_one_sleeve_rescues_another_that_was_also_too_small(self):
        """The reason the repair is a loop and not a filter.

        On a ₹6,000 SIP this mix asks for ₹360 of gold and ₹480 of debt, and
        both are under the ₹500 line. Judged once, both would be dropped and
        the plan would be equity-only. Dropping gold first lifts debt to ₹511,
        which is placeable — so debt survives and the goal keeps the ballast it
        was allocated.
        """
        plan = build_fund_plan(
            {"equity": 86.0, "debt": 8.0, "gold": 6.0},
            monthly_sip=6000.0,
            ranker=_fake_ranker,
        )
        classes = {p.asset_class for p in plan.picks}
        assert "gold" not in classes
        assert "debt" in classes

        debt = sum(p.monthly_amount for p in plan.picks if p.asset_class == "debt")
        assert debt >= MIN_MONTHLY_SIP
        assert debt == pytest.approx(6000 * 8 / 94, abs=1)
        assert [m.asset_class for m in plan.reallocations] == ["gold"]
        assert sum(p.monthly_amount for p in plan.picks) == pytest.approx(6000.0)

    def test_a_mix_that_all_fits_is_left_exactly_alone(self):
        plan = build_fund_plan(
            {"equity": 65.0, "debt": 25.0, "gold": 10.0},
            monthly_sip=20000.0,
            ranker=_fake_ranker,
        )
        assert plan.reallocations == []
        assert plan.actual_mix["equity"] == pytest.approx(65.0, abs=0.2)
        assert plan.actual_mix["gold"] == pytest.approx(10.0, abs=0.2)

    def test_a_sip_too_small_for_anything_says_so_rather_than_inventing_a_plan(self):
        plan = build_fund_plan(
            {"equity": 100.0}, monthly_sip=300.0, ranker=_fake_ranker
        )
        assert plan.picks == []
        assert plan.skipped
        assert "below" in plan.skipped[0].reason
