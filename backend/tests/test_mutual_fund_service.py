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


def test_empty_nav_history_raises_rather_than_returning_garbage(monkeypatch):
    _stub(monkeypatch, {**SCHEME_PAYLOAD, "data": []})
    with pytest.raises(mf.MutualFundDataError):
        mf.get_latest_nav("122639")
