"""Ranking the stock universe with the ported scorer.

The bridge, and nothing more. Every piece it needs already exists:
`marketdata/stock_universe.py` holds the NSE universe and index membership,
`marketdata/stock.py` fetches fundamentals and price history with its own
caches, `sector_benchmarks.py` supplies the peer medians in the units the
factors compare against, and `stock_scoring.py` is the arithmetic.

**Units are the whole risk here, and they are not uniform on either side.**
Written out because a wrong mapping produces a full, plausible ranking and
errors nowhere:

    traa's StockFundamentals        the port's Fundamentals
    ------------------------------  ------------------------------
    pe_ratio                        trailing_pe        (unchanged)
    price / book_value              price_to_book      (derived; traa stores
                                                        book value per share,
                                                        not the ratio)
    roe            decimal 0.18     roe                decimal  (unchanged --
                                                        _score_roe multiplies
                                                        by 100 itself)
    dividend_yield_pct  5.14 = 5.14%  div_yield        percent  (unchanged)
    eps_reported                    eps_ttm            two full years off the
    eps_previous_year               eps_prev           income statement, not
                                                        .info's TTM figure

Note `roe` stays a decimal while the *benchmark's* median_roe is a percent.
That asymmetry is upstream's and `_score_roe` reconciles it internally; making
both sides percentages would silently multiply every company's ROE by a
hundred.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.services.marketdata import stock as stock_data
from app.services.marketdata import stock_universe
from app.services.screener import plain_words, sector_benchmarks, stock_scoring

# Matches `advisor/stock_ranking.py`, which crawls the same universe from the
# same source at the same settings.
_FETCH_WORKERS = 16

# Two years of daily closes is ~500 rows, comfortably past the 200 the longest
# indicator window needs, without pulling a decade for a momentum reading.
_HISTORY_PERIOD = "2y"

# Delivery percentage has one source, NSE's `quote-equity` endpoint, and it
# returns 403 -- verified again on 2026-08-21. `_score_delivery(None)` therefore
# awards its neutral half, so 4.5 of every 100 points is a constant for every
# stock, forever. Passed explicitly rather than left to default, so the screen's
# disclosure and this line move together.
DELIVERY_UNAVAILABLE = None
DELIVERY_NOTE = (
    "Delivery volume is 9 of the 100 points and the exchange will not serve it, "
    "so every stock scores the same neutral half on it."
)


@dataclass(frozen=True)
class ScoredStock:
    ticker: str
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    total: float
    bucket: str
    fundamental: float
    technical: float
    factors: list[dict]
    adjustments: list[dict]
    price: float | None
    thin_history: bool
    benchmark_sector: str
    benchmark_constituents: int


@dataclass(frozen=True)
class UnscorableStock:
    ticker: str
    symbol: str
    name: str
    reason: str


def _to_port_fundamentals(f, sector: str | None, industry: str | None) -> dict:
    """traa's record in the shape the ported factors read. See the module docstring."""
    price_to_book = None
    if f.price and f.book_value:
        try:
            price_to_book = float(f.price) / float(f.book_value)
        except ZeroDivisionError:
            price_to_book = None
    return {
        "trailing_pe": f.pe_ratio,
        "price_to_book": price_to_book,
        "roe": f.roe,
        "div_yield": f.dividend_yield_pct,
        "eps_ttm": f.eps_reported,
        "eps_prev": f.eps_previous_year,
        "current_price": f.price,
        "name": f.name,
        "sector": sector,
        "industry": industry,
        "insider_pct": None,
    }


