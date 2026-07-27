import pytest

from app.services.advisor.fund_score import (
    PILLAR_WEIGHTS,
    FundEvidence,
    WindowEvidence,
    score_peer_group_v2,
)


def _evidence(
    code: str,
    *,
    r3y=0.15,
    r1y=0.18,
    worst3y=0.02,
    positive3y=1.0,
    vol=0.14,
    dd=-0.20,
    ter=0.008,
) -> FundEvidence:
    return FundEvidence(
        scheme_code=code,
        scheme_name=f"Fund {code}",
        category="Equity Scheme - Flexi Cap Fund",
        windows={
            "3y": WindowEvidence(mean=r3y, worst=worst3y, share_positive=positive3y, count=800),
            "1y": WindowEvidence(mean=r1y, worst=-0.10, share_positive=0.9, count=1500),
        },
        volatility=vol,
        max_drawdown=dd,
        direct_ter=ter,
    )


def test_the_weights_are_declared_and_sum_to_one():
    assert sum(PILLAR_WEIGHTS.values()) == pytest.approx(1.0)


def test_expense_ratio_is_a_real_term_not_a_tiebreak():
    """The one input with replicated predictive power. Bachatt syncs it and
    never scores on it; that is the gap we are closing."""
    assert PILLAR_WEIGHTS["cost"] >= 0.15


