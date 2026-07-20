from datetime import date

import pytest

from app.services.marketdata import mutual_fund as mf

SEARCH_PAYLOAD = [
    {"schemeCode": 122640, "schemeName": "Parag Parikh Flexi Cap Fund - Regular Plan - Growth"},
    {"schemeCode": 122639, "schemeName": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth"},
]

SCHEME_PAYLOAD = {
    "meta": {
        "fund_house": "PPFAS Mutual Fund",
        "scheme_type": "Open Ended Schemes",
        "scheme_category": "Equity Scheme - Flexi Cap Fund",
        "scheme_code": 122639,
        "scheme_name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        "isin_growth": "INF879O01027",
        "isin_div_reinvestment": None,
    },
    # mfapi.in returns newest-first; the service must flip it to oldest-first.
    "data": [
        {"date": "17-07-2026", "nav": "91.46030"},
        {"date": "16-07-2026", "nav": "91.02810"},
        {"date": "15-07-2026", "nav": "91.12620"},
    ],
    "status": "SUCCESS",
}


@pytest.fixture(autouse=True)
def _clear_cache():
    mf.clear_cache()
    yield
    mf.clear_cache()


def _stub(monkeypatch, payload, calls=None):
    def fake_get_json(path: str):
        if calls is not None:
            calls.append(path)
        return payload

    monkeypatch.setattr(mf, "_get_json", fake_get_json)


def test_search_returns_scheme_codes_as_strings(monkeypatch):
    _stub(monkeypatch, SEARCH_PAYLOAD)
    results = mf.search_schemes("parag parikh flexi")
    assert [r.scheme_code for r in results] == ["122640", "122639"]
    assert results[1].scheme_name.endswith("Direct Plan - Growth")


def test_search_query_is_url_encoded():
    """Fund names contain spaces and ampersands, which would otherwise
    corrupt the request URL."""
    calls: list[str] = []

    def fake_get_json(path: str):
        calls.append(path)
        return SEARCH_PAYLOAD

    import app.services.marketdata.mutual_fund as module

    original = module._get_json
    module._get_json = fake_get_json
    try:
        mf.search_schemes("Aditya Birla Sun Life & Co")
    finally:
        module._get_json = original

    assert " " not in calls[0]
    assert "%26" in calls[0]  # the ampersand


def test_nav_history_is_parsed_and_ordered_oldest_first(monkeypatch):
    _stub(monkeypatch, SCHEME_PAYLOAD)
    history = mf.get_nav_history("122639")
    assert [p.date for p in history] == [
        date(2026, 7, 15),
        date(2026, 7, 16),
        date(2026, 7, 17),
    ]
    assert history[-1].nav == pytest.approx(91.4603)
    assert isinstance(history[0].nav, float)


def test_latest_nav_is_the_most_recent_point(monkeypatch):
    _stub(monkeypatch, SCHEME_PAYLOAD)
    latest = mf.get_latest_nav("122639")
    assert latest.date == date(2026, 7, 17)
    assert latest.nav == pytest.approx(91.4603)


def test_scheme_meta_exposes_category_for_peer_ranking(monkeypatch):
    _stub(monkeypatch, SCHEME_PAYLOAD)
    meta = mf.get_scheme_meta("122639")
    assert meta.scheme_category == "Equity Scheme - Flexi Cap Fund"
    assert meta.fund_house == "PPFAS Mutual Fund"
    assert meta.is_direct_growth is True


def test_regular_plan_is_not_flagged_direct_growth(monkeypatch):
    payload = {
        **SCHEME_PAYLOAD,
        "meta": {
            **SCHEME_PAYLOAD["meta"],
            "scheme_name": "Parag Parikh Flexi Cap Fund - Regular Plan - Growth",
        },
    }
    _stub(monkeypatch, payload)
    assert mf.get_scheme_meta("122640").is_direct_growth is False


def test_repeat_calls_hit_cache_not_the_network(monkeypatch):
    calls: list[str] = []
    _stub(monkeypatch, SCHEME_PAYLOAD, calls)
    mf.get_nav_history("122639")
    mf.get_nav_history("122639")
    mf.get_scheme_meta("122639")
    assert len(calls) == 1


def test_zero_nav_placeholder_rows_are_dropped(monkeypatch):
    """AMFI's feed carries 0.0 NAV rows for dates before a scheme launched.
    Left in, they divide into infinities and poison every metric."""
    _stub(
        monkeypatch,
        {
            **SCHEME_PAYLOAD,
            "data": [
                {"date": "17-07-2026", "nav": "91.46030"},
                {"date": "16-07-2026", "nav": "91.02810"},
                {"date": "03-01-2013", "nav": "0.00000"},
                {"date": "04-01-2013", "nav": "0.00000"},
            ],
        },
    )
    history = mf.get_nav_history("122639")
    assert len(history) == 2
    assert all(p.nav > 0 for p in history)


def test_a_scheme_with_only_placeholder_rows_raises(monkeypatch):
    _stub(monkeypatch, {**SCHEME_PAYLOAD, "data": [{"date": "03-01-2013", "nav": "0.0"}]})
    with pytest.raises(mf.MutualFundDataError):
        mf.get_nav_history("122639")


def test_empty_nav_history_raises_rather_than_returning_garbage(monkeypatch):
    _stub(monkeypatch, {**SCHEME_PAYLOAD, "data": []})
    with pytest.raises(mf.MutualFundDataError):
        mf.get_latest_nav("122639")


def test_a_dropped_connection_is_retried(monkeypatch):
    """mfapi.in intermittently drops TLS handshakes; one blip must not fail
    a whole portfolio valuation."""
    import httpx

    attempts = {"n": 0}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return SCHEME_PAYLOAD

    def flaky_get(url, timeout):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectTimeout("handshake timed out")
        return FakeResponse()

    monkeypatch.setattr(mf.httpx, "get", flaky_get)
    monkeypatch.setattr(mf.time, "sleep", lambda _: None)

    assert mf.get_latest_nav("122639").nav == pytest.approx(91.4603)
    assert attempts["n"] == 2


def test_persistent_failure_still_raises(monkeypatch):
    import httpx

    attempts = {"n": 0}

    def always_fails(url, timeout):
        attempts["n"] += 1
        raise httpx.ConnectTimeout("down")

    monkeypatch.setattr(mf.httpx, "get", always_fails)
    monkeypatch.setattr(mf.time, "sleep", lambda _: None)

    with pytest.raises(mf.MutualFundDataError):
        mf.get_latest_nav("122639")
    assert attempts["n"] == mf._MAX_ATTEMPTS
