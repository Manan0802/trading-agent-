"""A company's own page: price in context, ratios against their sector.

Nothing here touches the network — every price and fundamental is stubbed.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.services.marketdata import stock as stock_data
from app.services.marketdata import stock_universe
from app.services.marketdata.stock import StockFundamentals
from app.services.marketdata.stock_universe import UniverseStock
from app.services.screener import plain_words as pw
from app.services.screener import stock_analysis_page as sp

AS_OF = date(2026, 8, 20)

# Captured before the autouse `offline` fixture stubs it out, so the one
# test that exercises the real cache can put it back.
_REAL_GET_PRICE_HISTORY = stock_data.get_price_history


def fundamentals(**over) -> StockFundamentals:
    base = dict(
        ticker="X.NS", name="Test Ltd", price=800.0, previous_close=790.0,
        currency="INR", sector="Technology", industry="Software", market_cap=5e12,
        pe_ratio=20.0, eps=40.0, book_value=200.0, dividend_yield_pct=1.2,
        week52_high=1000.0, week52_low=600.0, roe=0.22,
        eps_reported=40.0, eps_previous_year=34.0,
    )
    base.update(over)
    return StockFundamentals(**base)


def prices(n: int = 400, start: float = 500.0, step: float = 0.8) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp(AS_OF), periods=n)
    return pd.DataFrame(
        {"Close": [start + i * step for i in range(n)],
         "Low": [start + i * step - 5 for i in range(n)],
         "High": [start + i * step + 5 for i in range(n)],
         "Volume": [1_000_000 + i for i in range(n)]},
        index=idx,
    )


def universe(n: int = 14, industry: str = "Software") -> list[UniverseStock]:
    out = [UniverseStock("X.NS", "X", "Test Ltd", industry, None, ("NIFTY 50",))]
    for i in range(n):
        out.append(
            UniverseStock(
                f"P{i}.NS", f"P{i}", f"Peer {i}", industry, None,
                ("NIFTY 50",) if i < 3 else ("NIFTY 500",) if i < 8 else (),
            )
        )
    return out


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(stock_data, "get_price_history", lambda t, period="10y": prices())
    monkeypatch.setattr(stock_data, "get_stock_fundamentals", lambda t: fundamentals(ticker=t))
    monkeypatch.setattr(stock_universe, "list_stocks", lambda **kw: universe())
    monkeypatch.setattr(
        stock_universe, "lookup",
        lambda t: next((s for s in universe() if s.ticker == t), None),
    )
    monkeypatch.setattr(sp.stock_universe, "list_stocks", lambda **kw: universe())
    monkeypatch.setattr(
        sp.stock_universe, "lookup",
        lambda t: next((s for s in universe() if s.ticker == t), None),
    )
    monkeypatch.setattr(sp.stock_data, "get_price_history", lambda t, period="10y": prices())
    monkeypatch.setattr(sp.stock_data, "get_stock_fundamentals", lambda t: fundamentals(ticker=t))


# ------------------------------------------------- the sector comparison


def test_every_ratio_carries_its_sector_median_not_just_pe():
    """Brokers print "Industry P/E" and leave P/B, ROE and dividend yield bare,
    which makes them unreadable — a P/B of 7.6 is expensive for a bank and
    ordinary for a software company."""
    page = sp.build("X.NS", AS_OF, "1y")
    keys = {r.key for r in page.ratios}
    assert keys == {"pe", "pb", "roe", "div_yield"}
    for r in page.ratios:
        assert r.sector_median is not None, f"{r.key} has no peer to be judged against"


def test_low_is_good_for_price_ratios_and_bad_for_returns():
    """One comparison cannot serve both: a low P/E is good news and a low ROE is
    not."""
    page = sp.build("X.NS", AS_OF, "1y")
    by = {r.key: r for r in page.ratios}
    for key in ("pe", "pb"):
        r = by[key]
        if r.value is not None and r.sector_median:
            assert r.better == (r.value < r.sector_median)
    for key in ("roe", "div_yield"):
        r = by[key]
        if r.value is not None and r.sector_median:
            assert r.better == (r.value > r.sector_median)


def test_price_to_book_is_derived_because_only_book_value_is_published():
    page = sp.build("X.NS", AS_OF, "1y")
    pb = next(r for r in page.ratios if r.key == "pb")
    assert pb.value == pytest.approx(800.0 / 200.0)


def test_a_missing_roe_is_derived_from_price_to_book_over_price_to_earnings():
    """yfinance returns None for ROE on most Indian names. P/B over P/E is book
    over earnings inverted -- the price cancels -- and it lands within about two
    percentage points of the reported figure."""
    import app.services.screener.stock_analysis_page as mod

    r = mod._ratios(fundamentals(roe=None), {"median_pe": 20.0, "median_pb": 3.0,
                                             "median_roe": 15.0, "median_div_yield": 1.0})
    roe = next(x for x in r if x.key == "roe")
    assert roe.value == pytest.approx((800.0 / 200.0) / 20.0 * 100, abs=1e-6)


# ------------------------------------------------- price in context


def test_the_price_is_placed_inside_its_own_year():
    """A price on its own says nothing. Its position in the year says whether
    you are near the top or the bottom of what the market recently thought this
    company was worth."""
    page = sp.build("X.NS", AS_OF, "1y")
    assert page.position_in_52w == pytest.approx((800 - 600) / (1000 - 600))


def test_a_stock_with_no_range_gets_no_position_rather_than_a_divide_by_zero():
    import app.services.screener.stock_analysis_page as mod

    mod.stock_data.get_stock_fundamentals = lambda t: fundamentals(
        week52_low=900.0, week52_high=900.0
    )
    assert sp.build("X.NS", AS_OF, "1y").position_in_52w is None


# ------------------------------------------------- peers


def test_similar_companies_are_the_big_ones_not_the_alphabetical_ones():
    """Alphabetical order put 360ONE, AUBANK and AADHARHFC beside HDFC Bank.
    They are in its industry and they are not its peers."""
    page = sp.build("X.NS", AS_OF, "1y")
    shown = [s.symbol for s in page.similar]
    assert shown, "no similar companies at all"
    # The NIFTY 50 members in the fixture are P0-P2; they must come first.
    assert set(shown[:3]) == {"P0", "P1", "P2"}


def test_the_stock_is_never_its_own_peer():
    page = sp.build("X.NS", AS_OF, "1y")
    assert "X" not in [s.symbol for s in page.similar]


def test_the_sector_line_shares_the_price_line_s_axis():
    page = sp.build("X.NS", AS_OF, "1y")
    assert page.price_series and page.sector_series
    assert page.price_series[0].value == pytest.approx(100.0, abs=1e-6)
    assert page.sector_series[0].value == pytest.approx(100.0, abs=0.5)


def test_a_thin_industry_gets_no_sector_line_rather_than_a_fake_one():
    import app.services.screener.stock_analysis_page as mod

    mod.stock_universe.list_stocks = lambda **kw: universe(n=2)
    page = sp.build("X.NS", AS_OF, "1y")
    assert page.sector_series == []
    assert page.peers_compared == 0


# ------------------------------------------------- ranges


@pytest.mark.parametrize("range_key", list(sp.RANGES))
def test_every_range_works(range_key):
    page = sp.build("X.NS", AS_OF, range_key)
    assert page.range_key == range_key
    assert page.price_series


def test_a_short_range_does_not_download_a_decade(monkeypatch):
    """A one-year chart was pulling ten years of prices for the stock AND every
    peer -- thirteen ten-year downloads to draw twelve months. Asserting the
    mapping is non-empty does not catch this; a table of all "10y" satisfies
    that. Record what was actually asked for."""
    asked: list[str] = []

    def spy(ticker, period="10y"):
        asked.append(period)
        return prices()

    monkeypatch.setattr(sp.stock_data, "get_price_history", spy)

    sp.build("X.NS", AS_OF, "1m")
    short = set(asked)
    asked.clear()
    sp.build("X.NS", AS_OF, "max")
    longest = set(asked)

    assert short == {"3mo"}, f"a one-month chart fetched {short}"
    assert longest == {"10y"}
    # Every peer is fetched at the same period as the stock, or the two lines
    # would be rebased over different spans.
    assert len(short) == 1


def test_an_unknown_range_falls_back_to_the_default():
    assert sp.build("X.NS", AS_OF, "nonsense").range_key == sp.DEFAULT_RANGE


# ------------------------------------------------- the sentences


def test_the_position_sentence_says_top_or_bottom_not_a_percentage_alone():
    page = sp.build("X.NS", AS_OF, "1y")
    s = pw.price_position_sentence(page)
    assert "₹800" in s and "₹600" in s and "₹1,000" in s


def test_a_stock_near_its_low_is_described_as_near_the_bottom():
    import app.services.screener.stock_analysis_page as mod

    mod.stock_data.get_stock_fundamentals = lambda t: fundamentals(price=620.0)
    s = pw.price_position_sentence(sp.build("X.NS", AS_OF, "1y"))
    assert "near the bottom of" in s


def test_the_quality_sentence_explains_return_on_equity_in_rupees():
    """"ROE 22%" means nothing to most readers. "For every ₹100 shareholders
    own, it earns ₹22" is the same number and immediately legible."""
    s = pw.quality_sentence(sp.build("X.NS", AS_OF, "1y"))
    assert "For every ₹100" in s
    assert "ROE" not in s


