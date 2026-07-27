from datetime import date, timedelta

import pytest

from app.services.advisor.backtest import (
    BacktestWindow,
    forward_return,
    run_backtest,
)
from app.services.marketdata.mutual_fund import NavPoint


def _navs(start: date, days: int, daily: float, nav0: float = 100.0) -> list[NavPoint]:
    return [
        NavPoint(date=start + timedelta(days=i), nav=nav0 * (1 + daily) ** i)
        for i in range(days)
    ]


def test_forward_return_is_measured_from_the_decision_date_onward():
    # Long enough that the three-year window closes inside the series.
    navs = _navs(date(2015, 1, 1), 2600, 0.0004)
    r = forward_return(navs, start=date(2018, 1, 1), years=3)
    assert r is not None
    assert r == pytest.approx(0.1566, abs=0.01)


def test_no_forward_return_when_the_fund_stops_before_the_window_ends():
    """A fund that was wound up mid-window has no three-year return, and
    treating its last NAV as the endpoint would flatter it."""
    navs = _navs(date(2015, 1, 1), 1200, 0.0004)
    assert forward_return(navs, start=date(2017, 1, 1), years=3) is None


def test_no_forward_return_before_the_fund_existed():
    navs = _navs(date(2019, 1, 1), 1500, 0.0004)
    assert forward_return(navs, start=date(2015, 1, 1), years=3) is None


# --- the backtest itself -----------------------------------------------------


def _universe():
    """Three funds whose ranking at the decision date is knowable, and whose
    behaviour afterwards is not implied by it."""
    start = date(2012, 1, 1)
    return {
        # Steady through the whole period.
        "steady": _navs(start, 5200, 0.00045),
        # Strong before the decision date, weak after: the case a naive
        # backtest gets wrong by scoring on data it should not have.
        "hot_then_cold": _navs(start, 2400, 0.0009) + _navs(
            date(2018, 7, 24), 2800, 0.00005, nav0=100.0 * (1.0009**2399)
        ),
        "weak": _navs(start, 5200, 0.00015),
    }


def _decision(): return date(2018, 7, 24)


def test_the_score_only_sees_nav_up_to_the_decision_date():
    """The whole point. If the picker can see the future it is not a backtest."""
    seen: list[date] = []

    def spy_scorer(evidence_by_code):
        for navs in evidence_by_code.values():
            if navs:
                seen.append(navs[-1].date)
        return list(evidence_by_code)[:1]

    run_backtest(_universe(), decision_dates=[_decision()], holding_years=3,
                 picker=spy_scorer, top_n=1)
    assert seen
    assert all(d <= _decision() for d in seen)


def test_the_result_compares_the_picks_against_the_whole_category():
    """A pick that beat the market is only interesting against the alternative
    the user actually had, which is any fund in the category."""
    result = run_backtest(
        _universe(), decision_dates=[_decision()], holding_years=3,
        picker=lambda ev: ["steady"], top_n=1,
    )
    w = result.windows[0]
    assert w.picked_return is not None
    assert w.category_median_return is not None
    assert w.spread == pytest.approx(w.picked_return - w.category_median_return)


def test_a_window_with_no_survivors_is_reported_not_dropped():
    """Dropping it would quietly delete the periods where everything failed."""
    short = {"a": _navs(date(2012, 1, 1), 2400, 0.0004)}
    result = run_backtest(short, decision_dates=[_decision()], holding_years=3,
                          picker=lambda ev: ["a"], top_n=1)
    assert len(result.windows) == 1
    assert result.windows[0].picked_return is None


def test_survivorship_exposure_is_measured_and_reported():
    """Our catalogue only contains funds alive today, so a backtest over it is
    optimistic by construction. Saying so is the difference between a backtest
    and a brochure."""
    result = run_backtest(_universe(), decision_dates=[_decision()],
                          holding_years=3, picker=lambda ev: ["steady"], top_n=1)
    assert result.survivorship_note
    assert "alive today" in result.survivorship_note.lower()


def test_several_windows_are_summarised_by_how_often_the_picks_won():
    """One window is an anecdote. The hit rate across windows is the claim."""
    dates = [date(2016, 1, 1), date(2017, 1, 1), date(2018, 1, 1)]
    result = run_backtest(_universe(), decision_dates=dates, holding_years=3,
                          picker=lambda ev: ["steady"], top_n=1)
    assert result.windows_measured == 3
    assert 0.0 <= result.hit_rate <= 1.0
    assert result.median_spread is not None


def test_a_backtest_with_nothing_measurable_says_so_rather_than_claiming_zero():
    result = run_backtest({}, decision_dates=[_decision()], holding_years=3,
                          picker=lambda ev: [], top_n=1)
    assert result.windows_measured == 0
    assert result.hit_rate == 0.0
    assert result.median_spread is None


def test_the_picker_never_sees_a_fund_that_did_not_exist_yet():
    universe = dict(_universe())
    universe["newborn"] = _navs(date(2020, 1, 1), 900, 0.0004)
    offered: set[str] = set()

    def spy(evidence_by_code):
        offered.update(evidence_by_code)
        return ["steady"]

    run_backtest(universe, decision_dates=[_decision()], holding_years=3,
                 picker=spy, top_n=1)
    assert "newborn" not in offered
