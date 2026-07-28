"""Indian listed-equity data via yfinance (NSE tickers use a .NS suffix).

Yahoo's endpoint is unofficial and coverage thins out for small caps, so every
field except the price is treated as optional. A ticker Yahoo does not know
comes back as a near-empty dict rather than an error, which we turn into an
explicit StockDataError so callers never get a priceless holding.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yfinance as yf

_CACHE_TTL_SECONDS = 15 * 60  # prices move intraday; fundamentals barely do

# Yahoo has no bulk endpoint: every company costs its own request, and ranking
# an index means hundreds of them. In memory alone that bill is paid again after
# every restart, so it is also written to disk. The TTL is longer here than the
# in-memory one on purpose — a screen is ranked on earnings and book value,
# which move once a quarter, and refetching 751 companies to freshen a price
# nobody is trading on would be work for its own sake.
_DISK_CACHE_TTL_SECONDS = 12 * 60 * 60
_DISK_CACHE_DIR = Path(
    os.environ.get(
        "NEXTRADE_STOCK_CACHE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent / ".stockcache",
    )
)

_cache: dict[str, tuple[float, Any]] = {}


class StockDataError(Exception):
    """Raised when a ticker is unknown or has no usable price."""


@dataclass(frozen=True)
class StockFundamentals:
    ticker: str
    name: str
    price: float
    previous_close: float | None
    currency: str
    sector: str | None
    industry: str | None
    market_cap: float | None
    pe_ratio: float | None
    eps: float | None
    book_value: float | None
    dividend_yield_pct: float | None
    week52_high: float | None
    week52_low: float | None
    # Return on equity, as a fraction. yfinance publishes it directly.
    roe: float | None = None
    # The last two full years of diluted EPS, both off the income statement.
    # `eps` above is .info's trailing-twelve-months figure and is what to show
    # a reader; these two are what the growth comparison must use, because a
    # ratio built from two different sources can straddle two currencies.
    eps_reported: float | None = None
    eps_previous_year: float | None = None

    @property
    def day_change_pct(self) -> float | None:
        if not self.previous_close:
            return None
        return (self.price - self.previous_close) / self.previous_close * 100


def clear_cache() -> None:
    _cache.clear()
    try:
        for entry in _DISK_CACHE_DIR.glob("*.json"):
            entry.unlink()
    except OSError:
        # Nothing here is authoritative, so a cache we cannot clear is a
        # nuisance rather than a failure.
        pass


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return _DISK_CACHE_DIR / f"{digest}.json"


def _read_disk(key: str, now: float) -> Any | None:
    try:
        entry = json.loads(_cache_path(key).read_text())
        if now - entry["fetched_at"] < _DISK_CACHE_TTL_SECONDS:
            return entry["payload"]
    except (OSError, ValueError, KeyError):
        # A missing file is the common case; a truncated one is what a killed
        # process leaves behind. Both mean "fetch it again".
        return None
    return None


def _write_disk(key: str, payload: Any, now: float) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = _cache_path(key)
        # Written beside the target and moved into place, so a process killed
        # mid-write never leaves a half-file that looks valid.
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": now, "payload": payload}))
        tmp.replace(target)
    except (OSError, TypeError):
        # TypeError: yfinance occasionally returns a value json cannot encode.
        # Losing the cache entry is better than failing the request.
        pass


def _fetch_info(ticker: str) -> dict:
    """Yahoo's `.info`, or a StockDataError if it cannot answer.

    yfinance raises whatever the underlying HTTP layer raised, and for a blank
    or malformed symbol it raises a TypeError from inside its own parser rather
    than saying the symbol is bad. Uncaught, that reached the router as a 500 —
    an unknown ticker is a 404, not a server fault.
    """
    try:
        info = yf.Ticker(ticker).info
    except Exception as exc:  # noqa: BLE001 — yfinance raises an open-ended set
        raise StockDataError(f"No data available for ticker {ticker}") from exc
    if not isinstance(info, dict):
        raise StockDataError(f"No data available for ticker {ticker}")
    return info


def _info_cached(ticker: str) -> dict:
    # Checked before the cache, not inside the fetch: hashing the key for a
    # disk lookup is the first thing that touches the string, and a None
    # ticker died there with an AttributeError before any guard ran.
    if not (ticker or "").strip():
        raise StockDataError("No ticker given")

    now = time.time()
    hit = _cache.get(ticker)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    from_disk = _read_disk(ticker, now)
    if from_disk is not None:
        _cache[ticker] = (now, from_disk)
        return from_disk

    info = _fetch_info(ticker)
    _cache[ticker] = (now, info)
    _write_disk(ticker, info, now)
    return info


def _price_from(info: dict, ticker: str) -> float:
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        raise StockDataError(f"No price available for ticker {ticker}")
    return float(price)


def get_stock_price(ticker: str) -> float:
    return _price_from(_info_cached(ticker), ticker)


def _reported_eps_pair(ticker: str) -> tuple[float | None, float | None]:
    """The last two full years of diluted EPS, both from the income statement.

    Both from the same statement on purpose. The growth factor used to divide
    `.info`'s trailingEps by the statement's prior year, and for any company
    with an ADR listing Yahoo serves those two in different currencies:
    Infosys came back as 78.17 against 0.76, a spurious +10,186% that took full
    marks and put it top of the screen. Two numbers from one source cannot
    disagree about their own unit.

    It also compares like periods. `.info` is trailing twelve months while the
    statement is a fiscal year, so the old pair was measuring a different
    length of time at each end.

    Only on the income statement, which is a separate and slower call than
    .info, so it is cached on the same clock and failures are silent: a missing
    pair means the growth factor scores neutral, not zero.
    """
    now = time.time()
    key = f"{ticker}::eps_pair"
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    from_disk = _read_disk(key, now)
    if from_disk is not None:
        pair = (from_disk["latest"], from_disk["previous"])
        _cache[key] = (now, pair)
        return pair

    latest = previous = None
    try:
        statement = yf.Ticker(ticker).income_stmt
        for row in ("Diluted EPS", "Basic EPS"):
            if statement is not None and row in statement.index:
                series = statement.loc[row].dropna()
                if len(series) >= 2:
                    latest = float(series.iloc[0])
                    previous = float(series.iloc[1])
                    break
    except Exception:
        latest = previous = None

    pair = (latest, previous)
    _cache[key] = (now, pair)
    # Wrapped in a dict because cached Nones are a real answer here — the
    # company genuinely has no statement on file — and a bare null on disk is
    # indistinguishable from a missing entry.
    _write_disk(key, {"latest": latest, "previous": previous}, now)
    return pair


def get_stock_fundamentals(ticker: str) -> StockFundamentals:
    info = _info_cached(ticker)
    eps_reported, eps_previous = _reported_eps_pair(ticker)
    return StockFundamentals(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName") or ticker,
        price=_price_from(info, ticker),
        previous_close=info.get("previousClose"),
        currency=info.get("currency", "INR"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        market_cap=info.get("marketCap"),
        pe_ratio=info.get("trailingPE"),
        eps=info.get("trailingEps"),
        book_value=info.get("bookValue"),
        roe=info.get("returnOnEquity"),
        eps_reported=eps_reported,
        eps_previous_year=eps_previous,
        # yfinance already returns this as a percentage (5.14 == 5.14%).
        dividend_yield_pct=info.get("dividendYield"),
        week52_high=info.get("fiftyTwoWeekHigh"),
        week52_low=info.get("fiftyTwoWeekLow"),
    )
