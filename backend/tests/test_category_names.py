"""Live funds sitting in a category that is a *spelling variant* of a real one.

Commit 208f396 fixed one instance of this — AMFI writes some SEBI categories
in the plural, and 24 buyable funds were being dropped. The class of bug did
not go away with those names.

A variant does NOT produce a small-bucket ranking: `fund_catalogue._browsable()`
demands an exact SEBI prefix and at least five funds, and the rankings route
404s on anything else, so a variant never reaches the scorer. It produces
absence — the fund is unreachable through category browse, and the peer group
it belongs to is computed without it.

GREEN HERE MEANS "the known defect, unchanged" — not "no defect". 37 open-ended
funds are really missing today; the other 11 variant-labelled funds are
closed-ended `Series` schemes that `inputs.py` excludes on purpose. The test
exists so a *new* variant, or a silent fix, both show up.
"""

import json
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "app" / "data"

# Names AMFI publishes that normalise onto a real SEBI category but are not it.
# Counted against schemes AMFI publishes a current TER for, i.e. live funds.
KNOWN_VARIANTS = {
    "ELSS": 11,
    "Index Funds - Equity Funds": 8,
    "Equity Schemes - Thematic Fund": 7,
    "Hybrid Schemes - Aggressive Hybrid Fund": 2,
    "Hybrid Schemes - Balanced Advantage Fund/ Dynamic Asset Allocation": 2,
    "Income/Debt Oriented Schemes - Dynamic Term Fund": 2,
    "Income/Debt Oriented Schemes - Liquid Fund": 2,
    "Income/Debt Oriented Schemes - Overnight Fund": 2,
    "Income/Debt Oriented Schemes - Ultra Short Term Fund": 2,
    "Equity Schemes - ELSS- Tax Saver Fund": 1,
    "Equity Schemes - Flexi Cap Fund": 1,
    "Equity Schemes - Focused Fund": 1,
    "Equity Schemes - Large Cap Fund": 1,
    "Equity Schemes - Multi Cap Fund": 1,
    "Income/Debt Oriented Schemes - Banking and PSU Debt Fund": 1,
    "Income/Debt Oriented Schemes - Corporate Bond Fund": 1,
    "Income/Debt Oriented Schemes - Money Market Fund": 1,
    "Income/Debt Oriented Schemes - Short Term Fund": 1,
    "Index Funds - Debt Funds": 1,
}

# Legacy buckets that are NOT variants of anything — genuinely their own thing.
NOT_VARIANTS = {"IDF", "Income", "Growth", "Half Yearly Dividend",
                "Overseas Fund of Funds - Fund of Funds investing overseas"}


def _live_codes() -> set[str]:
    """Live means "published a NAV this month", not "has a TER".

    Pass 117: the TER table covers 1,408 schemes while 1,701 catalogue funds
    published a NAV since 2026-08-01 — a 353-fund gap. Using the TER table as
    the definition of live hid 15 mis-bucketed funds, including Mahindra
    Manulife Large Cap Fund, which trades daily and simply is not in it.
    """
    store = DATA.parent.parent / ".navstore" / "nav.db"
    with sqlite3.connect(store) as con:
        return {
            row[0]
            for row in con.execute(
                "SELECT scheme_code FROM nav_history GROUP BY scheme_code "
                "HAVING MAX(nav_date) >= '2026-08-01'"
            )
        }


def _live_category_counts() -> dict[str, int]:
    catalogue = json.loads((DATA / "fund_catalogue.json").read_text())
    by_code = {e["code"]: cat for cat, funds in catalogue.items() for e in funds}
    counts: dict[str, int] = {}
    for code in _live_codes():
        cat = by_code.get(code)
        if cat is not None:
            counts[cat] = counts.get(cat, 0) + 1
    return counts


def _is_sebi(name: str) -> bool:
    return " Scheme - " in name or name.startswith("Solution Oriented")


def test_no_new_category_variant_has_appeared():
    counts = _live_category_counts()
    outside = {c: n for c, n in counts.items() if not _is_sebi(c)}
    unexpected = set(outside) - set(KNOWN_VARIANTS) - NOT_VARIANTS
    assert not unexpected, f"new non-SEBI category for live funds: {sorted(unexpected)}"


def test_the_known_variants_still_hold_the_same_funds():
    counts = _live_category_counts()
    for name, expected in KNOWN_VARIANTS.items():
        assert counts.get(name, 0) == expected, (
            f"{name!r}: {counts.get(name, 0)} live funds, was {expected}. "
            "If this was fixed, remove the entry and update the plan's §2.3."
        )


def test_no_variant_category_is_reachable_through_browse():
    """The harm is absence. Prove the route really cannot serve these."""
    from app.services.advisor.fund_catalogue import is_browsable

    for name in KNOWN_VARIANTS:
        assert not is_browsable(name), (
            f"{name!r} became browsable — if the variant was mapped to its real "
            "category, remove it here and update the plan's §9.1 row."
        )


def test_the_open_ended_funds_lost_to_variants_still_number_22():
    """10 of the 32 are closed-ended Series schemes, excluded on purpose."""
    import json
    import re

    catalogue = json.loads((DATA / "fund_catalogue.json").read_text())
    by_code = {e["code"]: cat for cat, funds in catalogue.items() for e in funds}
    names = {e["code"]: e["name"] for funds in catalogue.values() for e in funds}
    series = re.compile(
        r"\bSeries\b|\bPlan [A-Z]\b|\bFMP\b|\bFixed Term\b|\bFixed Maturity\b", re.I
    )

    lost = [
        code
        for code in _live_codes()
        if by_code.get(code) in KNOWN_VARIANTS and not series.search(names[code])
    ]
    assert len(lost) == 37, f"{len(lost)} open-ended funds lost to a category variant"
