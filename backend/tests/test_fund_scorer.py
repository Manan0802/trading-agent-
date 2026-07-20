import pytest

from app.services.advisor.fund_metrics import FundMetrics
from app.services.advisor.fund_scorer import FundForScoring, score_peer_group


def _fund(code, *, sortino, consistency, alpha, downside, cagr_3y=0.12, name=None):
    return FundForScoring(
        scheme_code=code,
        scheme_name=name or f"Fund {code}",
        category="Equity Scheme - Flexi Cap Fund",
        metrics=FundMetrics(
            cagr_3y=cagr_3y,
            sortino=sortino,
            consistency=consistency,
            alpha=alpha,
            downside_capture=downside,
        ),
    )


GOOD = _fund("A", sortino=1.4, consistency=0.93, alpha=0.07, downside=0.40, name="Strong Fund")
MIDDLING = _fund("B", sortino=0.9, consistency=0.60, alpha=0.02, downside=0.85)
WEAK = _fund("C", sortino=0.4, consistency=0.20, alpha=-0.03, downside=1.30, name="Weak Fund")


def test_better_funds_rank_higher():
    ranked = score_peer_group([WEAK, GOOD, MIDDLING]).ranked
    assert [f.scheme_code for f in ranked] == ["A", "B", "C"]
    assert ranked[0].score > ranked[-1].score


def test_scores_stay_within_zero_to_hundred():
    for f in score_peer_group([WEAK, GOOD, MIDDLING]).ranked:
        assert 0 <= f.score <= 100


def test_lower_downside_capture_scores_better():
    """Downside capture is the one metric where smaller is better."""
    protective = _fund("P", sortino=1.0, consistency=0.5, alpha=0.0, downside=0.4)
    fragile = _fund("F", sortino=1.0, consistency=0.5, alpha=0.0, downside=1.4)

    ranked = score_peer_group([fragile, protective]).ranked
    assert ranked[0].scheme_code == "P"
    assert ranked[0].breakdown["downside_capture"] > ranked[1].breakdown["downside_capture"]


def test_breakdown_explains_where_the_score_came_from():
    result = score_peer_group([WEAK, GOOD, MIDDLING])
    best = result.ranked[0]
    assert set(best.breakdown) == {"sortino", "consistency", "alpha", "downside_capture"}
    # Contributions sum to the score, so a recommendation can always be justified.
    assert sum(best.breakdown.values()) == pytest.approx(best.score)


def test_weights_are_applied_in_the_researched_proportions():
    result = score_peer_group([WEAK, GOOD, MIDDLING])
    best = result.ranked[0]  # top percentile on every metric
    # Sortino carries the most weight, then consistency, then the two
    # benchmark-relative measures equally.
    assert best.breakdown["sortino"] > best.breakdown["consistency"]
    assert best.breakdown["consistency"] > best.breakdown["alpha"]
    assert best.breakdown["alpha"] == pytest.approx(best.breakdown["downside_capture"])


def test_funds_without_enough_history_are_excluded_not_guessed_at():
    newborn = FundForScoring(
        scheme_code="NEW",
        scheme_name="Just Launched Fund",
        category="Equity Scheme - Flexi Cap Fund",
        metrics=FundMetrics(cagr_1y=0.30),  # nothing longer-term yet
    )
    result = score_peer_group([GOOD, MIDDLING, newborn])

    assert [f.scheme_code for f in result.ranked] == ["A", "B"]
    assert [f.scheme_code for f in result.unscorable] == ["NEW"]
    assert "history" in result.unscorable[0].reason.lower()


def test_a_metric_missing_across_the_whole_group_is_dropped_from_the_weighting():
    """Without a benchmark there is no alpha or downside capture, so the
    remaining metrics must carry the full weight rather than the score
    silently topping out below 100."""
    a = _fund("A", sortino=1.4, consistency=0.9, alpha=None, downside=None)
    b = _fund("B", sortino=0.5, consistency=0.3, alpha=None, downside=None)

    result = score_peer_group([a, b])
    best = result.ranked[0]

    assert set(best.breakdown) == {"sortino", "consistency"}
    assert best.score == pytest.approx(100.0)


def test_single_fund_gets_a_neutral_score_rather_than_a_meaningless_rank():
    result = score_peer_group([GOOD])
    assert result.ranked[0].score == pytest.approx(50.0)


def test_empty_group_is_handled():
    result = score_peer_group([])
    assert result.ranked == [] and result.unscorable == []


def test_identical_funds_score_identically():
    twin_a = _fund("A", sortino=1.0, consistency=0.5, alpha=0.01, downside=0.9)
    twin_b = _fund("B", sortino=1.0, consistency=0.5, alpha=0.01, downside=0.9)
    ranked = score_peer_group([twin_a, twin_b]).ranked
    assert ranked[0].score == pytest.approx(ranked[1].score)
