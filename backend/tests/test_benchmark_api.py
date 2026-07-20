from datetime import date

import pytest
from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.routers import portfolio as portfolio_router
from app.services.marketdata.mutual_fund import NavPoint

client = TestClient(app)
settings = get_settings()


def setup_module():
    Base.metadata.create_all(bind=engine)


_seq = iter(range(7000, 7999))


def _user_headers() -> dict:
    n = next(_seq)
    db = SessionLocal()
    u = User(name=f"B{n}", phone=f"+9122{n}", email=f"b{n}@example.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    token = generate_jwt(
        {"sub": str(u.id), "aud": ["fastapi-users:auth"]}, settings.jwt_secret, 3600
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(
        portfolio_router, "get_current_price", lambda asset_type, identifier: 130.0
    )
    # A benchmark that was flat, so any gain is the fund's own doing.
    monkeypatch.setattr(
        portfolio_router,
        "get_benchmark_navs",
        lambda: [
            NavPoint(date=date(2020, 1, 1), nav=100.0),
            NavPoint(date=date(2030, 1, 1), nav=100.0),
        ],
    )


def _seed_holding(headers):
    hid = client.post(
        "/api/v1/portfolio/holdings",
        json={"name": "A Fund", "asset_type": "MF", "identifier": "122639"},
        headers=headers,
    ).json()["id"]
    client.post(
        f"/api/v1/portfolio/holdings/{hid}/transactions",
        json={"txn_date": "2024-01-01", "txn_type": "BUY", "units": 100, "price": 100.0},
        headers=headers,
    )
    return hid


def test_benchmark_endpoint_requires_auth():
    assert client.get("/api/v1/portfolio/benchmark").status_code == 401


def test_portfolio_beating_a_flat_benchmark():
    headers = _user_headers()
    _seed_holding(headers)

    body = client.get("/api/v1/portfolio/benchmark", headers=headers).json()

    assert body["comparable"] is True
    assert body["portfolio_value"] == pytest.approx(13000)  # 100 units @ 130
    assert body["benchmark_value"] == pytest.approx(10000)  # flat index
    assert body["outperformance"] > 0


def test_empty_portfolio_is_not_comparable():
    headers = _user_headers()
    body = client.get("/api/v1/portfolio/benchmark", headers=headers).json()
    assert body["comparable"] is False
    assert body["reason"]
