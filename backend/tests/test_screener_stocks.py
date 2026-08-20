"""The bridge from traa's stock data to the ported scorer.

Almost all of this file is about units. Every mapping below produces a full,
plausible-looking ranking when it is wrong, and errors nowhere.
"""

import pandas as pd
import pytest

from app.services.marketdata import stock as stock_data
from app.services.marketdata.stock import StockFundamentals
from app.services.marketdata.stock_universe import UniverseStock
from app.services.screener import sector_benchmarks, stock_scoring, stocks


def fundamentals(**over) -> StockFundamentals:
    base = dict(
        ticker="TEST.NS", name="Test Ltd", price=600.0, previous_close=595.0,
        currency="INR", sector="Technology", industry="Software",
        market_cap=1e12, pe_ratio=24.0, eps=25.0, book_value=120.0,
        dividend_yield_pct=1.4, week52_high=700.0, week52_low=400.0,
        roe=0.18, eps_reported=25.0, eps_previous_year=20.0,
    )
    base.update(over)
    return StockFundamentals(**base)


def closes(n: int, start: float = 500.0, step: float = 0.5) -> pd.Series:
    return pd.Series(
        [start + i * step for i in range(n)],
        index=pd.bdate_range("2025-01-01", periods=n),
    )


def entry(symbol: str = "TEST") -> UniverseStock:
    return UniverseStock(
        ticker=f"{symbol}.NS", symbol=symbol, name="Test Ltd",
        industry="Software", isin="INE000A01001", indices=("NIFTY 50",),
    )


# `None` is a meaningful value here -- it is what get_price_history returns for
# a delisted ticker -- so the fixture needs a separate "not supplied" marker.
# Without it, the no-history test silently got the 400-row default and passed
# for the wrong reason.
_DEFAULT = object()


@pytest.fixture
def wired(monkeypatch):
    """Point the bridge at fixtures. Nothing here touches the network."""
    def install(f=_DEFAULT, history=_DEFAULT):
        f = fundamentals() if f is _DEFAULT else f
        history = closes(400) if history is _DEFAULT else history
        monkeypatch.setattr(stock_data, "get_stock_fundamentals", lambda t: f)
        monkeypatch.setattr(
            stock_data, "get_price_history",
            lambda t, period="2y": None if history is None else pd.DataFrame({"Close": history}),
        )
    return install


# ------------------------------------------------------------------ units


def test_price_to_book_is_derived_because_traa_stores_book_value_per_share():
    """traa keeps `book_value` (per share), the port wants the ratio. Passing
    the book value straight through would tell the scorer a 600-rupee share
    trades at 120 times book."""
    record = stocks._to_port_fundamentals(fundamentals(price=600.0, book_value=120.0),
                                          "Technology", "Software")
    assert record["price_to_book"] == pytest.approx(5.0)


def test_roe_stays_a_decimal_while_the_benchmark_stays_a_percent():
    """The asymmetry is upstream's and `_score_roe` reconciles it internally.
    Converting the company's ROE to a percent as well would multiply it by a
    hundred against its own peer median."""
    record = stocks._to_port_fundamentals(fundamentals(roe=0.18), "Technology", None)
    assert record["roe"] == pytest.approx(0.18)
    assert sector_benchmarks.resolve("Technology")["median_roe"] > 1.5


def test_dividend_yield_passes_through_as_a_percent():
    """yfinance already returns 5.14 for 5.14%, and `_score_div_yield` compares
    against a percent median. Scaling it here would be the same bug twice."""
    record = stocks._to_port_fundamentals(fundamentals(dividend_yield_pct=5.14), None, None)
    assert record["div_yield"] == pytest.approx(5.14)


def test_growth_uses_the_two_reported_years_not_the_trailing_figure():
    """traa's own comment says why: a ratio built from .info's TTM number and
    the income statement's prior year can straddle two currencies."""
    record = stocks._to_port_fundamentals(
        fundamentals(eps=99.0, eps_reported=25.0, eps_previous_year=20.0), None, None
    )
    assert record["eps_ttm"] == 25.0 and record["eps_prev"] == 20.0


def test_a_zero_book_value_does_not_divide_by_zero():
    record = stocks._to_port_fundamentals(fundamentals(book_value=0.0), None, None)
    assert record["price_to_book"] is None


def test_a_missing_book_value_is_none_not_zero():
    """Zero would score as a spectacularly cheap stock; None takes half marks."""
    assert stocks._to_port_fundamentals(fundamentals(book_value=None), None, None)[
        "price_to_book"
    ] is None


# --------------------------------------------------------------- the gate


def test_a_fourteen_day_listing_is_refused_rather_than_ranked_first(wired):
    """The reason the gate exists: a NaN total clamps UP to 100.0, so the
    newest listing on the exchange would be the best stock in India."""
    wired(history=closes(14))
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.UnscorableStock)
    assert "15 needed" in result.reason


def test_a_stock_with_no_history_is_named_not_dropped(wired):
    wired(history=None)
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.UnscorableStock)
    assert result.reason == "no price history"


def test_a_stock_with_no_fundamentals_is_refused(wired):
    wired(f=fundamentals(pe_ratio=None, book_value=None, roe=None,
                         eps_reported=None, eps_previous_year=None, eps=None))
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.UnscorableStock)
    assert "fundamentals" in result.reason


def test_a_programming_error_is_not_disguised_as_a_feed_outage(monkeypatch):
    """The first version caught Exception around the fetch, so a misspelled
    function name came back as "fundamentals unavailable" for every stock --
    which reads exactly like yfinance being down, and cost real time."""
    def boom(_t):
        raise AttributeError("module has no attribute 'get_fundamentals'")
    monkeypatch.setattr(stock_data, "get_stock_fundamentals", boom)
    with pytest.raises(AttributeError):
        stocks._score_one(entry())


