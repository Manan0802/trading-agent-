"""`rank_category` was never called by any test, and it makes a product promise.

Found on pass 55 by profiling which functions the suite calls rather than which
modules it names. This one is four lines of wiring, and its docstring carries a
claim worth holding it to:

    "`monthly_sip` and `years` are only used to price the commission gap in
     rupees over the user's own horizon; the ranking itself does not depend on
     them, so an anonymous Research page and a specific goal see the same order."

That is a real invariant, not a note. If a goal's horizon could reorder the
list, the same fund would be "best" on one screen and third on another, and the
app would be arguing with itself — the consistency failure §14 says this repo
commits most often.

`rank_codes` fetches NAV histories, so it is substituted here. That is the
point: the wiring and the invariant are what this function owns, and both are
checkable without a network.
"""

from app.services.advisor import category_ranking


def test_the_horizon_prices_the_gap_and_does_not_reorder_the_list(monkeypatch):
    seen = []

    def fake_rank_codes(category, codes, *, monthly_sip=None, years=None):
        seen.append({"category": category, "codes": list(codes),
                     "monthly_sip": monthly_sip, "years": years})
        return "RANKING"

    monkeypatch.setattr(category_ranking, "rank_codes", fake_rank_codes)
    monkeypatch.setattr(category_ranking, "funds_in_category", lambda c: ["A", "B"])

    anonymous = category_ranking.rank_category("Large Cap")
    with_goal = category_ranking.rank_category("Large Cap", monthly_sip=10_000, years=7)

    assert anonymous == with_goal == "RANKING"
    # same category, same candidate set, both times -- the ordering inputs are
    # identical and only the pricing arguments differ
    assert seen[0]["codes"] == seen[1]["codes"] == ["A", "B"]
    assert seen[0]["category"] == seen[1]["category"] == "Large Cap"
    assert (seen[0]["monthly_sip"], seen[0]["years"]) == (None, None)
    assert (seen[1]["monthly_sip"], seen[1]["years"]) == (10_000, 7)


def test_the_candidate_set_comes_from_the_category_not_from_the_caller(monkeypatch):
    """A caller cannot narrow the field and still call the result a category rank.

    Section 14: a base-rate class never widens — and it must not silently
    narrow either. "Best Large Cap" computed over a caller's subset is a
    different claim wearing the same words.
    """
    asked = []
    monkeypatch.setattr(category_ranking, "rank_codes",
                        lambda c, codes, **kw: list(codes))
    monkeypatch.setattr(category_ranking, "funds_in_category",
                        lambda c: asked.append(c) or ["X", "Y", "Z"])

    assert category_ranking.rank_category("ELSS") == ["X", "Y", "Z"]
    assert asked == ["ELSS"]
