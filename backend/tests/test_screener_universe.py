"""Every edge case the universe scorer can meet, and the invariants that must never break.

The scoring arithmetic is proved against upstream in `test_scoring_parity.py`.
This file proves the layer around it: who gets scored, who gets refused and
why, how peer groups are cut, and the properties that must hold for *any*
input rather than the handful we happened to think of.

The order matters here as much as the maths. Grades are percentiles of the
score, so scoring must finish first; risk tiers need momentum and drawdown,
which only exist after scoring. A test for each.
"""

import math

import numpy as np
import pytest

from app.services.screener import universe as u


def fund(code="F1", category="Equity Scheme", sub_category="Flexi Cap Fund", **kw):
    """A scoreable fund. Override any field to make it interesting."""
    base = dict(
        code=code, category=category, sub_category=sub_category,
        roll1y=14.0, roll6m=9.0, roll3m=5.0, roll1m=1.5,
        ret3y=16.0, ret1y=13.0, ret3m=4.0, vol=11.0, sortino=1.4,
        momentum=0.30, drawdown=0.10, nav_fresh=True,
    )
    base.update(kw)
    return u.FundInputs(**base)


def peers(n, prefix="F", **kw):
    out = []
    for i in range(n):
        spec = dict(roll1y=8.0 + i, ret3y=10.0 + i, vol=8.0 + (i % 5),
                    momentum=0.2 + i / 100, drawdown=i / 200)
        spec.update(kw)                      # caller wins
        out.append(fund(code=f"{prefix}{i}", **spec))
    return out


# ─────────────────────────────────────────────────────────────────────────────
class TestSafeFloat:
    @pytest.mark.parametrize("value", [None, float("nan"), float("inf"), float("-inf"),
                                       "abc", "", [], {}, object()])
    def test_unusable_values_become_zero(self, value):
        assert u.safe_float(value) == 0.0

    @pytest.mark.parametrize("value,expected", [(3, 3.0), (2.5, 2.5), ("4.25", 4.25),
                                                (-1.5, -1.5), (0, 0.0), (True, 1.0)])
    def test_usable_values_pass_through(self, value, expected):
        assert u.safe_float(value) == expected


# ─────────────────────────────────────────────────────────────────────────────
class TestEligibility:
    def test_a_normal_fund_is_scoreable(self):
        ok, why = u.is_scoreable(fund())
        assert ok and why == ""

    @pytest.mark.parametrize("category", [None, ""])
    def test_missing_category_is_refused(self, category):
        ok, why = u.is_scoreable(fund(category=category))
        assert not ok and "category" in why

    @pytest.mark.parametrize("category", sorted(u.EXCLUDED_CATEGORIES))
    def test_every_excluded_category_is_refused(self, category):
        ok, why = u.is_scoreable(fund(category=category))
        assert not ok and "not an investable SEBI category" in why

    def test_missing_rolling_1y_is_refused(self):
        ok, why = u.is_scoreable(fund(roll1y=None))
        assert not ok and "1-year rolling return" in why

    @pytest.mark.parametrize("value", [0, 0.0, float("nan"), "nonsense"])
    def test_zero_or_unusable_rolling_1y_is_refused(self, value):
        """A fund younger than a year cannot form a 1y window; upstream treats
        both null and zero as 'no full year'."""
        ok, why = u.is_scoreable(fund(roll1y=value))
        assert not ok

    def test_a_dead_fund_is_refused(self):
        ok, why = u.is_scoreable(fund(nav_fresh=False))
        assert not ok and "wound up" in why


