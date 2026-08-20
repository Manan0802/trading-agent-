"""What the screen refuses to say, and the ways that refusal has been broken.

Every test here is about a bullet that must NOT appear. That is the whole value
of the thing: a claim like "Top Recent Returns vs Peers" is worth reading only
because 1,800 other funds did not get to make it. The failures worth guarding
are all one-directional -- a rule that leaks lets a mediocre fund boast, and
nobody downstream can tell that it should not have.

Three incidents shaped this file:

  * Upstream once printed the rank in the bullet ("#2 of 21 by 3M return") and
    removed it, leaving the comment that describes the old behaviour sitting
    above the code that does the new one. So the check here is structural: no
    field to hold a rank, and two funds at different ranks with the same value
    must produce byte-identical text.
  * Upstream's "lone top-10 pick" line used to fire for any fund in the
    category top-10, whether or not it was actually alone. Their own comment
    records the fix. Both directions are tested.
  * `universe.safe_float` maps None to 0.0 for scoring, and copying that habit
    into a *claim* would let half a peer group boast about beating funds that
    have no data at all.
"""

import ast
import collections
import math
import re
from dataclasses import fields

import pytest

from app.services.advisor import fund_catalogue
from app.services.screener import inputs, reference
from app.services.screener import reasons as port
from app.services.screener.metrics import FundMetrics
from app.services.screener.universe import ScoredFund

TOP_FUNDS_WEEK = "services/top_funds_week.py"
FUND_COPY = "services/fund_copy.py"
SETTINGS = "config/settings.py"

oracle_required = pytest.mark.skipif(
    not reference.available(),
    reason=f"reference checkout not present at {reference.root()}",
)

# Every metric defaults to None, never 0.0. A test that wants a fund to have a
# number has to say so, which keeps the "no data" path exercised by default.
_METRIC_FIELDS = {f.name for f in fields(FundMetrics)}


# `history_years` is a precondition, not a claim. Defaulting it to None -- as
# every real metric does -- would suppress every long-horizon bullet in every
# test, because a fund of unknown age is not allowed to claim a three-year
# record. Tests about the age gate pass it explicitly.
_LONG_ENOUGH_FOR_ANY_HORIZON = 5.0


def metrics_for(**values) -> FundMetrics:
    unknown = set(values) - _METRIC_FIELDS
    assert not unknown, f"FundMetrics has no field(s) {sorted(unknown)}"
    blank = {name: None for name in _METRIC_FIELDS}
    return FundMetrics(**{
        **blank,
        "nav_rows": 0,
        "capped_days": 0,
        "history_years": _LONG_ENOUGH_FOR_ANY_HORIZON,
        **values,
    })


def fund(
    code: str,
    *,
    category: str = "Equity Scheme",
    sub: str | None = "Small Cap Fund",
    score: float = 0.5,
    momentum: float = 0.0,
    **metric_values,
) -> tuple[ScoredFund, FundMetrics]:
    scored = ScoredFund(
        code=code,
        category=category,
        sub_category=sub,
        quality=0.5,
        momentum=momentum,
        drawdown=0.1,
        score=score,
        in_sample=True,
    )
    return scored, metrics_for(**metric_values)


def run(pairs) -> dict[str, list[port.FundReason]]:
    scored = [s for s, _m in pairs]
    metrics = {s.code: m for s, m in pairs}
    return port.reasons_for_universe(scored, metrics)


def kinds(bullets) -> list[str]:
    return [b.kind for b in bullets]


def texts(result) -> list[str]:
    return [b.text for bullets in result.values() for b in bullets]


def descending_group(n: int, *, metric: str = "returns_3m", sub: str = "Small Cap Fund",
                     category: str = "Equity Scheme", top: float = 40.0):
    """n funds of one sub-category, best first: fund `f00` is rank 1, `f01` rank 2..."""
    return [
        fund(f"f{i:02d}", category=category, sub=sub, **{metric: top - i})
        for i in range(n)
    ]


# --------------------------------------------------------------- the rank rule


def test_a_rank_six_fund_with_a_top_fifteen_percent_value_says_nothing():
    """The absolute cap, which is the clause that does the work in big groups.

    Forty peers puts the 15% cutoff at 6, so rank 6 clears the percentile and
    is silenced only by `_MAX_DISPLAY_RANK`. Drop that clause and #80 of 586
    equity funds starts calling itself a peer leader.
    """
    pairs = descending_group(40)
    result = run(pairs)
    assert math.ceil(port._TOP_PCTL_FRAC * 40) == 6, "the setup no longer tests the cap"
    assert kinds(result["f04"]) == ["short_term"], "rank 5 must still speak"
    assert result["f05"] == [], "rank 6 cleared the percentile and must still be silent"


