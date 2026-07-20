import pytest

from app.services.marketdata import stock

RELIANCE_INFO = {
    "longName": "Reliance Industries Limited",
    "shortName": "RELIANCE INDUSTRIES LTD",
    "currentPrice": 1323.1,
    "previousClose": 1327.2,
    "currency": "INR",
    "sector": "Energy",
    "industry": "Oil & Gas Refining & Marketing",
    "marketCap": 17904814784512,
    "trailingPE": 23.96486,
    "trailingEps": 55.21,
    "bookValue": 668.045,
    "dividendYield": 0.45,
    "fiftyTwoWeekHigh": 1611.8,
    "fiftyTwoWeekLow": 1253.2,
}

# What yfinance actually returns for a ticker that does not exist: no error,
# just a near-empty dict.
UNKNOWN_TICKER_INFO = {"trailingPegRatio": None}


@pytest.fixture(autouse=True)
def _clear_cache():
    stock.clear_cache()
    yield
    stock.clear_cache()


def _stub(monkeypatch, info, calls=None):
    def fake_fetch_info(ticker: str):
        if calls is not None:
            calls.append(ticker)
        return info

    monkeypatch.setattr(stock, "_fetch_info", fake_fetch_info)


def test_price_lookup(monkeypatch):
    _stub(monkeypatch, RELIANCE_INFO)
    assert stock.get_stock_price("RELIANCE.NS") == pytest.approx(1323.1)


def test_fundamentals_are_mapped(monkeypatch):
    _stub(monkeypatch, RELIANCE_INFO)
    f = stock.get_stock_fundamentals("RELIANCE.NS")
    assert f.name == "Reliance Industries Limited"
    assert f.sector == "Energy"
    assert f.pe_ratio == pytest.approx(23.96486)
    assert f.eps == pytest.approx(55.21)
    assert f.book_value == pytest.approx(668.045)
    assert f.market_cap == 17904814784512
    # yfinance already reports yield as a percentage, so it must not be scaled.
    assert f.dividend_yield_pct == pytest.approx(0.45)


def test_day_change_is_derived_from_previous_close(monkeypatch):
    _stub(monkeypatch, RELIANCE_INFO)
    f = stock.get_stock_fundamentals("RELIANCE.NS")
    assert f.day_change_pct == pytest.approx((1323.1 - 1327.2) / 1327.2 * 100)


def test_unknown_ticker_raises_rather_than_returning_a_priceless_object(monkeypatch):
    _stub(monkeypatch, UNKNOWN_TICKER_INFO)
    with pytest.raises(stock.StockDataError):
        stock.get_stock_price("NOTAREAL123.NS")
    with pytest.raises(stock.StockDataError):
        stock.get_stock_fundamentals("NOTAREAL123.NS")


def test_missing_optional_fields_are_none_not_errors(monkeypatch):
    _stub(monkeypatch, {"currentPrice": 100.0, "longName": "Thinly Covered Smallcap"})
    f = stock.get_stock_fundamentals("SMALLCAP.NS")
    assert f.price == pytest.approx(100.0)
    assert f.pe_ratio is None
    assert f.sector is None
    assert f.day_change_pct is None


def test_repeat_calls_hit_cache(monkeypatch):
    calls: list[str] = []
    _stub(monkeypatch, RELIANCE_INFO, calls)
    stock.get_stock_price("RELIANCE.NS")
    stock.get_stock_fundamentals("RELIANCE.NS")
    assert calls == ["RELIANCE.NS"]


def test_falls_back_to_regular_market_price_when_current_price_absent(monkeypatch):
    _stub(monkeypatch, {"regularMarketPrice": 250.0, "longName": "X"})
    assert stock.get_stock_price("X.NS") == pytest.approx(250.0)
