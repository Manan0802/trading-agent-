"""The two endpoints the AI layer is specified to call, and their declared shapes.

A tool with no declared shape cannot be grounded and cannot be cached. §3.2 says
the JSON shape is what `check_all` validates against and §4.4 hashes `tool_json`
into the cache key — both undefined operations on an endpoint whose response
type is `dict`.

These tests validate the models against what the ENGINES actually return, not
against a fixture. A model that agrees with a hand-written example and disagrees
with the engine is worse than no model: it declares a contract the app breaks.
"""

import json
from pathlib import Path

import pytest

from app.schemas.contracts import FactorEvidenceOut, TaxSavingOut
from app.services.advisor.tax_advisor import generate_tax_saving_plan

DATA = Path(__file__).resolve().parent.parent / "app" / "data"


class TestTaxSavingDeclaresWhatItReturns:
    @pytest.mark.parametrize(
        "income,c80,d80,nps,salaried,basic",
        [
            (600_000, 0, 0, False, True, 300_000),
            (1_500_000, 50_000, 0, False, True, 600_000),
            (2_500_000, 150_000, 25_000, True, True, 1_000_000),
            (5_500_000, 150_000, 50_000, True, False, 0),
            (12_000_000, 150_000, 50_000, True, True, 5_000_000),
        ],
    )
    def test_the_model_matches_the_engine_across_the_income_range(
        self, income, c80, d80, nps, salaried, basic
    ):
        payload = generate_tax_saving_plan(
            income, c80, d80, nps, is_salaried=salaried,
            other_deductions=0, basic_salary=basic,
        )
        out = TaxSavingOut.model_validate(payload)
        assert out.regime.recommended in {"new", "old"}
        assert out.evaluated_under == out.regime.recommended, (
            "pricing 80C against the old regime while recommending the new one "
            "produces a saving nobody can collect"
        )

    def test_an_inapplicable_deduction_is_shown_at_zero_not_dropped(self):
        """Under the new regime most of these are worth nothing.

        Hiding them leaves a reader wondering what happened to 80C, which is the
        question the screen exists to answer.
        """
        payload = generate_tax_saving_plan(
            1_500_000, 50_000, 0, False, is_salaried=True,
            other_deductions=0, basic_salary=600_000,
        )
        out = TaxSavingOut.model_validate(payload)
        assert out.regime.recommended == "new"
        unusable = [a for a in out.actions if not a.applicable]
        assert unusable, "no action was marked inapplicable under the new regime"
        for action in unusable:
            assert action.tax_saved == 0
            assert action.note, "an action shown at zero must say why"

    def test_the_declared_shape_serialises_without_losing_a_field(self):
        payload = generate_tax_saving_plan(
            2_500_000, 150_000, 25_000, True, is_salaried=True,
            other_deductions=0, basic_salary=1_000_000,
        )
        dumped = TaxSavingOut.model_validate(payload).model_dump(by_alias=True)
        assert set(dumped) == set(payload), (
            f"the contract adds or drops keys: {set(dumped) ^ set(payload)}"
        )
        assert set(dumped["regime"]) == set(payload["regime"])
        assert set(dumped["actions"][0]) == set(payload["actions"][0])


class TestFactorEvidenceDeclaresWhatItReturns:
    def test_the_model_matches_the_committed_file(self):
        raw = json.loads((DATA / "factor_evidence.json").read_text())
        out = FactorEvidenceOut.model_validate(raw)
        assert out.built_on, "a stale file must not be able to pass for a fresh one"
        assert len(out.factors) >= 3

    def test_the_reserved_word_field_keeps_its_real_name_in_json(self):
        """`from` is a Python keyword. Declaring a shape must not rename a field
        the frontend is already keyed on."""
        raw = json.loads((DATA / "factor_evidence.json").read_text())
        dumped = FactorEvidenceOut.model_validate(raw).model_dump(by_alias=True)
        assert set(dumped["period"]) == set(raw["period"])
        assert dumped["period"]["from"] == raw["period"]["from"]

    def test_every_factor_carries_its_episodes(self):
        """The honest half.

        Momentum's full-period t-stat is 3.11; across the 2009 rebound the same
        factor returned -53.5% annualised. A headline figure with no episodes
        reads as a promise.
        """
        raw = json.loads((DATA / "factor_evidence.json").read_text())
        out = FactorEvidenceOut.model_validate(raw)
        momentum = next(f for f in out.factors if f.code == "WML")
        assert momentum.significant and momentum.t_stat > 2
        assert momentum.episodes, "the winning factor ships with no bad periods shown"
        assert any(e.annual_return < 0 for e in momentum.episodes), (
            "every episode is positive, which is not what the source says"
        )


def test_both_routes_now_declare_a_shape():
    from app.main import app

    declared = {
        r.path: getattr(r, "response_model", None)
        for r in app.routes
        if getattr(r, "methods", None)
    }
    assert declared.get("/api/v1/advisor/tax-saving") is TaxSavingOut
    assert declared.get("/api/v1/research/evidence") is FactorEvidenceOut


def test_the_route_survives_the_form_s_own_defaults():
    """The regression this file did not catch the first time.

    Every parametrised case above passes a `basic_salary`. The app's own form
    does not, and without it the employer-NPS action has no amount — it is a
    percentage of basic. Declaring `amount` required therefore 500'd the
    endpoint for the ordinary path while five hand-picked incomes all passed.

    A contract validated only against fixtures you chose is a contract validated
    against your own assumptions.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    for income in (1_200_000, 1_200_001, 2_400_000, 50_000_000):
        response = client.post(
            "/api/v1/advisor/tax-saving",
            json={
                "annual_income": income,
                "existing_80c": 0,
                "existing_80d": 0,
                "has_nps": False,
            },
        )
        assert response.status_code == 200, f"{income}: {response.text[:200]}"
        actions = response.json()["actions"]
        nps = next(a for a in actions if "Employer NPS" in a["name"])
        assert nps["amount"] is None, (
            "an unknown basic salary must read as unknown, not as zero — zero "
            "says 'you can claim nothing', which is a different fact"
        )
        assert nps["note"], "and it has to say why"


def test_the_route_survives_a_taxpayer_who_owes_nothing():
    """The case a contract written from one example gets wrong.

    `breakeven_deductions` is None below the new regime's threshold — no amount
    of deductions can beat zero — and declaring it required makes the endpoint
    500 for exactly the people with the least money.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    body = {
        "annual_income": 600000,
        "existing_80c": 0,
        "existing_80d": 0,
        "has_nps": False,
        "is_salaried": True,
        "basic_salary": 300000,
    }
    response = TestClient(app).post("/api/v1/advisor/tax-saving", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["regime"]["new_regime_tax"] == 0
    assert payload["regime"]["breakeven_deductions"] is None
    assert "no amount of deductions" in payload["regime"]["rationale"]
