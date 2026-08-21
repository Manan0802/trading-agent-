"""Everything a stock's own page needs: price history, peers, and the factors.

Modelled on what a real Indian broker's stock page carries -- price chart, day
and 52-week range, a fundamentals grid, sector comparison, similar stocks --
with two things they do not have.

**Every ratio is shown against its sector median, not just P/E.** Brokers print
"Industry P/E" beside P/E and leave P/B, ROE and dividend yield as bare numbers,
which makes them unreadable: a P/B of 7.6 is expensive for a bank and cheap for
a software company. traa has medians for all four, taken across its own NSE
universe. And they are true medians -- an index P/E is market-cap weighted, so
Nifty IT reads near 21 because TCS and Infosys dominate it, and a mid-cap at 30
looks expensive when 30 is the middle of its sector.

**The score is shown as its ten parts, with the sentence each one produced.**
The number on its own is a number. "PE 28.1 vs sector median 42" is the reason.

Prices come from yfinance and are cached in-process, so the first call for a
cold peer set costs a few seconds and later ones are instant. That is the same
arrangement the momentum screen already runs on.
"""

from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date

from app.services.marketdata import stock as stock_data
from app.services.marketdata import stock_universe
from app.services.screener import sector_benchmarks

# Matching the fund page's vocabulary so one control behaves the same on both.
RANGES: dict[str, int | None] = {
    "1m": 30, "6m": 182, "1y": 365, "3y": 1095, "5y": 1826, "max": None,
}
DEFAULT_RANGE = "1y"
CHART_POINTS = 240

# Each peer is a price-history fetch on a cold cache, so the sector line is
# built from a sample. The median of twelve and the median of ninety are the
# same line, and the second costs a slow page.
PEER_SAMPLE = 12
MIN_PEERS_FOR_COMPARISON = 5

# How many similar companies the page lists. Enough to place the stock, few
# enough to read.
SIMILAR_SHOWN = 6

# Peer prices are network-bound, not CPU-bound, so they overlap. Serially this
# page took 10.4 seconds on a cold cache; the same fetches at sixteen workers
# take about a second. Matches `advisor/stock_ranking.py`, which crawls the same
# source at the same width.
_FETCH_WORKERS = 16

# Only fetch as much history as the range needs. A one-year chart was pulling
# ten years of prices for the stock and every peer.
_PERIOD_FOR: dict[str, str] = {
    "1m": "3mo", "6m": "1y", "1y": "1y", "3y": "5y", "5y": "5y", "max": "10y",
}


@dataclass(frozen=True)
class Point:
    date: date
    value: float


@dataclass(frozen=True)
class RatioVsSector:
    key: str
    label: str
    value: float | None
    sector_median: float | None
    # "cheaper" / "dearer" / "higher" / "lower" -- whichever word is right for
    # this ratio, because low P/E is good and low ROE is not.
    verdict: str | None
    better: bool | None


@dataclass(frozen=True)
class SimilarStock:
    ticker: str
    symbol: str
    name: str
    price: float | None
    pe: float | None
    market_cap: float | None


@dataclass(frozen=True)
class StockPage:
    ticker: str
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    price: float | None
    previous_close: float | None
    day_change_pct: float | None
    day_low: float | None
    day_high: float | None
    week52_low: float | None
    week52_high: float | None
    # Where today's price sits between the 52-week low and high, 0 to 1. The
    # single most useful number on a price page and almost nobody prints it.
    position_in_52w: float | None
    volume: int | None
    market_cap: float | None
    range_key: str
    price_series: list[Point]
    sector_series: list[Point]
    peers_compared: int
    ratios: list[RatioVsSector]
    similar: list[SimilarStock]
    benchmark_sector: str
    benchmark_constituents: int


def _window_start(as_of: date, range_key: str) -> date | None:
    days = RANGES.get(range_key, RANGES[DEFAULT_RANGE])
    return None if days is None else date.fromordinal(as_of.toordinal() - days)


def _downsample(points: list[Point], limit: int = CHART_POINTS) -> list[Point]:
    if len(points) <= limit:
        return points
    stride = len(points) / float(limit - 1)
    out = [points[int(i * stride)] for i in range(limit - 1)]
    out.append(points[-1])
    return out


def _closes(ticker: str, start: date | None, period: str = "10y") -> list[tuple[date, float]]:
    return _closes_from(stock_data.get_price_history(ticker, period=period), start)


def _closes_from(frame, start: date | None) -> list[tuple[date, float]]:
    if frame is None or frame.empty or "Close" not in frame:
        return []
    out: list[tuple[date, float]] = []
    for idx, value in frame["Close"].items():
        d = idx.date() if hasattr(idx, "date") else idx
        if start is None or d >= start:
            out.append((d, float(value)))
    return out


def _rebase(series: list[tuple[date, float]]) -> list[Point]:
    if not series or series[0][1] <= 0:
        return []
    base = series[0][1]
    return [Point(d, round(v / base * 100.0, 4)) for d, v in series]


def _sector_median(
    tickers: list[str], start: date | None, period: str = "10y"
) -> list[Point]:
    """The median peer's rebased path, over the dates they share."""
    sample = tickers[:PEER_SAMPLE]
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        fetched = list(pool.map(lambda t: _closes(t, start, period), sample))
    rebased = []
    for series_raw in fetched:
        series = _rebase(series_raw)
        if len(series) >= 2:
            rebased.append({p.date: p.value for p in series})
    if len(rebased) < MIN_PEERS_FOR_COMPARISON:
        return []
    counts: dict[date, int] = {}
    for s in rebased:
        for d in s:
            counts[d] = counts.get(d, 0) + 1
    needed = max(2, int(len(rebased) * 0.6))
    return [
        Point(d, round(statistics.median([s[d] for s in rebased if d in s]), 4))
        for d in sorted(d for d, n in counts.items() if n >= needed)
    ]