def test_the_score_sentence_names_the_momentum_share_every_time():
    """Forty-one of the hundred points are indicators this project's own
    measurements do not support. A score shown without that is borrowing
    credibility it has not earned."""
    s = pw.stock_score_sentence(64.0, "Buy", 31.0, 33.0)
    assert "momentum" in s and "do not support" in s


def test_a_stock_with_no_score_gets_no_score_sentence():
    assert pw.stock_score_sentence(None, None, None, None) is None


def test_market_cap_is_written_in_crores():
    """The unit every Indian reader thinks in."""
    s = pw.size_sentence(sp.build("X.NS", AS_OF, "1y"))
    assert "Cr" in s and "5,00,000" in s


# ------------------------------------------------- the price cache


def test_two_ranges_of_the_same_stock_do_not_share_a_cached_frame(monkeypatch):
    """The in-memory history cache was keyed on ticker alone. Every caller
    asked for "2y" so it never mattered -- until this page matched the period
    to the chart range. Then a one-year chart was handed the three-month frame
    a one-month chart had already cached, and drew 67 points as a year."""
    from app.services.marketdata import stock as real_stock

    real_stock._HISTORY.clear()
    lengths = {"3mo": 60, "1y": 250}

    def fake(ticker, period="2y"):
        return prices(n=lengths.get(period, 250))

    monkeypatch.setattr(real_stock.yf, "Ticker", None, raising=False)
    monkeypatch.setattr(real_stock, "_HISTORY", {})
    monkeypatch.setattr(sp.stock_data, "get_price_history", fake)

    short = len(sp.build("X.NS", AS_OF, "1m").price_series)
    long = len(sp.build("X.NS", AS_OF, "1y").price_series)
    assert long > short, f"a one-year chart drew {long} points, a one-month one {short}"