def test_a_rank_three_fund_outside_the_top_fifteen_percent_says_nothing():
    """The percentile clause, which is what binds in almost every real group.

    Thirteen peers puts the cutoff at 2. Rank 3 is comfortably inside the
    top-5 cap and must still say nothing.
    """
    pairs = descending_group(13)
    result = run(pairs)
    assert math.ceil(port._TOP_PCTL_FRAC * 13) == 2
    assert kinds(result["f01"]) == ["short_term"], "rank 2 is inside the top 15%"
    assert result["f02"] == [], "rank 3 of 13 is not the top 15% of anything"


def test_a_fund_whose_value_would_lead_a_thin_group_is_ranked_against_the_wider_one():
    """A fund can lead its four peers and still be nowhere near the category."""
    pairs = (
        [fund("thin0", sub="Contra Fund", returns_3m=8.0)]
        + [fund(f"thin{i}", sub="Contra Fund", returns_3m=1.0) for i in range(1, 4)]
        + descending_group(20, sub="Large Cap Fund")
    )
    result = run(pairs)
    assert result["thin0"] == [], "best of four, but 13th of the category"


# ------------------------------------------------------------ the peer group


def test_a_sub_category_of_four_falls_back_to_the_category():
    pairs = (
        [fund(f"contra{i}", sub="Contra Fund", returns_3m=99.0 - i) for i in range(4)]
        + descending_group(20, sub="Large Cap Fund")
    )
    result = run(pairs)
    bullet = result["contra0"][0]
    assert bullet.peer_group == "Equity Scheme", (
        "four peers is not a ranking; the claim has to be made against the category"
    )
    assert result["f00"][0].peer_group == "Large Cap Fund", (
        "a sub-category with twenty funds keeps its own peer group"
    )


def test_a_fund_whose_category_is_also_thin_gets_no_metric_reasons_at_all():
    """No fallback below the fallback. Four funds is four funds."""
    pairs = [fund(f"t{i}", category="Commodity", sub="Gold", returns_3m=50.0 - i)
             for i in range(4)]
    result = run(pairs)
    assert all(bullets == [] for bullets in result.values())


def test_a_universe_of_one_fund_makes_no_claims():
    """A peer group of one is not a ranking -- `universe.py` says the same thing."""
    result = run([fund("solo", returns_3m=42.0, returns_1y=90.0, rolling_3m=30.0)])
    assert result == {"solo": []}


def test_an_empty_universe_returns_an_empty_mapping():
    assert port.reasons_for_universe([], {}) == {}


def test_every_scored_code_appears_in_the_mapping_even_with_nothing_to_say():
    """Silence and absence must be distinguishable to the caller."""
    pairs = descending_group(13)
    result = run(pairs)
    assert set(result) == {s.code for s, _m in pairs}
    assert sum(1 for b in result.values() if b) == 2


# ------------------------------------------------------------------- nulls


def test_a_fund_with_a_null_metric_is_out_of_the_denominator_not_ranked_as_zero():
    """The claim's denominator is funds WITH the metric, never all funds.

    Twenty funds, five of which have a 3-month return. Ranked over the five,
    the cutoff is 1 and only the leader speaks. Score the missing fifteen as
    0.0 -- which is what `safe_float` does for scoring -- and n becomes 20, the
    cutoff becomes 3, and two more funds start boasting about beating funds
    that published nothing.
    """
    pairs = (
        [fund(f"has{i}", returns_3m=10.0 - i) for i in range(5)]
        + [fund(f"none{i}") for i in range(15)]
    )
    result = run(pairs)
    assert kinds(result["has0"]) == ["short_term"]
    assert result["has1"] == [], "rank 2 of 5 is not the top 15% of 5"
    assert result["has2"] == [], "only reachable if the fifteen nulls were counted"
    assert all(result[f"none{i}"] == [] for i in range(15))


def test_a_metric_carried_by_fewer_than_five_funds_is_not_a_ranking():
    """Our one deliberate divergence, and the hole it closes.

    Upstream gates group size on COUNT(*) but ranks over the non-null subset,
    so a group of twenty where four funds have a 3-year return hands the best
    of those four a "top of its peers" bullet -- #1 of 4. The peer floor
    belongs wherever the ranking actually happens.
    """
    pairs = (
        [fund(f"has{i}", returns_3y=10.0 - i) for i in range(4)]
        + [fund(f"none{i}") for i in range(16)]
    )
    assert run(pairs)["has0"] == []


