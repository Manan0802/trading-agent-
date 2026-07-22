"""The browsable set of NSE-listed stocks, read from the committed catalogue.

Built by scripts/build_stock_universe.py from NSE's own index constituent
files. Held in memory because it is a few hundred kilobytes that changes twice
a year, and reading it per request to filter a list would be the slowest part
of an otherwise instant endpoint.

Nothing here touches the network. Live prices and fundamentals come from
marketdata/stock.py, and only for a stock the user has actually opened,
because 751 yfinance calls to render a list is not a page anyone waits for.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_CATALOGUE = Path(__file__).resolve().parent.parent.parent / "data" / "stock_universe.json"

# Narrowest first: this is the order the filter control offers, and the first
# entry is the sensible default for someone who does not know where to start.
INDEX_CHOICES = ["NIFTY 50", "NIFTY 500", "NIFTY TOTAL MARKET"]


@dataclass(frozen=True)
class UniverseStock:
    ticker: str
    symbol: str
    name: str
    industry: str | None
    isin: str | None
    indices: tuple[str, ...]


@lru_cache(maxsize=1)
def _all() -> tuple[UniverseStock, ...]:
    raw = json.loads(_CATALOGUE.read_text())
    return tuple(
        UniverseStock(
            ticker=s["ticker"],
            symbol=s["symbol"],
            name=s["name"],
            industry=s.get("industry"),
            isin=s.get("isin"),
            indices=tuple(s.get("indices", [])),
        )
        for s in raw
    )


@lru_cache(maxsize=1)
def _by_symbol() -> dict[str, UniverseStock]:
    return {s.symbol: s for s in _all()}


def lookup(symbol_or_ticker: str) -> UniverseStock | None:
    """Accepts either form, because the portfolio stores the suffixed ticker."""
    key = (symbol_or_ticker or "").strip().upper().removesuffix(".NS")
    return _by_symbol().get(key)


def industries() -> list[str]:
    return sorted({s.industry for s in _all() if s.industry})


def list_stocks(
    index: str | None = None,
    industry: str | None = None,
    query: str | None = None,
    limit: int | None = None,
) -> list[UniverseStock]:
    """Filter the catalogue. An unrecognised index yields nothing rather than
    everything, so a typo in the filter cannot look like a successful search."""
    results = list(_all())

    if index:
        results = [s for s in results if index in s.indices]
    if industry:
        results = [s for s in results if s.industry == industry]
    if query:
        # Company name as well as symbol: nobody remembers that Larsen &
        # Toubro trades as LT.
        needle = query.strip().lower()
        results = [
            s
            for s in results
            if needle in s.symbol.lower() or needle in s.name.lower()
        ]
    return results[:limit] if limit else results
