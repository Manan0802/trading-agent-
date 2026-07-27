import pytest

from app.services.advisor.fund_score import FundEvidence, WindowEvidence
from app.services.advisor.fund_verdict import build_verdict


def _ev(**kw) -> FundEvidence:
    d = dict(
        scheme_code="1",
        scheme_name="Test Flexi Cap Fund - Direct Plan - Growth",
        category="Equity Scheme - Flexi Cap Fund",
        windows={
            "3y": WindowEvidence(mean=0.192, worst=0.008, share_positive=1.0, count=1414),
            "1y": WindowEvidence(mean=0.206, worst=-0.208, share_positive=0.90, count=2291),
        },
        volatility=0.13,
        max_drawdown=-0.29,
        direct_ter=0.0063,
        regular_ter=0.0128,
        history_years=13.2,
    )
    d.update(kw)
    return FundEvidence(**d)


def test_the_headline_is_about_holding_periods_not_a_ratio():
    """A ratio is a number a user cannot act on. How often the fund actually
    made money over a real holding period is."""
    v = build_verdict(_ev(), rank=1, peers=34)
    assert "1,414" in v.headline
    assert "three-year" in v.headline.lower() or "3-year" in v.headline
    assert "sortino" not in v.headline.lower()


def test_a_fund_that_never_lost_says_so_with_the_worst_case_attached():
    v = build_verdict(_ev(), rank=1, peers=34)
    joined = " ".join([v.headline, *v.points])
    assert "0.8%" in joined


def test_a_fund_with_losing_windows_leads_with_that_not_the_average():
    v = build_verdict(
        _ev(windows={
            "3y": WindowEvidence(mean=0.219, worst=-0.088, share_positive=0.77, count=1473),
        }),
        rank=2,
        peers=34,
    )
    joined = " ".join([v.headline, *v.points])
    assert "8.8%" in joined
    assert "23%" in joined or "77%" in joined


def test_the_commission_cost_is_stated_in_rupees_not_just_percent():
    """0.65pp means nothing to most people. What it costs over their horizon does."""
    v = build_verdict(_ev(), rank=1, peers=34, monthly_sip=15000, years=15)
    joined = " ".join(v.points)
    assert "₹" in joined
    assert "0.65" in joined or "0.7" in joined


def test_no_commission_line_when_only_one_plan_is_published():
    v = build_verdict(_ev(regular_ter=None), rank=1, peers=34, monthly_sip=15000, years=15)
    assert not any("regular plan" in p.lower() for p in v.points)


def test_a_thin_record_is_disclosed_rather_than_scored_silently():
    """The user must be told when a good-looking record is only three years of
    one market, not shown a confident claim built on it."""
    v = build_verdict(
        _ev(history_years=3.2, windows={
            "3y": WindowEvidence(mean=0.21, worst=0.19, share_positive=1.0, count=9),
        }),
        rank=1,
        peers=34,
    )
    joined = " ".join([v.headline, *v.points, v.caveat or ""])
    assert "3.2" in joined or "one market" in joined.lower() or "9" in joined
    assert v.caveat


def test_a_long_record_carries_no_caveat():
    assert build_verdict(_ev(), rank=1, peers=34).caveat is None


def test_the_rank_is_stated_against_a_named_peer_group():
    v = build_verdict(_ev(), rank=3, peers=34)
    joined = " ".join([v.headline, *v.points])
    assert "3" in joined and "34" in joined
    assert "Flexi Cap" in joined


def test_every_point_carries_a_number():
    """A claim without a figure behind it is marketing."""
    v = build_verdict(_ev(), rank=1, peers=34, monthly_sip=10000, years=10)
    assert all(any(c.isdigit() for c in point) for point in v.points)


def test_nothing_is_invented_when_the_evidence_is_absent():
    bare = _ev(volatility=None, max_drawdown=None, direct_ter=None, regular_ter=None,
               windows={"3y": WindowEvidence(mean=0.15, worst=0.01, share_positive=1.0, count=500)})
    v = build_verdict(bare, rank=1, peers=10)
    assert v.headline
    assert all(p for p in v.points)


def test_the_drawdown_is_framed_as_what_the_holder_lived_through():
    v = build_verdict(_ev(), rank=1, peers=34)
    joined = " ".join(v.points)
    assert "29%" in joined
