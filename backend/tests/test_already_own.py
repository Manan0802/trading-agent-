"""How much of a fund you are about to buy you already own — and the zero that lies.

Somebody holding two large-cap funds who buys a third is usually buying the same
thirty companies a third time, and every other number on the screen — the rank,
the cost, the base rate — will say the third fund is good.

The failure mode this file exists for is §14's: an unmeasured overlap rendered as
0%. 0% reads as perfectly diversified, which is the opposite of "we could not
tell", and it is the more ATTRACTIVE of the two readings — so the failure
silently encourages the purchase it should have questioned.
"""

from datetime import date

import pytest

from app.services.marketdata import holdings_store
from app.services.marketdata.fund_holdings import Holding, SchemePortfolio
from app.services.portfolio.already_own import overlap_with_holdings


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_HOLDINGS_DB", str(tmp_path / "h.db"))

    def save(name, rows):
        holdings_store.save(
            SchemePortfolio(
                scheme_name=name,
                as_of=date(2026, 7, 31),
                covered=95.0,
                holdings=[Holding(i, n, "X", w) for i, n, w in rows],
            )
        )

    save("Candidate Fund", [
        ("INE001", "HDFC Bank", 10.0),
        ("INE002", "Reliance", 8.0),
        ("INE003", "Infosys", 6.0),
        ("INE004", "Something Else", 4.0),
    ])
    save("Held A", [("INE001", "HDFC Bank", 9.0), ("INE002", "Reliance", 7.0)])
    save("Held B", [("INE003", "Infosys", 5.0)])
    save("Held Unrelated", [("INE999", "Nobody", 12.0)])
    yield


class TestTheShareIsOfTheFundYouAreLookingAt:
    def test_it_sums_the_candidates_weights_you_already_reach(self):
        found = overlap_with_holdings("Candidate Fund", ["Held A"])
        assert found.share_pct == pytest.approx(18.0), (
            "HDFC Bank 10% + Reliance 8% OF THE CANDIDATE — not of Held A"
        )

    def test_a_company_two_held_funds_share_is_counted_once(self):
        """Summing per-fund overlaps double-counts, and can exceed 100%."""
        found = overlap_with_holdings("Candidate Fund", ["Held A", "Held A"])
        assert found.share_pct == pytest.approx(18.0)

    def test_it_names_the_funds_the_overlap_arrives_through(self):
        found = overlap_with_holdings("Candidate Fund", ["Held A", "Held B"])
        assert found.share_pct == pytest.approx(24.0)
        assert [name for name, _ in found.through] == ["Held A", "Held B"]
        assert found.through[0][1] > found.through[1][1], "heaviest first"

    def test_no_shared_holdings_is_a_real_zero(self):
        found = overlap_with_holdings("Candidate Fund", ["Held Unrelated"])
        assert found.share_pct == 0.0
        assert found.measured, "this IS measured — it genuinely shares nothing"


class TestUnmeasuredIsNeverZero:
    def test_a_candidate_we_cannot_read_returns_none_with_a_reason(self):
        found = overlap_with_holdings("Some Fund We Do Not Cover", ["Held A"])
        assert found.share_pct is None, (
            "0% here reads as perfectly diversified, which is the opposite of "
            "'we could not tell' and the more attractive of the two readings"
        )
        assert not found.measured
        assert found.reason and "cannot tell" in found.reason

    def test_holding_only_unreadable_funds_returns_none(self):
        found = overlap_with_holdings("Candidate Fund", ["Unknown Fund"])
        assert found.share_pct is None
        assert "None of the funds you hold" in found.reason

    def test_holding_nothing_says_so_rather_than_reporting_no_overlap(self):
        found = overlap_with_holdings("Candidate Fund", [])
        assert found.share_pct is None
        assert "do not hold any funds yet" in found.reason

    def test_the_two_unmeasurable_cases_give_different_reasons(self):
        """One is about the fund, one is about the portfolio. A single message
        for both leaves the reader unable to tell which."""
        theirs = overlap_with_holdings("Some Fund We Do Not Cover", ["Held A"])
        ours = overlap_with_holdings("Candidate Fund", ["Unknown Fund"])
        assert theirs.reason != ours.reason


def test_the_endpoint_never_serialises_an_unmeasured_zero():
    """The schema, not just the engine — a null that becomes 0.0 in the response
    model would undo all of the above."""
    from app.schemas.portfolio import AlreadyOwnOut

    out = AlreadyOwnOut(
        scheme_code="122639",
        share_pct=None,
        through=[],
        reason="not readable",
        summary="not readable",
    )
    assert out.model_dump()["share_pct"] is None