def test_a_cheaper_fund_beats_an_identical_expensive_one():
    result = score_peer_group_v2([
        _evidence("cheap", ter=0.004),
        _evidence("dear", ter=0.021),
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["cheap"].score > by_code["dear"].score


def test_a_fund_that_never_lost_over_three_years_beats_a_higher_returning_one_that_did():
    """PPFAS versus quant on real data: quant returns more on average and has
    lost 8.8% annualised over some three-year stretches. A goal-based investor
    is not indifferent between those."""
    result = score_peer_group_v2([
        _evidence("steady", r3y=0.19, worst3y=0.008, positive3y=1.0, vol=0.12),
        _evidence("swingy", r3y=0.22, worst3y=-0.088, positive3y=0.85, vol=0.22),
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["steady"].score > by_code["swingy"].score


def test_scores_span_zero_to_one_hundred():
    peers = [_evidence(str(i), r3y=0.05 + i * 0.01, ter=0.02 - i * 0.001) for i in range(12)]
    result = score_peer_group_v2(peers)
    assert result.ranked[0].score <= 100.0
    assert result.ranked[-1].score >= 0.0


def test_ranking_is_deterministic_across_runs():
    peers = [_evidence(str(i), r3y=0.10 + i * 0.005) for i in range(8)]
    first = [f.scheme_code for f in score_peer_group_v2(peers).ranked]
    second = [f.scheme_code for f in score_peer_group_v2(list(reversed(peers))).ranked]
    assert first == second


def test_a_fund_without_a_three_year_window_is_set_aside_not_guessed():
    """A one-year-old fund cannot be ranked against ten-year records. Scoring
    it on partial evidence would put it top of a list it does not belong in."""
    young = _evidence("young")
    young = FundEvidence(**{**young.__dict__, "windows": {"1y": young.windows["1y"]}})
    result = score_peer_group_v2([young, _evidence("old"), _evidence("older")])
    assert [f.scheme_code for f in result.ranked] == ["old", "older"] or [
        f.scheme_code for f in result.ranked
    ] == ["older", "old"]
    assert [f.scheme_code for f in result.unscorable] == ["young"]
    assert "3y" in result.unscorable[0].reason


def test_a_missing_expense_ratio_does_not_punish_the_fund():
    """AMFI's TER filing does not cover every scheme. A gap in our data is not
    evidence against the fund, so it is scored neutral on cost, neither
    rewarded nor penalised for what we could not measure."""
    peers = [_evidence("a", ter=0.005), _evidence("b", ter=0.005), _evidence("c", ter=None)]
    result = score_peer_group_v2(peers)
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["c"].breakdown["cost"] == pytest.approx(0.5)
    assert by_code["c"].score < by_code["a"].score


def test_the_breakdown_explains_every_pillar_that_counted():
    result = score_peer_group_v2([_evidence("a"), _evidence("b", r3y=0.09)])
    breakdown = result.ranked[0].breakdown
    assert set(breakdown) <= set(PILLAR_WEIGHTS)
    assert breakdown
    assert all(0.0 <= v <= 1.0 for v in breakdown.values())


def test_a_single_fund_peer_group_is_reported_as_unrankable():
    """One fund ranked against itself is not a ranking, and presenting it as
    100 out of 100 would be a lie."""
    result = score_peer_group_v2([_evidence("only")])
    assert not result.ranked
    assert result.unscorable[0].scheme_code == "only"


def test_an_empty_peer_group_returns_empty():
    result = score_peer_group_v2([])
    assert result.ranked == [] and result.unscorable == []


# --- evidence strength -------------------------------------------------------


def _with_span(code: str, span_years: float, **kw) -> FundEvidence:
    base = _evidence(code, **kw)
    return FundEvidence(**{**base.__dict__, "history_years": span_years})


def test_a_short_lived_fund_cannot_claim_it_never_lost_money():
    """A fund three years old has seen one market. Its nine near-identical
    overlapping windows are not evidence that it survives bad ones, and
    crediting them equally puts a bull-run debutant above a fund that has been
    through 2018 and 2020."""
    # Returns held equal so this isolates the consistency claim.
    result = score_peer_group_v2([
        _with_span("young", 3.1, worst3y=0.19, positive3y=1.0, r3y=0.19),
        _with_span("seasoned", 13.5, worst3y=0.008, positive3y=1.0, r3y=0.19),
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["seasoned"].score > by_code["young"].score


def test_a_long_record_is_trusted_at_face_value():
    long_run = _with_span("long", 12.0, worst3y=0.05, positive3y=1.0)
    short_run = _with_span("short", 3.2, worst3y=0.05, positive3y=1.0)
    result = score_peer_group_v2([long_run, short_run, _with_span("other", 12.0, worst3y=-0.05)])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["long"].breakdown["consistency"] > by_code["short"].breakdown["consistency"]


def test_a_thin_record_is_pulled_toward_neutral_not_toward_zero():
    """Absence of evidence is not evidence of a bad fund. A short record should
    stop the fund making a strong claim, not brand it as poor."""
    result = score_peer_group_v2([
        _with_span("young_good", 3.1, worst3y=0.19, positive3y=1.0),
        _with_span("old_bad", 13.0, worst3y=-0.30, positive3y=0.4),
        _with_span("old_good", 13.0, worst3y=0.05, positive3y=1.0),
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["young_good"].score > by_code["old_bad"].score


def test_evidence_strength_is_reported_so_the_discount_is_visible():
    result = score_peer_group_v2([
        _with_span("a", 3.1), _with_span("b", 13.0),
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["a"].evidence_strength < by_code["b"].evidence_strength
    assert 0.0 <= by_code["a"].evidence_strength <= 1.0


# --- the weights are set by evidence, not taste -------------------------------


def test_cost_is_the_heaviest_pillar_because_it_is_the_only_one_that_predicts():
    """Measured over 52 three-year windows: the cheapest quartile returned
    20.0% against 17.8% for the dearest, winning 45 of them. Past returns, on
    the same test, were a coin flip with the sign wrong."""
    assert PILLAR_WEIGHTS["cost"] == max(PILLAR_WEIGHTS.values())
    assert PILLAR_WEIGHTS["cost"] >= 0.5


def test_past_return_is_not_a_ranking_input():
    """It was tested directly and failed directly. It is still reported on
    every fund; it just does not move one up the list."""
    assert "return" not in PILLAR_WEIGHTS


def test_two_funds_with_the_same_cost_and_risk_are_not_separated_by_returns():
    result = score_peer_group_v2([
        _evidence("mediocre", r3y=0.09, r1y=0.09),
        _evidence("stellar", r3y=0.31, r1y=0.31),
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["mediocre"].score == pytest.approx(by_code["stellar"].score)


def test_a_fund_with_no_published_cost_cannot_outrank_a_cheap_one():
    """Dropping a missing pillar and reweighting the rest was fine when cost
    was a fifth of the score. Now that it is the majority and the only pillar
    that predicts, dropping it would score a fund purely on inputs we know do
    not predict, and let it climb above funds we can actually measure."""
    result = score_peer_group_v2([
        _evidence("cheap", ter=0.004),
        _evidence("unknown", ter=None),
        _evidence("dear", ter=0.022),
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["cheap"].score > by_code["unknown"].score
    assert by_code["unknown"].score > by_code["dear"].score


def test_an_unpriced_fund_is_scored_neutral_on_cost_rather_than_exempted():
    result = score_peer_group_v2([
        _evidence("a", ter=0.004), _evidence("b", ter=0.02), _evidence("c", ter=None)
    ])
    by_code = {f.scheme_code: f for f in result.ranked}
    assert by_code["c"].breakdown["cost"] == pytest.approx(0.5)
