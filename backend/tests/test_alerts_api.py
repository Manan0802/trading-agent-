"""The alert endpoint must not be a free WhatsApp gateway.

It shipped unauthenticated and taking the destination from the request body, so
with Twilio configured any stranger could send a message to any number in the
world on this account — a bill and an abuse report, with no login required.
Nothing broke while the credentials were empty, which is why it survived.

Both halves matter. Requiring a login stops strangers; taking the number from
the profile rather than the body stops the endpoint being a relay even for
someone who has one.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.routers import alerts as alerts_router

client = TestClient(app)
settings = get_settings()


def setup_module():
    Base.metadata.create_all(bind=engine)


_user_seq = iter(range(4000, 4999))


def _new_user(phone: str | None) -> dict:
    n = next(_user_seq)
    db = SessionLocal()
    user = User(
        name=f"A{n}", phone=phone, email=f"a{n}@example.com", hashed_password="x"
    )
    db.add(user)
    db.commit()
    token = generate_jwt(
        {"sub": str(user.id), "aud": ["fastapi-users:auth"]}, settings.jwt_secret, 3600
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sent(monkeypatch):
    """Record what would have gone out, without a Twilio account."""
    calls: list[tuple[str, str]] = []

    def fake_send(to_number: str, message: str) -> str:
        calls.append((to_number, message))
        return "SM_fake"

    monkeypatch.setattr(alerts_router, "send_whatsapp_message", fake_send)
    return calls


def test_anonymous_cannot_send(sent):
    response = client.post("/api/v1/alerts/test", json={})
    assert response.status_code == 401
    assert sent == []


def test_sends_to_the_caller_s_own_number_not_the_body_s(sent):
    headers = _new_user(phone="+919000000001")
    response = client.post(
        "/api/v1/alerts/test",
        json={"to_number": "+14155550000", "message": "hello"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["sent"] is True
    # The body named someone else's number and it was ignored.
    assert sent == [("+919000000001", "hello")]


def test_refuses_when_the_profile_has_no_number(sent):
    headers = _new_user(phone=None)
    response = client.post("/api/v1/alerts/test", json={}, headers=headers)
    assert response.status_code == 400
    assert "phone" in response.json()["detail"].lower()
    assert sent == []
