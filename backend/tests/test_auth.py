from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_users_me_requires_auth():
    r = client.get("/api/v1/users/me")
    assert r.status_code == 401


def test_google_authorize_returns_google_url():
    r = client.get("/api/v1/auth/google/authorize")
    assert r.status_code == 200
    assert "accounts.google.com" in r.json()["authorization_url"]


def test_register_and_login_with_password():
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "pw-user@example.com", "password": "correct-horse-battery", "name": "PW"},
    )
    assert r.status_code == 201, r.text

    r = client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "pw-user@example.com", "password": "correct-horse-battery"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "pw-user@example.com"


def test_login_with_wrong_password_rejected():
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "correct-horse-battery"},
    )
    r = client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "wrongpw@example.com", "password": "not-the-password"},
    )
    assert r.status_code == 400