def test_a_nan_is_treated_as_missing_rather_than_as_a_number():
    pairs = [fund("nan", returns_3m=float("nan"))] + descending_group(10)
    result = run(pairs)
    assert result["nan"] == []
    assert kinds(result["f00"]) == ["short_term"], "the NaN must not have moved anyone"


# -------------------------------------------------------------------- ties


def test_a_tie_at_the_boundary_is_resolved_the_way_we_documented():
    """Minimum rank, not pandas' default average. Both tied funds speak.

    Forty peers, cutoff 6, cap 5. Two funds tie for fifth place. Under minimum
    rank both are rank 5 -- "exactly four funds beat me", true of both -- and
    both qualify. Under `method="average"` both would be 5.5, fail `<= 5`, and
    be silenced despite the claim being true. The rank number here means
    "peers strictly better, plus one", and that is the sentence the bullet is
    making.
    """
    values = [40.0, 39.0, 38.0, 37.0, 36.0, 36.0] + [10.0 - i for i in range(34)]
    pairs = [fund(f"f{i:02d}", returns_3m=v) for i, v in enumerate(values)]
    result = run(pairs)
    assert kinds(result["f04"]) == ["short_term"]
    assert kinds(result["f05"]) == ["short_term"], (
        "the second half of a boundary tie was silenced -- that is average ranking"
    )
    assert result["f06"] == [], "rank 7 is behind six funds and must stay silent"


def test_ties_do_not_let_a_whole_group_through_the_cap():
    values = [40.0] * 3 + [39.0 - i for i in range(10)]
    pairs = [fund(f"f{i:02d}", returns_3m=v) for i, v in enumerate(values)]
    result = run(pairs)
    assert math.ceil(port._TOP_PCTL_FRAC * 13) == 2
    assert all(kinds(result[f"f{i:02d}"]) == ["short_term"] for i in range(3)), (
        "three funds tied at the top are all rank 1; none of them is beaten by anyone"
    )
    assert all(result[f"f{i:02d}"] == [] for i in range(3, 13))


# ------------------------------------------------------- percentile display


@pytest.mark.parametrize(
    "pos,n,expected",
    [
        (1, 17, 10),    # 5.9% -> "top 10%" is true; "top 5%" is not a whole fund
        (1, 20, 5),
        (1, 100, 5),
        (2, 17, 15),
        (3, 20, 15),
        (1, 3, 35),
        (1, 1, 100),
    ],
)
def test_percentiles_are_bucketed_up_so_the_claim_is_true_not_flattering(pos, n, expected):
    assert port.bucket_pct(pos, n) == expected


def test_the_bucketed_standing_never_overstates_the_position():
    """The property behind the rounding: the bucket must contain the fund."""
    for n in range(1, 60):
        for pos in range(1, n + 1):
            pct = port.bucket_pct(pos, n)
            assert pct >= 100 * pos / n - 1e-9, f"#{pos} of {n} claimed top {pct}%"


def test_a_standing_worth_no_sentence_returns_nothing():
    assert port.peer_standing(1, 17) == "top 10%"
    assert port.peer_standing(9, 20) is None, "top 45% is not a claim"
    assert port.peer_standing(None, 20) is None
    assert port.peer_standing(3, 0) is None


# -------------------------------------------------------------- the lone pick


def _lone_pick_universe(second_small_cap_score: float):
    """One category, two sub-categories, ten slots. `lone` always makes the top ten."""
    pairs = [fund("lone", sub="Small Cap Fund", score=1.0)]
    pairs += [fund("small_other", sub="Small Cap Fund", score=second_small_cap_score)]
    pairs += [fund(f"small_low{i}", sub="Small Cap Fund", score=0.01) for i in range(3)]
    pairs += [fund(f"large{i}", sub="Large Cap Fund", score=0.5 - i * 0.01)
              for i in range(12)]
    return pairs


def test_the_only_fund_of_its_sub_category_in_the_top_ten_gets_the_lone_pick_line():
    result = run(_lone_pick_universe(second_small_cap_score=0.01))
    bullet = result["lone"][0]
    assert bullet.kind == "outperforming_peers"
    assert bullet.text == (
        "Outperforming peers in Small Cap Fund — lone top-10 pick "
        "while most peers rank lower"
    )


def test_when_a_second_fund_of_the_sub_category_is_also_in_the_top_ten_both_stay_silent():
    """Upstream's own bug: the line fired for anyone in the top ten, alone or not."""
    result = run(_lone_pick_universe(second_small_cap_score=0.9))
    assert "outperforming_peers" not in kinds(result["lone"])
    assert "outperforming_peers" not in kinds(result["small_other"])


