"""Every Direct-Growth scheme AMFI publishes, grouped by SEBI category.

Built by scripts/build_fund_catalogue.py and committed, because the category
only appears on mfapi's per-scheme detail call and crawling 5,000 of those per
request is not a page anyone waits for.

This replaces a hand-written list of sixteen scheme codes across three
categories, which is why the app only ever showed Flexi Cap, Corporate Bond
and gold.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_CATALOGUE = Path(__file__).resolve().parent.parent.parent / "data" / "fund_catalogue.json"

# A percentile rank across a handful of funds is not a ranking, and a category
# that thin is usually a labelling artefact rather than a real peer group.
_MIN_FUNDS_TO_RANK = 5

# The feed still carries pre-2018 labels: "Income", "Growth", "IDF",
# "1099 Days" and similar are wound-up or closed-ended schemes a retail
# investor cannot act on. SEBI's current taxonomy always names its scheme
# type first, so that prefix is the filter.
_SEBI_PREFIXES = (
    "Equity Scheme - ",
    "Debt Scheme - ",
    "Hybrid Scheme - ",
    "Other Scheme - ",
    "Solution Oriented Scheme - ",
)


@dataclass(frozen=True)
class CatalogueFund:
    code: str
    name: str
    category: str
    fund_house: str | None


# AMFI writes the scheme-type half of a category in more than one way, and the
# spelling is not information -- "Equity Schemes - Mid Cap Fund" is SEBI's
# "Equity Scheme - Mid Cap Fund" with an s. A variant does not produce a wrong
# ranking, it produces ABSENCE: `_browsable()` demands an exact SEBI prefix, so
# the fund is unreachable through category browse and the peer group it belongs
# to is computed without it. Measured on the 2026-08-29 catalogue: **196 funds
# across 20 variant labels**, including 14 Flexi Cap and 12 Mid Cap.
#
# Only the scheme-type half is rewritten, and only when the result is a category
# that ALREADY EXISTS. Guessing at the sub-category half -- "Ultra Short Term
# Fund" for SEBI's "Ultra Short Duration Fund" -- would invent peer groups, and
# a fund ranked against the wrong peers is worse than one that is missing.
_TYPE_VARIANTS = (
    ("Equity Schemes - ", "Equity Scheme - "),
    ("Hybrid Schemes - ", "Hybrid Scheme - "),
    ("Income/Debt Oriented Schemes - ", "Debt Scheme - "),
    ("Solution Oriented Schemes - ", "Solution Oriented Scheme - "),
    ("Other Schemes - ", "Other Scheme - "),
)


# Measured synonyms, built by `scripts/build_category_synonyms.py` from two
# catalogue snapshots. mfapi serves a DIFFERENT category string for the same
# scheme code between crawls -- 563 funds changed label between 2026-08-28 and
# 2026-08-29 -- so a fund seen under both names has told us they are one bucket.
#
# This is why the file exists rather than a hand-written table. Reading two
# labels and deciding they look alike gets it wrong: the obvious reading of
# "Ultra Short to Short Term Fund" is SEBI's *Ultra Short Duration*, and all 23
# funds wearing it are actually *Low Duration*. That mapping was written by
# hand here, wrongly, before the evidence was looked at.
_SYNONYMS_FILE = (
    Path(__file__).resolve().parent.parent.parent / "data" / "category_synonyms.json"
)


@lru_cache(maxsize=1)
def _measured_synonyms() -> dict[str, str]:
    try:
        raw = json.loads(_SYNONYMS_FILE.read_text())
    except (OSError, ValueError):
        # Built by a script and may not exist. Without it the rule-based fold
        # below still runs, so a missing file costs coverage, never correctness.
        return {}
    return {variant: row["canonical"] for variant, row in raw.items()}


# Labels carrying no scheme-type half at all. `ELSS` is an Equity Linked Savings
# Scheme by definition, so there is no second reading of it.
_BARE_VARIANTS = {"ELSS": "Equity Scheme - ELSS"}


def canonical_category(category: str, existing: frozenset[str]) -> str:
    """A variant folded onto the real SEBI category, when there is one to fold onto.

    Never invents a category. If the folded name is not already in the
    catalogue, the original is kept and the fund stays unbrowsable -- visibly
    missing rather than quietly mis-ranked.
    """
    for candidate in (_measured_synonyms().get(category), _BARE_VARIANTS.get(category)):
        if candidate is not None and candidate in existing:
            return candidate
    # The rule-based fold, for the pure plural-vs-singular cases. It stays even
    # though the measured map covers most of them, because it needs no evidence:
    # `Equity Schemes - Contra Fund` had only ONE fund switch labels, too few to
    # accept as a measurement, and it is still obviously the same category.
    for variant, canon in _TYPE_VARIANTS:
        if not category.startswith(variant):
            continue
        folded = canon + category[len(variant) :]
        return folded if folded in existing else category
    return category


@lru_cache(maxsize=1)
def _by_category() -> dict[str, tuple[CatalogueFund, ...]]:
    raw = json.loads(_CATALOGUE.read_text())
    existing = frozenset(c for c in raw if c.startswith(_SEBI_PREFIXES))

    merged: dict[str, list[CatalogueFund]] = {}
    for category, funds in raw.items():
        key = canonical_category(category, existing)
        merged.setdefault(key, []).extend(
            CatalogueFund(
                code=str(f["code"]),
                name=f["name"],
                category=key,
                fund_house=f.get("fund_house"),
            )
            for f in funds
        )
    return {category: tuple(funds) for category, funds in merged.items()}


@lru_cache(maxsize=1)
def _browsable() -> tuple[str, ...]:
    return tuple(
        sorted(
            category
            for category, funds in _by_category().items()
            if category.startswith(_SEBI_PREFIXES) and len(funds) >= _MIN_FUNDS_TO_RANK
        )
    )


BROWSABLE_CATEGORIES: list[str] = list(_browsable())


def is_browsable(category: str) -> bool:
    return category in _browsable()


def funds_in_category(category: str) -> list[CatalogueFund]:
    return list(_by_category().get(category, ()))


def codes_for_category(category: str) -> list[str]:
    return [f.code for f in _by_category().get(category, ())]


def funds_matching(category: str, name_contains: str) -> list[CatalogueFund]:
    """Narrow a category by fund name.

    Needed because gold funds are not their own SEBI category: they sit inside
    "Other Scheme - FoF Domestic" alongside overseas-equity and silver FoFs,
    so category alone would recommend a Nasdaq tracker as gold.
    """
    needle = name_contains.lower()
    return [f for f in _by_category().get(category, ()) if needle in f.name.lower()]


@lru_cache(maxsize=1)
def all_funds() -> tuple[CatalogueFund, ...]:
    """Every scheme in the catalogue, flat. Used to find a regular plan's
    direct twin, which is a search across categories rather than within one."""
    return tuple(f for funds in _by_category().values() for f in funds)
