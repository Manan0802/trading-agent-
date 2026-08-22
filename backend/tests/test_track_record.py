"""How often this app's own claims have been right.

The thing no Indian investing app publishes about itself. These tests are
mostly about it staying honest when the honest answer is unflattering.
"""

import pytest

from app.services.advisor import track_record as tr
from app.services.screener import plain_words as pw


def test_every_claim_carries_the_sample_it_rests_on():
    """A hit rate without a denominator is the same trick as a testimonial."""
    for claim in tr.load().claims:
        assert claim.windows.median >= 40, claim.key
        assert 0 <= claim.wins.median <= claim.windows.median, claim.key


def test_the_denominator_reaches_the_sentence_not_just_the_data():
    """Holding it in the payload is not the feature — a reader seeing "worked 83
    times in 100" with no sample cannot tell it from a testimonial. Univest's
    "Price moved −196.70 since then" is exactly that: one call, no denominator.

    This is asserted on the rendered sentence because the data-level check above
    passes happily while the sentence drops it."""
    import re

    for claim in tr.load().claims:
        said = pw.track_record_sentence(claim)
        wins, windows = round(claim.wins.median), round(claim.windows.median)
        assert re.search(rf"\b{wins}\b of \b{windows}\b", said), (
            f"{claim.key}: sentence gives no sample — {said}"
        )


def test_cost_beats_past_returns_which_is_the_whole_product_thesis():
    record = tr.load()
    cost, past = record.claim("cost"), record.claim("past_3y")
    assert cost.rank_ic.median > past.rank_ic.median
    assert cost.hit_rate > past.hit_rate


def test_past_returns_are_reported_as_a_coin_flip_rather_than_rounded_up():
    claim = tr.load().claim("past_3y")
    assert not claim.beats_chance
    said = pw.track_record_sentence(claim)
    assert "coin flip" in said
    assert "round it up" in said


def test_the_shipped_score_is_not_flattered():
    """Our composite works in 61% of stretches; cost alone in 83%. Adding risk
    and consistency to cost dilutes it. That is a finding about our own product
    and it has to be able to reach the screen."""
    record = tr.load()
    shipped, cost = record.claim("shipped_score"), record.claim("cost_alone")
    said = pw.better_signal_sentence(shipped, cost)
    if cost.hit_rate > shipped.hit_rate + 0.05:
        assert said is not None, "the app is beaten by its own ingredient and says nothing"
        assert "dilute" in said
    else:
        assert said is None, "it claimed a gap that is not there"


def test_no_sentence_is_produced_when_there_is_no_gap_to_report():
    record = tr.load()
    shipped = record.claim("shipped_score")
    assert pw.better_signal_sentence(shipped, shipped) is None


def test_a_missing_claim_produces_no_sentence_rather_than_a_crash():
    assert pw.track_record_sentence(None) is None
    assert tr.load().claim("nonsense") is None


def test_the_figures_are_ranges_because_they_move_between_runs():
    """A single number would be a lie of precision: five runs of the identical
    script gave 37, 35, 36, 35 and 35 windows out of 44."""
    record = tr.load()
    assert record.runs >= 2
    assert any(c.wins.moves or c.rank_ic and c.rank_ic.moves for c in record.claims), (
        "nothing moved across runs — either the runs are identical or only one ran"
    )
    for claim in record.claims:
        assert claim.wins.low <= claim.wins.median <= claim.wins.high, claim.key


def test_the_caveat_says_when_and_why_it_moves():
    said = pw.track_record_caveat(tr.load())
    assert tr.load().measured_on in said
    assert "downloads succeed" in said
    assert "copying an old result" in said


def test_the_best_signal_we_have_found_is_cost():
    """If this ever changes, the product's premise changed and somebody should
    have to notice."""
    assert tr.load().best.key == "cost"


def test_no_sentence_uses_jargon():
    banned = ("rank ic", "spearman", "quartile", "correlation", "p-value", "t-stat")
    record = tr.load()
    for claim in record.claims:
        said = (pw.track_record_sentence(claim) or "").lower()
        assert not any(word in said for word in banned), said
