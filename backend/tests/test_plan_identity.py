"""What a holding really is, and what replaces it.

Two bugs lived here and cancelled into a plausible-looking number, which is why
neither was visible: a direct plan somebody had typed "Regular" against was
billed for a switch it did not need, and a genuine regular holding could not be
priced at all because AMFI files both plans' expense ratios under the *direct*
scheme code. The cost review worked only for the people who did not need it.
"""

import pytest

from app.services.portfolio import plan_identity
from app.services.portfolio.plan_identity import classify, core_name, identify


class TestTheNameIsALabelNotEvidence:
    def test_the_official_name_decides_the_plan_not_the_typed_one(self, monkeypatch):
        """Scheme 118955 is AMFI's Direct plan. Somebody typing "Regular Plan"
        against it used to be shown a lever worth over a lakh to fix nothing."""
        monkeypatch.setattr(
            plan_identity,
            "get_scheme_meta",
            lambda code: type("M", (), {"scheme_name": "HDFC Flexi Cap Fund - Growth Option - Direct Plan"})(),
        )
        result = identify("118955", "HDFC Flexi Cap Fund - Growth Option - Regular Plan")
        assert result.plan == "direct"
        assert result.direct_code is None

    def test_the_typed_name_is_only_a_fallback_when_the_feed_is_down(self, monkeypatch):
        def down(code):
            raise RuntimeError("mfapi unreachable")

        monkeypatch.setattr(plan_identity, "get_scheme_meta", down)
        result = identify("999999", "Some Fund - Regular Plan - Growth")
        assert result.official_name is None
        assert result.plan == "regular"

    def test_a_scheme_that_says_neither_is_not_guessed_at(self, monkeypatch):
        monkeypatch.setattr(
            plan_identity,
            "get_scheme_meta",
            lambda code: type("M", (), {"scheme_name": "Old Scheme From 2005 - Growth"})(),
        )
        result = identify("100001")
        assert result.plan is None
        assert result.direct_code is None
        assert "do not assume" in result.note


class TestNamingTheReplacement:
    def test_plan_and_option_words_are_stripped_before_matching(self):
        assert core_name("HDFC Flexi Cap Fund - Growth Option - Regular Plan") == (
            core_name("HDFC Flexi Cap Fund - Growth Option - Direct Plan")
        )
        assert core_name("SBI Small Cap Fund - Regular Plan - Growth") == "SBI SMALL CAP FUND"

    def test_two_different_funds_do_not_collapse_into_one(self):
        assert core_name("SBI Small Cap Fund - Regular Plan") != core_name(
            "SBI Large Cap Fund - Regular Plan"
        )

    def test_an_ambiguous_match_refuses_rather_than_picking(self, monkeypatch):
        """Naming the wrong fund is far worse than naming none — the reader
        would move real money into it."""
        twins = [
            type("F", (), {"code": "1", "name": "Ambiguous Fund - Direct Plan"})(),
            type("F", (), {"code": "2", "name": "Ambiguous Fund - Direct - Growth"})(),
        ]
        monkeypatch.setattr(plan_identity, "all_funds", lambda: twins)
        monkeypatch.setattr(
            plan_identity,
            "get_scheme_meta",
            lambda code: type("M", (), {"scheme_name": "Ambiguous Fund - Regular Plan"})(),
        )
        result = identify("123")
        assert result.direct_code is None
        assert "not guessing" in result.note or "could not identify" in result.note

    def test_no_match_at_all_says_what_to_search_for(self, monkeypatch):
        monkeypatch.setattr(plan_identity, "all_funds", lambda: [])
        monkeypatch.setattr(
            plan_identity,
            "get_scheme_meta",
            lambda code: type("M", (), {"scheme_name": "Unlisted Fund - Regular Plan"})(),
        )
        result = identify("123")
        assert result.direct_code is None
        assert "Direct" in result.note


@pytest.mark.parametrize(
    "name,expected",
    [
        ("HDFC Fund - Direct Plan", "direct"),
        ("HDFC Fund - Regular Plan", "regular"),
        ("HDFC Fund - Growth", None),
        ("", None),
        (None, None),
    ],
)
def test_classify(name, expected):
    assert classify(name) == expected