# ─────────────────────────────────────────────────────────────────────────────
class TestScoreUniverse:
    def test_empty_universe_scores_nobody_and_says_why(self):
        scored, unscorable = u.score_universe([], [fund()])
        assert scored == []
        assert len(unscorable) == 1 and "no eligible peer group" in unscorable[0].reason

    def test_a_single_fund_still_scores(self):
        scored, unscorable = u.score_universe([fund()])
        assert len(scored) == 1 and unscorable == []
        assert 0.0 <= scored[0].score <= 1.0

    @pytest.mark.parametrize("missing", ["momentum", "drawdown"])
    def test_no_nav_history_is_unscorable_not_zero(self, missing):
        """The failure mode that matters: a fund with no history must be named,
        never handed a zero that sorts it to the bottom as if measured."""
        group = peers(5) + [fund(code="THIN", **{missing: None})]
        scored, unscorable = u.score_universe(group)
        assert "THIN" not in {f.code for f in scored}
        assert [x.reason for x in unscorable if x.code == "THIN"] == [
            "not enough NAV history to score"
        ]

    def test_out_of_sample_funds_do_not_move_in_sample_scores(self):
        """The whole reason the OOS path exists. Displaying an extra fund must
        not change anybody else's rank."""
        eligible = peers(20)
        alone, _ = u.score_universe(eligible)
        with_extras, _ = u.score_universe(eligible, others=peers(6, prefix="X", ret3y=900.0))
        alone_by_code = {f.code: f.score for f in alone}
        for f in with_extras:
            if f.in_sample:
                assert f.score == alone_by_code[f.code]

    def test_out_of_sample_funds_are_marked_as_such(self):
        scored, _ = u.score_universe(peers(10), others=peers(3, prefix="X"))
        assert {f.in_sample for f in scored if f.code.startswith("F")} == {True}
        assert {f.in_sample for f in scored if f.code.startswith("X")} == {False}

    def test_every_input_is_accounted_for(self):
        group = peers(12) + [fund(code="THIN", momentum=None)]
        scored, unscorable = u.score_universe(group)
        assert len(scored) + len(unscorable) == len(group)
        assert {f.code for f in scored} | {x.code for x in unscorable} == {f.code for f in group}

    def test_scores_are_rounded_the_way_upstream_writes_them(self):
        scored, _ = u.score_universe(peers(8))
        for f in scored:
            assert f.score == round(f.score, u.SCORE_DECIMALS)
            assert f.momentum == round(f.momentum, u.SCORE_DECIMALS)


# ─────────────────────────────────────────────────────────────────────────────
class TestGrading:
    def test_a_group_of_one_is_left_ungraded(self):
        scored, _ = u.score_universe([fund(code="ONLY")])
        graded = u.grade_universe(scored)
        assert graded[0].grade is None and graded[0].peer_size == 1

    def test_a_group_of_two_is_graded(self):
        scored, _ = u.score_universe(peers(2))
        graded = u.grade_universe(scored)
        assert all(f.grade in {"Very Good", "Good", "Avg", "Bad"} for f in graded)

    def test_debt_grades_within_sub_category_equity_does_not(self):
        debt = ([fund(code=f"L{i}", category="Debt Scheme", sub_category="Liquid Fund",
                      roll1y=6 + i * 0.1) for i in range(4)]
                + [fund(code=f"C{i}", category="Debt Scheme", sub_category="Credit Risk Fund",
                        roll1y=9 + i) for i in range(4)])
        scored, _ = u.score_universe(debt)
        graded = {f.code: f for f in u.grade_universe(scored)}
        assert graded["L0"].peer_size == 4, "Liquid must be graded against Liquid only"
        assert graded["C0"].peer_size == 4

        equity = ([fund(code=f"A{i}", sub_category="Flexi Cap Fund", roll1y=10 + i) for i in range(3)]
                  + [fund(code=f"B{i}", sub_category="Small Cap Fund", roll1y=14 + i) for i in range(3)])
        scored, _ = u.score_universe(equity)
        graded = {f.code: f for f in u.grade_universe(scored)}
        assert graded["A0"].peer_size == 6, "Equity grades across the whole category"

    def test_identical_scores_get_identical_grades(self):
        """Value-based cutoffs, not rank position -- ties must never split."""
        group = [fund(code=f"S{i}") for i in range(9)]   # every field identical
        graded = u.grade_universe(u.score_universe(group)[0])
        assert len({f.grade for f in graded}) == 1

    def test_input_order_is_preserved(self):
        group = peers(15)
        graded = u.grade_universe(u.score_universe(group)[0])
        assert [f.code for f in graded] == [f"F{i}" for i in range(15)]

    def test_peer_median_never_zero(self):
        """It is used as a denominator downstream."""
        graded = u.grade_universe(u.score_universe(peers(6))[0])
        assert all(f.peer_median is None or f.peer_median >= u.MIN_PEER_MEDIAN
                   for f in graded)

    def test_close_scores_are_never_more_than_one_grade_apart(self):
        """What the minimum-gap floor actually buys.

        My first version of this test asserted that near-identical *inputs*
        produce near-identical grades. That is false and worth recording: rank
        normalisation spreads any set of distinct values across the full 0..1
        range, so inputs a millionth apart still produce well-separated scores.
        The floor is about clustered SCORES -- and what it guarantees is that
        two funds within MIN_GRADE_CUTOFF_GAP of each other can straddle at
        most one band boundary, never land in distant grades.
        """
        order = ["Bad", "Avg", "Good", "Very Good"]
        for group in (peers(40), peers(12), [fund(code=f"D{i}", category="Debt Scheme",
                                                  sub_category="Liquid Fund",
                                                  roll1y=6.0 + i * 0.01) for i in range(30)]):
            graded = [f for f in u.grade_universe(u.score_universe(group)[0])
                      if f.grade is not None]
            for a in graded:
                for b in graded:
                    if abs(a.score - b.score) <= u.scoring.MIN_GRADE_CUTOFF_GAP:
                        assert abs(order.index(a.grade) - order.index(b.grade)) <= 1, (
                            f"{a.code}({a.score},{a.grade}) vs {b.code}({b.score},{b.grade})"
                        )


