import pytest
from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.routers import advisor as advisor_router
from app.services.advisor.fund_metrics import FundMetrics
from app.services.advisor.fund_recommender import (
    FundRecommendation,
    RecommendationResult,
    SkippedAssetClass,
)

client = TestClient(app)
settings = get_settings()


def setup_module():
    Base.metadata.create_all(bind=engine)


_seq = iter(range(5000, 5999))


def _user_headers() -> dict:
    n = next(_seq)
    db = SessionLocal()
    u = User(name=f"G{n}", phone=f"+9111{n}", email=f"g{n}@example.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    token = generate_jwt(
        {"sub": str(u.id), "aud": ["fastapi-users:auth"]}, settings.jwt_secret, 3600
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


def _fake_recommendations(allocation, monthly_sip, **kwargs):
    return RecommendationResult(
        recommendations=[
            FundRecommendation(
                asset_class="equity",
                scheme_code="122639",
                scheme_name="Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
                category="Equity Scheme - Flexi Cap Fund",
                monthly_amount=monthly_sip * 0.65,
                score=98.0,
                rationale="Ranked 1 of 9 Flexi Cap Fund funds. 14.6% a year over 3 years.",
                metrics=FundMetrics(cagr_3y=0.146, sortino=1.4),
            )
        ],
        skipped=[SkippedAssetClass(asset_class="gold", reason="below the minimum")],
    )


@pytest.fixture(autouse=True)
def _offline_recommender(monkeypatch):
    monkeypatch.setattr(
        advisor_router, "recommend_for_allocation", _fake_recommendations
    )


def _create_goal(headers) -> str:
    r = client.post(
        "/api/v1/goals",
        json={
            "goal_type": "retirement",
            "goal_name": "Retirement",
            "target_amount": 20000000,
            "target_date": "2046-01-01",
            "years": 20,
            "risk_profile": "aggressive",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_recommendations_require_auth():
    assert client.get("/api/v1/goals/some-id/recommendations").status_code == 401


def test_goal_returns_named_funds_with_amounts():
    headers = _user_headers()
    goal_id = _create_goal(headers)

    body = client.get(f"/api/v1/goals/{goal_id}/recommendations", headers=headers).json()

    assert body["goal_id"] == goal_id
    assert body["monthly_sip"] > 0
    assert body["allocation"]["equity"] > 0

    fund = body["recommendations"][0]
    assert fund["scheme_name"].startswith("Parag Parikh")
    assert fund["scheme_code"] == "122639"
    assert fund["monthly_amount"] > 0
    assert "Ranked 1 of 9" in fund["rationale"]


def test_asset_classes_that_were_skipped_are_disclosed():
    headers = _user_headers()
    goal_id = _create_goal(headers)
    body = client.get(f"/api/v1/goals/{goal_id}/recommendations", headers=headers).json()
    assert body["skipped"][0]["asset_class"] == "gold"


def test_another_user_cannot_read_your_recommendations():
    owner = _user_headers()
    intruder = _user_headers()
    goal_id = _create_goal(owner)
    r = client.get(f"/api/v1/goals/{goal_id}/recommendations", headers=intruder)
    assert r.status_code == 404


def test_a_data_source_outage_returns_503_not_a_crash(monkeypatch):
    from app.services.marketdata.mutual_fund import MutualFundDataError

    def failing(*args, **kwargs):
        raise MutualFundDataError("mfapi.in unreachable")

    monkeypatch.setattr(advisor_router, "recommend_for_allocation", failing)

    headers = _user_headers()
    goal_id = _create_goal(headers)
    r = client.get(f"/api/v1/goals/{goal_id}/recommendations", headers=headers)
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()
