import pytest

from app.services.advisor.fund_metrics import FundMetrics
from app.services.advisor.fund_recommender import recommend_for_allocation
from app.services.advisor.fund_scorer import FundForScoring, ScoringResult, score_peer_group


def _fund(code, name, category, *, sortino, consistency, alpha, downside):
    return FundForScoring(
        scheme_code=code,
        scheme_name=name,
        category=category,
        metrics=FundMetrics(
            cagr_3y=0.14,
            sortino=sortino,
            consistency=consistency,
            alpha=alpha,
            downside_capture=downside,
        ),
    )


FAKE_UNIVERSE = {
    "equity": [
        _fund("E1", "Best Equity Fund", "Flexi Cap", sortino=1.5, consistency=0.9, alpha=0.07, downside=0.4),
        _fund("E2", "Second Equity Fund", "Flexi Cap", sortino=1.2, consistency=0.7, alpha=0.04, downside=0.7),
        _fund("E3", "Third Equity Fund", "Flexi Cap", sortino=0.8, consistency=0.5, alpha=0.01, downside=0.9),
    ],
    "debt": [
        _fund("D1", "Best Debt Fund", "Corporate Bond", sortino=1.1, consistency=0.8, alpha=0.02, downside=0.3),
        _fund("D2", "Second Debt Fund", "Corporate Bond", sortino=0.7, consistency=0.4, alpha=0.00, downside=0.6),
    ],
    "gold": [
        _fund("G1", "Best Gold Fund", "FoF Domestic", sortino=0.9, consistency=0.6, alpha=0.01, downside=0.5),
        _fund("G2", "Second Gold Fund", "FoF Domestic", sortino=0.6, consistency=0.3, alpha=0.00, downside=0.8),
    ],
}


def fake_scorer(asset_class: str) -> ScoringResult:
    return score_peer_group(FAKE_UNIVERSE[asset_class])


ALLOCATION = {"equity": 65, "debt": 25, "gold": 10}


def test_recommends_specific_funds_not_just_percentages():
    recs = recommend_for_allocation(ALLOCATION, monthly_sip=20000, scorer=fake_scorer)
    assert all(r.scheme_name and r.scheme_code for r in recs)
    assert {r.asset_class for r in recs} == {"equity", "debt", "gold"}


def test_amounts_follow_the_allocation_and_add_up_to_the_sip():
    recs = recommend_for_allocation(ALLOCATION, monthly_sip=20000, scorer=fake_scorer)

    by_class: dict[str, float] = {}
    for r in recs:
        by_class[r.asset_class] = by_class.get(r.asset_class, 0) + r.monthly_amount

    assert by_class["equity"] == pytest.approx(13000)
    assert by_class["debt"] == pytest.approx(5000)
    assert by_class["gold"] == pytest.approx(2000)
    assert sum(r.monthly_amount for r in recs) == pytest.approx(20000)


def test_spreads_across_a_small_basket_rather_than_one_fund():
    recs = recommend_for_allocation(
        ALLOCATION, monthly_sip=20000, funds_per_class=2, scorer=fake_scorer
    )
    equity = [r for r in recs if r.asset_class == "equity"]
    assert len(equity) == 2
    assert {r.scheme_code for r in equity} == {"E1", "E2"}  # the two best


def test_the_highest_scoring_fund_gets_the_larger_share():
    recs = recommend_for_allocation(
        ALLOCATION, monthly_sip=20000, funds_per_class=2, scorer=fake_scorer
    )
    equity = sorted(
        [r for r in recs if r.asset_class == "equity"], key=lambda r: -r.score
    )
    assert equity[0].scheme_code == "E1"
    assert equity[0].monthly_amount >= equity[1].monthly_amount


def test_every_recommendation_explains_itself():
    recs = recommend_for_allocation(ALLOCATION, monthly_sip=20000, scorer=fake_scorer)
    top = max(recs, key=lambda r: r.score)
    assert "1 of 3" in top.rationale  # rank within its peer group
    assert "%" in top.rationale  # a concrete figure, not vague praise


def test_small_sip_falls_back_to_one_fund_per_class_instead_of_unusable_amounts():
    """Splitting a 1,000 SIP three ways then halving each leaves amounts below
    any fund's minimum, so the basket narrows rather than recommending
    something that cannot actually be bought."""
    recs = recommend_for_allocation(
        {"equity": 65, "debt": 25, "gold": 10},
        monthly_sip=1000,
        funds_per_class=2,
        scorer=fake_scorer,
    )
    equity = [r for r in recs if r.asset_class == "equity"]
    assert len(equity) == 1
    assert equity[0].monthly_amount == pytest.approx(650)


def test_an_asset_class_too_small_to_invest_is_dropped_with_a_note():
    result = recommend_for_allocation(
        {"equity": 98, "debt": 1, "gold": 1},
        monthly_sip=10000,
        scorer=fake_scorer,
        return_skipped=True,
    )
    assert all(r.asset_class == "equity" for r in result.recommendations)
    assert {s.asset_class for s in result.skipped} == {"debt", "gold"}
    assert "minimum" in result.skipped[0].reason.lower()


def test_zero_allocation_classes_are_ignored():
    recs = recommend_for_allocation(
        {"equity": 100, "debt": 0, "gold": 0}, monthly_sip=20000, scorer=fake_scorer
    )
    assert {r.asset_class for r in recs} == {"equity"}
    assert sum(r.monthly_amount for r in recs) == pytest.approx(20000)
