"""Whether a holding's price is actually current, or quietly frozen.

`get_current_price` returns the last NAV in a scheme's series, whatever its
date. That is right almost always -- NAVs publish around 11 PM IST, so
yesterday's is today's answer. It is wrong in exactly one case, and that case
is silent: when a scheme merges, winds up, or drops out of the feed, the series
stops and the same NAV is returned forever. The portfolio keeps showing a value
as though it were live.

**The rule calibrates against the portfolio itself rather than the calendar.**
A fixed "older than N days is stale" threshold has to be loose enough to survive
Diwali and a long weekend, which makes it too loose to catch anything that
matters for a week or more. But if one fund published yesterday and another has
not published in three weeks, the second one is stale no matter what the holiday
calendar says -- the market was clearly open. Comparing holdings to each other
removes the holiday problem entirely instead of tolerating it.

A single holding has nothing to compare against, so it falls back to a calendar
threshold, chosen loose on purpose: a false "your data is stale" teaches the
owner to ignore the warning, which costs more than the rare late catch.
"""
from __future__ import annotations

from datetime import date

# How far behind the freshest holding a price may fall before it is worth
# saying so. Four covers a Friday NAV read on a Tuesday after a long weekend.
BEHIND_PEERS_DAYS = 4

# Used only when there is nothing to compare against. Two weeks is far past any
# Indian market closure, so reaching this means the feed stopped, not a holiday.
ALONE_DAYS = 14


def stale_days(
    price_date: date | None,
    *,
    peer_dates: list[date],
    today: date,
) -> int | None:
    """Days this price is behind, or None when it is as current as it can be.

    `peer_dates` is every other priced holding's date, the caller's own
    portfolio. Pass an empty list when there are none.
    """
    if price_date is None:
        return None

    behind = (today - price_date).days
    if behind <= 0:
        return None

    others = [d for d in peer_dates if d != price_date]
    if others:
        gap = (max(others) - price_date).days
        return gap if gap > BEHIND_PEERS_DAYS else None

    return behind if behind >= ALONE_DAYS else None
