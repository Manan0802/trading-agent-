from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User

client = TestClient(app)
settings = get_settings()


def setup_module():
    Base.metadata.create_all(bind=engine)


_seq = iter(range(9000, 9999))


def _headers() -> dict:
    n = next(_seq)
    db = SessionLocal()
    u = User(name=f"P{n}", phone=f"+9155{n}", email=f"p{n}@example.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    token = generate_jwt(
        {"sub": str(u.id), "aud": ["fastapi-users:auth"]}, settings.jwt_secret, 3600
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


def test_the_profile_requires_auth():
    assert client.get("/api/v1/profile").status_code == 401
    assert client.patch("/api/v1/profile", json={}).status_code == 401


def test_a_new_profile_is_empty_rather_than_guessed():
    """Defaulting somebody's income would put a confident rupee figure on the
    tax lever built from a number nobody supplied."""
    body = client.get("/api/v1/profile", headers=_headers()).json()
    assert body["annual_income"] is None
    assert body["basic_salary"] is None


def test_saving_a_profile_returns_what_was_saved():
    h = _headers()
    r = client.patch(
        "/api/v1/profile",
        json={"annual_income": 1500000, "basic_salary": 600000, "years_to_goal": 15},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["annual_income"] == 1500000
    assert body["basic_salary"] == 600000
    assert client.get("/api/v1/profile", headers=h).json()["years_to_goal"] == 15


def test_a_partial_update_leaves_the_rest_alone():
    h = _headers()
    client.patch("/api/v1/profile", json={"annual_income": 1200000, "existing_80c": 50000}, headers=h)
    client.patch("/api/v1/profile", json={"years_to_goal": 20}, headers=h)
    body = client.get("/api/v1/profile", headers=h).json()
    assert body["annual_income"] == 1200000
    assert body["existing_80c"] == 50000
    assert body["years_to_goal"] == 20


def test_the_profile_carries_the_tax_comparison_once_income_is_known():
    """The point of collecting income is the answer it unlocks, so the answer
    comes back with it rather than needing a second call."""
    h = _headers()
    body = client.patch(
        "/api/v1/profile",
        json={"annual_income": 1500000, "is_salaried": True},
        headers=h,
    ).json()
    assert body["tax"]["recommended"] in ("new", "old")
    assert body["tax"]["saving"] > 0


def test_no_tax_comparison_without_an_income():
    body = client.get("/api/v1/profile", headers=_headers()).json()
    assert body["tax"] is None


def test_a_negative_income_is_rejected_rather_than_stored():
    r = client.patch("/api/v1/profile", json={"annual_income": -5}, headers=_headers())
    assert r.status_code == 422


def test_one_user_cannot_read_another_profile():
    a, b = _headers(), _headers()
    client.patch("/api/v1/profile", json={"annual_income": 999000}, headers=a)
    assert client.get("/api/v1/profile", headers=b).json()["annual_income"] is None