def test_a_fund_outside_its_categorys_top_ten_never_claims_peer_standing():
    pairs = (
        [fund("a0", sub="Sub A", score=1.0)]
        + [fund(f"a{i}", sub="Sub A", score=0.0) for i in range(1, 5)]
        + [fund(f"b{i}", sub="Sub B", score=0.9 - i * 0.01) for i in range(5)]
        + [fund(f"c{i}", sub="Sub C", score=0.8 - i * 0.01) for i in range(5)]
    )
    result = run(pairs)
    assert kinds(result["a0"]) == ["outperforming_peers"]
    assert result["b0"] == [], "five of Sub B are in the top ten; none of them is alone"
    assert result["a4"] == [], "outside the top ten entirely"


def test_a_fund_with_no_sub_category_peers_at_all_is_not_a_lone_pick():
    """A sub-category of one is trivially the only one of its kind anywhere.

    Upstream's version fires here -- it checks only that the count in the
    category's top ten is exactly one -- so a universe of a single fund gets
    told it outperforms peers that do not exist.
    """
    assert run([fund("only", sub="Contra Fund", score=1.0)])["only"] == []
    crowd = ([fund("only", sub="Contra Fund", score=1.0)]
             + [fund(f"big{i}", sub="Large Cap Fund", score=0.5 - i * 0.01)
                for i in range(20)])
    assert run(crowd)["only"] == []


# ---------------------------------------------------------------- momentum


def test_momentum_is_never_shown_as_a_number():
    """A 0-1 signal on a card invites "0.41 out of what?" and has no answer."""
    pairs = [fund("hot", momentum=0.4237), fund("warm", momentum=0.3299),
             fund("cold", momentum=0.3199)]
    result = run(pairs)
    hot = result["hot"][0]
    assert hot.text == "Strong accelerated growth over the last two weeks"
    assert result["warm"][0].text == "Accelerated growth over the last two weeks"
    assert result["cold"] == [], "below 0.32 there is no momentum claim"
    for bullet in result["hot"] + result["warm"]:
        assert not any(ch.isdigit() for ch in bullet.text), bullet.text
    assert hot.value == pytest.approx(0.4237), "the number is carried, just not printed"
    assert hot.unit == "ratio"


def test_momentum_survives_a_peer_group_too_thin_to_rank():
    """It is the fund's own two-week signal, not a comparison, so thinness is
    irrelevant to it -- unlike every other bullet here."""
    result = run([fund("solo", momentum=0.5, returns_3m=99.0)])
    assert kinds(result["solo"]) == ["momentum"]


# ------------------------------------------------------- shape of the output


def test_no_kind_appears_twice_for_one_fund():
    result = run(_full_house())
    for bullets in result.values():
        assert len(kinds(bullets)) == len(set(kinds(bullets)))


def test_no_fund_gets_more_than_six_bullets():
    result = run(_full_house())
    assert all(len(bullets) <= port._MAX_BULLETS for bullets in result.values())


def test_the_cap_holds_when_more_candidates_than_slots_are_offered():
    """The public API cannot reach seven candidates today -- five of upstream's
    eleven kinds are not wired in -- so the cap is exercised directly. Without
    this the cap could be deleted and every test would stay green.
    """
    candidates = [
        port.FundReason(kind=k, label="", value=0.0, unit="ratio", peer_group="", text=k)
        for k in ("rank", "grade", "outperforming_peers", "momentum",
                  "sub_category_boom", "nifty", "consistency", "long_term",
                  "short_term", "sector_context")
    ]
    selected = port._select_bullets(candidates)
    assert len(selected) == 6
    assert kinds(selected) == [
        "sector_context", "short_term", "long_term", "consistency",
        "nifty", "sub_category_boom",
    ]


def test_the_bullets_come_out_in_the_documented_priority_order():
    result = run(_full_house())
    assert kinds(result["star"]) == [
        "short_term", "long_term", "consistency", "momentum", "outperforming_peers",
    ]


def test_every_slot_upstream_defines_is_still_reserved():
    """Wiring a sector or benchmark bullet later must not reshuffle the rest."""
    assert port._BULLET_PRIORITY == {
        "sector_context": 0,
        "sector_context_fund": 0.5,
        "short_term": 1,
        "long_term": 2,
        "consistency": 3,
        "nifty": 4,
        "sub_category_boom": 5,
        "momentum": 6,
        "outperforming_peers": 7,
        "grade": 8,
        "rank": 9,
    }


