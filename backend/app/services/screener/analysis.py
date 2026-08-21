"""Everything a fund's own page needs, drawn from the local NAV store.

Five million NAV rows sit on disk covering 2006 to today, so every chart here
is a read rather than a fetch. Nothing in this module touches the network, and
the clock arrives as `as_of`.

Three choices worth knowing about, because each one is the difference between a
chart that informs and a chart that flatters:

**Everything is rebased to 100 at the start of the window.** A fund at NAV 12
and a fund at NAV 890 are not comparable as levels; rebasing makes the shapes
comparable and is what "growth of 10,000" means on every fund page in the
country.

**The comparison line is the fund's own category, not the Nifty.** Judging a
liquid fund or a gold fund against an equity index says nothing except that
equity and gold are different things. The median peer is rebuilt the same way
over the same dates, so the two lines answer one question: did this fund beat
the funds it actually competes with.

**Drawdown is shown as its own series, not as a number.** "Worst fall 24%" is a
fact about one day. The shape shows how long the fund spent underwater, which is
what a person actually lives through.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from app.services.screener import metrics as metrics_mod
from app.services.screener import navstore

# What the range buttons offer, in calendar days. `max` is the fund's whole
# history. Matching the ranges every Indian fund page uses, so the control is
# familiar rather than clever.
RANGES: dict[str, int | None] = {
    "1m": 30,
    "6m": 182,
    "1y": 365,
    "3y": 1095,
    "5y": 1826,
    "max": None,
}
DEFAULT_RANGE = "1y"

# A chart is a few hundred pixels wide. Sending 5,000 points draws the same line
# and costs the reader a slower page; traa's research router already made this
# call at 180 for the same reason.
CHART_POINTS = 240

# Below this a "median peer" is one or two funds wearing the word median, so the
# comparison line is withheld rather than drawn. Same floor the screen uses
# before it will publish a category's leaders.
MIN_PEERS_FOR_COMPARISON = 8

# Peers are sampled rather than fully loaded: the median of 40 funds and the
# median of 364 are the same line to two decimal places, and the second costs a
# third of a second of disk reads on every page view.
PEER_SAMPLE = 40


@dataclass(frozen=True)
class Point:
    date: date
    value: float


@dataclass(frozen=True)
class FundAnalysis:
    scheme_code: str
    range_key: str
    start: date | None
    end: date | None
    # All three rebased to 100 at `start`, so they can share one axis.
    nav: list[Point]
    peer_median: list[Point]
    # Percent below the running peak, always <= 0.
    drawdown: list[Point]
    # Cumulative return over the window, as a fraction.
    total_return: float | None
    peer_total_return: float | None
    peers_compared: int
    # True when the fund is younger than the range asked for, so both lines were
    # clipped to the fund's own history. The screen has to say so, or a reader
    # compares a 15-month record against a 3-year one.
    clipped_to_fund_history: bool
    nav_points_available: int
    first_nav_date: date | None
    latest_nav: float | None
    latest_nav_date: date | None


def _window_start(as_of: date, range_key: str) -> date | None:
    days = RANGES.get(range_key, RANGES[DEFAULT_RANGE])
    return None if days is None else date.fromordinal(as_of.toordinal() - days)


def downsample(points: list[Point], limit: int = CHART_POINTS) -> list[Point]:
    """Thin a series to at most `limit` points, keeping both ends.

    Stride sampling rather than averaging: an average would smooth away the
    single-day drop that a drawdown chart exists to show. The last point is
    always kept, because the most recent NAV is the one a reader checks against
    everywhere else on the page.
    """
    if len(points) <= limit:
        return points
    stride = len(points) / float(limit - 1)
    picked = [points[int(i * stride)] for i in range(limit - 1)]
    picked.append(points[-1])
    return picked


def _rebase(navs: list[tuple[date, float]]) -> list[Point]:
    """NAV levels to growth of 100 from the first day in the window."""
    if not navs:
        return []
    base = navs[0][1]
    if base <= 0:
        return []
    return [Point(d, round(v / base * 100.0, 4)) for d, v in navs]


def _drawdown(navs: list[tuple[date, float]]) -> list[Point]:
    """How far below its own running peak the fund is, on each day."""
    out: list[Point] = []
    peak = float("-inf")
    for d, v in navs:
        peak = max(peak, v)
        out.append(Point(d, round((v / peak - 1.0) * 100.0, 4) if peak > 0 else 0.0))
    return out


def _peer_median(session, codes: list[str], start: date | None, end: date) -> list[Point]:
    """The median peer's rebased path, over the dates the peers actually share.

    Each peer is rebased on its own first day in the window before the median is
    taken. Taking the median of raw NAVs instead would produce a line dominated
    by whichever fund happens to have the largest unit price, which is a fact
    about a fund's launch price and nothing else.
    """
    series: list[dict[date, float]] = []
    for code in codes[:PEER_SAMPLE]:
        navs = navstore.nav_window(session, code, start=start, end=end)
        rebased = _rebase(navs)
        if len(rebased) >= 2:
            series.append({p.date: p.value for p in rebased})
    if len(series) < MIN_PEERS_FOR_COMPARISON:
        return []

    # Only dates most peers actually have. A date one fund published on is not a
    # median of anything, and including it makes the line jump.
    counts: dict[date, int] = {}
    for s in series:
        for d in s:
            counts[d] = counts.get(d, 0) + 1
    # Deliberately NOT floored at MIN_PEERS_FOR_COMPARISON. Doing that made this
    # line secretly enforce the peer-count rule as well as the date-coverage
    # rule, so removing the explicit count check above changed nothing and a
    # sabotage of it walked through. Two rules, two places.
    needed = max(2, int(len(series) * 0.6))
    shared = sorted(d for d, n in counts.items() if n >= needed)

    return [
        Point(d, round(statistics.median([s[d] for s in series if d in s]), 4))
        for d in shared
    ]


def analyse(
    session,
    scheme_code: str,
    peers: list[str],
    as_of: date,
    range_key: str = DEFAULT_RANGE,
) -> FundAnalysis:
    """One fund's chart data. `peers` are the other funds in its category."""
    if range_key not in RANGES:
        range_key = DEFAULT_RANGE
    start = _window_start(as_of, range_key)

    everything = navstore.nav_window(session, scheme_code)
    navs = [(d, v) for d, v in everything if start is None or d >= start]

    rebased = downsample(_rebase(navs))
    drawdown = downsample(_drawdown(navs))

    # The peer line starts on the fund's OWN first day, not the window's.
    #
    # Without this the two lines cover different periods and the chart lies. A
    # fifteen-month-old silver fund asked for "3 years" draws fifteen months of
    # itself against three years of its peers: measured, +128.8% against
    # +156.7%, which reads as underperformance when over every day they actually
    # share it is +100.3% against +56.3%. Same axis, same rebase point, or no
    # comparison at all.
    comparison_start = navs[0][0] if navs else start
    peer = downsample(
        _peer_median(
            session, [c for c in peers if c != scheme_code], comparison_start, as_of
        )
    )

    def total(points: list[Point]) -> float | None:
        return None if len(points) < 2 else round(points[-1].value / 100.0 - 1.0, 6)

    return FundAnalysis(
        scheme_code=scheme_code,
        range_key=range_key,
        start=navs[0][0] if navs else None,
        end=navs[-1][0] if navs else None,
        nav=rebased,
        peer_median=peer,
        drawdown=drawdown,
        total_return=total(rebased),
        peer_total_return=total(peer),
        peers_compared=min(len(peers), PEER_SAMPLE) if peer else 0,
        clipped_to_fund_history=bool(
            start is not None and navs and navs[0][0] > start
        ),
        nav_points_available=len(navs),
        first_nav_date=everything[0][0] if everything else None,
        latest_nav=everything[-1][1] if everything else None,
        latest_nav_date=everything[-1][0] if everything else None,
    )


