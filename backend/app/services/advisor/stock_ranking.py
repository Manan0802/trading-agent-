"""Ranking a whole index against itself, rather than one company at a time.

Until now a stock was only ever scored when the user opened it, which quietly
made the screen useless: a score of 74 means nothing without knowing what the
other 500 companies scored. A screen has to rank, or it is a lookup tool
wearing a screen's clothes.

Two costs shape the design.

**Yahoo has no bulk endpoint.** Every company is its own request, and the
prior-year EPS needs a second, slower one. Fetching is therefore concurrent and
cached to disk; see marketdata/stock.py.

**Coverage is finite and must be stated.** Ranking the NIFTY 500 cold is
hundreds of requests, so the caller passes a limit and the result says exactly
how many companies were covered and how many were not. A screen that silently
ranks the first 50 of 751 and presents them as "the best" is lying by
omission — the same failure as a fund list that hides the funds it could not
price.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.services.advisor.stock_analysis import sector_benchmarks
from app.services.advisor.stock_score import StockInputs, StockScore, score_stock
from app.services.marketdata import stock as stock_data
from app.services.marketdata.stock_universe import UniverseStock

# Yahoo tolerates this comfortably and the work is entirely network latency.
# Higher mostly buys rate-limiting.
_FETCH_WORKERS = 16

# Promoter shareholding is scraped per company from a second site. At index
# scale that doubles the request count for an adjustment worth at most six
# points, so the ranked screen skips it and the company page still applies it.
_WITH_PROMOTER = False


@dataclass(frozen=True)
class RankedStock:
    rank: int
    score: StockScore


@dataclass(frozen=True)
class UnscorableStock:
    ticker: str
    name: str
    reason: str


@dataclass(frozen=True)
class StockRanking:
    label: str
    ranked: list[RankedStock]
    unscorable: list[UnscorableStock]
    # How many companies matched the filter, against how many we actually
    # priced. Surfaced so the page can say "50 of 751" rather than imply 751.
    matched: int
    covered: int


def _inputs_for(entry: UniverseStock) -> StockInputs:
    """Fetch one company's fundamentals. Raises if Yahoo has no usable price."""
    f = stock_data.get_stock_fundamentals(entry.ticker)
    return StockInputs(
        ticker=f.ticker,
        # The catalogue name is NSE's official one and reads better than
        # Yahoo's, which abbreviates inconsistently.
        name=entry.name or f.name,
        sector=f.sector,
        price=f.price,
        pe=f.pe_ratio,
        pb=f.price / f.book_value if f.book_value else None,
        roe=f.roe,
        dividend_yield=(
            f.dividend_yield_pct / 100 if f.dividend_yield_pct is not None else None
        ),
        # The statement's own latest year, not .info's TTM: the growth
        # factor divides these two and they must come from one source.
        eps_ttm=f.eps_reported,
        eps_prev=f.eps_previous_year,
        week52_high=f.week52_high,
        week52_low=f.week52_low,
        promoter_history=[],
    )


def rank_stocks(
    label: str,
    entries: list[UniverseStock],
    *,
    limit: int = 50,
) -> StockRanking:
    """Score every company in `entries` up to `limit`, best first.

    Ties break on ticker rather than arbitrarily, so the same universe always
    produces the same order and a user comparing two visits is not looking at
    noise.
    """
    matched = len(entries)
    selected = entries[:limit]
    if not selected:
        return StockRanking(
            label=label, ranked=[], unscorable=[], matched=matched, covered=0
        )

    benchmarks = sector_benchmarks()

    def load(entry: UniverseStock):
        try:
            return entry, _inputs_for(entry), None
        except stock_data.StockDataError as exc:
            return entry, None, str(exc)
        except Exception as exc:  # noqa: BLE001
            # yfinance raises a wide and undocumented set of its own. One
            # company Yahoo has indigestion over must not empty the screen.
            return entry, None, f"Could not read fundamentals: {exc}"

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        loaded = list(pool.map(load, selected))

    scored: list[StockScore] = []
    unscorable: list[UnscorableStock] = []
    for entry, inputs, error in loaded:
        if inputs is None:
            unscorable.append(
                UnscorableStock(ticker=entry.ticker, name=entry.name, reason=error or "")
            )
            continue
        scored.append(score_stock(inputs, benchmarks))

    scored.sort(key=lambda s: (-s.total, s.ticker))
    return StockRanking(
        label=label,
        ranked=[RankedStock(rank=i, score=s) for i, s in enumerate(scored, start=1)],
        unscorable=unscorable,
        matched=matched,
        covered=len(scored),
    )
