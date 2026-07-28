"""Editing and deleting a goal.

The affordability check on the goals page tells a user their goals cost more
than they earn and that a target or date has to move. Until this existed, there
was no way to move one: goals could be created and read and nothing else. Advice
with the door locked.
"""

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


def _user(email: str) -> dict:
    db = SessionLocal()
    user = User(
        email=email,
        hashed_password="x",
        is_active=True,
        is_verified=True,
        name="Editor",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    headers = {
        "Authorization": "Bearer "
        + generate_jwt(
            {"sub": str(user.id), "aud": ["fastapi-users:auth"]},
            settings.jwt_secret,
            60 * 60,
        )
    }
    db.close()
    return headers


def _goal(headers: dict, **overrides) -> dict:
    body = {
        "goal_type": "education",
        "goal_name": "College",
        "target_amount": 4_000_000,
        "current_savings": 200_000,
        "target_date": "2041-06-01",
        "years": 15,
        "risk_profile": "moderate",
    }
    body.update(overrides)
    r = client.post("/api/v1/goals", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


class TestMovingTheDate:
    """What the affordability verdict actually tells people to do."""

    def test_pushing_the_date_out_lowers_the_monthly_figure(self):
        headers = _user("edit-date@example.com")
        goal = _goal(headers)
        before = goal["required_monthly_sip"]

        r = client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"years": 25, "target_date": "2051-06-01"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        after = r.json()
        assert after["required_monthly_sip"] < before
        assert after["years"] == 25

    def test_cutting_the_target_also_lowers_it(self):
        headers = _user("edit-target@example.com")
        goal = _goal(headers)
        r = client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"target_amount": 2_000_000},
            headers=headers,
        )
        assert r.json()["required_monthly_sip"] < goal["required_monthly_sip"]


class TestEverythingDerivedFollows:
    def test_the_allocation_is_recomputed_not_left_behind(self):
        """A shorter horizon means less equity. Patching the years and leaving
        a 75% equity split beside it would be a plan for the old goal."""
        headers = _user("edit-alloc@example.com")
        goal = _goal(headers, years=25, target_date="2051-06-01")
        r = client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"years": 2, "target_date": "2028-06-01"},
            headers=headers,
        )
        assert r.json()["equity_allocation"] < goal["equity_allocation"]

    def test_the_explanation_is_regenerated_rather_than_kept(self):
        headers = _user("edit-explain@example.com")
        goal = _goal(headers)
        r = client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"target_amount": 9_000_000},
            headers=headers,
        )
        assert r.json()["llm_explanation"] != goal["llm_explanation"]

    def test_changing_the_goal_type_moves_its_inflation_rate_with_it(self):
        """Education inflates far faster than a holiday. A type change that
        left the old rate would silently under-fund or over-fund the goal."""
        headers = _user("edit-type@example.com")
        goal = _goal(headers, goal_type="education")
        r = client.patch(
            f"/api/v1/goals/{goal['id']}", json={"goal_type": "travel"}, headers=headers
        )
        assert r.json()["inflation_rate"] != goal["inflation_rate"]

    def test_an_explicitly_pinned_rate_survives_a_type_change(self):
        headers = _user("edit-pinned@example.com")
        goal = _goal(headers)
        r = client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"goal_type": "travel", "inflation_rate": 0.09},
            headers=headers,
        )
        assert r.json()["inflation_rate"] == 0.09


class TestPartialEdits:
    def test_a_field_left_out_keeps_its_value(self):
        headers = _user("edit-partial@example.com")
        goal = _goal(headers)
        r = client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"goal_name": "Renamed"},
            headers=headers,
        )
        after = r.json()
        assert after["goal_name"] == "Renamed"
        assert after["target_amount"] == goal["target_amount"]
        assert after["years"] == goal["years"]

    def test_a_negative_target_is_rejected_rather_than_stored(self):
        headers = _user("edit-negative@example.com")
        goal = _goal(headers)
        r = client.patch(
            f"/api/v1/goals/{goal['id']}",
            json={"target_amount": -5000},
            headers=headers,
        )
        assert r.status_code == 422


class TestDeleting:
    def test_a_deleted_goal_is_gone_from_the_list_and_the_total(self):
        headers = _user("delete-goal@example.com")
        first = _goal(headers, goal_name="Keep")
        second = _goal(headers, goal_name="Drop")

        before = client.get("/api/v1/goals/commitment", headers=headers).json()
        assert before["total_monthly"] > first["required_monthly_sip"]

        assert client.delete(f"/api/v1/goals/{second['id']}", headers=headers).status_code == 204

        names = [g["goal_name"] for g in client.get("/api/v1/goals", headers=headers).json()]
        assert names == ["Keep"]
        after = client.get("/api/v1/goals/commitment", headers=headers).json()
        assert after["total_monthly"] == first["required_monthly_sip"]

    def test_deleting_twice_reports_not_found_rather_than_succeeding(self):
        headers = _user("delete-twice@example.com")
        goal = _goal(headers)
        assert client.delete(f"/api/v1/goals/{goal['id']}", headers=headers).status_code == 204
        assert client.delete(f"/api/v1/goals/{goal['id']}", headers=headers).status_code == 404


class TestOtherPeoplesGoals:
    def test_another_user_cannot_edit_your_goal(self):
        mine = _user("owner-edit@example.com")
        theirs = _user("intruder-edit@example.com")
        goal = _goal(mine)
        r = client.patch(
            f"/api/v1/goals/{goal['id']}", json={"target_amount": 1}, headers=theirs
        )
        assert r.status_code == 404

    def test_another_user_cannot_delete_your_goal(self):
        mine = _user("owner-delete@example.com")
        theirs = _user("intruder-delete@example.com")
        goal = _goal(mine)
        assert client.delete(f"/api/v1/goals/{goal['id']}", headers=theirs).status_code == 404
        assert client.get(f"/api/v1/goals/{goal['id']}", headers=mine).status_code == 200
