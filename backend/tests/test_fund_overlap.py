import math
from datetime import date, timedelta

import numpy as np
import pytest

from app.services.advisor.fund_overlap import (
    DUPLICATE_ABOVE,
    MIN_MONTHS,
    analyse_overlap,
)
from app.services.marketdata.mutual_fund import NavPoint


def _next_month_end(d: date) -> date:
    """From one month-end to the next. Stepping into the following month first
    matters: without it, the 28th-plus-eight-days trick lands back on the month
    it started in."""
    first_of_next = (d + timedelta(days=1)).replace(day=28) + timedelta(days=8)
    return first_of_next.replace(day=1) - timedelta(days=1)


def _series(monthly_returns: list[float], start: date = date(2018, 1, 31)) -> list[NavPoint]:
    """One NAV per month-end, built from the returns given."""
    navs = [NavPoint(date=start, nav=100.0)]
    d = start
    for r in monthly_returns:
        d = _next_month_end(d)
        navs.append(NavPoint(date=d, nav=navs[-1].nav * (1 + r)))
    return navs


def _market(n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(rng.normal(0.01, 0.05, n))


def test_two_funds_tracking_the_same_market_are_called_one_position():
    """The finding the whole thing exists for: a second flexi-cap that moves
    with the first is not diversification, it is duplicate paperwork."""
    market = _market(60, seed=1)
    noise = _market(60, seed=2)
    a = _series(market)
    b = _series([m + 0.002 * n for m, n in zip(market, noise)])

    report = analyse_overlap([("a", "Fund A", a), ("b", "Fund B", b)])
    assert report.pairs[0].correlation > DUPLICATE_ABOVE
    assert "one position" in report.summary


def test_a_genuinely_different_fund_is_not_flagged():
    report = analyse_overlap(
        [
            ("a", "Equity Fund", _series(_market(60, seed=3))),
            ("b", "Debt Fund", _series([0.006] * 30 + [0.005] * 30)),
        ]
    )
    # A near-flat debt series still has variance, so a correlation exists and
    # it should be nowhere near duplicate territory.
    assert report.pairs
    assert report.pairs[0].correlation < DUPLICATE_ABOVE
    assert "not a duplicate" in report.summary or "Nothing here is a duplicate" in report.summary


def test_effective_positions_collapses_when_everything_moves_together():
    """Four identical funds are one bet, not four. The number has to say so."""
    market = _market(60, seed=4)
    funds = [(f"f{i}", f"Fund {i}", _series(market)) for i in range(4)]
    report = analyse_overlap(funds)
    assert report.counted == 4
    assert report.effective_positions is not None
    assert report.effective_positions < 1.5


def test_effective_positions_approaches_the_count_when_nothing_is_related():
    funds = [
        (f"f{i}", f"Fund {i}", _series(_market(80, seed=10 + i))) for i in range(4)
    ]
    report = analyse_overlap(funds)
    assert report.effective_positions is not None
    assert report.effective_positions > 3.0


def test_a_short_record_is_excluded_by_name_not_dropped_silently():
    long_fund = _series(_market(60, seed=5))
    short_fund = _series(_market(6, seed=6))
    report = analyse_overlap(
        [("a", "Long Fund", long_fund), ("b", "New Fund", short_fund)]
    )
    assert "New Fund" in report.excluded
    assert str(MIN_MONTHS) in report.excluded["New Fund"]
    assert report.pairs == []


def test_one_fund_alone_says_so_rather_than_reporting_nothing():
    report = analyse_overlap([("a", "Only Fund", _series(_market(60, seed=7)))])
    assert report.pairs == []
    assert report.effective_positions is None
    assert "Two funds" in report.summary


def test_a_fund_whose_nav_never_moves_is_skipped_not_scored_as_diversifying():
    """Correlation against a constant is undefined. Returning 0 would read as
    'perfectly diversifying', which is the opposite of what we know."""
    flat = _series([0.0] * 60)

    report = analyse_overlap(
        [("a", "Real Fund", _series(_market(60, seed=8))), ("b", "Frozen Fund", flat)]
    )
    assert report.pairs == []


def test_a_gap_in_one_series_does_not_become_a_multi_month_return():
    """Comparing a three-month move against a one-month move is two different
    questions treated as one."""
    market = _market(60, seed=9)
    full = _series(market)
    holed = [p for i, p in enumerate(_series(market)) if i not in (20, 21, 22)]

    report = analyse_overlap([("a", "Full", full), ("b", "Holed", holed)])
    assert report.pairs
    # The shared consecutive months are fewer than the full history, and the
    # correlation stays honest rather than being wrecked by a stitched return.
    assert report.pairs[0].months < 60
    assert report.pairs[0].correlation > 0.95


def test_correlations_come_back_worst_first():
    funds = [
        ("a", "A", _series(_market(70, seed=21))),
        ("b", "B", _series(_market(70, seed=22))),
        ("c", "C", _series(_market(70, seed=21))),
    ]
    report = analyse_overlap(funds)
    values = [p.correlation for p in report.pairs]
    assert values == sorted(values, reverse=True)
    assert not math.isnan(values[0])


@pytest.mark.parametrize("count", [2, 3, 5])
def test_every_pair_is_reported_once(count):
    funds = [
        (f"f{i}", f"Fund {i}", _series(_market(70, seed=30 + i))) for i in range(count)
    ]
    report = analyse_overlap(funds)
    assert len(report.pairs) == count * (count - 1) // 2
