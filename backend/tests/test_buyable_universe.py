"""The buyable universe, and the four figures that could not be reproduced.

§12 recorded all four as measured live and thrown away, which §11.4 calls worse
than no record: not wrong, unauditable. This file is where they become checkable
again.
"""

import json
from pathlib import Path

from app.services.advisor import buyable, cost_of_holding

DATA = Path(__file__).resolve().parent.parent / "app" / "data"


class TestTheUniverseIsRealAndActionable:
    def test_it_holds_the_buyable_funds_not_the_whole_catalogue(self):
        codes = buyable.buyable_codes()
        assert 1_200 <= len(codes) <= 2_500, (
            f"{len(codes)} funds. The catalogue holds 4,957 and Groww sells "
            "~1,689 of them; a count near either extreme means the filter "
            "stopped filtering or the pull came back short"
        )
        assert all(c.isdigit() for c in codes), (
            "keyed on AMFI scheme codes, which is what joins this to the NAV "
            "store, the catalogue and the TER table"
        )

    def test_specialised_investment_funds_are_kept_out(self):
        """Groww's listing now carries SIFs, keyed `SIF-14`, not by AMFI code.

        38 rows in the pull, 30 passing every other buyability filter. Zero of
        them appear in AMFI's expense file, so the app can compute no NAV, no
        cost, no category rank and no score for any of them — while showing
        them as buyable. They also carry a ₹10,00,000 minimum against a ₹1,000
        median, so a ranking that includes them offers something a thousand
        times out of reach.
        """
        assert not [c for c in buyable.buyable_codes() if c.startswith("SIF")]
        assert not buyable.is_buyable("SIF-14")

    def test_the_fund_this_plan_uses_as_its_own_example_is_buyable(self):
        """PPFAS 122639 — among the most widely held funds in India, and the
        one whose detail page this document links to."""
        assert buyable.is_buyable("122639")
        assert buyable.is_passive("122639") is False

    def test_a_fund_nobody_sells_is_not_buyable(self):
        assert not buyable.is_buyable("000000")


class TestThePassiveSplitIsReadNotGuessed:
    def test_an_index_fund_filed_under_large_cap_is_still_flagged_passive(self):
        """The exact confound the split exists for.

        UTI Nifty 50 Index sits in the Large Cap sub-category alongside active
        funds. Its TER is a fraction of theirs, so ranking them together makes
        every genuine Large Cap fund look expensive against a fund that is not
        doing the same job.
        """
        assert buyable.sub_category("120716") == "Large Cap"
        assert buyable.is_passive("120716") is True

    def test_the_whole_buyable_universe_carries_the_flag(self):
        table = json.loads((DATA / "groww_buyable.json").read_text())
        unknown = [c for c, row in table.items() if not row.get("passive_known")]
        assert not unknown, (
            f"{len(unknown)} buyable funds have no `index` flag. It lives in the "
            "st_filter listing and NOT in scheme detail, so this many means the "
            "build pulled the wrong endpoint"
        )

    def test_an_unclassified_fund_reads_unknown_rather_than_active(self):
        assert buyable.is_passive("000000") is None, (
            "collapsing unknown to False files an unclassified index fund among "
            "active funds, where its 0.20% TER makes every active fund look dear"
        )

    def test_the_cost_gate_prefers_the_flag_over_the_name(self):
        """A name test cannot see this one: nothing in the name says index."""
        by_name = cost_of_holding.looks_passive(scheme_name="UTI Nifty 50 Index Fund")
        by_flag = cost_of_holding.looks_passive(
            scheme_name="A Name That Says Nothing", scheme_code="120716"
        )
        assert by_name and by_flag

    def test_the_name_test_still_covers_a_code_groww_does_not_carry(self):
        """Regular plans are not in Groww's direct-growth listing at all."""
        assert cost_of_holding.looks_passive(
            scheme_name="Some Nifty Index Fund - Regular", scheme_code="000000"
        )


class TestTheUniverseFileDoesNotRepublishGrowwsContent:
    def test_it_carries_only_the_four_facts_the_product_cannot_work_without(self):
        """Groww's /v1/api/* is Disallow: in their robots.txt.

        The raw pull is retained in .growwcache/, which is gitignored. What is
        committed is a list of AMFI codes with three attributes — a fact about
        the market rather than Groww's own measurements.
        """
        table = json.loads((DATA / "groww_buyable.json").read_text())
        allowed = {"buyable", "is_passive", "passive_known", "sub_category"}
        for code, row in list(table.items())[:400]:
            extra = set(row) - allowed
            assert not extra, f"{code} carries {extra}, which was not pulled to publish"

    def test_no_returns_ratings_or_measurements_leaked_in(self):
        raw = (DATA / "groww_buyable.json").read_text()
        for field in ("return1y", "return3y", "groww_rating", "expense_ratio",
                      "aum", "fund_manager", "groww_verdict_score", "nav"):
            assert field not in raw, f"{field} is Groww's measurement, not ours"


def test_the_app_still_works_with_the_universe_missing():
    """§2.1's rule: Groww is an enrichment layer the app degrades without.

    AMFI is the spine. With this file absent the screener must still rank; it
    simply cannot narrow to what is buyable, and the surface has to say so.
    """
    buyable._table.cache_clear()
    original = buyable._FILE
    try:
        buyable._FILE = Path("/nonexistent/groww_buyable.json")
        buyable._table.cache_clear()
        assert not buyable.known()
        assert buyable.buyable_codes() == frozenset()
        assert buyable.is_passive("120716") is None
        assert not buyable.is_buyable("122639")
    finally:
        buyable._FILE = original
        buyable._table.cache_clear()
    assert buyable.known(), "the real table must be back for every later test"