# ─────────────────────────────────────────────────────────────────────────────
class TestRiskTiers:
    def test_tiers_are_assigned_across_the_whole_universe(self):
        group = peers(30)
        scored, _ = u.score_universe(group)
        tiered = u.assign_risk_tiers(scored, group)
        assert all(f.risk_tier in u.scoring.RISK_TIERS for f in tiered)

    def test_a_fund_missing_inputs_gets_no_tier_rather_than_a_wrong_one(self):
        group = peers(10) + [fund(code="NOVOL", vol=None, sortino=None)]
        scored, _ = u.score_universe(group)
        tiered = {f.code: f for f in u.assign_risk_tiers(scored, group)}
        assert tiered["NOVOL"].risk_tier is None
        assert tiered["F0"].risk_tier is not None

    def test_riskier_funds_land_in_higher_tiers(self):
        """The reason this exists at all -- SEBI's riskometer cannot separate these."""
        calm = [fund(code=f"C{i}", vol=2.0 + i * 0.1, drawdown=0.01, momentum=0.05,
                     sortino=4.0, roll1y=6 + i * 0.1) for i in range(15)]
        wild = [fund(code=f"W{i}", vol=34.0 + i, drawdown=0.55, momentum=0.62,
                     sortino=0.2, roll1y=25 + i) for i in range(15)]
        group = calm + wild
        tiered = {f.code: f for f in u.assign_risk_tiers(u.score_universe(group)[0], group)}
        order = list(u.scoring.RISK_TIERS)
        assert order.index(tiered["W0"].risk_tier) > order.index(tiered["C0"].risk_tier)

    def test_empty_input_is_returned_untouched(self):
        assert u.assign_risk_tiers([], []) == []


# ─────────────────────────────────────────────────────────────────────────────
class TestFullPipeline:
    def test_nothing_is_ever_silently_dropped(self):
        group = (peers(20)
                 + [fund(code="DEAD", nav_fresh=False)]
                 + [fund(code="JUNK", category="IDF")]
                 + [fund(code="NEW", roll1y=None)]
                 + [fund(code="THIN", momentum=None)])
        scored, unscorable = u.run(group)
        assert len(scored) + len(unscorable) == len(group)
        assert {f.code for f in scored}.isdisjoint({x.code for x in unscorable})

    def test_every_refusal_carries_a_reason(self):
        scored, unscorable = u.run([fund(code="DEAD", nav_fresh=False),
                                    fund(code="JUNK", category="IDF"), *peers(3)])
        assert all(x.reason for x in unscorable)

    def test_a_scored_fund_carries_the_whole_story(self):
        scored, _ = u.run(peers(25))
        f = scored[0]
        assert f.grade is not None and f.risk_tier is not None
        assert f.peer_median is not None and f.peer_size == 25
        assert f.quality is not None and f.momentum is not None

    def test_running_twice_gives_identical_output(self):
        group = peers(40)
        a, _ = u.run(group)
        b, _ = u.run(group)
        assert [(f.code, f.score, f.grade, f.risk_tier) for f in a] == \
               [(f.code, f.score, f.grade, f.risk_tier) for f in b]

    def test_a_universe_of_only_junk_scores_nobody(self):
        scored, unscorable = u.run([fund(code=f"J{i}", category="IDF") for i in range(5)])
        assert scored == [] and len(unscorable) == 5


