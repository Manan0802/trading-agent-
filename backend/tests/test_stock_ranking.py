import pytest

from app.services.advisor import stock_ranking
from app.services.marketdata import stock as stock_data
from app.services.marketdata.stock import StockFundamentals
from app.services.marketdata.stock_universe import UniverseStock


def _entry(symbol: str, name: str | None = None) -> UniverseStock:
    return UniverseStock(
        ticker=f"{symbol}.NS",
        symbol=symbol,
        name=name or f"{symbol} Limited",
        industry="Banking",
        isin=None,
        indices=("NIFTY 50",),
    )


def _fundamentals(ticker: str, *, pe: float, roe: float) -> StockFundamentals:
    return StockFundamentals(
        ticker=ticker,
        name=ticker,
        price=100.0,
        previous_close=99.0,
        currency="INR",
        sector="Financial Services",
        industry="Banking",
        market_cap=1e11,
        pe_ratio=pe,
        eps=10.0,
        book_value=50.0,
        dividend_yield_pct=1.0,
        week52_high=120.0,
        week52_low=80.0,
        roe=roe,
        eps_previous_year=9.0,
    )


@pytest.fixture
def fake_market(monkeypatch):
    """A tiny deterministic market: cheap+profitable through to dear+weak."""
    table = {
        "CHEAP.NS": _fundamentals("CHEAP.NS", pe=8.0, roe=0.28),
        "MID.NS": _fundamentals("MID.NS", pe=18.0, roe=0.15),
        "DEAR.NS": _fundamentals("DEAR.NS", pe=60.0, roe=0.04),
    }

    def fake_get(ticker: str) -> StockFundamentals:
        if ticker not in table:
            raise stock_data.StockDataError(f"No price available for ticker {ticker}")
        return table[ticker]

    monkeypatch.setattr(stock_ranking.stock_data, "get_stock_fundamentals", fake_get)
    monkeypatch.setattr(
        stock_ranking,
        "sector_benchmarks",
        lambda: {
            "Financial Services": {
                "pe": 18.0,
                "pb": 2.0,
                "roe": 0.15,
                "dividend_yield": 0.012,
            }
        },
    )
    return table


def test_the_whole_group_is_ranked_against_itself(fake_market):
    """The reason this exists: a score of 74 is meaningless until you know what
    the other companies scored."""
    result = stock_ranking.rank_stocks(
        "NIFTY 50", [_entry("CHEAP"), _entry("MID"), _entry("DEAR")]
    )
    assert [r.score.ticker for r in result.ranked] == ["CHEAP.NS", "MID.NS", "DEAR.NS"]
    assert [r.rank for r in result.ranked] == [1, 2, 3]


def test_scores_fall_monotonically_down_the_ranking(fake_market):
    result = stock_ranking.rank_stocks(
        "NIFTY 50", [_entry("DEAR"), _entry("CHEAP"), _entry("MID")]
    )
    totals = [r.score.total for r in result.ranked]
    assert totals == sorted(totals, reverse=True)


def test_a_company_yahoo_cannot_price_is_named_not_dropped(fake_market):
    """Silently omitting it would make the screen look complete when it is not."""
    result = stock_ranking.rank_stocks(
        "NIFTY 50", [_entry("CHEAP"), _entry("UNKNOWN"), _entry("MID")]
    )
    assert [r.score.ticker for r in result.ranked] == ["CHEAP.NS", "MID.NS"]
    assert [u.ticker for u in result.unscorable] == ["UNKNOWN.NS"]
    assert result.covered == 2
    assert result.matched == 3


def test_one_company_blowing_up_does_not_empty_the_screen(fake_market, monkeypatch):
    """yfinance raises a wide undocumented set of its own exceptions."""

    def explode(ticker: str):
        if ticker == "MID.NS":
            raise RuntimeError("yfinance had indigestion")
        return fake_market[ticker]

    monkeypatch.setattr(stock_ranking.stock_data, "get_stock_fundamentals", explode)
    result = stock_ranking.rank_stocks(
        "NIFTY 50", [_entry("CHEAP"), _entry("MID"), _entry("DEAR")]
    )
    assert result.covered == 2
    assert len(result.unscorable) == 1


def test_coverage_is_reported_when_the_limit_bites(fake_market):
    """A screen that ranks 2 of 3 and says nothing is lying by omission."""
    result = stock_ranking.rank_stocks(
        "NIFTY 50", [_entry("CHEAP"), _entry("MID"), _entry("DEAR")], limit=2
    )
    assert result.matched == 3
    assert result.covered == 2
    assert len(result.ranked) == 2


def test_ties_break_deterministically_so_two_visits_agree(fake_market, monkeypatch):
    same = _fundamentals("A.NS", pe=18.0, roe=0.15)
    monkeypatch.setattr(
        stock_ranking.stock_data,
        "get_stock_fundamentals",
        lambda t: _fundamentals(t, pe=18.0, roe=0.15),
    )
    first = stock_ranking.rank_stocks("x", [_entry("ZZZ"), _entry("AAA")])
    second = stock_ranking.rank_stocks("x", [_entry("AAA"), _entry("ZZZ")])
    assert [r.score.ticker for r in first.ranked] == [
        r.score.ticker for r in second.ranked
    ]
    assert same.pe_ratio == 18.0


def test_the_catalogue_name_wins_over_yahoos(fake_market):
    """NSE's official name reads better than Yahoo's inconsistent abbreviations."""
    result = stock_ranking.rank_stocks(
        "NIFTY 50", [_entry("CHEAP", name="Cheap Industries Limited")]
    )
    assert result.ranked[0].score.name == "Cheap Industries Limited"


def test_an_empty_filter_returns_an_empty_ranking_not_an_error(fake_market):
    result = stock_ranking.rank_stocks("Nothing matched", [])
    assert result.ranked == []
    assert result.matched == 0
    assert result.covered == 0
