"""Whether a price is genuinely current, or quietly frozen.

Half of these assert silence. A false "your data is stale" on every Diwali
teaches the owner to ignore the warning, and then the one that matters -- a
scheme that merged and stopped publishing -- goes unread too.
"""
from datetime import date, timedelta

from app.services.portfolio.freshness import ALONE_DAYS, stale_days

TODAY = date(2026, 7, 31)


def days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)


class TestStaysQuiet:
    def test_yesterdays_nav_is_todays_answer(self):
        # NAVs publish around 11 PM IST, so yesterday's is normal, not stale.
        assert stale_days(days_ago(1), peer_dates=[days_ago(1)], today=TODAY) is None

    def test_a_long_weekend_is_not_a_frozen_feed(self):
        # Friday's NAV read on Tuesday. Every fund is equally behind, because
        # the market was shut -- which is exactly what peer comparison sees.
        friday = days_ago(4)
        assert stale_days(friday, peer_dates=[friday, friday, friday], today=TODAY) is None

    def test_a_whole_week_of_holidays_still_says_nothing(self):
        # Diwali. A fixed threshold would have to be looser than this to
        # survive, which is why the rule compares holdings instead.
        shut = days_ago(9)
        assert stale_days(shut, peer_dates=[shut, shut], today=TODAY) is None

    def test_one_day_behind_a_peer_is_ordinary_publishing_lag(self):
        assert stale_days(days_ago(2), peer_dates=[days_ago(1)], today=TODAY) is None

    def test_an_unpriced_holding_has_no_staleness_to_report(self):
        # It is already flagged as unpriced; two warnings for one fact is noise.
        assert stale_days(None, peer_dates=[days_ago(1)], today=TODAY) is None

    def test_a_lone_holding_is_given_the_benefit_of_the_doubt(self):
        # Nothing to compare against, so the calendar threshold applies and it
        # is deliberately loose.
        assert stale_days(days_ago(5), peer_dates=[], today=TODAY) is None


class TestCatchesTheRealThing:
    def test_a_fund_that_stopped_publishing_while_the_others_carried_on(self):
        # The case this exists for: a scheme merges or winds up, its series
        # stops, and the last NAV is returned forever as though it were today's.
        frozen = days_ago(30)
        assert stale_days(frozen, peer_dates=[days_ago(1), frozen], today=TODAY) == 29

    def test_it_reports_the_gap_to_the_peers_not_to_today(self):
        # What matters is how far behind the rest of the portfolio it is, since
        # the portfolio itself proves the market was open.
        assert stale_days(days_ago(20), peer_dates=[days_ago(2)], today=TODAY) == 18

    def test_a_lone_holding_is_eventually_still_caught(self):
        # Two weeks is past any Indian market closure, so this is a dead feed.
        assert stale_days(days_ago(ALONE_DAYS + 1), peer_dates=[], today=TODAY) == ALONE_DAYS + 1

    def test_the_freshest_peer_sets_the_bar_not_the_average(self):
        # One live fund is enough to prove the market published.
        frozen = days_ago(40)
        peers = [days_ago(1), days_ago(35), days_ago(38), frozen]
        assert stale_days(frozen, peer_dates=peers, today=TODAY) == 39


class TestEdges:
    def test_a_future_date_is_not_stale(self):
        assert stale_days(TODAY + timedelta(days=1), peer_dates=[], today=TODAY) is None

    def test_todays_price_is_never_stale_however_far_behind_peers_cannot_be(self):
        assert stale_days(TODAY, peer_dates=[TODAY], today=TODAY) is None


class TestStocksAreCoveredToo:
    """A suspended ticker freezes exactly as a wound-up scheme does.

    `price_as_of` used to return None for stocks on the belief that yfinance
    hands back no trade date. It does -- `regularMarketTime` -- so stocks had
    strictly less staleness protection than funds on the same page.
    """

    def test_a_market_timestamp_becomes_a_date(self, monkeypatch):
        from datetime import datetime

        from app.services.marketdata import stock

        stamp = datetime(2026, 8, 6, 15, 30).timestamp()
        monkeypatch.setattr(stock, "_info_cached", lambda _: {"regularMarketTime": stamp})
        assert stock.get_price_date("TATASTEEL.NS") == date(2026, 8, 6)

    def test_a_missing_timestamp_is_unknown_rather_than_today(self, monkeypatch):
        # Substituting today would assert the price is current, which is the
        # claim we cannot make.
        from app.services.marketdata import stock

        monkeypatch.setattr(stock, "_info_cached", lambda _: {"currentPrice": 100.0})
        assert stock.get_price_date("TATASTEEL.NS") is None

    def test_a_nonsense_timestamp_is_refused(self, monkeypatch):
        from app.services.marketdata import stock

        for bad in (0, -1, "yesterday", None):
            monkeypatch.setattr(stock, "_info_cached", lambda _, b=bad: {"regularMarketTime": b})
            assert stock.get_price_date("X.NS") is None