# ─────────────────────────────────────────────────────────────────────────────
class TestInvariants:
    """Properties that must hold for any input, not just the cases above."""

    @pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
    def test_score_stays_inside_zero_and_one(self, seed):
        rng = np.random.default_rng(seed)
        group = [
            fund(code=f"R{i}",
                 roll1y=float(rng.normal(12, 30)) or 1.0, roll6m=float(rng.normal(8, 20)),
                 roll3m=float(rng.normal(4, 15)), roll1m=float(rng.normal(1, 8)),
                 ret3y=float(rng.normal(15, 40)), ret1y=float(rng.normal(12, 30)),
                 ret3m=float(rng.normal(4, 12)), vol=abs(float(rng.normal(14, 10))) + 0.1,
                 sortino=float(rng.normal(1.2, 3)),
                 momentum=float(rng.uniform(0, 1)), drawdown=float(rng.uniform(0, 1)))
            for i in range(50)
        ]
        for f in u.run(group)[0]:
            assert 0.0 <= f.score <= 1.0, f"{f.code} scored {f.score}"
            assert 0.0 <= f.quality <= 1.0

    def test_improving_a_fund_never_lowers_its_own_quality(self):
        group = peers(20)
        before = {f.code: f.quality for f in u.score_universe(group)[0]}
        improved = [fund(code="F7", roll1y=99.0, roll6m=60.0, roll3m=40.0, roll1m=12.0,
                         ret3y=120.0, ret1y=90.0, ret3m=30.0, vol=3.0,
                         momentum=0.27, drawdown=0.035)
                    if f.code == "F7" else f for f in group]
        after = {f.code: f.quality for f in u.score_universe(improved)[0]}
        assert after["F7"] >= before["F7"]

    def test_lower_volatility_never_hurts(self):
        """Volatility is inverted inside the risk pillar; a sign slip here would
        silently reward the riskiest fund in every category."""
        group = peers(20)
        calmer = [fund(code="F5", roll1y=13.0, ret3y=15.0, vol=0.6,
                       momentum=0.25, drawdown=0.025)
                  if f.code == "F5" else f for f in group]
        base = {f.code: f.quality for f in u.score_universe(group)[0]}["F5"]
        quiet = {f.code: f.quality for f in u.score_universe(calmer)[0]}["F5"]
        assert quiet >= base

    def test_no_nan_ever_reaches_output(self):
        group = [fund(code=f"N{i}", ret3y=None, ret1y=None, ret3m=None,
                      roll6m=None, roll3m=None, roll1m=None, vol=None,
                      sortino=None, roll1y=5.0 + i) for i in range(10)]
        for f in u.run(group)[0]:
            for value in (f.score, f.quality, f.momentum, f.drawdown):
                assert not math.isnan(value), f"{f.code} produced NaN"


class TestDuplicateCodes:
    """Scheme codes should be unique. If they ever are not, nothing may be lost.

    Both grade_universe and assign_risk_tiers originally reordered through a
    code-keyed map, which would have returned one record twice and dropped the
    other with no error anywhere. Position-keyed now.
    """

    def test_grading_keeps_both_records(self):
        group = peers(6) + [fund(code="F0", roll1y=40.0)]   # duplicate of F0
        scored, _ = u.score_universe(group)
        graded = u.grade_universe(scored)
        assert len(graded) == len(scored)
        assert [f.code for f in graded] == [f.code for f in scored]
        assert graded[0].score != graded[-1].score, "the two F0 records must stay distinct"

    def test_risk_tiers_keep_both_records(self):
        group = peers(6) + [fund(code="F0", vol=45.0, roll1y=40.0)]
        scored, _ = u.score_universe(group)
        tiered = u.assign_risk_tiers(scored, group)
        assert len(tiered) == len(scored)
        assert [f.code for f in tiered] == [f.code for f in scored]


class TestGapsFoundBySabotage:
    """Two holes a deliberate-bug pass exposed, now closed.

    Running five planted bugs through the suite, three went red and two did
    not. Both survivors are here. This is why the sabotage pass exists at all:
    a green suite says nothing until you have watched it go red for the right
    reasons.
    """

    def test_out_of_sample_scores_do_not_depend_on_other_out_of_sample_funds(self):
        """The hole: the original isolation test only checked that OOS funds
        leave IN-SAMPLE scores alone. Pooling the OOS set into one shared
        distribution passes that test while making every OOS fund's score
        depend on whichever other funds happened to be displayed alongside it.
        """
        eligible = peers(25)
        subject = fund(code="X0", roll1y=30.0, ret3y=41.0, vol=6.0,
                       momentum=0.44, drawdown=0.06)

        alone, _ = u.score_universe(eligible, others=[subject])
        crowded, _ = u.score_universe(
            eligible,
            others=[subject] + peers(9, prefix="Z", roll1y=200.0, ret3y=400.0, vol=0.4),
        )
        alone_x = next(f for f in alone if f.code == "X0")
        crowded_x = next(f for f in crowded if f.code == "X0")
        assert alone_x.score == crowded_x.score, (
            "an out-of-sample fund's score changed because other out-of-sample "
            "funds were displayed with it -- the reference distribution is leaking"
        )

    def test_peer_median_falls_back_when_every_score_is_zero(self):
        """The hole: no realistic peer group produces a median of exactly zero,
        so removing the fallback changed nothing and the branch was never run.
        It is a divide-by-zero guard for a downstream consumer, so it is
        exercised directly instead.
        """
        zeros = [
            u.ScoredFund(code=f"Z{i}", category="Equity Scheme",
                         sub_category="Flexi Cap Fund", quality=0.0, momentum=0.0,
                         drawdown=1.0, score=0.0, in_sample=True)
            for i in range(4)
        ]
        graded = u.grade_universe(zeros)
        assert all(f.peer_median == u.MIN_PEER_MEDIAN for f in graded), (
            "a zero peer median would divide by zero downstream"
        )