def _score_one(entry) -> ScoredStock | UnscorableStock:
    """One stock, end to end. Never raises -- one bad ticker must not fail a screen."""
    unscorable = lambda why: UnscorableStock(  # noqa: E731
        ticker=entry.ticker, symbol=entry.symbol, name=entry.name, reason=why
    )
    try:
        fundamentals = stock_data.get_stock_fundamentals(entry.ticker)
    except stock_data.StockDataError as exc:
        # Only the feed's own error. Deliberately NOT `except Exception`.
        #
        # The first version of this function caught everything, so a misspelled
        # function name came back as "fundamentals unavailable" for all twelve
        # stocks -- which reads exactly like yfinance being down, and cost real
        # time before anyone looked closer. An AttributeError here is a bug in
        # this file and must reach the caller as one.
        #
        # A re-raise clause for those was tried and removed: with no broad catch
        # below it, it changed nothing, and a sabotage pass proved it. A guard
        # that cannot be turned off is not a guard, it is a comment.
        return unscorable(f"fundamentals unavailable: {exc}")

    frame = stock_data.get_price_history(entry.ticker, period=_HISTORY_PERIOD)
    closes = None if frame is None else frame.get("Close")
    if closes is None or len(closes) == 0:
        return unscorable("no price history")

    sector = fundamentals.sector
    port_record = _to_port_fundamentals(fundamentals, sector, fundamentals.industry)

    ok, why = stock_scoring.is_scoreable(closes, port_record)
    if not ok:
        return unscorable(why)

    benchmark = sector_benchmarks.resolve(sector)
    try:
        result = stock_scoring.score_stock(
            port_record, closes, benchmark, delivery_pct=DELIVERY_UNAVAILABLE
        )
    except Exception as exc:  # noqa: BLE001
        return unscorable(f"could not be scored: {type(exc).__name__}")

    # Belt to `is_scoreable`'s braces: a NaN total clamps UP to 100.0 rather
    # than to zero, because `nan < 100.0` is False. See stock_scoring.
    if stock_scoring.is_meaningless(result):
        return unscorable(
            "the score came out meaningless, which happens when an indicator "
            "has too little history to produce a number"
        )

    return ScoredStock(
        ticker=entry.ticker,
        symbol=entry.symbol,
        name=entry.name,
        sector=sector,
        industry=fundamentals.industry,
        total=round(float(result["total"]), 2),
        bucket=str(result.get("bucket", "")),
        fundamental=round(float(result.get("fundamental") or 0.0), 2),
        technical=round(float(result.get("technical") or 0.0), 2),
        # The gloss is attached here rather than in either router, so the
        # expanded row on the table and the company's own page cannot end up
        # explaining the same factor differently.
        factors=[
            {**f, "plain": plain_words.factor_gloss(f.get("key", ""))}
            for f in result.get("factors", [])
        ],
        adjustments=list(result.get("adjustments", [])),
        price=fundamentals.price,
        thin_history=stock_scoring.thin_history(closes),
        benchmark_sector=sector if sector in sector_benchmarks.sectors() else
                         sector_benchmarks.ALL_STOCKS,
        benchmark_constituents=int(benchmark.get("constituents", 0)),
    )


def rank_entries(entries) -> tuple[list, list]:
    """Score the stocks given and return them ranked, plus what could not be.

    Takes the entries rather than a filter, because the caller has already
    applied one and re-deriving the universe here would apply it twice.

    Returns `(scored, unscorable)`. Every stock offered appears in exactly one
    of the two, because a screen that silently drops names is indistinguishable
    from one that lost them.
    """
    entries = list(entries)
    if not entries:
        return [], []

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        results = list(pool.map(_score_one, entries))

    scored = [r for r in results if isinstance(r, ScoredStock)]
    unscorable = [r for r in results if isinstance(r, UnscorableStock)]
    # Ties break on ticker rather than arbitrarily, matching the Research page's
    # ranking, so the same universe always comes back in the same order and
    # someone comparing two visits is not looking at noise.
    scored.sort(key=lambda s: (-s.total, s.ticker))
    return scored, unscorable


def rank(index: str | None = None, limit: int | None = None) -> tuple[list, list]:
    """Convenience wrapper for scripts and smoke tests. The router uses
    `rank_entries`, because it has already filtered."""
    universe = stock_universe.list_stocks(index=index) if index else stock_universe.list_stocks()
    return rank_entries(universe[:limit] if limit else universe)