def test_a_real_feed_outage_is_still_caught(monkeypatch):
    def boom(_t):
        raise stock_data.StockDataError("yfinance timed out")
    monkeypatch.setattr(stock_data, "get_stock_fundamentals", boom)
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.UnscorableStock)
    assert "timed out" in result.reason


# ------------------------------------------------------------ the scoring


def test_a_healthy_stock_is_scored_with_its_sector_peers(wired):
    wired()
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.ScoredStock)
    assert 0.0 < result.total < 100.0
    assert result.bucket
    assert result.benchmark_sector == "Technology"
    assert result.benchmark_constituents > 0


def test_an_unknown_sector_falls_back_and_says_so(wired):
    """The scorer silently uses a default benchmark for an unmapped sector and
    upstream never surfaces it. The row records which peer group was used."""
    wired(f=fundamentals(sector="Interdimensional Widgets"))
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.ScoredStock)
    assert result.benchmark_sector == sector_benchmarks.ALL_STOCKS


def test_delivery_is_passed_as_unavailable_on_purpose(wired):
    """Not left to default. NSE's quote-equity returns 403, so this is a
    constant 4.5 of every 100 points for every stock, and the screen's
    disclosure and this constant have to move together."""
    assert stocks.DELIVERY_UNAVAILABLE is None
    assert "9 of the 100" in stocks.DELIVERY_NOTE


def test_a_short_but_scoreable_history_is_flagged_rather_than_excluded(wired):
    """60 closes gives a real RSI and MACD but no 200-day EMA, so the trend
    factor is measured against a shorter average than every other stock's."""
    wired(history=closes(60))
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.ScoredStock)
    assert result.thin_history is True


def test_a_long_history_is_not_flagged(wired):
    wired(history=closes(400))
    assert stocks._score_one(entry()).thin_history is False


def test_a_meaningless_total_is_refused_even_if_the_gate_let_it_through(wired, monkeypatch):
    """Belt to the gate's braces. If a NaN reaches a total by some future route
    it must not sort to the top of the page."""
    wired()
    monkeypatch.setattr(
        stock_scoring, "score_stock",
        lambda *a, **k: {"total": float("nan"), "bucket": "Strong Buy",
                         "factors": [], "adjustments": []},
    )
    result = stocks._score_one(entry())
    assert isinstance(result, stocks.UnscorableStock)
    assert "meaningless" in result.reason


# --------------------------------------------------------------- the ranking


def test_every_stock_offered_lands_in_exactly_one_list(monkeypatch, wired):
    wired()
    universe = [entry(f"S{i}") for i in range(9)]
    monkeypatch.setattr(
        "app.services.screener.stocks.stock_universe.list_stocks",
        lambda **kw: universe,
    )
    scored, unscorable = stocks.rank()
    assert len(scored) + len(unscorable) == len(universe)
    landed = [s.symbol for s in scored] + [u.symbol for u in unscorable]
    assert sorted(landed) == sorted(e.symbol for e in universe)


def test_the_ranking_comes_back_best_first(monkeypatch):
    """Six identical stocks all score the same, so a sorted-check on them passes
    whether or not anything sorted. A sabotage pass caught that. These differ."""
    universe = [entry(f"S{i}") for i in range(6)]
    # Cheaper P/E scores better, so this makes the expected order S5..S0.
    by_ticker = {e.ticker: fundamentals(pe_ratio=60.0 - i * 8) for i, e in enumerate(universe)}
    monkeypatch.setattr(stock_data, "get_stock_fundamentals", lambda t: by_ticker[t])
    monkeypatch.setattr(
        stock_data, "get_price_history",
        lambda t, period="2y": pd.DataFrame({"Close": closes(400)}),
    )
    monkeypatch.setattr(
        "app.services.screener.stocks.stock_universe.list_stocks", lambda **kw: universe
    )
    scored, _ = stocks.rank()
    totals = [s.total for s in scored]
    assert len(set(totals)) > 1, "the fixture produced identical scores, so this proves nothing"
    assert totals == sorted(totals, reverse=True)
    assert scored[0].symbol == "S5", "the cheapest stock should lead"


def test_a_programming_error_reaches_the_caller_rather_than_becoming_a_data_error(monkeypatch):
    """An AttributeError must propagate, not turn into a row saying the feed was
    unavailable. The first version of `_score_one` caught Exception here, so a
    misspelled function name reported "fundamentals unavailable" for every stock
    -- indistinguishable from yfinance being down."""
    def boom(_t):
        raise AttributeError("module has no attribute 'get_fundamentals'")
    monkeypatch.setattr(stock_data, "get_stock_fundamentals", boom)
    with pytest.raises(AttributeError):
        stocks._score_one(entry())


def test_the_fundamentals_fetch_has_no_broad_except():
    """Belt, checked structurally rather than by string matching.

    Finds the try block that actually calls `get_stock_fundamentals` and asserts
    none of its handlers is a bare `except:` or `except Exception:`. The scoring
    call further down legitimately has one, so a whole-function text search
    would be wrong.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(stocks._score_one).lstrip())
    fetch_tries = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and "get_stock_fundamentals" in ast.dump(ast.Module(node.body, []))
    ]
    assert fetch_tries, "could not find the fundamentals fetch; this test needs updating"
    for handler in fetch_tries[0].handlers:
        assert handler.type is not None, "a bare `except:` guards the fundamentals fetch"
        caught = ast.dump(handler.type)
        assert "Exception" not in caught or "StockDataError" in caught, (
            f"a broad except reappeared around the fundamentals fetch: {caught}"
        )
