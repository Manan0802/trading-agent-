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


# ---------------------------------------------------------------------------
# What you add each month: omitted means DERIVE, zero means zero.
# ---------------------------------------------------------------------------


def _recent_sips(headers, holding_id, months=12, amount=25_000.0):
    """Twelve monthly buys ending last month, so they sit inside the window."""
    from datetime import date, timedelta

    today = date.today()
    for i in range(months):
        when = today - timedelta(days=30 * (i + 1))
        _add_txn(headers, holding_id, when.isoformat(), "BUY", amount / 100.0, 100.0)


def test_omitting_the_monthly_amount_derives_it_from_actual_buys():
    """The decision screen passed a hardcoded 0, and 0 is not the same as
    "unsupplied" — it silently removed the largest lever on the page, the one
    worth ₹25 lakh to the reference user.

    Omitted must mean "work it out from what they actually put in"."""
    headers = _new_user()
    holding = _add_fund(headers)
    _recent_sips(headers, holding)

    got = client.get("/api/v1/portfolio/levers?years_remaining=15", headers=headers)
    assert got.status_code == 200, got.text
    keys = [lever["key"] for lever in got.json()["levers"]]
    assert "save_more" in keys, f"derivation did not fire: {keys}"


def test_passing_zero_still_means_zero():
    """Someone who genuinely adds nothing must not be told to add more on the
    strength of a purchase they made last year."""
    headers = _new_user()
    holding = _add_fund(headers)
    _recent_sips(headers, holding)

    got = client.get(
        "/api/v1/portfolio/levers?years_remaining=15&monthly_sip=0", headers=headers
    )
    keys = [lever["key"] for lever in got.json()["levers"]]
    assert "save_more" not in keys, "an explicit zero was overridden by the derivation"


def test_a_portfolio_with_no_recent_buys_gets_no_saving_lever():
    headers = _new_user()
    _add_fund(headers)
    got = client.get("/api/v1/portfolio/levers?years_remaining=15", headers=headers)
    assert "save_more" not in [lever["key"] for lever in got.json()["levers"]]


def test_the_four_lists_are_always_present_even_when_empty():
    """The screen reads all four. A missing key is a crash; an empty array is a
    finding."""
    headers = _new_user()
    body = client.get("/api/v1/portfolio/levers", headers=headers).json()
    for key in ("gates", "levers", "trades", "unpriced"):
        assert key in body, key
        assert isinstance(body[key], list)


def test_what_could_not_be_priced_comes_back_named():
    headers = _new_user()
    _add_fund(headers)
    body = client.get("/api/v1/portfolio/levers", headers=headers).json()
    assert body["unpriced"], "nothing was reported as unpriceable"
    for gap in body["unpriced"]:
        assert gap["why"] and gap["what_we_need"]


def test_the_decision_screen_shows_the_reference_class_for_the_users_own_money():
    """Not the fund they are reading about — the category holding most of what
    they actually own, with their own money in it."""
    headers = _new_user()
    holding = _add_fund(headers)
    _recent_sips(headers, holding)

    body = client.get("/api/v1/portfolio/levers", headers=headers).json()
    rate = body["base_rate"]
    assert rate is not None, "no reference class for a real holding"
    assert "Flexi Cap" in rate["sub_category"], rate["sub_category"]
    assert rate["rupees_at_risk"] and rate["rupees_at_risk"] > 0
    # The sentences, not just the numbers.
    assert "of every 100 stretches" in rate["plain"]["base_rate"]
    assert "₹" in rate["plain"]["worst_fall"]


def test_an_empty_portfolio_gets_no_reference_class_rather_than_a_default_one():
    """A base rate for a category you do not own is worse than none."""
    headers = _new_user()
    body = client.get("/api/v1/portfolio/levers", headers=headers).json()
    assert body["base_rate"] is None


def test_both_screens_describe_the_same_category_identically():
    """The fund page and the decision screen assemble this from one function.
    Two copies is how two screens start quoting different loss rates for the
    same category — the failure `scripts/consistency.py` exists to catch."""
    headers = _new_user()
    holding = _add_fund(headers)
    _recent_sips(headers, holding)

    from_decide = client.get("/api/v1/portfolio/levers", headers=headers).json()["base_rate"]
    from_fund = client.get(
        "/api/v1/screener/funds/122639/analysis?range=1y", headers=headers
    ).json().get("base_rate")
    if from_fund is None:
        pytest.skip("screener has no completed run in this environment")
    for field in ("category", "sub_category", "funds", "worst_fall", "first_safe_horizon"):
        assert from_decide[field] == from_fund[field], field


def test_the_decision_screen_publishes_our_own_hit_rate():
    """No Indian investing app publishes an audited track record for its own
    engine. Univest comes closest — "Price moved −196.70 (21.23%) since then" —
    one call marked to market, with no denominator."""
    headers = _new_user()
    body = client.get("/api/v1/portfolio/levers", headers=headers).json()
    record = body["track_record"]
    assert record is not None
    assert record["windows"] >= 40, "a hit rate with no sample is a testimonial"
    assert 0 < record["hit_rate"] < 1
    assert f"{record['wins']} of {record['windows']}" in record["plain"]
    assert record["measured_on"]


def test_when_our_own_ingredient_beats_our_score_the_screen_says_so():
    """Cost alone works 83 times in 100; the score we ship, 61. Adding risk and
    consistency to cost dilutes it. A product that hides that is marketing."""
    headers = _new_user()
    body = client.get("/api/v1/portfolio/levers", headers=headers).json()
    assert body["better_signal"], "the unflattering comparison was suppressed"
    assert "dilute" in body["better_signal"]
