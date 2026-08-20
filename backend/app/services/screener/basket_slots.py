"""Translating the reference's basket slot keys into traa's fund categories.

`basket.py` is a faithful port and speaks upstream's vocabulary: slot keys like
`Commodity::Gold` and `Equity Index Fund`. traa's categories come from AMFI via
`fund_catalogue.json` and use SEBI's 2017 names. Neither is wrong; they are
different naming schemes for the same funds, and something has to map one to
the other. This is that something, and it is deliberately the only place the
mapping exists.

Five of the seven slots are a plain rename. The two commodity slots are not,
and this is the part worth reading: **AMFI has no Commodity category at all.**
Gold and silver funds sit inside `Other Scheme - FoF Domestic`, alongside
Nasdaq trackers and overseas-equity FoFs, and the only thing separating them is
the fund's name.

traa already solved that, in `advisor/fund_universe.gold_funds()`, and its
comment explains why filtering that category by name matters: without it the
gold sleeve of a portfolio can be filled with a Nasdaq tracker. That function is
reused here rather than reimplemented -- a second, subtly different definition
of "which funds are gold" is exactly how two screens start disagreeing.

Silver is separated the same way. Note `fund_universe` deliberately excludes
silver from its *gold* list, because a gold-and-silver fund is a different
exposure from the one a gold sleeve is asking for; the same exclusion runs in
reverse here.

Measured on today's catalogue, every slot resolves and every one clears the
eight-peer floor the fund screen already uses:

    Equity Index Fund                    Other Scheme - Index Funds          364
    Sectoral/ Thematic                   Equity Scheme - Sectoral/ Thematic  246
    Flexi / Multi::Flexi Cap Fund        Equity Scheme - Flexi Cap Fund       44
    Commodity::Gold                      FoF Domestic, name contains gold     23
    Commodity::Silver                    FoF Domestic, name contains silver   19
    Equity Scheme::Large & Mid Cap Fund  Equity Scheme - Large & Mid Cap Fund 36
    Debt Scheme::Liquid Fund             Debt Scheme - Liquid Fund            51

**Two of these carry a caveat the screen must repeat.** `Other Scheme - Index
Funds` holds 364 funds tracking wildly different indices -- a Nifty 50 tracker
and a Nifty Smallcap 250 Momentum tracker are both in it -- and
`Sectoral/ Thematic` holds 246 funds betting on different sectors. Picking "the
best" from either ranks *which segment ran*, not which fund is better run. The
same caveat already appears on the fund screen for the same two groups
(`serve.CAVEATED_SUB_CATEGORIES`), and a basket that fills a slot from one of
them is making a sector bet whether or not anyone intended to.
"""

from __future__ import annotations

from app.services.advisor import fund_catalogue, fund_universe
from app.services.screener import serve

# Where gold and silver actually live. AMFI has no Commodity category, so the
# only separator is the fund's name -- see the module docstring.
COMMODITY_CATEGORY = "Other Scheme - FoF Domestic"

# slot key -> (traa category, name keyword or None)
SLOT_CATEGORIES: dict[str, tuple[str, str | None]] = {
    "Equity Index Fund": ("Other Scheme - Index Funds", None),
    "Sectoral/ Thematic": ("Equity Scheme - Sectoral/ Thematic", None),
    "Flexi / Multi::Flexi Cap Fund": ("Equity Scheme - Flexi Cap Fund", None),
    "Commodity::Gold": (COMMODITY_CATEGORY, "gold"),
    "Commodity::Silver": (COMMODITY_CATEGORY, "silver"),
    "Equity Scheme::Large & Mid Cap Fund": ("Equity Scheme - Large & Mid Cap Fund", None),
    "Debt Scheme::Liquid Fund": ("Debt Scheme - Liquid Fund", None),
}

# Repeated onto any basket that fills a slot from one of these, because the
# choice inside them is a sector call rather than a quality one.
SLOT_CAVEATS: dict[str, str] = {
    "Equity Index Fund": serve.CAVEATED_SUB_CATEGORIES["Index Funds"],
    "Sectoral/ Thematic": serve.CAVEATED_SUB_CATEGORIES["Sectoral/ Thematic"],
}


class UnmappedSlot(Exception):
    """A slot key with no traa category behind it.

    Raised rather than returning an empty pool: an empty pool looks exactly like
    "no fund qualified today", which is a market observation, while this is a
    missing line in a table. The two must not be confused.
    """


def codes_for_slot(slot_key: str) -> list[str]:
    """Every catalogue code that could fill this slot, before any scoring.

    Membership only -- eligibility (peer size, NAV freshness, history) is
    `basket.pool_eligibility`'s job, and keeping the two apart means a slot that
    comes back empty can say whether that is because nothing matched or because
    nothing qualified.
    """
    if slot_key not in SLOT_CATEGORIES:
        raise UnmappedSlot(
            f"{slot_key!r} has no traa category. Known slots: "
            f"{sorted(SLOT_CATEGORIES)}"
        )
    category, keyword = SLOT_CATEGORIES[slot_key]

    if keyword == "gold":
        # Reused, not reimplemented. A second definition of "which funds are
        # gold" is how two screens start disagreeing about the same sleeve.
        return [f.code for f in fund_universe.gold_funds()]
    if keyword == "silver":
        return [
            f.code
            for f in fund_catalogue.funds_matching(category, "silver")
        ]
    return [f.code for f in fund_catalogue.all_funds() if f.category == category]


def caveat_for_slot(slot_key: str) -> str | None:
    return SLOT_CAVEATS.get(slot_key)


def slot_sizes() -> dict[str, int]:
    """How many funds sit behind each slot, for a coverage line."""
    return {slot: len(codes_for_slot(slot)) for slot in SLOT_CATEGORIES}
