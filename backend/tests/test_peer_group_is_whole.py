"""A fund that fails to load must not take everyone else's score with it.

The score is PEER-RELATIVE: a fund's number is its standing among the peers that
loaded. So a single transient NAV fetch failure moves every other fund in the
category — and the old code returned `(None, None)` on that failure, which
removed the fund from the ranked list AND from the unscorable list. It
evaporated, and nothing on screen said the peer group had shrunk.

Measured on a cold server: the goal plan and the research page returned **87.81
and 88.13 for the same fund in the same category**, and on the second call, with
everything cached, they agreed exactly. Two surfaces disagreeing about one
number is the thing this app exists not to do.
"""

from datetime import date, timedelta

import pytest

from app.services.advisor import category_ranking
from app.services.marketdata import mutual_fund
from app.services.marketdata.mutual_fund import NavPoint


class _Entry:
    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name
        self.category = "Equity Scheme - Flexi Cap Fund"


def _series(days: int = 1400, start: float = 100.0) -> list[NavPoint]:
    """Comfortably past the three years the scorer needs.

    A 900-day fixture made every fund unscorable, which quietly turned the
    first test in this file into an assertion about an empty list.
    """
    first = date.today() - timedelta(days=days)
    return [NavPoint(date=first + timedelta(days=i), nav=start + i * 0.05) for i in range(days)]


def test_a_fund_whose_nav_fails_is_named_rather_than_vanishing(monkeypatch):
    entries = [_Entry(f"10000{i}", f"Fund {i}") for i in range(6)]

    def flaky(code: str):
        if code == "100003":
            raise mutual_fund.MutualFundDataError("upstream said no")
        return _series()

    monkeypatch.setattr(category_ranking.mutual_fund, "get_nav_history", flaky)
    result = category_ranking.rank_codes("Equity Scheme - Flexi Cap Fund", entries)

    ranked = {r.fund.scheme_code for r in result.ranked}
    unscorable = {u.scheme_code for u in result.unscorable}
    assert ranked, "the fixture must produce a real ranking, or these prove nothing"
    assert "100003" not in ranked
    assert "100003" in unscorable, (
        "it disappeared from both lists, so the peer group silently shrank and "
        "every remaining fund's percentile moved"
    )
    assert len(ranked) + len(unscorable) == len(entries), (
        "every fund asked about must be accounted for in one list or the other"
    )
    reason = next(u.reason for u in result.unscorable if u.scheme_code == "100003")
    assert "could not be fetched" in reason


def test_a_transient_failure_is_retried_before_it_counts(monkeypatch):
    """One bad response should not cost a fund its place in its own category."""
    attempts: dict[str, int] = {}

    def once_flaky(code: str):
        attempts[code] = attempts.get(code, 0) + 1
        if code == "100002" and attempts[code] == 1:
            raise mutual_fund.MutualFundDataError("transient")
        return _series()

    monkeypatch.setattr(category_ranking.mutual_fund, "get_nav_history", once_flaky)
    entries = [_Entry(f"10000{i}", f"Fund {i}") for i in range(5)]
    result = category_ranking.rank_codes("Equity Scheme - Flexi Cap Fund", entries)

    assert attempts["100002"] == 2, "it was never retried"
    assert "100002" in {r.fund.scheme_code for r in result.ranked}
    assert not result.unscorable


def test_an_empty_series_is_also_named(monkeypatch):
    monkeypatch.setattr(
        category_ranking.mutual_fund,
        "get_nav_history",
        lambda code: [] if code == "100001" else _series(),
    )
    entries = [_Entry(f"10000{i}", f"Fund {i}") for i in range(4)]
    result = category_ranking.rank_codes("Equity Scheme - Flexi Cap Fund", entries)
    assert "100001" in {u.scheme_code for u in result.unscorable}


def test_the_same_peers_give_the_same_scores_every_time(monkeypatch):
    """The property the two surfaces were failing: determinism given one input."""
    monkeypatch.setattr(
        category_ranking.mutual_fund, "get_nav_history", lambda code: _series()
    )
    entries = [_Entry(f"10000{i}", f"Fund {i}") for i in range(6)]
    runs = [
        [(r.fund.scheme_code, round(r.fund.score, 6))
         for r in category_ranking.rank_codes("Equity Scheme - Flexi Cap Fund", entries).ranked]
        for _ in range(3)
    ]
    assert runs[0], "nothing ranked, so this proves nothing"
    assert runs[0] == runs[1] == runs[2]


def test_no_code_path_drops_a_fund_without_saying_so():
    """Pinned against the source, because the failure is an ABSENCE — there is
    no wrong number to catch, only a fund that is not there."""
    import inspect

    source = inspect.getsource(category_ranking.rank_codes)
    body = source[source.index("def load("):]
    # The only mention left should be the comment explaining what it used to do.
    live = [
        line for line in body.splitlines()
        if "return None, None" in line and not line.strip().startswith("#")
    ]
    assert not live, f"a fund can still vanish silently: {live}"
