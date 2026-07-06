from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import User

client = TestClient(app)


def setup_module():
    Base.metadata.create_all(bind=engine)


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


def test_create_and_get_goal():
    db = SessionLocal()
    u = User(name="A", phone="+910000000000")
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = u.id
    db.close()

    r = client.post(
        "/api/v1/goals",
        json={
            "user_id": uid,
            "goal_type": "home",
            "goal_name": "House",
            "target_amount": 2000000,
            "target_date": "2031-01-01",
            "years": 5,
            "risk_profile": "moderate",
        },
    )
    assert r.status_code == 200
    gid = r.json()["id"]
    assert client.get(f"/api/v1/goals/{gid}").json()["equity_allocation"] == 50
