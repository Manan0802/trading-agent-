from datetime import date

import pytest
from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.routers import research as research_router
from app.services.advisor.fund_metrics import FundMetrics
from app.services.advisor.fund_scorer import ScoredFund, ScoringResult, UnscorableFund
from app.services.marketdata.mutual_fund import NavPoint, SchemeMeta, SchemeSearchResult
from app.services.marketdata.stock import StockDataError, StockFundamentals

client = TestClient(app)
settings = get_settings()


def setup_module():
    Base.metadata.create_all(bind=engine)


_seq = iter(range(8000, 8999))


def _headers() -> dict:
    n = next(_seq)
    db = SessionLocal()
    u = User(name=f"R{n}", phone=f"+9133{n}", email=f"r{n}@example.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    token = generate_jwt(
        {"sub": str(u.id), "aud": ["fastapi-users:auth"]}, settings.jwt_secret, 3600
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


META = SchemeMeta(
    scheme_code="122639",
    scheme_name="Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
    fund_house="PPFAS Mutual Fund",
    scheme_type="Open Ended Schemes",
    scheme_category="Equity Scheme - Flexi Cap Fund",
    isin="INF879O01027",
)

NAVS = [NavPoint(date=date(2020, 1, i + 1), nav=100.0 + i) for i in range(30)]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(
        research_router.mutual_fund,
        "search_schemes",
        lambda q: [SchemeSearchResult(scheme_code="122639", scheme_name=META.scheme_name)],
    )
    monkeypatch.setattr(research_router.mutual_fund, "get_scheme_meta", lambda c: META)
    monkeypatch.setattr(research_router.mutual_fund, "get_nav_history", lambda c: NAVS)
    monkeypatch.setattr(
        research_router,
        "load_scored_universe",
        lambda asset_class: ScoringResult(
            ranked=[
                ScoredFund(
                    scheme_code="122639",
                    scheme_name=META.scheme_name,
                    category=META.scheme_category,
                    metrics=FundMetrics(cagr_3y=0.146, sortino=1.4, consistency=0.93),
                    score=98.0,
                    breakdown={"sortino": 38.9, "consistency": 27.8},
                )
            ],
            unscorable=[
                UnscorableFund(
                    scheme_code="999", scheme_name="New Fund", reason="Not enough history"
                )
            ],
        ),
    )


def test_research_endpoints_require_auth():
    assert client.get("/api/v1/research/funds/search?q=parag").status_code == 401
    assert client.get("/api/v1/research/funds/122639").status_code == 401
    assert client.get("/api/v1/research/categories/equity").status_code == 401
    assert client.get("/api/v1/research/stocks/RELIANCE.NS").status_code == 401


def test_fund_search():
    body = client.get("/api/v1/research/funds/search?q=parag", headers=_headers()).json()
    assert body[0]["scheme_code"] == "122639"


def test_search_requires_a_real_query():
    assert client.get("/api/v1/research/funds/search?q=ab", headers=_headers()).status_code == 422


def test_fund_detail_includes_metrics_and_a_chart_series():
    body = client.get("/api/v1/research/funds/122639", headers=_headers()).json()
    assert body["scheme_name"].startswith("Parag Parikh")
    assert body["category"] == "Equity Scheme - Flexi Cap Fund"
    assert body["is_direct_growth"] is True
    assert body["latest_nav"] == pytest.approx(129.0)
    assert "metrics" in body
    assert len(body["nav_series"]) > 0


def test_category_ranking_lists_scored_and_unscorable_funds():
    body = client.get("/api/v1/research/categories/equity", headers=_headers()).json()
    assert body["benchmarked"] is True
    assert body["ranked"][0]["score"] == pytest.approx(98.0)
    assert body["ranked"][0]["breakdown"]["sortino"] == pytest.approx(38.9)
    assert body["unscorable"][0]["reason"] == "Not enough history"


def test_debt_category_is_reported_as_not_benchmarked():
    body = client.get("/api/v1/research/categories/debt", headers=_headers()).json()
    assert body["benchmarked"] is False


def test_unknown_asset_class_is_404():
    r = client.get("/api/v1/research/categories/crypto", headers=_headers())
    assert r.status_code == 404


def test_stock_fundamentals(monkeypatch):
    monkeypatch.setattr(
        research_router.stock,
        "get_stock_fundamentals",
        lambda t: StockFundamentals(
            ticker="RELIANCE.NS",
            name="Reliance Industries Limited",
            price=1323.1,
            previous_close=1327.2,
            currency="INR",
            sector="Energy",
            industry="Oil & Gas",
            market_cap=17904814784512,
            pe_ratio=23.96,
            eps=55.21,
            book_value=668.045,
            dividend_yield_pct=0.45,
            week52_high=1611.8,
            week52_low=1253.2,
        ),
    )
    body = client.get("/api/v1/research/stocks/RELIANCE.NS", headers=_headers()).json()
    assert body["name"] == "Reliance Industries Limited"
    assert body["pe_ratio"] == pytest.approx(23.96)
    assert body["day_change_pct"] < 0


def test_unknown_ticker_is_404(monkeypatch):
    def boom(t):
        raise StockDataError("No price available")

    monkeypatch.setattr(research_router.stock, "get_stock_fundamentals", boom)
    r = client.get("/api/v1/research/stocks/NOTREAL.NS", headers=_headers())
    assert r.status_code == 404


def test_data_outage_returns_503(monkeypatch):
    from app.services.marketdata.mutual_fund import MutualFundDataError

    def boom(*a, **k):
        raise MutualFundDataError("mfapi.in unreachable")

    monkeypatch.setattr(research_router.mutual_fund, "get_scheme_meta", boom)
    r = client.get("/api/v1/research/funds/122639", headers=_headers())
    assert r.status_code == 503
