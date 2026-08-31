"""The three new endpoints, called as ROUTES rather than as engines.

`GET /portfolio/look-through` shipped returning 500 for anybody who actually
held something. The route multiplied `holding.quantity * holding.avg_price` —
two fields `Holding` does not have. It is a name, a code and a list of
transactions, and the value comes from `value_portfolio`, which every other
handler in that file already uses.

Every test passed. They called `look_through([("Fund A", 100_000.0)])` — the
engine, with tuples — and never called the route with a row. An engine test and
a route test are different tests, and only one of them would have caught this.
"""

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

_PRICES = {"122639": 130.0, "118955": 1500.0}


def setup_module():
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _offline_prices(monkeypatch):
    def fake_price(asset_type: str, identifier: str) -> float:
        if identifier not in _PRICES:
            raise ValueError(f"no price for {identifier}")
        return _PRICES[identifier]

    monkeypatch.setattr(portfolio_router, "get_current_price", fake_price)


_seq = iter(range(41000, 49999))


def _user() -> dict:
    n = next(_seq)
    db = SessionLocal()
    u = User(name=f"R{n}", phone=f"+9100{n}", email=f"r{n}@example.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    token = generate_jwt(
        {"sub": str(u.id), "aud": ["fastapi-users:auth"]}, settings.jwt_secret, 3600
    )
    db.close()
    return {"Authorization": f"Bearer {token}"}


def _holds(headers, identifier="118955", name="HDFC Flexi Cap Fund - Growth Option - Regular Plan"):
    created = client.post(
        "/api/v1/portfolio/holdings",
        json={"name": name, "asset_type": "MF", "identifier": identifier, "category": "Flexi Cap"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    holding_id = created.json()["id"]
    txn = client.post(
        f"/api/v1/portfolio/holdings/{holding_id}/transactions",
        json={"txn_type": "BUY", "txn_date": "2023-01-05", "units": 15, "price": 1400},
        headers=headers,
    )
    assert txn.status_code in (200, 201), txn.text
    return holding_id


class TestLookThrough:
    def test_it_answers_for_somebody_who_actually_holds_something(self):
        """The exact case that 500'd: a user with a holding and transactions."""
        headers = _user()
        _holds(headers)
        r = client.get("/api/v1/portfolio/look-through", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "covered_share" in body
        assert body["summary"]

    def test_an_empty_portfolio_is_a_prompt_not_a_crash(self):
        r = client.get("/api/v1/portfolio/look-through", headers=_user())
        assert r.status_code == 200, r.text
        assert r.json()["companies"] == []
        assert "Add a fund holding" in r.json()["summary"]

    def test_a_holding_we_cannot_price_does_not_take_the_page_down(self):
        headers = _user()
        _holds(headers, identifier="999999", name="A Fund With No Price")
        r = client.get("/api/v1/portfolio/look-through", headers=headers)
        assert r.status_code == 200, r.text


class TestAlreadyOwn:
    def test_it_answers_against_a_real_portfolio(self):
        headers = _user()
        _holds(headers)
        r = client.get("/api/v1/portfolio/already-own/122639", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scheme_code"] == "122639"
        assert body["summary"]

    def test_an_unknown_scheme_is_a_404_not_a_zero(self):
        r = client.get("/api/v1/portfolio/already-own/000000", headers=_user())
        assert r.status_code == 404


class TestCompanyExposure:
    def test_a_company_we_hold_nothing_of_is_a_404_not_a_zero(self):
        """"You own none of this" and "none of the funds we could open holds it"
        are different claims, and the second is the honest one."""
        headers = _user()
        _holds(headers)
        r = client.get("/api/v1/portfolio/company-exposure/INE000000000", headers=headers)
        assert r.status_code == 404
        assert "we could read" in r.json()["detail"]


def test_none_of_the_three_reads_a_field_the_model_does_not_have():
    """Pinned against the source. `Holding` has no quantity and no avg_price,
    and reaching for them raised only at request time — past every test that
    called the engine instead of the route."""
    import ast
    import inspect

    from app.routers import portfolio

    # Parsed, not grepped. The docstring above deliberately quotes the broken
    # expression, and a string search would match its own explanation — the
    # same trap `test_ter_coverage` fell into when it asserted a constant was
    # gone and matched the comment describing what the constant had cost.
    tree = ast.parse(inspect.getsource(portfolio))
    reads = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "holding"
    }
    for missing in ("quantity", "avg_price"):
        assert missing not in reads, (
            f"a handler reads `holding.{missing}`, which does not exist on the "
            "model — it raises at request time, past every test that calls the "
            "engine instead of the route"
        )
