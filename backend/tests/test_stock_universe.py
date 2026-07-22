import pytest

from app.services.marketdata.stock_universe import (
    INDEX_CHOICES,
    industries,
    list_stocks,
    lookup,
)


def test_the_universe_is_not_empty():
    assert len(list_stocks()) > 500


def test_every_entry_carries_a_yfinance_ready_ticker():
    """The .NS suffix lives in the catalogue so it is not appended at each
    call site, where one omission produces a silently unpriceable holding."""
    for stock in list_stocks()[:50]:
        assert stock.ticker.endswith(".NS")
        assert stock.ticker == f"{stock.symbol}.NS"


def test_the_nifty_50_is_exactly_fifty_names():
    assert len(list_stocks(index="NIFTY 50")) == 50


def test_indices_nest_so_a_nifty_50_name_is_also_in_the_500():
    fifty = {s.symbol for s in list_stocks(index="NIFTY 50")}
    five_hundred = {s.symbol for s in list_stocks(index="NIFTY 500")}
    assert fifty < five_hundred


def test_reliance_is_present_and_correctly_shaped():
    stock = lookup("RELIANCE")
    assert stock is not None
    assert stock.ticker == "RELIANCE.NS"
    assert "NIFTY 50" in stock.indices
    assert stock.isin


def test_lookup_accepts_the_suffixed_ticker_too():
    """The portfolio stores RELIANCE.NS, the universe is keyed on RELIANCE."""
    assert lookup("RELIANCE.NS") == lookup("RELIANCE")


def test_lookup_is_case_insensitive_and_trims():
    assert lookup("  reliance ") == lookup("RELIANCE")


def test_an_unknown_symbol_returns_none_rather_than_raising():
    assert lookup("NOTATICKER") is None


def test_search_matches_company_name_not_just_symbol():
    """Nobody remembers that Larsen & Toubro trades as LT."""
    hits = {s.symbol for s in list_stocks(query="larsen")}
    assert "LT" in hits


def test_search_matches_symbol_prefix():
    assert "TCS" in {s.symbol for s in list_stocks(query="tcs")}


def test_industry_filter_narrows_the_list():
    all_stocks = list_stocks(index="NIFTY 50")
    banks = list_stocks(index="NIFTY 50", industry="Financial Services")
    assert 0 < len(banks) < len(all_stocks)


def test_industries_are_listed_for_the_filter_control():
    names = industries()
    assert len(names) > 5
    assert names == sorted(names)
    assert all(n for n in names)


def test_limit_bounds_the_response():
    assert len(list_stocks(limit=10)) == 10


def test_index_choices_are_ordered_narrowest_first():
    assert INDEX_CHOICES[0] == "NIFTY 50"


def test_an_unknown_index_yields_nothing_rather_than_everything():
    """Falling back to the full list would silently ignore the filter."""
    assert list_stocks(index="NIFTY 9000") == []


def test_results_are_stable_across_calls():
    assert [s.symbol for s in list_stocks(limit=20)] == [
        s.symbol for s in list_stocks(limit=20)
    ]