def _full_house():
    """A fund that legitimately earns every bullet this module can emit."""
    pairs = [fund("star", sub="Small Cap Fund", score=1.0, momentum=0.61,
                  returns_3m=40.0, returns_1m=30.0, returns_1y=99.0,
                  returns_3y=88.0, rolling_3m=45.0)]
    pairs += [
        fund(f"small{i}", sub="Small Cap Fund", score=0.01,
             returns_3m=1.0 - i, returns_1m=1.0 - i, returns_1y=1.0 - i,
             returns_3y=1.0 - i, rolling_3m=1.0 - i)
        for i in range(9)
    ]
    pairs += [fund(f"large{i}", sub="Large Cap Fund", score=0.5 - i * 0.01)
              for i in range(12)]
    return pairs


# ------------------------------------------------------------- the rank leak


def test_the_rank_never_appears_in_the_output():
    """Structural, then textual, then unrecoverable.

    A field would be the obvious leak, a "#2 of 21" in the sentence the next
    one. The third check is the one that actually binds: two funds at
    different ranks holding the same value must produce the identical
    sentence, so no amount of parsing recovers the standing.
    """
    forbidden = ("rank", "position", "percentile", "place", "ordinal")
    for field in fields(port.FundReason):
        assert not any(word in field.name.lower() for word in forbidden), (
            f"FundReason.{field.name} is somewhere a rank could be put"
        )

    result = run(_full_house())
    for text in texts(result):
        assert not re.search(r"#\s*\d", text), text
        assert not re.search(r"\b(rank|ranked|ranks)\b", text, re.I) or "rank lower" in text, text
        assert not re.search(r"\bof \d+\b", text), text
        assert not re.search(r"\btop \d+%", text), text

    # Same value, different standing, identical sentence.
    high = [fund("a", returns_3m=50.0)] + [fund(f"h{i}", returns_3m=49.0 - i)
                                           for i in range(12)]
    low = [fund("b", returns_3m=50.0), fund("x", returns_3m=60.0)] + [
        fund(f"l{i}", returns_3m=49.0 - i) for i in range(11)
    ]
    assert run(high)["a"][0].text == run(low)["b"][0].text


def test_the_reason_dataclass_is_frozen_so_a_rank_cannot_be_attached_later():
    bullet = run(descending_group(10))["f00"][0]
    with pytest.raises(Exception):
        bullet.rank = 1


# --------------------------------------------------- the real 39 peer groups


def _real_sub_category_sizes() -> dict[tuple, int]:
    sizes: collections.Counter = collections.Counter()
    for f in fund_catalogue.all_funds():
        category, sub = inputs.split_category(f.category)
        ok, _why = inputs.is_eligible(category)
        if ok:
            sizes[(category, sub)] += 1
    return dict(sizes)


def test_exactly_two_sub_categories_fall_below_the_five_peer_floor():
    """Measured, not assumed -- the brief for this module said three.

    Gilt Fund with 10 year constant duration has exactly five funds, and five
    passes. Only Contra and Balanced Hybrid are genuinely below it, and both
    then rank against 586 equity and 224 hybrid funds respectively, where the
    absolute cap is the only clause that can ever let them speak.
    """
    thin = sorted(k for k, n in _real_sub_category_sizes().items() if n < port._MIN_PCTL_PEERS)
    assert thin == [("Equity Scheme", "Contra Fund"),
                    ("Hybrid Scheme", "Balanced Hybrid Fund")]


def test_no_real_category_is_thin_enough_to_silence_a_fund_entirely():
    """So the no-reasons-at-all path is unreachable on live data, and the test
    that covers it has to build its own universe."""
    sizes: collections.Counter = collections.Counter()
    for f in fund_catalogue.all_funds():
        category, _sub = inputs.split_category(f.category)
        if inputs.is_eligible(category)[0]:
            sizes[category] += 1
    assert min(sizes.values()) >= port._MIN_PCTL_PEERS
    assert len(sizes) == 5


def test_the_absolute_cap_binds_independently_in_twenty_of_the_thirty_nine_groups():
    """ceil(0.15 * 33) is 5, so below 34 peers the two clauses are one clause."""
    sizes = _real_sub_category_sizes()
    assert len(sizes) == 39 and sum(sizes.values()) == 1886
    binds = [k for k, n in sizes.items() if math.ceil(port._TOP_PCTL_FRAC * n) > port._MAX_DISPLAY_RANK]
    assert len(binds) == 20
    assert all(n >= 34 for k, n in sizes.items() if k in binds)
    assert max(n for k, n in sizes.items() if k not in binds) == 33


# ------------------------------------------------------- against their source


def _lift(rel_path: str, names: set[str], into: dict) -> dict:
    """Exec the named module-level functions/constants out of a reference file.

    Read through `reference.read_source` -- the only door to that tree, and one
    with no write side. Same shape as `test_scoring_parity._lift`.
    """
    source = reference.read_source(rel_path)
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            exec(compile(ast.Module([node], []), rel_path, "exec"), into)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                exec(compile(ast.Module([node], []), rel_path, "exec"), into)
    return into


