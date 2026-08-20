"""The boundary that stops a newly listed company being ranked the best stock in India.

`stock_scoring.py` is a faithful port and reproduces upstream's behaviour,
including the worst of it. This is the other half: the gate everything must
come through before it can be ranked. Same arrangement as the fund side, where
`scoring.py` is faithful and `universe.is_scoreable` decides who gets in.
"""

import numpy as np
import pandas as pd
import pytest

from app.services.screener import sector_benchmarks as sb
from app.services.screener import stock_scoring as ss


def closes(n: int, start: float = 100.0, step: float = 0.4) -> pd.Series:
    return pd.Series(
        [start + i * step for i in range(n)],
        index=pd.bdate_range("2026-01-01", periods=n),
    )


FUNDAMENTALS = {
    "trailing_pe": 24.0, "price_to_book": 4.0, "roe": 0.18,
    "div_yield": 1.2, "eps_ttm": 30.0, "eps_prev": 25.0, "current_price": 720.0,
}


# ------------------------------------------------- the incident, encoded


def test_a_nan_total_clamps_to_the_top_of_the_scale_not_the_bottom():
    """The arithmetic behind the whole file, in one line of Python.

    `max(0.0, min(100.0, nan))` is 100.0, because `nan < 100.0` is False. A NaN
    does not surface as missing data and does not surface as an error. It
    surfaces as the highest score the model can award.
    """
    nan = float("nan")
    assert (nan < 100.0) is False
    assert max(0.0, min(100.0, nan)) == 100.0


def test_fourteen_days_of_history_is_refused_before_it_can_be_ranked():
    """`_compute_rsi` needs 14 non-null deltas, so 15 closes. Upstream guards
    with `>= 14` -- one short -- and the result is a perfect 100 "Strong Buy"
    for a company the model has computed nothing about. Companies with exactly
    14 days of history are the newest listings on the exchange."""
    ok, why = ss.is_scoreable(closes(14), FUNDAMENTALS)
    assert ok is False
    assert "14 days" in why and "15 needed" in why


def test_fifteen_days_is_enough():
    assert ss.is_scoreable(closes(15), FUNDAMENTALS) == (True, "")


def test_the_gate_sits_exactly_one_row_above_upstreams():
    """If someone "aligns" this with upstream's `>= 14`, the 100-score returns."""
    assert ss.MIN_ROWS_TO_SCORE == ss.MIN_ROWS_RSI + 1


def test_the_refused_stock_really_would_have_scored_a_hundred():
    """The gate is only worth having if the thing behind it is real. This runs
    the port on the input the gate refuses and asserts what comes out."""
    result = ss.score_stock(FUNDAMENTALS, closes(14), sb.resolve("Technology"))
    assert result["total"] == 100.0, (
        "the port no longer reproduces the incident; the gate may be unnecessary "
        "or the port may have drifted"
    )
    assert ss.is_scoreable(closes(14), FUNDAMENTALS)[0] is False


def test_a_scoreable_stock_does_not_score_a_hundred():
    result = ss.score_stock(FUNDAMENTALS, closes(400), sb.resolve("Technology"))
    assert 0.0 < result["total"] < 100.0
    assert ss.is_meaningless(result) is False


# ------------------------------------------------- the belt behind the braces


@pytest.mark.parametrize(
    "total", [float("nan"), 100.0, 100.1, None, "not a number"]
)
def test_a_meaningless_total_is_caught_at_the_point_of_use(total):
    """If a NaN ever reaches a total by another route -- a new factor, a changed
    window -- this catches it before it sorts to the top of the page."""
    assert ss.is_meaningless({"total": total}) is True


@pytest.mark.parametrize("total", [0.0, 47.5, 99.9])
def test_a_real_total_passes(total):
    assert ss.is_meaningless({"total": total}) is False


# ------------------------------------------------- other refusals


def test_no_history_at_all_is_refused_by_name():
    assert ss.is_scoreable(None)[1] == "no price history"
    assert ss.is_scoreable(pd.Series(dtype=float))[1] == "no price history"


def test_a_company_with_no_published_fundamentals_is_refused():
    """Half the score is valuation. With no PE, no P/B, no ROE and no EPS, every
    one of those factors takes its neutral half-marks and the stock is ranked on
    momentum wearing a fundamentals label."""
    blank = {"trailing_pe": None, "price_to_book": None, "roe": None, "eps_ttm": None}
    ok, why = ss.is_scoreable(closes(400), blank)
    assert ok is False and "fundamentals" in why


def test_one_published_fundamental_is_enough_to_be_scoreable():
    partial = {"trailing_pe": 24.0, "price_to_book": None, "roe": None, "eps_ttm": None}
    assert ss.is_scoreable(closes(400), partial)[0] is True


def test_history_is_checked_even_when_fundamentals_are_not_supplied():
    assert ss.is_scoreable(closes(14))[0] is False
    assert ss.is_scoreable(closes(400))[0] is True


# ------------------------------------------------- disclosure, not exclusion


def test_a_stock_without_two_hundred_closes_is_scoreable_but_flagged():
    """60 closes gives a real RSI and a real MACD but no 200-day EMA, so the
    trend factor is measured against a shorter average than every other stock's.
    Not a reason to exclude it; a reason to say so on screen."""
    assert ss.is_scoreable(closes(60), FUNDAMENTALS)[0] is True
    assert ss.thin_history(closes(60)) is True
    assert ss.thin_history(closes(400)) is False


def test_the_thin_threshold_is_the_longest_window_the_port_uses():
    assert ss.MIN_ROWS_FOR_FULL_TECHNICALS == ss.MIN_ROWS_EMA200
