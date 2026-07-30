"""A holding whose label names a different fund from its scheme code.

Found in our own demo data: "ICICI Prudential Corporate Bond Fund" carried code
119533, which AMFI publishes as "Aditya Birla Sun Life Corporate Bond Fund".
Nothing errored. Every number was right, and right about Aditya Birla.

This is the worst shape a wrong number takes, so the check refuses to guess in
both directions: it must not miss a real mismatch, and it must not cry wolf over
a plan suffix or an AMFI outage.
"""
from unittest.mock import patch

from app.services.marketdata.mutual_fund import MutualFundDataError
from app.services.portfolio import plan_identity
from app.services.portfolio.plan_identity import misnamed_as


class _Meta:
    def __init__(self, name):
        self.scheme_name = name


def _with_official(name):
    return patch.object(plan_identity, "get_scheme_meta", lambda _: _Meta(name))


class TestCatchesTheRealThing:
    def test_the_case_that_actually_happened(self):
        with _with_official("Aditya Birla Sun Life Corporate Bond Fund - Growth - Direct Plan"):
            assert misnamed_as("119533", "ICICI Prudential Corporate Bond Fund") == (
                "Aditya Birla Sun Life Corporate Bond Fund - Growth - Direct Plan"
            )

    def test_same_category_different_amc_is_still_a_different_fund(self):
        # The dangerous near-miss: right category, right instrument, wrong house.
        with _with_official("HDFC Small Cap Fund - Direct Plan - Growth"):
            assert misnamed_as("999", "SBI Small Cap Fund") is not None


class TestDoesNotCryWolf:
    def test_a_shorthand_is_not_a_claim_about_a_different_fund(self):
        # Our own consistency harness types "PPFAS". A plain string compare
        # flags it, and a warning that fires on every nickname trains people to
        # ignore the one that matters.
        with _with_official("Parag Parikh Flexi Cap Fund - Direct Plan - Growth"):
            assert misnamed_as("122639", "PPFAS") is None

    def test_a_label_naming_no_fund_house_stays_silent(self):
        with _with_official("SBI Small Cap Fund - Regular Plan - Growth"):
            assert misnamed_as("125494", "My retirement fund") is None

    def test_a_plan_suffix_is_not_a_different_fund(self):
        with _with_official("Parag Parikh Flexi Cap Fund - Direct Plan - Growth"):
            assert misnamed_as("122639", "Parag Parikh Flexi Cap Fund") is None

    def test_growth_against_direct_growth_agrees(self):
        with _with_official("SBI Small Cap Fund - Regular Plan - Growth"):
            assert misnamed_as("125494", "SBI Small Cap Fund - Growth") is None

    def test_an_amfi_outage_is_not_evidence_of_a_mismatch(self):
        # Reporting "this is a different fund" because a feed was down would
        # send someone to edit a holding that was never wrong.
        def boom(_):
            raise MutualFundDataError("feed down")

        with patch.object(plan_identity, "get_scheme_meta", boom):
            assert misnamed_as("122639", "Anything At All") is None

    def test_a_blank_label_has_nothing_to_disagree_with(self):
        with _with_official("SBI Small Cap Fund"):
            assert misnamed_as("125494", "") is None

    def test_an_empty_official_name_is_not_a_mismatch(self):
        with _with_official(""):
            assert misnamed_as("125494", "SBI Small Cap Fund") is None