class _StubLogger:
    def __getattr__(self, _name):
        return lambda *a, **k: None


# Their metric column -> ours. Only `rolling_ret_3m` was renamed.
_REF_NAMES = {
    "returns_3m": "returns_3m",
    "returns_1m": "returns_1m",
    "returns_1y": "returns_1y",
    "returns_3y": "returns_3y",
    "rolling_ret_3m": "rolling_3m",
}


@pytest.fixture(scope="module")
def oracle():
    """Their real claim functions, executed from their source.

    They lift cleanly: everything below the SQL layer is a pure function over a
    dict and a snapshot. Only `resolve_category_stats` and
    `build_data_backed_reasons` touch anything outside, and only a logger.
    """
    import os

    ns: dict = {"math": math, "os": os, "logger": _StubLogger(), "__name__": "oracle"}
    _lift(SETTINGS, {"TOP_FUNDS_DOMINANCE_N"}, ns)
    _lift(
        TOP_FUNDS_WEEK,
        {
            "sub_category_key", "_metric_rank", "_is_top_rank", "_value_phrase",
            "build_short_term_reason", "build_long_term_reason",
            "build_consistency_reason", "build_data_backed_reasons",
            "resolve_category_stats", "build_momentum_reason",
            "build_sub_category_reason", "_select_bullets",
            "_SHORT_TERM_METRICS", "_LONG_TERM_METRICS", "_CONSISTENCY_METRIC",
            "_GLOBAL_PCTL_METRICS", "_TOP_PCTL_FRAC", "_MIN_PCTL_PEERS",
            "_MAX_DISPLAY_RANK", "_BULLET_PRIORITY", "_BULLET_LABELS", "_MAX_BULLETS",
            "MOMENTUM_SCORE_MODERATE", "MOMENTUM_SCORE_STRONG",
        },
        ns,
    )
    _lift(FUND_COPY, {"_bucket_pct", "_PCTL_STEP"}, ns)
    return ns


def _oracle_snapshot(oracle, pairs):
    """Their {"sub": ..., "cat": ...} peer snapshot, built from our universe."""
    sub: dict = {}
    cat: dict = {}
    for scored, m in pairs:
        if scored.sub_category:
            key = oracle["sub_category_key"](scored.category, scored.sub_category)
            sub.setdefault(key, []).append(m)
        cat.setdefault(str(scored.category), []).append(m)

    def group(members):
        out = {"_count": len(members)}
        for ref_name in oracle["_GLOBAL_PCTL_METRICS"]:
            ours = _REF_NAMES.get(ref_name)
            out[ref_name] = [] if ours is None else [
                float(getattr(m, ours)) for m in members if getattr(m, ours) is not None
            ]
        return out

    return {"sub": {k: group(v) for k, v in sub.items()},
            "cat": {k: group(v) for k, v in cat.items()}}


def _oracle_fund(scored, m) -> dict:
    row = {"category": scored.category, "sub_category": scored.sub_category,
           "momentum_score": scored.momentum}
    for ref_name, ours in _REF_NAMES.items():
        row[ref_name] = getattr(m, ours)
    return row


def _random_universe(seed: int, n_per_sub: int = 24):
    import random

    rng = random.Random(seed)
    pairs = []
    for sub in ("Small Cap Fund", "Large Cap Fund", "Flexi Cap Fund"):
        for i in range(n_per_sub):
            pairs.append(fund(
                f"{sub[:2]}{i:03d}", sub=sub,
                score=rng.uniform(0, 1),
                momentum=rng.uniform(0, 0.6),
                returns_3m=round(rng.gauss(6, 8), 4),
                returns_1m=round(rng.gauss(2, 4), 4),
                returns_1y=round(rng.gauss(18, 14), 4),
                returns_3y=round(rng.gauss(45, 25), 4),
                rolling_3m=round(rng.gauss(5, 6), 4),
            ))
    return pairs


