"""Live funds sitting in a category that is a *spelling variant* of a real one.

Commit 208f396 fixed one instance — AMFI writes some SEBI categories in the
plural, and 24 buyable funds were being dropped. The class of bug did not go
away with those names, and it grew when the catalogue did: rebuilding it on
2026-08-29 took it from 4,957 funds to 5,470 and surfaced 27 more variant
labels.

A variant does NOT produce a wrong ranking. `_browsable()` demands an exact
SEBI prefix and at least five funds, and the rankings route 404s on anything
else, so a variant never reaches the scorer. It produces **absence**: the fund
is unreachable through category browse, and the peer group it belongs to is
computed without it.

`fund_catalogue.canonical_category` now folds them, and most of the map is
MEASURED rather than judged: mfapi serves a different category string for the
same scheme code between crawls, so a fund seen under both names has proved they
are one bucket. 563 funds changed label between 2026-08-28 and 2026-08-29.

That evidence overturned a hand-written guess. "Ultra Short to Short Term Fund"
reads like SEBI's *Ultra Short Duration Fund*; all 23 funds carrying it are
*Low Duration*. The guess was in this repo before the measurement was taken.

Result: live funds reachable through browse went 1,282 -> 1,714, and the ones
outside SEBI's taxonomy went 428 -> 12.
"""

import json
import re
import sqlite3
from pathlib import Path

from app.services.advisor.fund_catalogue import (
    _by_category,
    canonical_category,
    is_browsable,
)

DATA = Path(__file__).resolve().parent.parent / "app" / "data"

_SERIES = re.compile(
    r"\bSeries\b|\bPlan [A-Z]\b|\bFMP\b|\bFixed Term\b|\bFixed Maturity\b", re.I
)

# Labels deliberately NOT folded, with the reason. Each is a decision, not a gap.
UNFOLDED_ON_PURPOSE = {
    # Its measured target, `Debt Scheme - Gilt Fund with 10 year constant
    # duration`, is not a category this catalogue has -- and the fold refuses to
    # invent one. Visibly missing beats quietly mis-ranked.
    "Income/Debt Oriented Schemes - 10-year Constant Maturity Gilt Fund",
    "Income/Debt Oriented Schemes - Other Debt Scheme",
    "Index Funds - Hybrid Fund",
    # Too few funds switched labels to accept as a measurement: one apiece, and
    # one fund moving is as likely to be a fund that genuinely changed category.
    "Life Cycle Funds - Life Cycle Fund with Maturity of 10 Years",
    "Life Cycle Funds - Life Cycle Fund with Maturity of 15 Years",
    "Children’s Fund - Childrens' Fund",
    # Genuinely their own buckets, not variants of anything.
    "IDF",
    "Income",
    "Growth",
    "Half Yearly Dividend",
    "Income/Debt Oriented Schemes - Fixed Term Plan",
}


