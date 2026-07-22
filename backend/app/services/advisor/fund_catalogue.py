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


@lru_cache(maxsize=1)
def _by_category() -> dict[str, tuple[CatalogueFund, ...]]:
    raw = json.loads(_CATALOGUE.read_text())
    return {
        category: tuple(
            CatalogueFund(
                code=str(f["code"]),
                name=f["name"],
                category=category,
                fund_house=f.get("fund_house"),
            )
            for f in funds
        )
        for category, funds in raw.items()
    }


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