class TestAgainstReferenceSource:
    @oracle_required
    @pytest.mark.parametrize("n", [1, 4, 5, 6, 7, 13, 20, 33, 34, 40, 100, 364])
    def test_the_top_rank_rule_matches(self, oracle, n):
        for rank in range(1, n + 1):
            assert port._is_top_rank(rank, n) == oracle["_is_top_rank"](rank, n)
        assert port._is_top_rank(None, n) == oracle["_is_top_rank"](None, n)
        assert port._is_top_rank(1, None) == oracle["_is_top_rank"](1, None)

    @oracle_required
    @pytest.mark.parametrize("seed", [1, 7, 42])
    def test_the_rank_itself_matches_including_ties(self, oracle, seed):
        import random

        rng = random.Random(seed)
        values = [round(rng.choice([1.0, 2.0, 2.0, 3.5, 7.25]) + rng.choice([0, 0, 0.1]), 3)
                  for _ in range(30)]
        for v in values + [0.0, 99.0]:
            assert port._metric_rank(v, values) == oracle["_metric_rank"](v, values)
        assert port._metric_rank(None, values) == oracle["_metric_rank"](None, values)
        assert port._metric_rank(1.0, []) == oracle["_metric_rank"](1.0, [])

    @oracle_required
    @pytest.mark.parametrize("seed", [3, 11, 2026])
    def test_the_three_metric_bullets_match_word_for_word(self, oracle, seed):
        pairs = _random_universe(seed)
        snapshot = _oracle_snapshot(oracle, pairs)
        mine = run(pairs)
        for scored, m in pairs:
            theirs = oracle["build_data_backed_reasons"](_oracle_fund(scored, m), snapshot)
            expected = [(r["type"], r["text"]) for r in theirs]
            actual = [(b.kind, b.text) for b in mine[scored.code]
                      if b.kind in ("short_term", "long_term", "consistency")]
            assert actual == expected, scored.code

    @oracle_required
    def test_the_peer_group_fallback_matches(self, oracle):
        pairs = (
            [fund(f"contra{i}", sub="Contra Fund", returns_3m=99.0 - i) for i in range(4)]
            + [fund(f"large{i}", sub="Large Cap Fund", returns_3m=50.0 - i) for i in range(20)]
        )
        snapshot = _oracle_snapshot(oracle, pairs)
        mine = run(pairs)
        for scored, m in pairs:
            _stats, group = oracle["resolve_category_stats"](
                snapshot, scored.category, scored.sub_category
            )
            for bullet in mine[scored.code]:
                if bullet.kind in ("short_term", "long_term", "consistency"):
                    assert bullet.peer_group == group

    @oracle_required
    @pytest.mark.parametrize("score", [None, 0.0, 0.31, 0.32, 0.399, 0.40, 0.9])
    def test_the_momentum_wording_matches(self, oracle, score):
        theirs = oracle["build_momentum_reason"](score)
        pairs = [fund("m", momentum=score)]
        mine = [b for b in run(pairs)["m"] if b.kind == "momentum"]
        if theirs is None:
            assert mine == []
        else:
            assert [(b.kind, b.text) for b in mine] == [(theirs["type"], theirs["text"])]

    @oracle_required
    def test_the_lone_pick_wording_matches(self, oracle):
        theirs = oracle["build_sub_category_reason"](
            "outperforming_peers",
            {"category": "Equity Scheme", "sub_category": "Small Cap Fund"},
            {}, True,
        )
        bullet = run(_lone_pick_universe(0.01))["lone"][0]
        assert (bullet.kind, bullet.text) == (theirs["type"], theirs["text"])
        assert oracle["build_sub_category_reason"](
            "outperforming_peers",
            {"category": "Equity Scheme", "sub_category": "Small Cap Fund"},
            {}, False,
        ) is None

    @oracle_required
    def test_the_bullet_priority_and_cap_match(self, oracle):
        assert port._BULLET_PRIORITY == oracle["_BULLET_PRIORITY"]
        assert port._MAX_BULLETS == oracle["_MAX_BULLETS"]
        assert port._TOP_PCTL_FRAC == oracle["_TOP_PCTL_FRAC"]
        assert port._MIN_PCTL_PEERS == oracle["_MIN_PCTL_PEERS"]
        assert port._MAX_DISPLAY_RANK == oracle["_MAX_DISPLAY_RANK"]
        assert port.MOMENTUM_STRONG == oracle["MOMENTUM_SCORE_STRONG"]
        assert port.MOMENTUM_MODERATE == oracle["MOMENTUM_SCORE_MODERATE"]

    @oracle_required
    def test_the_selection_order_matches(self, oracle):
        order = ("rank", "grade", "outperforming_peers", "momentum",
                 "sub_category_boom", "nifty", "consistency", "long_term",
                 "short_term", "sector_context", "sector_context_fund")
        theirs = oracle["_select_bullets"]([{"type": k, "text": k} for k in order])
        mine = port._select_bullets([
            port.FundReason(kind=k, label="", value=0.0, unit="ratio",
                            peer_group="", text=k)
            for k in order
        ])
        assert kinds(mine) == [r["type"] for r in theirs]

    @oracle_required
    def test_the_percentile_bucketing_matches(self, oracle):
        for n in range(1, 80):
            for pos in range(1, n + 1):
                assert port.bucket_pct(pos, n) == oracle["_bucket_pct"](pos, n)

    @oracle_required
    def test_where_we_deliberately_differ_from_them(self, oracle):
        """Named, not discovered later: the non-null peer floor.

        Their group-size gate counts every fund in the group; the ranking then
        runs over whichever of them have the metric. So four funds with a
        3-year return inside a group of twenty produce a bullet, ranked #1 of
        4. We refuse it. This test exists to make that divergence deliberate
        and visible, and it goes red the day we accidentally match them again.
        """
        pairs = (
            [fund(f"has{i}", returns_3y=10.0 - i) for i in range(4)]
            + [fund(f"none{i}") for i in range(16)]
        )
        snapshot = _oracle_snapshot(oracle, pairs)
        scored, m = pairs[0]
        theirs = oracle["build_data_backed_reasons"](_oracle_fund(scored, m), snapshot)
        assert [r["type"] for r in theirs] == ["long_term"], (
            "upstream stopped making this claim -- re-check whether we still need to differ"
        )
        assert run(pairs)["has0"] == []