def rolling_returns(
    session, scheme_code: str, as_of: date, window_days: int = 365
) -> dict:
    """What a person actually got, entering on any day and holding a year.

    A single "1-year return" is one entry date's luck. This is every entry date
    in the fund's history, which is the honest version of the same question and
    the one that shows whether a good number was typical or a lucky window.
    """
    navs = navstore.nav_window(session, scheme_code)
    if len(navs) < 60:
        return {"windows": 0, "best": None, "worst": None, "median": None,
                "positive_share": None, "window_days": window_days}

    by_date = {d: v for d, v in navs}
    dates = [d for d, _ in navs]
    results: list[float] = []
    for d, v in navs:
        target = date.fromordinal(d.toordinal() + window_days)
        if target > dates[-1]:
            break
        later = next((x for x in dates if x >= target), None)
        if later is None or v <= 0:
            continue
        results.append(by_date[later] / v - 1.0)

    if not results:
        return {"windows": 0, "best": None, "worst": None, "median": None,
                "positive_share": None, "window_days": window_days}
    return {
        "windows": len(results),
        "best": round(max(results), 6),
        "worst": round(min(results), 6),
        "median": round(statistics.median(results), 6),
        "positive_share": round(sum(1 for r in results if r > 0) / len(results), 4),
        "window_days": window_days,
    }
