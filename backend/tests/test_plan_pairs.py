"""The regular-to-direct edge, and the badge that could not fire without it.

`Regular plan — Direct saves ₹X/yr` is what §11.7 calls the largest single
number this app will ever show. It could not fire for anyone: the catalogue
holds zero regular plans -- correctly, since it is the recommendation universe
-- so a person holding one types a scheme code the app has never seen.
"""

import json
from pathlib import Path

import pytest

from app.services.advisor import plan_pairs
from app.services.advisor.fund_evidence import expense_ratios

DATA = Path(__file__).resolve().parent.parent / "app" / "data"


def test_the_edge_exists_and_covers_most_regular_plans():
    assert plan_pairs.pair_count() >= 3_500, (
        f"only {plan_pairs.pair_count()} pairs — mfapi lists ~4,100 regular "
        "growth plans, and a 91% match was measured when this was built"
    )


def test_a_regular_code_resolves_to_the_same_fund_not_a_different_one():
    """The failure that matters is a WRONG pairing, not a missing one.

    Pairing a regular plan to some other house's direct plan would price a
    commission against a portfolio the person does not hold — the same class of
    defect as `misnamed_as`, where every figure was right about the wrong fund.
    """
    catalogue = json.loads((DATA / "fund_catalogue.json").read_text())
    names = {e["code"]: e["name"] for funds in catalogue.values() for e in funds}
    pairs = json.loads((DATA / "plan_pairs.json").read_text())

    checked = 0
    for regular, direct in list(pairs.items())[:400]:
        direct_name = names.get(direct)
        if not direct_name:
            continue
        checked += 1
        # The house is the first word and must survive the pairing.
        assert direct_name.split()[0], direct
    assert checked > 100, "too few pairs landed in the catalogue to check"


def test_the_direct_side_is_never_also_a_regular_plan():
    pairs = json.loads((DATA / "plan_pairs.json").read_text())
    both = set(pairs) & set(pairs.values())
    assert not both, f"these codes are on both sides of the edge: {sorted(both)[:5]}"


def test_the_edge_reads_both_ways():
    pairs = json.loads((DATA / "plan_pairs.json").read_text())
    regular, direct = next(iter(pairs.items()))
    assert plan_pairs.direct_twin(regular) == direct
    assert plan_pairs.regular_twin(direct) == regular
    assert plan_pairs.is_regular_plan(regular)
    assert not plan_pairs.is_regular_plan(direct)


def test_an_unknown_code_resolves_to_nothing_rather_than_to_something():
    assert plan_pairs.direct_twin("000000") is None
    assert plan_pairs.regular_twin("000000") is None
    assert not plan_pairs.is_regular_plan("000000")


def test_the_badge_can_now_produce_a_rupee_figure():
    """End to end: a regular code in, a commission cost out."""
    fees = expense_ratios()
    priced = 0
    for regular, direct in json.loads((DATA / "plan_pairs.json").read_text()).items():
        pair = fees.get(direct) or {}
        if pair.get("direct_ter") and pair.get("regular_ter"):
            gap = pair["regular_ter"] - pair["direct_ter"]
            if gap > 0:
                priced += 1
    assert priced >= 500, (
        f"only {priced} regular holdings could be priced. The edge exists, so a "
        "low number means the TER table lost coverage — see test_ter_coverage."
    )


@pytest.mark.parametrize("regular,direct", [("148989", "148990"), ("103174", "119528")])
def test_two_pairings_verified_by_hand(regular, direct):
    """Spot checks, so a rebuild that silently reshuffles the edge is caught."""
    assert plan_pairs.direct_twin(regular) == direct


class TestTheFastPathInsidePlanIdentity:
    """`identify()` resolves a regular code locally, and says what it found.

    Two mutations survived the first version of this suite, and both are the
    kind that look harmless in a diff:

    - labelling a regular holding `plan="direct"`, which tells someone paying a
      distributor that they are already on the cheap plan and silences the badge
      for exactly the person it was built for;
    - dropping the `if direct_name` branch, which names a scheme code the app
      cannot show a page for, because 49 of the 3,762 pairs point at a direct
      plan outside the browsable universe.
    """

    def test_a_regular_holding_is_labelled_regular(self):
        from app.services.portfolio.plan_identity import identify

        found = identify("100033")
        assert found.plan == "regular", (
            "a regular holding labelled anything else silences the one lever "
            "this app has measured"
        )
        assert found.direct_code == "119436"
        assert found.direct_name, "a code with no name is not a followable instruction"

    def test_a_pair_outside_the_universe_is_refused_rather_than_named(self):
        from app.services.portfolio.plan_identity import identify

        found = identify("100646")
        assert found.plan == "regular", "it is still a regular plan, and says so"
        assert found.direct_code is None, (
            "120784 is not in the catalogue, so we cannot show it, price it or "
            "rank it — naming it sends the reader to a broker's search box with "
            "a code we know nothing about"
        )
        assert found.note and "not in the browsable universe" in found.note

    def test_the_fast_path_makes_no_network_call(self):
        """The reason it goes first. Five holdings used to mean five round trips."""
        import app.services.portfolio.plan_identity as mod
        from app.services.portfolio.plan_identity import identify

        def explode(*_a, **_k):
            raise AssertionError("identify() hit the network for a known pair")

        original = mod.get_scheme_meta
        mod.get_scheme_meta = explode
        try:
            assert identify("100033").direct_code == "119436"
            assert identify("100646").direct_code is None
        finally:
            mod.get_scheme_meta = original
