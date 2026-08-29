"""Whole fund houses have no expense ratio, and cost is how this app ranks.

`build_expense_ratios.py` walks AMFI's AMC ids with a hardcoded ceiling,
`_MAX_MF_ID = 55`. Pass 120 probed AMFI directly: ids 56-86 return TER rows for
at least 24 fund houses, including 63 Groww, 64 Parag Parikh, 77 Zerodha and 82
JioBlackRock. The ceiling is the cause, confirmed rather than inferred — and the
app's central method, established by `validate_cost_ranking.py`, is cost.

GREEN HERE MEANS "the known defect, unchanged". The test exists so the number
cannot grow unnoticed, and so a fix shows up as a failure rather than passing
silently.
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "app" / "data"

# Live fund houses with zero TER coverage, measured on pass 118.
HOUSES_WITH_NO_TER = 23
LIVE_FUNDS_AFFECTED = 297


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


def test_the_ter_gap_is_whole_fund_houses_not_scattered_funds():
    coverage = _live_house_coverage()
    zero = {h: t for h, (t, w) in coverage.items() if w == 0 and t > 0}
    assert len(zero) == HOUSES_WITH_NO_TER, (
        f"{len(zero)} houses have no TER at all, was {HOUSES_WITH_NO_TER}: "
        f"{sorted(zero)[:6]}"
    )
    assert sum(zero.values()) == LIVE_FUNDS_AFFECTED


def test_the_houses_a_reader_should_not_skim_past():
    """Groww is the platform; PPFAS Flexi Cap is among India's most held funds.

    122639 is also the scheme code this plan uses as its own example URL, so the
    app ships a detail page for a fund whose expense ratio it cannot state.
    """
    coverage = _live_house_coverage()
    for house in ("Groww Mutual Fund", "PPFAS Mutual Fund"):
        total, with_ter = coverage.get(house, (0, 0))
        assert total > 0, f"{house} is no longer in the catalogue"
        assert with_ter == 0, (
            f"{house} now has TER coverage — remove it here and update §9.1."
        )

    ters = json.loads((DATA / "expense_ratios.json").read_text())
    assert "122639" not in ters, "Parag Parikh Flexi Cap now has a TER — update §9.1"


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