def _live_codes() -> set[str]:
    """Live means "published a NAV this month", not "has a TER".

    Pass 117: the TER table covers 1,408 schemes while 1,701 catalogue funds
    published a NAV since 2026-08-01. Using the TER table as the definition of
    live hid 15 mis-bucketed funds.
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


def _folded() -> dict[str, tuple[str, str]]:
    """code -> (category after folding, name)."""
    return {f.code: (cat, f.name) for cat, funds in _by_category().items() for f in funds}


def _is_sebi(name: str) -> bool:
    return " Scheme - " in name or name.startswith("Solution Oriented")


def test_the_fold_only_ever_lands_on_a_category_that_already_exists():
    """It must never INVENT a peer group. That is the whole safety property."""
    raw = json.loads((DATA / "fund_catalogue.json").read_text())
    existing = frozenset(
        c for c in raw if c.startswith(
            ("Equity Scheme - ", "Debt Scheme - ", "Hybrid Scheme - ",
             "Other Scheme - ", "Solution Oriented Scheme - ")
        )
    )
    for category in raw:
        folded = canonical_category(category, existing)
        assert folded == category or folded in existing, (
            f"{category!r} folded to {folded!r}, which is not a real category"
        )


def test_the_known_variants_are_now_reachable_through_browse():
    """The ones this fixed, named — so a regression says which funds vanish."""
    for variant, expected in [
        ("Equity Schemes - Flexi Cap Fund", "Equity Scheme - Flexi Cap Fund"),
        ("Equity Schemes - Mid Cap Fund", "Equity Scheme - Mid Cap Fund"),
        ("Equity Schemes - Small Cap Fund", "Equity Scheme - Small Cap Fund"),
        ("Hybrid Schemes - Arbitrage Fund", "Hybrid Scheme - Arbitrage Fund"),
        ("Income/Debt Oriented Schemes - Liquid Fund", "Debt Scheme - Liquid Fund"),
        ("Equity Schemes - Thematic Fund", "Equity Scheme - Sectoral/ Thematic"),
        ("Equity Schemes - ELSS- Tax Saver Fund", "Equity Scheme - ELSS"),
        (
            "Income/Debt Oriented Schemes - Banking and PSU Debt Fund",
            "Debt Scheme - Banking and PSU Fund",
        ),
        ("Hybrid Schemes - Equity Savings Fund", "Hybrid Scheme - Equity Savings"),
        ("ELSS", "Equity Scheme - ELSS"),
        # The ones no reading of the names would have got right.
        (
            "Income/Debt Oriented Schemes - Ultra Short to Short Term Fund",
            "Debt Scheme - Low Duration Fund",
        ),
        ("Income/Debt Oriented Schemes - Dynamic Term Fund", "Debt Scheme - Dynamic Bond"),
        (
            "Income/Debt Oriented Schemes - Floating Interest Rates Fund",
            "Debt Scheme - Floater Fund",
        ),
        ("Index Funds - Equity Funds", "Other Scheme - Index Funds"),
        (
            "Overseas Fund of Funds - Fund of Funds investing overseas",
            "Other Scheme - FoF Overseas",
        ),
    ]:
        assert variant not in _by_category(), f"{variant!r} is still its own bucket"
        assert is_browsable(expected), f"{expected!r} is not browsable"


def test_no_new_variant_has_appeared():
    """A label outside SEBI's taxonomy that nobody has ruled on yet."""
    folded = _folded()
    outside = {
        folded[code][0]
        for code in _live_codes()
        if code in folded and not _is_sebi(folded[code][0])
    }
    unexpected = outside - UNFOLDED_ON_PURPOSE
    assert not unexpected, (
        f"new non-SEBI category holding live funds: {sorted(unexpected)}. Either "
        "fold it in `_SUB_VARIANTS` or record why not in UNFOLDED_ON_PURPOSE."
    )


def test_the_residual_loss_is_the_size_it_should_be():
    """12 open-ended live funds remain unbrowsable, every one of them on purpose.

    GREEN HERE MEANS "the decided state, unchanged" — not "no defect". If this
    moves, either a fold started working or a new label appeared, and both are
    worth looking at rather than renumbering.
    """
    folded = _folded()
    lost = [
        code
        for code in _live_codes()
        if code in folded
        and not _is_sebi(folded[code][0])
        and not _SERIES.search(folded[code][1])
    ]
    assert len(lost) == 12, (
        f"{len(lost)} open-ended live funds outside SEBI's taxonomy, was 12"
    )


def test_a_synonym_is_only_accepted_on_plentiful_one_sided_evidence():
    """One fund switching labels is as likely to be a fund that changed category.

    The map is built with a floor of 5 funds and 80% agreement, and the entries
    it rejected are exactly the ones a human eye would have waved through:
    `Life Cycle Funds - ... 10 Years` -> `Hybrid Scheme - Multi Asset Allocation`
    on the strength of a single fund.
    """
    raw = json.loads((DATA / "category_synonyms.json").read_text())
    assert raw, "the measured synonym map is missing"
    for variant, row in raw.items():
        assert row["funds"] >= 5, f"{variant} accepted on {row['funds']} funds"
        assert row["funds"] / row["of"] >= 0.80, f"{variant}: evidence disagreed"
        assert _is_sebi(row["canonical"]), f"{variant} folds onto a non-SEBI label"
