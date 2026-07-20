import pytest
from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.routers import portfolio as portfolio_router

client = TestClient(app)
settings = get_settings()

PRICES = {"122639": 130.0, "RELIANCE.NS": 1300.0}


def setup_module():
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _offline_prices(monkeypatch):
    """Never hit mfapi.in / Yahoo from the test suite."""

    def fake_price(asset_type: str, identifier: str) -> float:
        if identifier not in PRICES:
            raise ValueError(f"no price for {identifier}")
        return PRICES[identifier]

    monkeypatch.setattr(portfolio_router, "get_current_price", fake_price)


_user_seq = iter(range(1000, 9999))


def _new_user() -> dict:
    n = next(_user_seq)
    db = SessionLocal()
    u = User(
        name=f"P{n}",
        phone=f"+9100000{n}",
        email=f"p{n}@example.com",
        hashed_password="x",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    token = generate_jwt(
        {"sub": str(u.id), "aud": ["fastapi-users:auth"]}, settings.jwt_secret, 3600
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


def _add_fund(headers, identifier="122639", name="PPFAS Flexi Cap - Direct Growth"):
    r = client.post(
        "/api/v1/portfolio/holdings",
        json={
            "name": name,
            "asset_type": "MF",
            "identifier": identifier,
            "category": "Flexi Cap",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_txn(headers, holding_id, txn_date, txn_type, units, price):
    return client.post(
        f"/api/v1/portfolio/holdings/{holding_id}/transactions",
        json={
            "txn_date": txn_date,
            "txn_type": txn_type,
            "units": units,
            "price": price,
        },
        headers=headers,
    )


def test_requires_auth():
    assert client.get("/api/v1/portfolio").status_code == 401
    assert client.post("/api/v1/portfolio/holdings", json={}).status_code == 401


def test_create_holding_and_add_transactions():
    headers = _new_user()
    hid = _add_fund(headers)

    r = _add_txn(headers, hid, "2024-01-01", "BUY", 100, 100.0)
    assert r.status_code == 201, r.text
    # Amount is derived server-side, never taken from the client.
    assert r.json()["amount"] == pytest.approx(10000)

    detail = client.get(f"/api/v1/portfolio/holdings/{hid}", headers=headers).json()
    assert len(detail["transactions"]) == 1


def test_portfolio_summary_reports_value_and_returns():
    headers = _new_user()
    hid = _add_fund(headers)
    _add_txn(headers, hid, "2024-01-01", "BUY", 100, 100.0)

    body = client.get("/api/v1/portfolio", headers=headers).json()

    assert body["total_invested"] == pytest.approx(10000)
    assert body["total_current_value"] == pytest.approx(13000)  # 100 units @ 130
    assert body["total_unrealised_gain"] == pytest.approx(3000)
    assert body["absolute_return"] == pytest.approx(0.30)
    assert body["xirr"] is not None
    assert body["has_pricing_errors"] is False

    holding = body["holdings"][0]
    assert holding["units_held"] == pytest.approx(100)
    assert holding["current_price"] == pytest.approx(130.0)


def test_summary_handles_a_sell_and_reports_realised_gain():
    headers = _new_user()
    hid = _add_fund(headers)
    _add_txn(headers, hid, "2024-01-01", "BUY", 100, 100.0)
    _add_txn(headers, hid, "2024-07-01", "SELL", 40, 120.0)

    holding = client.get("/api/v1/portfolio", headers=headers).json()["holdings"][0]
    assert holding["units_held"] == pytest.approx(60)
    assert holding["realised_gain"] == pytest.approx(800)  # 40 x (120 - 100)
    assert holding["current_value"] == pytest.approx(7800)


def test_cannot_sell_more_units_than_held():
    headers = _new_user()
    hid = _add_fund(headers)
    _add_txn(headers, hid, "2024-01-01", "BUY", 10, 100.0)

    r = _add_txn(headers, hid, "2024-02-01", "SELL", 25, 120.0)
    assert r.status_code == 400
    assert "more units than held" in r.json()["detail"]


def test_units_and_price_must_be_positive():
    headers = _new_user()
    hid = _add_fund(headers)
    assert _add_txn(headers, hid, "2024-01-01", "BUY", 0, 100.0).status_code == 422
    assert _add_txn(headers, hid, "2024-01-01", "BUY", 10, -5).status_code == 422


def test_unpriceable_holding_does_not_break_the_summary():
    headers = _new_user()
    good = _add_fund(headers)
    _add_txn(headers, good, "2024-01-01", "BUY", 100, 100.0)
    bad = _add_fund(headers, identifier="999999", name="Delisted Fund")
    _add_txn(headers, bad, "2024-01-01", "BUY", 50, 100.0)

    body = client.get("/api/v1/portfolio", headers=headers).json()

    assert body["has_pricing_errors"] is True
    assert body["unpriced_invested"] == pytest.approx(5000)
    # Returns still reflect only what could actually be valued.
    assert body["total_invested"] == pytest.approx(10000)
    assert body["absolute_return"] == pytest.approx(0.30)
    assert len(body["holdings"]) == 2


def test_holdings_are_scoped_to_their_owner():
    alice = _new_user()
    bob = _new_user()
    hid = _add_fund(alice)
    _add_txn(alice, hid, "2024-01-01", "BUY", 100, 100.0)

    assert client.get(f"/api/v1/portfolio/holdings/{hid}", headers=bob).status_code == 404
    assert _add_txn(bob, hid, "2024-02-01", "BUY", 1, 100.0).status_code == 404
    assert client.get("/api/v1/portfolio", headers=bob).json()["holdings"] == []


def test_delete_holding_removes_its_transactions():
    headers = _new_user()
    hid = _add_fund(headers)
    _add_txn(headers, hid, "2024-01-01", "BUY", 100, 100.0)

    assert client.delete(f"/api/v1/portfolio/holdings/{hid}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/portfolio/holdings/{hid}", headers=headers).status_code == 404
    assert client.get("/api/v1/portfolio", headers=headers).json()["holdings"] == []


def test_stock_and_fund_appear_together_in_one_portfolio():
    headers = _new_user()
    fund = _add_fund(headers)
    _add_txn(headers, fund, "2024-01-01", "BUY", 10, 100.0)

    r = client.post(
        "/api/v1/portfolio/holdings",
        json={
            "name": "Reliance Industries",
            "asset_type": "STOCK",
            "identifier": "RELIANCE.NS",
        },
        headers=headers,
    )
    stock_id = r.json()["id"]
    _add_txn(headers, stock_id, "2024-01-01", "BUY", 5, 1000.0)

    body = client.get("/api/v1/portfolio", headers=headers).json()
    assert body["total_invested"] == pytest.approx(1000 + 5000)
    assert body["total_current_value"] == pytest.approx(1300 + 6500)
    assert {h["asset_type"] for h in body["holdings"]} == {"MF", "STOCK"}


def test_empty_portfolio_is_valid_not_an_error():
    headers = _new_user()
    body = client.get("/api/v1/portfolio", headers=headers).json()
    assert body["holdings"] == []
    assert body["total_invested"] == 0
    assert body["xirr"] is None
    assert body["absolute_return"] == 0
