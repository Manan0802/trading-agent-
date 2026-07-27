from datetime import date

import pytest
from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.routers import research as research_router
from app.services.advisor.category_ranking import CategoryRanking, RankedFund
from app.services.advisor.fund_score import (
    FundEvidence,
    ScoredFund,
    UnscorableFund,
    WindowEvidence,
)
from app.services.advisor.fund_verdict import Verdict
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
        "build_category_ranking",
        lambda category, **kw: CategoryRanking(
            category=category,
            priced=1,
            ranked=[
                RankedFund(
                    rank=1,
                    fund=ScoredFund(
                        scheme_code="122639",
                        scheme_name=META.scheme_name,
                        category=META.scheme_category,
                        score=81.0,
                        breakdown={"consistency": 0.92, "cost": 0.71},
                        evidence_strength=1.0,
                        evidence=FundEvidence(
                            scheme_code="122639",
                            scheme_name=META.scheme_name,
                            category=META.scheme_category,
                            windows={
                                "3y": WindowEvidence(
                                    mean=0.192, worst=0.008, share_positive=1.0, count=1414
                                )
                            },
                            volatility=0.13,
                            max_drawdown=-0.31,
                            direct_ter=0.0063,
                            regular_ter=0.0128,
                            history_years=13.2,
                        ),
                    ),
                    verdict=Verdict(
                        headline=(
                            "Across 1,414 possible three-year holding periods, this "
                            "fund never lost money."
                        ),
                        points=["Ranked 1 of 34 Flexi Cap funds."],
                    ),
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
    assert client.get(
        "/api/v1/research/fund-rankings/Equity Scheme - Flexi Cap Fund"
    ).status_code == 401
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


def test_category_ranking_carries_the_evidence_and_the_verdict():
    body = client.get(
        "/api/v1/research/fund-rankings/Equity Scheme - Flexi Cap Fund",
        headers=_headers(),
    ).json()
    top = body["ranked"][0]
    assert top["rank"] == 1
    assert top["score"] == pytest.approx(81.0)
    assert top["windows"]["3y"]["count"] == 1414
    assert top["windows"]["3y"]["worst"] == pytest.approx(0.008)
    assert "1,414" in top["verdict"]["headline"]
    assert body["unscorable"][0]["reason"] == "Not enough history"


def test_both_plans_are_returned_so_the_commission_can_be_priced():
    """The gap between them is what a distributor takes every year, and it is
    the one number an advisor can show and a distributor cannot."""
    body = client.get(
        "/api/v1/research/fund-rankings/Equity Scheme - Flexi Cap Fund",
        headers=_headers(),
    ).json()
    top = body["ranked"][0]
    assert top["direct_ter"] < top["regular_ter"]
    assert body["priced"] == 1


def test_the_length_of_the_record_is_reported_alongside_the_score():
    """A score built on three years of one market is not the same claim as one
    built on thirteen, and the caller has to be able to tell them apart."""
    body = client.get(
        "/api/v1/research/fund-rankings/Equity Scheme - Flexi Cap Fund",
        headers=_headers(),
    ).json()
    top = body["ranked"][0]
    assert top["history_years"] == pytest.approx(13.2)
    assert top["evidence_strength"] == pytest.approx(1.0)


def test_an_unknown_category_is_404():
    r = client.get("/api/v1/research/fund-rankings/Equity Scheme - Unicorn Fund",
                   headers=_headers())
    assert r.status_code == 404
