"""The set of funds NexTrade will consider recommending for a goal.

Derived from the committed catalogue rather than hand-picked. The previous
version listed sixteen scheme codes typed in by hand across three categories,
which is why the app only ever surfaced Flexi Cap, Corporate Bond and gold.

Only scheme codes are stored here. Names and categories are always read from
the live API, because a hand-written label drifts from the scheme it points at
and a mislabelled code would silently recommend the wrong fund.
"""

from app.services.advisor.fund_catalogue import codes_for_category, funds_matching

# The SEBI category each asset class allocates to. One category per class, so
# a goal's equity sleeve is a peer group and not a mixture of large caps and
# small caps ranked against each other.
ASSET_CLASS_CATEGORY = {
    "equity": "Equity Scheme - Flexi Cap Fund",
    "debt": "Debt Scheme - Corporate Bond Fund",
}

# Gold is not a SEBI category. Gold fund-of-funds sit inside "Other Scheme -
# FoF Domestic" next to overseas-equity and silver FoFs, so filtering by
# category alone would offer a Nasdaq tracker as the gold sleeve. Silver is
# excluded too: a gold-and-silver fund is a different exposure from the one
# the allocation asked for.
_GOLD_CATEGORY = "Other Scheme - FoF Domestic"


def gold_funds() -> list:
    """Gold fund-of-funds, as catalogue entries.

    Silver is excluded as well: a gold-and-silver fund is a different exposure
    from the one the allocation asked for.
    """
    return [
        f
        for f in funds_matching(_GOLD_CATEGORY, "gold")
        if "silver" not in f.name.lower()
    ]


def _gold_codes() -> list[str]:
    return [f.code for f in gold_funds()]


UNIVERSE: dict[str, list[str]] = {
    "equity": codes_for_category(ASSET_CLASS_CATEGORY["equity"]),
    "debt": codes_for_category(ASSET_CLASS_CATEGORY["debt"]),
    "gold": _gold_codes(),
}

# UTI Nifty 50 Index Fund (Direct, Growth). An index fund's NAV is used as the
# total-return benchmark because it already includes dividends, unlike the
# headline Nifty 50 price index.
BENCHMARK_SCHEME_CODE = "120716"

BENCHMARK_NAME = "Nifty 50"

# The textbook benchmark for a Flexi Cap fund is the Nifty 500, which includes
# the mid and small caps these funds actually hold. No Nifty 500 index fund on
# our data source has more than two years of NAV history (checked 2026-07-20:
# the oldest, Axis, launched 2024-07), and three-year rolling windows need far
# more than that. So the Nifty 50 stands in.
#
# The cost is measured, not assumed: over the two years where both exist, using
# the Nifty 50 flatters every Flexi Cap fund's alpha by 1.0-1.7 percentage
# points. Because the bias lands on all of them at once it barely moves the
# ranking, but the alpha figure shown to a user is optimistic and must be
# labelled as such.
BENCHMARK_CAVEAT = (
    "Measured against the Nifty 50, which holds only large caps. Flexi Cap "
    "funds also hold mid and small caps, so alpha here reads about 1-1.7 "
    "percentage points higher than it would against the Nifty 500, the "
    "textbook benchmark, which has no index fund old enough to use yet."
)

# Only equity is measured against the Nifty. Judging a gold or corporate bond
# fund against an equity index produces numbers that look damning but mean
# nothing — those funds are not trying to track equities. They are ranked on
# their own risk-adjusted record instead.
BENCHMARK_BY_ASSET_CLASS: dict[str, str | None] = {
    "equity": BENCHMARK_SCHEME_CODE,
    "debt": None,
    "gold": None,
}


# Which equity categories the Nifty 50 can honestly measure, and what has to be
# said out loud when it cannot. The old code had one caveat string written for
# Flexi Cap and applied it everywhere, which both overstated the problem for
# large caps and badly understated it for small caps.
_LARGE_CAP = "Equity Scheme - Large Cap Fund"

_BROAD_EQUITY_CAVEAT = (
    "Measured against the Nifty 50, which holds only large caps. Funds in this "
    "category also hold mid and small caps, so alpha here reads about 1-1.7 "
    "percentage points higher than it would against the Nifty 500, the "
    "textbook benchmark, which has no index fund old enough to use yet."
)

_SMALL_CAP_CAVEAT = (
    "Measured against the Nifty 50, which holds only large caps. A small-cap "
    "fund earns much of its return from the size premium, and against a "
    "large-cap index that premium is credited to the manager. Read the alpha "
    "here as a rough sanity check, not as evidence of skill."
)

_MID_CAP_CAVEAT = (
    "Measured against the Nifty 50, which holds only large caps. A mid-cap "
    "fund takes more risk than that index, so part of the alpha shown here is "
    "payment for risk rather than manager skill."
)

# An explicit allowlist rather than a default, because a category we have not
# thought about would otherwise be handed whichever caveat happened to be the
# fallback, which is a guess presented as a disclosure. The catalogue currently
# holds ten equity categories and every one of them is listed here.
_CATEGORY_CAVEATS: dict[str, str | None] = {
    _LARGE_CAP: None,
    "Equity Scheme - Large & Mid Cap Fund": _MID_CAP_CAVEAT,
    "Equity Scheme - Mid Cap Fund": _MID_CAP_CAVEAT,
    "Equity Scheme - Small Cap Fund": _SMALL_CAP_CAVEAT,
    "Equity Scheme - Flexi Cap Fund": _BROAD_EQUITY_CAVEAT,
    # Multi Cap is mandated to hold at least 25% each of large, mid and small,
    # so it carries more small-cap exposure than a flexi cap typically does.
    "Equity Scheme - Multi Cap Fund": _BROAD_EQUITY_CAVEAT,
    "Equity Scheme - Focused Fund": _BROAD_EQUITY_CAVEAT,
    "Equity Scheme - Value Fund": _BROAD_EQUITY_CAVEAT,
    "Equity Scheme - ELSS": _BROAD_EQUITY_CAVEAT,
}

# Categories that are equity but where an alpha figure would mislead whatever
# caveat sat beside it. A sector fund beating the Nifty says the sector ran; an
# index fund's "alpha" is tracking error under a flattering name.
_NOT_BENCHMARKABLE = (
    "Sectoral",
    "Thematic",
    "Index Fund",
    "ETF",
)


def benchmark_for_category(category: str) -> tuple[str | None, str | None]:
    """The benchmark scheme code for a category, and the caveat it demands.

    Returns (None, None) for anything the Nifty 50 cannot honestly measure,
    because a meaningless alpha is worse than no alpha.
    """
    if not category.startswith("Equity Scheme - "):
        return None, None
    if any(marker in category for marker in _NOT_BENCHMARKABLE):
        return None, None
    if category not in _CATEGORY_CAVEATS:
        return None, None
    return BENCHMARK_SCHEME_CODE, _CATEGORY_CAVEATS[category]
