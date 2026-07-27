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