def test_the_history_cache_key_includes_the_period(monkeypatch):
    """The layer below, tested directly -- so the guarantee survives a
    refactor of the page that stops exercising it."""
    from app.services.marketdata import stock as real_stock

    calls: list[str] = []

    class FakeTicker:
        def __init__(self, t):
            pass

        def history(self, period, auto_adjust=True):
            calls.append(period)
            return prices(n=10 if period == "3mo" else 99)

    monkeypatch.setattr(real_stock, "_HISTORY", {})
    monkeypatch.setattr(real_stock, "get_price_history", _REAL_GET_PRICE_HISTORY)
    monkeypatch.setattr(real_stock.yf, "Ticker", FakeTicker)

    assert len(real_stock.get_price_history("X.NS", period="3mo")) == 10
    assert len(real_stock.get_price_history("X.NS", period="1y")) == 99
    assert len(real_stock.get_price_history("X.NS", period="3mo")) == 10
    assert calls == ["3mo", "1y"], f"refetched or cross-served: {calls}"


# ------------------------------------------------- near-ties and blanks


def test_a_near_tie_on_profitability_is_not_written_up_as_a_difference():
    """HDFC Bank earning ₹14.4 against a sector's ₹15.0 was written up as "less
    profitable than its peers" -- a ranking claim resting on six-tenths of a
    rupee, off a ROE this page derived rather than read."""
    import app.services.screener.stock_analysis_page as mod

    r = mod._ratios(fundamentals(roe=0.144), {"median_pe": 20.0, "median_pb": 3.0,
                                              "median_roe": 15.0, "median_div_yield": 1.0})
    page = sp.build("X.NS", AS_OF, "1y")
    s = pw.quality_sentence(page.__class__(**{**page.__dict__, "ratios": r}))
    assert "earns about what its peers do" in s
    assert "less profitable" not in s