# ------------------------------------------------- a claim needs a record


class TestAFundMustHaveLivedTheHorizonItClaims:
    """The live case that prompted this.

    Groww Silver ETF FOF came out #1 in the real universe carrying the bullet
    "Higher long-run returns vs Peers : +163.3% (1Y), +148.6% (3Y)". The fund is
    fifteen months old. Its "3-year return" is those fifteen months annualised,
    because upstream's `get_trailing_ret` falls back to the whole available
    window whenever the fund is younger than the period asked for.

    That is reproduced in the SCORE -- it is a faithful port, and changing it
    would move every rank. It is NOT reproduced in the CLAIM. A module whose
    entire purpose is refusing to say untrue things must not say "long-run
    returns" about a fund with no long run.
    """

    def _universe(self, winner_history):
        winner = fund(
            "W", returns_3y=150.0, returns_1y=160.0, returns_3m=9.0,
            history_years=winner_history,
        )
        peers = [
            fund(
                f"P{i}", returns_3y=8.0 + i * 0.1, returns_1y=7.0 + i * 0.1,
                returns_3m=1.0 + i * 0.1, history_years=6.0,
            )
            for i in range(9)
        ]
        return [winner, *peers]

    def _texts(self, winner_history) -> str:
        return " ".join(r.text for r in run(self._universe(winner_history))["W"])

    def test_a_fifteen_month_fund_does_not_claim_a_three_year_record(self):
        """Only the three-year horizon goes.

        The bullet keeps its "long-run returns" wording and keeps citing 1Y,
        which is correct: the fund has lived a year, the +160% is real, and one
        year is a long run next to three months. The gate is per horizon, not
        per bullet -- silencing the whole line would hide a true claim to avoid
        a false one.
        """
        texts = self._texts(1.23)
        assert "3Y" not in texts, f"claimed a three-year record it does not have: {texts}"
        assert "1Y" in texts, "over-suppressed: the one-year record is real"

    def test_it_still_claims_the_horizons_it_has_actually_lived(self):
        """Suppressing the false claim must not silence the true ones. Fifteen
        months is a real one-year record and a real three-month one."""
        texts = self._texts(1.23)
        assert "1Y" in texts or "3M" in texts, f"over-suppressed to nothing: {texts}"

    def test_a_six_year_fund_claims_everything_it_leads_on(self):
        texts = self._texts(6.0)
        assert "3Y" in texts and "1Y" in texts

    def test_a_fund_of_unknown_age_claims_no_horizon(self):
        """Silence is the default everywhere else here, and a missing
        `history_years` means we cannot show the claim is honest."""
        texts = self._texts(None)
        assert "3Y" not in texts and "1Y" not in texts

    def test_exactly_three_years_is_enough(self):
        assert "3Y" in self._texts(3.0)

    def test_a_whisker_under_three_years_is_not(self):
        assert "3Y" not in self._texts(2.99)

    def test_the_reference_would_have_made_the_claim_and_we_do_not(self):
        """Pins the divergence explicitly, so it reads as a decision rather than
        as drift. The number is identical on both sides; only the sentence differs."""
        from app.services.screener import reasons as port_mod

        assert port_mod._MIN_YEARS_FOR["returns_3y"] == 3.0
        winner_metrics = self._universe(1.23)[0][1]
        assert winner_metrics.returns_3y == 150.0, (
            "the metric itself is untouched -- the score still uses it"
        )
        assert "3Y" not in self._texts(1.23), "but the claim is withheld"
