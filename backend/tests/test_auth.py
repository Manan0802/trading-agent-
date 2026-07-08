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
