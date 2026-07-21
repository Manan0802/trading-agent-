"""The curated set of funds NexTrade will consider recommending.

Only scheme codes are stored. Names and categories are always read from the
live API, because a hand-written label drifts from the scheme it points at —
scheme codes are not guessable from a fund's name, and a mislabelled code
would silently recommend the wrong fund.

Every code below was verified to be Direct-Growth, in the stated SEBI
category, and still publishing NAVs. Re-run scripts/verify_universe.py after
editing: funds do get merged or wound up (Tata Corporate Bond and Canara
Robeco Gold Savings were both dropped here for going stale).
"""

# Equity Scheme - Flexi Cap Fund
EQUITY_FLEXI_CAP = [
    "122639",  # Parag Parikh
    "118955",  # HDFC
    "120564",  # Aditya Birla Sun Life
    "120166",  # Kotak
    "120843",  # quant
    "118535",  # Franklin India
    "118275",  # Canara Robeco
    "133839",  # PGIM India
    "120492",  # JM
]

# Debt Scheme - Corporate Bond Fund
DEBT_CORPORATE_BOND = [
    "118987",  # HDFC
    "118814",  # Nippon India
    "119533",  # Aditya Birla Sun Life
    "119621",  # Sundaram
]

# Other Scheme - FoF Domestic (gold fund-of-funds)
GOLD = [
    "118663",  # Nippon India Gold Savings
    "119788",  # SBI Gold
    "119781",  # Kotak Gold
]

UNIVERSE: dict[str, list[str]] = {
    "equity": EQUITY_FLEXI_CAP,
    "debt": DEBT_CORPORATE_BOND,
    "gold": GOLD,
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
    "percentage points higher than it would against the Nifty 500 — the "
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
