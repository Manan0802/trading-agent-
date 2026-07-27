"""Indian listed-equity data via yfinance (NSE tickers use a .NS suffix).

Yahoo's endpoint is unofficial and coverage thins out for small caps, so every
field except the price is treated as optional. A ticker Yahoo does not know
comes back as a near-empty dict rather than an error, which we turn into an
explicit StockDataError so callers never get a priceless holding.
"""

import time
from dataclasses import dataclass
from typing import Any

import yfinance as yf

_CACHE_TTL_SECONDS = 15 * 60  # prices move intraday; fundamentals barely do

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
    # Diluted EPS from the prior full year, for the growth comparison. Only on
    # the income statement, which .info does not carry.
    eps_previous_year: float | None = None

    @property
    def day_change_pct(self) -> float | None:
        if not self.previous_close:
            return None
        return (self.price - self.previous_close) / self.previous_close * 100


def clear_cache() -> None:
    _cache.clear()


def _fetch_info(ticker: str) -> dict:
    return yf.Ticker(ticker).info


def _info_cached(ticker: str) -> dict:
    now = time.time()
    hit = _cache.get(ticker)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    info = _fetch_info(ticker)
    _cache[ticker] = (now, info)
    return info


def _price_from(info: dict, ticker: str) -> float:
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        raise StockDataError(f"No price available for ticker {ticker}")
    return float(price)


def get_stock_price(ticker: str) -> float:
    return _price_from(_info_cached(ticker), ticker)


def _previous_year_eps(ticker: str) -> float | None:
    """Diluted EPS from the year before last, for a growth comparison.

    Only on the income statement, which is a separate and slower call than
    .info, so it is cached on the same clock and failures are silent: a missing
    prior year means the growth factor scores neutral, not zero.
    """
    now = time.time()
    key = f"{ticker}::eps_prev"
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    value = None
    try:
        statement = yf.Ticker(ticker).income_stmt
        for row in ("Diluted EPS", "Basic EPS"):
            if statement is not None and row in statement.index:
                series = statement.loc[row].dropna()
                if len(series) >= 2:
                    value = float(series.iloc[1])
                    break
    except Exception:
        value = None

    _cache[key] = (now, value)
    return value


def get_stock_fundamentals(ticker: str) -> StockFundamentals:
    info = _info_cached(ticker)
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
        eps_previous_year=_previous_year_eps(ticker),
        # yfinance already returns this as a percentage (5.14 == 5.14%).
        dividend_yield_pct=info.get("dividendYield"),
        week52_high=info.get("fiftyTwoWeekHigh"),
        week52_low=info.get("fiftyTwoWeekLow"),
    )
