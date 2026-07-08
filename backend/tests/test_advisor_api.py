from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import User

client = TestClient(app)
settings = get_settings()


def setup_module():
    Base.metadata.create_all(bind=engine)


def _auth_headers_for(user: User) -> dict:
    token = generate_jwt(
        {"sub": str(user.id), "aud": ["fastapi-users:auth"]},
        settings.jwt_secret,
        60 * 60,
    )
    return {"Authorization": f"Bearer {token}"}


def test_calc_sip_endpoint():
    r = client.post(
        "/api/v1/advisor/calculate-sip",
        json={
            "target_amount": 12000,
            "years": 1,
            "annual_return_rate": 0.0,
            "inflation_rate": 0.0,
        },
    )
    assert r.status_code == 200 and r.json()["required_monthly_sip"] == 1000


def test_unauthenticated_goal_creation_rejected():
    r = client.post("/api/v1/goals", json={"goal_type": "home", "goal_name": "House"})
    assert r.status_code == 401


def test_create_and_get_goal():
    db = SessionLocal()
    u = User(
        name="A",
        phone="+910000000000",
        email="a@example.com",
        hashed_password="not-used-oauth-only",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    headers = _auth_headers_for(u)
    db.close()

    r = client.post(
        "/api/v1/goals",
        json={
            "goal_type": "home",
            "goal_name": "House",
            "target_amount": 2000000,
            "target_date": "2031-01-01",
            "years": 5,
            "risk_profile": "moderate",
        },
        headers=headers,
    )
    assert r.status_code == 200
    gid = r.json()["id"]
    assert (
        client.get(f"/api/v1/goals/{gid}", headers=headers).json()["equity_allocation"] == 50
    )


def test_cannot_see_another_users_goal():
    db = SessionLocal()
    owner = User(
        name="Owner",
        phone="+910000000001",
        email="owner@example.com",
        hashed_password="x",
    )
    other = User(
        name="Other",
        phone="+910000000002",
        email="other@example.com",
        hashed_password="x",
    )
    db.add_all([owner, other])
    db.commit()
    db.refresh(owner)
    db.refresh(other)
    owner_headers = _auth_headers_for(owner)
    other_headers = _auth_headers_for(other)
    db.close()

    r = client.post(
        "/api/v1/goals",
        json={
            "goal_type": "home",
            "goal_name": "Owner's goal",
            "target_amount": 1000000,
            "target_date": "2031-01-01",
            "years": 5,
            "risk_profile": "moderate",
        },
        headers=owner_headers,
    )
    gid = r.json()["id"]
    assert client.get(f"/api/v1/goals/{gid}", headers=other_headers).status_code == 404
