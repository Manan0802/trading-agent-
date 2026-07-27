import pytest

from app.services.advisor.peer_normalise import PeerScale, hybrid


def test_pure_rank_ignores_how_far_ahead_the_leader_is():
    """The failure mode we are fixing: percentile rank alone scores a fund that
    wins by 0.1pp exactly like one that wins by 8pp."""
    narrow = hybrid([0.10, 0.101], w_rank=1.0)
    wide = hybrid([0.10, 0.18], w_rank=1.0)
    assert narrow == wide


def test_the_magnitude_component_separates_them():
    narrow = hybrid([0.10, 0.101, 0.102], w_rank=0.7)
    wide = hybrid([0.10, 0.101, 0.180], w_rank=0.7)
    # Same ranks, but the runaway leader should pull further clear.
    assert wide[2] - wide[1] > narrow[2] - narrow[1]


def test_output_is_bounded():
    scores = hybrid([0.02, 0.11, 0.4, -0.3, 0.09], w_rank=0.7)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_a_single_outlier_cannot_squash_everyone_else():
    """Raw min-max hands the whole scale to the extremes: one fund returning
    300% would compress every ordinary fund into the bottom of the range.
    Scaling between the 10th and 90th percentile is what stops that."""
    peers = [0.10 + 0.004 * i for i in range(25)]  # a realistic category
    ordinary = hybrid(peers, w_rank=0.7)
    with_outlier = hybrid(peers + [3.0], w_rank=0.7)
    mid = len(peers) // 2
    # The middle fund's score must barely move when one freak fund joins.
    assert abs(with_outlier[mid] - ordinary[mid]) < 0.05


def test_identical_values_all_score_the_same():
    scores = hybrid([0.12, 0.12, 0.12], w_rank=0.7)
    assert scores[0] == scores[1] == scores[2]


def test_a_single_fund_peer_group_is_neutral_not_perfect():
    """Ranking one fund against itself proves nothing, so it must not score 1.0."""
    assert hybrid([0.15], w_rank=0.7) == [0.5]


def test_ordering_is_always_preserved():
    values = [0.03, -0.11, 0.27, 0.09, 0.09, 0.5]
    scores = hybrid(values, w_rank=0.7)
    pairs = sorted(zip(values, scores))
    assert all(a[1] <= b[1] for a, b in zip(pairs, pairs[1:]))


def test_lower_is_better_inverts_the_scale():
    """Expense ratio and downside capture are better when small."""
    scores = hybrid([0.005, 0.02], w_rank=0.7, lower_is_better=True)
    assert scores[0] > scores[1]


def test_none_values_are_excluded_from_the_scale_not_treated_as_zero():
    """A fund missing a metric must not drag the peer distribution down."""
    with_gap = hybrid([0.10, None, 0.20], w_rank=0.7)
    without = hybrid([0.10, 0.20], w_rank=0.7)
    assert with_gap[1] is None
    assert with_gap[0] == pytest.approx(without[0])
    assert with_gap[2] == pytest.approx(without[1])


def test_an_all_missing_metric_yields_all_none():
    assert hybrid([None, None], w_rank=0.7) == [None, None]


# --- out-of-sample scaling ---------------------------------------------------


def test_a_fund_scored_against_a_reference_does_not_shift_it():
    """Showing a score for a fund the user holds must not move the percentiles
    of the funds we are ranking for a recommendation."""
    peers = [0.08, 0.12, 0.16, 0.20]
    scale = PeerScale.fit(peers, w_rank=0.7)
    before = [scale.score(v) for v in peers]
    scale.score(9.99)  # an extreme outsider
    assert [scale.score(v) for v in peers] == before


def test_out_of_sample_matches_in_sample_for_a_member_of_the_group():
    peers = [0.08, 0.12, 0.16, 0.20]
    scale = PeerScale.fit(peers, w_rank=0.7)
    in_sample = hybrid(peers, w_rank=0.7)
    assert scale.score(0.16) == pytest.approx(in_sample[2], abs=0.02)


def test_a_value_beyond_the_reference_range_is_clamped_not_extrapolated():
    scale = PeerScale.fit([0.08, 0.12, 0.16], w_rank=0.7)
    assert 0.0 <= scale.score(50.0) <= 1.0
    assert 0.0 <= scale.score(-50.0) <= 1.0


def test_fitting_on_an_empty_reference_scores_everything_neutral():
    scale = PeerScale.fit([], w_rank=0.7)
    assert scale.score(0.13) == 0.5
