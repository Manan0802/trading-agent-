"""`fund_evidence.py` had no test file at all, and it defines what "1y" means.

Found by mutation testing on pass 51 of the Phase 1 review: changing
`WINDOWS = {"1y": 365, …}` to `{"1y": 300, …}` left **all 1,577 tests passing**.
The module is imported by `routers/research.py`, `routers/portfolio.py`,
`category_ranking.py`, `screener/serve.py` and `fund_facts.py`, and it decides
what a year means in every piece of fund evidence this app produces — including
the base rates §1.4 of the plan calls one of the five findings the design rests
on.

These tests are written to fail on that mutation, not to raise a coverage
number. Each pins a decision the module's own comments explain: the window
lengths, the percentage-to-fraction conversion for TER, and the refusal to
invent evidence from nothing.
"""

from datetime import date, timedelta

import pytest

from app.services.advisor.fund_evidence import WINDOWS, build_evidence
from app.services.marketdata.mutual_fund import NavPoint


def _series(days: int, start: float = 100.0, daily: float = 0.0004) -> list[NavPoint]:
    """A smoothly rising NAV series, oldest first, one point per calendar day."""
    first = date(2026, 8, 27) - timedelta(days=days - 1)
    return [
        NavPoint(date=first + timedelta(days=i), nav=start * (1 + daily) ** i)
        for i in range(days)
    ]


def test_the_window_lengths_are_what_the_labels_say():
    """The mutation that survived: 1y meaning 300 days rather than 365.

    Written as an equality on the constant because that is the thing that can
    silently move. A window labelled "1y" that covers ten months makes every
    rolling statistic, base rate and peer comparison built on it wrong in a way
    no screen would reveal — the number still renders, it just measures
    something else.
    """
    assert WINDOWS == {"1y": 365, "3y": 1095, "5y": 1825}


def test_a_window_only_appears_when_the_history_can_support_it():
    """Two years of NAV must produce 1y evidence and no 3y or 5y evidence.

    Partial windows are the failure this guards: a fund with 22 months of
    history that reports a "3y" figure is being compared against funds measured
    over a genuinely different period, which is §14's rule that a base-rate
    class never widens, applied one level down.
    """
    ev = build_evidence("100001", "Two Year Fund", "Equity", _series(730))
    assert ev is not None
    assert "1y" in ev.windows
    assert "3y" not in ev.windows
    assert "5y" not in ev.windows


def test_four_years_of_history_reaches_3y_but_not_5y():
    ev = build_evidence("100002", "Four Year Fund", "Equity", _series(1461))
    assert ev is not None
    assert {"1y", "3y"} <= set(ev.windows)
    assert "5y" not in ev.windows


def test_no_nav_returns_none_rather_than_empty_evidence():
    """None, not a hollow object. An empty `FundEvidence` would rank."""
    assert build_evidence("100003", "No Data Fund", "Equity", []) is None


def test_history_years_measures_the_series_not_the_windows():
    ev = build_evidence("100004", "Three Year Fund", "Equity", _series(1096))
    assert ev is not None
    assert ev.history_years == pytest.approx(3.0, abs=0.05)


def test_ter_is_converted_from_percent_to_fraction():
    """The module's own comment: "a 0.75% TER and a 0.0075 return are the same
    units". The table stores percentages, the scorer works in fractions, and a
    missed division by 100 makes cost a hundred times the strongest signal in
    the score while nothing looks obviously broken.

    ⚠️ A first version of this test asserted against an UNKNOWN scheme code,
    which returns `None` before the conversion ever runs — so it passed while
    the mutation that deletes `/ 100.0` still survived. The test was
    decoration. It has to use a code that is actually in the table.
    """
    # 103490 = QUANTUM VALUE FUND in app/data/expense_ratios.json:
    # direct_ter 1.12, regular_ter 2.15, both stored as PERCENTAGES.
    ev = build_evidence("103490", "Quantum Value Fund", "Equity", _series(400))
    assert ev is not None
    assert ev.direct_ter == pytest.approx(0.0112)
    assert ev.regular_ter == pytest.approx(0.0215)
    # and the sanity band the scorer relies on: a TER is never a whole number
    assert 0.0 < ev.direct_ter < 0.10


def test_an_unpriced_fund_gets_none_not_zero():
    """Section 14: missing cost is neutral, never dropped and never 0.0.

    A zero would read as "this fund is free" and rank it first on the one
    signal that measurably predicts — which is how three unpriced funds once
    reached a Large Cap top five.
    """
    ev = build_evidence("999999", "Unknown Fund", "Equity", _series(400))
    assert ev is not None
    assert ev.direct_ter is None
    assert ev.regular_ter is None
