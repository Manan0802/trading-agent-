"""Expense-ratio coverage, and the two ways it used to be lost.

Cost is how this app ranks, established by `validate_cost_ranking.py`, so a fund
with no TER is a fund the method does not reach.

**Defect one, fixed:** `build_expense_ratios.py` walked AMFI's AMC ids with a
hardcoded `_MAX_MF_ID = 55`. Ids 56-86 carry at least 24 fund houses, including
63 Groww, 64 Parag Parikh, 77 Zerodha and 82 JioBlackRock -- 297 live funds
across 23 houses, every one of them an AMC that registered recently. The walk
now stops on eight consecutive empty ids and the 2026-08-29 rebuild reached 86.

**Defect two, found by fixing the first:** the builder REPLACED the file, so one
crawl that missed a fund deleted its cost. The rebuild dropped 469 buyable funds
and added 357 -- a net loss of 112 on the app's only measured signal -- and
several of the dropped funds normalised to exactly the string AMFI had used for
them, so the join was not at fault. AMFI simply did not serve them that day. It
now merges: a TER filed in July is still the TER filed in July, `as_of` says so,
and newer always wins.

This file now pins the FIXED state. A regression shows up as a failure.
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "app" / "data"

# What the two defects cost when they were live, kept as the thing not to
# regress to.
HOUSES_ONCE_AT_ZERO = 23
LIVE_FUNDS_ONCE_AFFECTED = 297


def _live_house_coverage() -> dict[str, tuple[int, int]]:
    catalogue = json.loads((DATA / "fund_catalogue.json").read_text())
    ters = json.loads((DATA / "expense_ratios.json").read_text())
    with sqlite3.connect(BACKEND / ".navstore" / "nav.db") as con:
        live = {
            row[0]
            for row in con.execute(
                "SELECT scheme_code FROM nav_history GROUP BY scheme_code "
                "HAVING MAX(nav_date) >= '2026-08-01'"
            )
        }
    per_house: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for funds in catalogue.values():
        for fund in funds:
            if fund["code"] not in live:
                continue
            house = fund.get("fund_house") or "?"
            per_house[house][0] += 1
            if fund["code"] in ters:
                per_house[house][1] += 1
    return {h: (total, with_ter) for h, (total, with_ter) in per_house.items()}


def test_no_live_fund_house_is_left_without_a_single_expense_ratio():
    """23 houses were at zero, covering 297 live funds. Now none is."""
    coverage = _live_house_coverage()
    zero = {h: t for h, (t, w) in coverage.items() if w == 0 and t > 0}
    assert not zero, (
        f"{len(zero)} live fund houses have no TER at all: {sorted(zero)[:6]}. "
        f"This was {HOUSES_ONCE_AT_ZERO} houses and "
        f"{LIVE_FUNDS_ONCE_AFFECTED} funds before the AMC ceiling was removed"
    )


def test_almost_every_buyable_fund_can_be_priced():
    """The number that matters, because it is measured against what you can buy.

    Counting against the whole catalogue is technically true and misleading:
    ICICI has 456 catalogue funds with no TER and exactly FOUR of them are
    buyable, the rest being closed-ended series and wound-up schemes.
    """
    from app.services.advisor import buyable

    ters = json.loads((DATA / "expense_ratios.json").read_text())
    codes = buyable.buyable_codes()
    priced = len(codes & set(ters))
    assert priced / len(codes) >= 0.95, (
        f"only {priced} of {len(codes)} buyable funds can be priced "
        f"({priced / len(codes) * 100:.0f}%). Cost is the one signal this app "
        "has measured, so an unpriced fund is outside the method"
    )


def test_a_crawl_that_misses_a_fund_does_not_delete_its_cost():
    """The merge, pinned against the code.

    Replacing the file cost 112 buyable funds their TER in a single rebuild,
    and every one of them still had a published figure from the month before.
    """
    import ast

    source = (BACKEND / "scripts" / "build_expense_ratios.py").read_text()
    tree = ast.parse(source)
    names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    assert "_merge_with_committed" in names, (
        "the builder writes the file without merging, so one bad crawl deletes "
        "every fund it failed to reach"
    )
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {
        n.func.id
        for n in ast.walk(main)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "_merge_with_committed" in called, "the merge exists but is not called"


def test_the_houses_the_ceiling_used_to_hide():
    """Groww is the platform Manan invests through; PPFAS Flexi Cap is among
    India's most widely held funds, and 122639 is the scheme code this plan uses
    as its own example URL. The app shipped a detail page for it and could not
    state its expense ratio."""
    coverage = _live_house_coverage()
    for house in ("Groww Mutual Fund", "PPFAS Mutual Fund"):
        total, with_ter = coverage.get(house, (0, 0))
        assert total > 0, f"{house} is no longer in the catalogue"
        assert with_ter > 0, f"{house} is back to zero TER coverage"

    ters = json.loads((DATA / "expense_ratios.json").read_text())
    assert "122639" in ters, "Parag Parikh Flexi Cap has lost its TER again"
    assert ters["122639"].get("direct_ter"), "its direct TER is missing"


def test_the_walk_stops_on_evidence_not_on_a_number():
    """The fix, pinned — and pinned against the code, not against prose.

    A first version of this test asserted `"_MAX_MF_ID = 55" in source`. After
    the fix, that string still appeared — inside the comment explaining what
    the old constant had cost — so the test went on passing against a file that
    no longer contained the defect. A checker that matches a quotation of the
    wrong form instead of the form itself is the same failure the plan's own
    contrast-pair guard exists for.
    """
    import ast

    source = (BACKEND / "scripts" / "build_expense_ratios.py").read_text()
    tree = ast.parse(source)
    assigned = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert "_MAX_MF_ID" not in assigned, (
        "the hardcoded AMC ceiling is back — it cost 297 live funds their "
        "expense ratio, across 23 whole fund houses including Groww's own"
    )
    stop = assigned.get("_STOP_AFTER_EMPTY")
    assert stop is not None, "the walk must stop on consecutive empty ids"
    assert isinstance(stop, ast.Constant) and stop.value >= 8, (
        "eight is four times the largest gap observed inside the live id "
        f"range; {getattr(stop, 'value', None)} is not enough margin"
    )