def test_a_real_gap_on_profitability_still_gets_named():
    """The band must not silence everything."""
    import app.services.screener.stock_analysis_page as mod

    page = sp.build("X.NS", AS_OF, "1y")
    for roe, word in ((0.30, "more profitable"), (0.05, "less profitable")):
        r = mod._ratios(fundamentals(roe=roe), {"median_pe": 20.0, "median_pb": 3.0,
                                                "median_roe": 15.0, "median_div_yield": 1.0})
        s = pw.quality_sentence(page.__class__(**{**page.__dict__, "ratios": r}))
        assert word in s, f"ROE {roe} produced: {s}"


def test_a_company_that_pays_no_dividend_says_so():
    """Seven of thirty real stocks in a sweep had no dividend yield. A blank
    cell does not distinguish "pays nothing" from "we could not find out"."""
    import app.services.screener.stock_analysis_page as mod

    mod.stock_data.get_stock_fundamentals = lambda t: fundamentals(dividend_yield_pct=None)
    s = pw.dividend_sentence(sp.build("X.NS", AS_OF, "1y"))
    assert "No dividend is reported" in s


def test_a_company_that_does_pay_gets_the_figure_and_its_peer_median():
    s = pw.dividend_sentence(sp.build("X.NS", AS_OF, "1y"))
    assert "1.20%" in s and "middle company" in s


def test_rupees_round_the_way_the_browser_does():
    """A 52-week high of ₹1020.5 was labelled ₹1,021 on the bar (the browser's
    rounding) and ₹1,020 in the sentence right beneath it (Python's default
    half-to-even). Two numbers, one figure."""
    assert pw._inr(1020.5) == "1,021"
    assert pw._inr(2.5) == "3"
    assert pw._inr(-1020.5) == "-1,021"
    # And the ordinary cases still group the Indian way.
    assert pw._inr(1126467) == "11,26,467"
    assert pw._inr(999) == "999"


def test_the_similar_list_is_labelled_with_the_group_it_came_from():
    """The universe's `industry` field holds a broad sector ("Financial
    Services"); the fundamentals feed's holds a granular one ("Banks -
    Regional"). Labelling six peers drawn from the first with the second says
    they are regional banks when two are insurers."""
    page = sp.build("X.NS", AS_OF, "1y")
    assert page.similar_group == "Software"
    assert all(
        next(s for s in universe() if s.ticker == p.ticker).industry == page.similar_group
        for p in page.similar
    )


# ------------------------------------------------- the factor glosses


def test_every_scored_factor_carries_a_plain_explanation():
    """The factor `detail` lines are compared character for character against
    the reference by test_stock_scoring_parity, so they cannot be reworded --
    "Death Cross" and "MACD -12.36, Signal -13.34" are theirs. A reader still
    has to be told what those mean, so the gloss sits beside them."""
    from app.services.screener import stock_scoring

    keys = {f["key"] for f in stock_scoring.FACTOR_WEIGHTS} if hasattr(
        stock_scoring, "FACTOR_WEIGHTS"
    ) else {"pe", "eps_growth", "roe", "pb", "div_yield",
            "rsi", "macd", "ema_trend", "delivery", "support"}
    missing = [k for k in keys if not pw.factor_gloss(k)]
    assert not missing, f"no plain words for {missing}"


def test_a_gloss_explains_the_term_and_never_restates_the_number():
    """One gloss has to be right for every company. A gloss carrying a figure
    would be wrong for all but one of them, and would duplicate arithmetic that
    already lives upstream."""
    import re

    for key in ("pe", "rsi", "macd", "ema_trend", "delivery", "support",
                "roe", "pb", "div_yield", "eps_growth"):
        text = pw.factor_gloss(key)
        assert "₹" not in text, f"{key} quotes rupees"
        # "50-day", "200-day", "70", "30" are part of what the term means; a
        # decimal or a percent sign is a measurement of one company.
        assert "%" not in text, f"{key} quotes a percentage"
        assert not re.search(r"\d+\.\d", text), f"{key} quotes a decimal"


def test_the_delivery_gloss_says_it_is_one_day_and_therefore_jumpy():
    """This factor spent its whole life as a constant 4.5 for every company,
    because the scorer's documented source returns 403. The exchange's
    end-of-day archive was never gated, so it is real now — but it is ONE day,
    and a single block deal moves a mid-cap's figure by twenty points. The
    gloss has to carry that, or a live number reads as a considered one."""
    text = pw.factor_gloss("delivery")
    assert "one day" in text
    assert "end-of-day" in text


def test_an_unknown_factor_gets_no_gloss_rather_than_a_wrong_one():
    assert pw.factor_gloss("something_new") is None
