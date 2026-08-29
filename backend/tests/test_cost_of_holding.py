"""Cost is the axis this app ranks on, so its failure modes are the product's.

Every test here is a way the number can be wrong while looking right.
"""

import json
from pathlib import Path

from app.services.advisor import cost_of_holding as cost
from app.services.advisor.cost_of_holding import CostOfHolding, looks_passive, read

DATA = Path(__file__).resolve().parent.parent / "app" / "data"

# A fund the committed AMFI table actually carries, so these are real filings.
_HELD = "119436"


def _amfi(code: str) -> dict:
    return json.loads((DATA / "expense_ratios.json").read_text())[code]


class TestTheTwoSourcesAreNeverAveraged:
    def test_agreement_within_a_tenth_of_a_point_yields_one_figure(self):
        filed = float(_amfi(_HELD)["direct_ter"])
        found = read(_HELD, groww_ter=filed + 0.05)
        assert found.agrees is True
        assert found.ter == filed, "AMFI's filing is the figure of record"
        assert found.rankable_on_cost

    def test_a_disagreement_is_shown_rather_than_averaged(self):
        filed = float(_amfi(_HELD)["direct_ter"])
        found = read(_HELD, groww_ter=filed + 0.40)
        assert found.agrees is False
        assert found.ter is None, (
            "an average of two numbers that disagree is a third number neither "
            "source stands behind, and it looks as confident as agreement"
        )
        assert found.amfi_direct_ter == filed and found.groww_ter == filed + 0.40
        assert abs(found.disagreement_pp - 0.40) < 1e-9
        assert not found.rankable_on_cost, (
            "cost is the axis this app ranks on; a fund whose cost is contested "
            "must not compete on it"
        )
        assert "not averaging" in found.note

    def test_the_boundary_is_inclusive_at_a_tenth_of_a_point(self):
        filed = float(_amfi(_HELD)["direct_ter"])
        assert read(_HELD, groww_ter=filed + 0.10).agrees is True
        assert read(_HELD, groww_ter=filed + 0.1001).agrees is False


class TestOneSourceIsNotAZero:
    def test_a_fund_with_only_amfi_still_ranks(self):
        found = read(_HELD)
        assert found.sources == ("amfi",)
        assert found.agrees is None, "there is nothing to agree with"
        assert found.rankable_on_cost

    def test_a_fund_with_neither_source_reads_as_unknown_not_as_free(self):
        found = read("000000")
        assert found.ter is None, (
            "a TER we failed to read must not sort as the cheapest fund — that "
            "failure once put three unpriced funds in a Large Cap top five"
        )
        assert found.sources == ()
        assert not found.rankable_on_cost
        assert found.note and "could not read" in found.note

    def test_a_published_zero_is_treated_as_a_read_failure(self):
        found = read("000000", groww_ter=0.0)
        assert found.ter is None
        assert found.sources == ()

    def test_an_unparseable_ter_is_none_rather_than_zero(self):
        assert cost._percent("") is None
        assert cost._percent("n/a") is None
        assert cost._percent(None) is None
        assert cost._percent("0.24") == 0.24


class TestTheJoinKey:
    def test_the_committed_table_is_keyed_on_scheme_code_not_on_name(self):
        """Joining these two sources by NAME returns zero, silently.

        It does not error. It returns an empty table, and a cost gate that has
        no second source for anything while looking like it works.
        """
        table = json.loads((DATA / "expense_ratios.json").read_text())
        keys = list(table)[:200]
        assert all(k.isdigit() for k in keys), (
            "the expense table is keyed on AMFI scheme codes; anything else "
            "means a builder joined on the field a human reaches for"
        )
        assert read(_HELD).sources, "the held code must join"


class TestUnusuallyHighIsNotAComplianceClaim:
    def test_a_high_direct_plan_is_flagged_with_the_number_and_no_breach_claim(self):
        found = read("000000", groww_ter=2.60)
        assert found.flag and "2.60%" in found.flag
        assert "unusually high" in found.flag
        for word in ("SEBI", "limit", "ceiling", "cap", "breach", "exceeds"):
            assert word.lower() not in found.flag.lower(), (
                f"{word!r} claims a regulatory breach. SEBI's limit is slab-based "
                "on AUM and that table could not be sourced, and this repo's own "
                "2,793 AMFI values run smoothly through 2.25% up to 3.46"
            )

    def test_an_ordinary_direct_plan_is_not_flagged(self):
        assert read("000000", groww_ter=1.10).flag is None

    def test_an_index_fund_is_measured_against_a_lower_bar(self):
        active = read("000000", groww_ter=1.10, scheme_name="Some Active Fund")
        passive = read("000000", groww_ter=1.10, scheme_name="UTI Nifty 50 Index Fund")
        assert active.flag is None
        assert passive.flag and "tracks an index" in passive.flag, (
            "1.10% is ordinary for an active fund and steep for a tracker; "
            "one threshold for both makes an index fund its own peer group"
        )

    def test_passive_detection_reads_names_and_sub_categories(self):
        assert looks_passive(scheme_name="ICICI Nifty Next 50 Index Fund")
        assert looks_passive(sub_category="Index Funds")
        assert looks_passive(scheme_name="Nippon India ETF Gold BeES")
        assert not looks_passive(scheme_name="Parag Parikh Flexi Cap Fund")


def test_the_reading_is_pure_and_does_not_reach_the_network():
    """Groww's TER is passed in, not fetched, so an outage cannot become a cost.

    It also means every branch above is reachable from a fixture instead of
    from a live feed that may or may not disagree today.
    """
    import inspect

    source = inspect.getsource(cost)
    for banned in ("httpx", "requests", "fetch_", "urlopen"):
        assert banned not in source, f"{banned} makes this module a request"


def test_every_reading_is_frozen():
    found = read(_HELD)
    assert isinstance(found, CostOfHolding)
    try:
        found.ter = 0.01  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("a cost reading must not be editable after the fact")
