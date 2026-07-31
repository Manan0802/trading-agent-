"""A wound-up scheme must not be ranked as something you could buy.

A scheme that merged or matured keeps its full history in AMFI's feed, so it
builds evidence like any other fund and scores like any other fund. Nothing
about it looks wrong -- the record is real, it simply ended. Before this check,
Sundaram Multi Asset Fund ranked #6 of 23 in Multi Cap having last published a
NAV 2,772 days earlier.
"""
from datetime import date, timedelta

import pytest

from app.services.advisor import category_ranking as cr
from app.services.marketdata.mutual_fund import NavPoint


class _Entry:
    def __init__(self, code, name):
        self.code = code
        self.name = name
        self.category = "Equity Scheme - Multi Cap Fund"


def _series(last_date: date, days: int = 1500) -> list[NavPoint]:
    """A plausible NAV history ending on `last_date`.

    Over four years, because the scorer refuses anything without a full three
    and a shorter fixture would fail for that reason instead of this one.
    """
    return [
        NavPoint(date=last_date - timedelta(days=i), nav=100.0 + (days - i) * 0.05)
        for i in range(days, -1, -1)
    ]


@pytest.fixture
def feed(monkeypatch):
    """Map scheme code -> last NAV date."""
    series: dict[str, date] = {}

    def fake(code):
        if code not in series:
            raise cr.mutual_fund.MutualFundDataError("unknown")
        return _series(series[code])

    monkeypatch.setattr(cr.mutual_fund, "get_nav_history", fake)
    return series


# The score is peer-relative, so a category of one cannot be ranked at all.
# Every case therefore carries live peers, and asserts about the fund under test.
_PEERS = ("peer-a", "peer-b")


def _rank(series):
    return cr.rank_codes(
        "Equity Scheme - Multi Cap Fund",
        [_Entry(code, f"Fund {code}") for code in series],
    )


def _with_peers(feed, **subjects):
    """Populate the feed with two live peers plus the funds under test."""
    for peer in _PEERS:
        feed[peer] = date.today() - timedelta(days=1)
    feed.update(subjects)
    return feed


def _ranked_codes(feed):
    return {f.fund.evidence.scheme_code for f in _rank(feed).ranked}


class TestExclusion:
    def test_a_scheme_that_stopped_publishing_years_ago_is_not_ranked(self, feed):
        _with_peers(feed, dead=date.today() - timedelta(days=2772))
        ranked = _ranked_codes(feed)
        assert "peer-a" in ranked
        assert "dead" not in ranked

    def test_it_is_listed_with_a_reason_rather_than_dropped_in_silence(self, feed):
        # "23 funds" that was really 29 is an omission the reader cannot see.
        _with_peers(feed, dead=date.today() - timedelta(days=2772))
        closed = [u for u in _rank(feed).unscorable if u.scheme_code == "dead"]
        assert len(closed) == 1
        assert "2772 days ago" in closed[0].reason
        assert "wound up" in closed[0].reason

    def test_the_reason_names_the_last_date_so_it_can_be_checked(self, feed):
        last = date.today() - timedelta(days=400)
        _with_peers(feed, dead=last)
        closed = [u for u in _rank(feed).unscorable if u.scheme_code == "dead"][0]
        assert str(last) in closed.reason


class TestDoesNotOverreach:
    def test_a_fund_that_published_yesterday_is_ranked(self, feed):
        _with_peers(feed, live=date.today() - timedelta(days=1))
        assert "live" in _ranked_codes(feed)

    def test_a_long_holiday_does_not_remove_a_live_fund(self, feed):
        # The threshold is a month precisely so no Indian market closure
        # reaches it. Diwali plus a weekend is nowhere near.
        _with_peers(feed, holiday=date.today() - timedelta(days=10))
        assert "holiday" in _ranked_codes(feed)

    def test_the_boundary_is_inclusive_of_thirty_days(self, feed):
        _with_peers(feed, edge=date.today() - timedelta(days=cr._CLOSED_AFTER_DAYS))
        assert "edge" in _ranked_codes(feed)

    def test_one_day_past_the_boundary_is_excluded(self, feed):
        _with_peers(feed, past=date.today() - timedelta(days=cr._CLOSED_AFTER_DAYS + 1))
        assert "past" not in _ranked_codes(feed)
        assert any(u.scheme_code == "past" for u in _rank(feed).unscorable)

    def test_an_unreachable_fund_is_not_reported_as_wound_up(self, feed):
        # The feed being down is not evidence a scheme closed. It is simply
        # absent, as it was before.
        _with_peers(feed)
        result = cr.rank_codes(
            "Equity Scheme - Multi Cap Fund",
            [_Entry(c, c) for c in (*_PEERS, "missing")],
        )
        assert not any(
            u.scheme_code == "missing" and "wound up" in u.reason
            for u in result.unscorable
        )