# (key, label, lower is better) -- because a low P/E is good news and a low ROE
# is not, and one comparison function cannot know which without being told.
_RATIOS = (
    ("pe", "Price to earnings", "median_pe", True),
    ("pb", "Price to book", "median_pb", True),
    ("roe", "Return on equity", "median_roe", False),
    ("div_yield", "Dividend yield", "median_div_yield", False),
)


def _ratios(fundamentals, benchmark: dict) -> list[RatioVsSector]:
    price, book = fundamentals.price, fundamentals.book_value
    pb = (price / book) if price and book else None
    roe = fundamentals.roe
    if roe is None and pb and fundamentals.pe_ratio:
        # The accounting identity, used because yfinance omits ROE for most
        # Indian names: P/B over P/E is book over earnings inverted, so the
        # price cancels. Checked against every basket stock that does report
        # it, this lands within 2.3 percentage points.
        roe = pb / fundamentals.pe_ratio
    values = {
        "pe": fundamentals.pe_ratio,
        "pb": pb,
        # Held as a percent to match the sector median, which is one.
        "roe": (roe * 100) if roe is not None else None,
        "div_yield": fundamentals.dividend_yield_pct,
    }

    out = []
    for key, label, bench_key, lower_better in _RATIOS:
        value, median = values[key], benchmark.get(bench_key)
        verdict = better = None
        if value is not None and median:
            cheaper = value < median
            better = cheaper if lower_better else not cheaper
            if key in ("pe", "pb"):
                verdict = "cheaper than its sector" if cheaper else "dearer than its sector"
            else:
                verdict = "below its sector" if cheaper else "above its sector"
        out.append(
            RatioVsSector(key, label, round(value, 4) if value is not None else None,
                          median, verdict, better)
        )
    return out


def build(ticker: str, as_of: date, range_key: str = DEFAULT_RANGE) -> StockPage:
    """One stock's page. Raises `StockDataError` if the feed cannot price it."""
    if range_key not in RANGES:
        range_key = DEFAULT_RANGE
    entry = stock_universe.lookup(ticker)
    fundamentals = stock_data.get_stock_fundamentals(ticker)
    sector = fundamentals.sector
    benchmark = sector_benchmarks.resolve(sector)

    start = _window_start(as_of, range_key)
    period = _PERIOD_FOR.get(range_key, "10y")
    own_frame = stock_data.get_price_history(ticker, period=period)
    own = _closes_from(own_frame, start)

    # Same industry, biggest first.
    #
    # Alphabetical order put 360ONE, AUBANK and AADHARHFC beside HDFC Bank,
    # which are in its industry and are not its peers. Index membership is a
    # free size proxy -- the universe already carries it, and reaching for
    # market cap would mean fetching every name in the industry to sort them.
    # NIFTY 50 first, then NIFTY 500, then the rest.
    _INDEX_RANK = {"NIFTY 50": 0, "NIFTY 500": 1}

    def _size_rank(s) -> tuple[int, str]:
        best = min((_INDEX_RANK.get(i, 2) for i in (s.indices or ())), default=2)
        return best, s.name

    peers = sorted(
        (
            s for s in stock_universe.list_stocks()
            if s.ticker != ticker and (entry is None or s.industry == entry.industry)
        ),
        key=_size_rank,
    )
    sector_line = _sector_median([p.ticker for p in peers], start, period)

    # The day's range and volume come off the LAST ROW of the frame already
    # fetched. This used to be a second, separate one-year download of the same
    # stock -- twelve months of prices to read four numbers off the final row.
    day_low = day_high = volume = None
    if own_frame is not None and not own_frame.empty:
        last = own_frame.iloc[-1]
        day_low = float(last.get("Low")) if "Low" in own_frame else None
        day_high = float(last.get("High")) if "High" in own_frame else None
        volume = int(last.get("Volume")) if "Volume" in own_frame else None

    lo, hi = fundamentals.week52_low, fundamentals.week52_high
    position = None
    if lo is not None and hi is not None and hi > lo and fundamentals.price:
        position = round((fundamentals.price - lo) / (hi - lo), 4)

    def _similar(p):
        try:
            pf = stock_data.get_stock_fundamentals(p.ticker)
        except Exception:  # noqa: BLE001 -- one unpriceable peer is not a failure
            return None
        return SimilarStock(p.ticker, p.symbol, p.name, pf.price, pf.pe_ratio, pf.market_cap)

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        similar = [s for s in pool.map(_similar, peers[:SIMILAR_SHOWN]) if s]

    return StockPage(
        ticker=ticker,
        symbol=getattr(entry, "symbol", ticker.replace(".NS", "")),
        name=fundamentals.name,
        sector=sector,
        industry=fundamentals.industry,
        price=fundamentals.price,
        previous_close=fundamentals.previous_close,
        day_change_pct=fundamentals.day_change_pct,
        day_low=day_low,
        day_high=day_high,
        week52_low=lo,
        week52_high=hi,
        position_in_52w=position,
        volume=volume,
        market_cap=fundamentals.market_cap,
        range_key=range_key,
        price_series=_downsample(_rebase(own)),
        sector_series=_downsample(sector_line),
        peers_compared=min(len(peers), PEER_SAMPLE) if sector_line else 0,
        ratios=_ratios(fundamentals, benchmark),
        similar=similar,
        benchmark_sector=sector if sector in sector_benchmarks.sectors()
        else sector_benchmarks.ALL_STOCKS,
        benchmark_constituents=int(benchmark.get("constituents", 0)),
    )
