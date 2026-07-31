"""Adversarial pass over every endpoint, looking for 500s and nonsense answers.

Not a unit test suite. The tests assert what the code is supposed to do; this
asks what happens when someone types something the code was never shown — a
target date in the past, an income of one rupee, a fifty-crore goal, a negative
holding. A 500 is a bug. So is a 200 carrying a number that cannot be true.

    python scripts/edge_cases.py [--api http://127.0.0.1:8020]
"""

import argparse
import math
import sys
from datetime import date, timedelta

import httpx

FAILURES: list[str] = []
CHECKS = 0


def fail(what: str, detail: str) -> None:
    FAILURES.append(f"{what}: {detail}")


def check(what: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        fail(what, detail)


def finite(value) -> bool:
    """Rejects NaN and infinity, which serialise to JSON as bare tokens and
    render in a browser as 'NaN' sitting where a rupee figure should be."""
    return value is None or (isinstance(value, (int, float)) and math.isfinite(value))


def all_finite(payload, path="") -> list[str]:
    bad = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            bad += all_finite(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for i, value in enumerate(payload):
            bad += all_finite(value, f"{path}[{i}]")
    elif isinstance(payload, float) and not math.isfinite(payload):
        bad.append(f"{path} = {payload}")
    return bad


def main() -> int:
    parser = argparse.ArgumentParser()
    # 8000 and 8010 are other projects on this machine. A wrong default does not
    # error -- it runs the whole harness against a different app and passes.
    parser.add_argument("--api", default="http://127.0.0.1:8020")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    client = httpx.Client(base_url=api, timeout=60)
    email = f"edge{date.today().isoformat()}{id(client)}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "edge-case-pw", "name": "Edge", "phone": "+919000009999"},
    )
    token = client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "edge-case-pw"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # ---- the SIP calculator, at its edges -------------------------------
    for label, body in [
        ("zero years", {"target_amount": 100000, "years": 0}),
        ("half a year", {"target_amount": 100000, "years": 0.5}),
        ("a century", {"target_amount": 100000, "years": 100}),
        ("zero target", {"target_amount": 0, "years": 10}),
        ("one rupee target", {"target_amount": 1, "years": 10}),
        ("fifty crore", {"target_amount": 500_000_000, "years": 20}),
        ("already saved more than the target",
         {"target_amount": 100000, "years": 10, "current_savings": 10_000_000}),
        ("zero return", {"target_amount": 100000, "years": 10, "annual_return_rate": 0}),
        ("negative return", {"target_amount": 100000, "years": 10, "annual_return_rate": -0.05}),
        ("runaway inflation", {"target_amount": 100000, "years": 30, "inflation_rate": 0.5}),
    ]:
        r = client.post("/api/v1/advisor/calculate-sip", json=body)
        check(f"calculate-sip / {label}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:120]}")
        if r.status_code == 200:
            bad = all_finite(r.json())
            check(f"calculate-sip / {label} finite", not bad, str(bad))
            sip = r.json().get("required_monthly_sip")
            check(
                f"calculate-sip / {label} non-negative",
                sip is None or sip >= 0,
                f"required_monthly_sip = {sip}",
            )

    # ---- the tax comparison, across the whole income range --------------
    for income in [0, 1, 250_000, 700_000, 1_200_000, 1_200_001, 2_400_000, 50_000_000]:
        r = client.post(
            "/api/v1/advisor/tax-saving",
            json={"annual_income": income, "is_salaried": True},
        )
        check(f"tax-saving / income {income}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:120]}")
        if r.status_code == 200:
            payload = r.json()
            check(f"tax-saving / income {income} finite", not all_finite(payload), "")
            for key in ("new_regime_tax", "old_regime_tax", "saving"):
                value = payload["regime"][key]
                check(
                    f"tax-saving / income {income} {key} non-negative",
                    value >= 0,
                    f"{key} = {value}",
                )

    # ---- goals, including inputs a form should have caught --------------
    today = date.today()
    goal_cases = [
        ("a date in the past", {"target_date": str(today - timedelta(days=400)), "years": 1}, None),
        ("a date tomorrow", {"target_date": str(today + timedelta(days=1)), "years": 0.01}, None),
        ("fifty crore", {"target_amount": 500_000_000}, None),
        ("one rupee", {"target_amount": 1}, None),
        ("already fully saved", {"target_amount": 100_000, "current_savings": 100_000}, None),
        ("saved more than the target", {"target_amount": 100_000, "current_savings": 900_000}, None),
        ("a hundred years out", {"years": 100, "target_date": "2126-01-01"}, None),
        ("an unknown goal type", {"goal_type": "spaceship"}, None),
        ("an empty name", {"goal_name": ""}, None),
    ]
    created: list[str] = []
    for label, overrides, _ in goal_cases:
        body = {
            "goal_type": "education",
            "goal_name": f"Edge {label}",
            "target_amount": 1_000_000,
            "current_savings": 0,
            "target_date": str(today + timedelta(days=365 * 10)),
            "years": 10,
            "risk_profile": "moderate",
        }
        body.update(overrides)
        r = client.post("/api/v1/goals", json=body, headers=auth)
        check(f"create goal / {label}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:160]}")
        if r.status_code == 200:
            payload = r.json()
            bad = all_finite(payload)
            check(f"create goal / {label} finite", not bad, str(bad))
            sip = payload.get("required_monthly_sip")
            check(
                f"create goal / {label} sip sane",
                sip is None or (sip >= 0 and sip < 1e12),
                f"required_monthly_sip = {sip}",
            )
            alloc = sum(
                payload.get(k) or 0
                for k in ("equity_allocation", "debt_allocation", "gold_allocation")
            )
            check(
                f"create goal / {label} allocation sums to 100",
                alloc == 100,
                f"sums to {alloc}",
            )
            created.append(payload["id"])

    # ---- the commitment view over that pile -----------------------------
    r = client.get("/api/v1/goals/commitment", headers=auth)
    check("commitment", r.status_code < 500, f"HTTP {r.status_code} {r.text[:120]}")
    if r.status_code == 200:
        bad = all_finite(r.json())
        check("commitment finite", not bad, str(bad))

    # With income set, the shortfall must be arithmetic that holds.
    client.patch(
        "/api/v1/profile",
        json={"annual_income": 1_200_000, "monthly_expenses": 40_000},
        headers=auth,
    )
    r = client.get("/api/v1/goals/commitment", headers=auth)
    if r.status_code == 200:
        c = r.json()
        expected = max(0.0, c["total_monthly"] - (c["affordable_monthly"] or 0))
        check(
            "commitment shortfall is total minus affordable",
            abs(c["shortfall"] - expected) < 1,
            f"{c['shortfall']} vs {expected}",
        )

    # ---- editing into nonsense -----------------------------------------
    if created:
        goal_id = created[0]
        for label, body in [
            ("target of zero", {"target_amount": 0}),
            ("negative target", {"target_amount": -1}),
            ("negative savings", {"current_savings": -1}),
            ("zero years", {"years": 0}),
            ("a past date", {"target_date": str(today - timedelta(days=30))}),
            ("an unknown type", {"goal_type": "spaceship"}),
        ]:
            r = client.patch(f"/api/v1/goals/{goal_id}", json=body, headers=auth)
            check(f"edit goal / {label}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:160]}")
            if r.status_code == 200:
                bad = all_finite(r.json())
                check(f"edit goal / {label} finite", not bad, str(bad))

    # ---- portfolio with awkward transactions ----------------------------
    holding = client.post(
        "/api/v1/portfolio/holdings",
        json={"asset_type": "MF", "identifier": "122639", "name": "Edge Fund", "category": "Flexi Cap"},
        headers=auth,
    ).json()
    for label, body in [
        ("zero units", {"txn_type": "BUY", "txn_date": "2024-01-01", "units": 0, "price": 100}),
        ("zero price", {"txn_type": "BUY", "txn_date": "2024-01-01", "units": 10, "price": 0}),
        ("negative units", {"txn_type": "BUY", "txn_date": "2024-01-01", "units": -5, "price": 100}),
        ("a future date", {"txn_type": "BUY", "txn_date": "2099-01-01", "units": 10, "price": 100}),
        ("selling what was never bought", {"txn_type": "SELL", "txn_date": "2024-02-01", "units": 999, "price": 100}),
        ("a tiny fraction", {"txn_type": "BUY", "txn_date": "2024-01-02", "units": 0.0001, "price": 100}),
    ]:
        r = client.post(
            f"/api/v1/portfolio/holdings/{holding['id']}/transactions", json=body, headers=auth
        )
        check(f"transaction / {label}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:160]}")

    for path in ("", "/benchmark", "/cost-review", "/levers", "/overlap", "/history"):
        r = client.get(f"/api/v1/portfolio{path}", headers=auth)
        check(f"portfolio{path or ' summary'}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:120]}")
        if r.status_code == 200:
            bad = all_finite(r.json())
            check(f"portfolio{path or ' summary'} finite", not bad, str(bad))

    # ---- research, with filters that match nothing ----------------------
    for label, params in [
        ("an unknown index", {"index": "NIFTY NOTHING"}),
        ("an unknown industry", {"industry": "Interplanetary Mining"}),
        ("a query matching nothing", {"q": "zzzzzzzz"}),
        ("a zero limit", {"index": "NIFTY 50", "limit": 0}),
        ("a huge limit", {"index": "NIFTY 50", "limit": 100000}),
    ]:
        r = client.get("/api/v1/research/stocks/ranked", params=params, headers=auth)
        check(f"stocks ranked / {label}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:120]}")
        if r.status_code == 200:
            bad = all_finite(r.json())
            check(f"stocks ranked / {label} finite", not bad, str(bad))

    for label, ticker in [
        ("a ticker that does not exist", "NOSUCHCO.NS"),
        ("an empty-ish ticker", "%20"),
        ("a path-traversal attempt", "..%2F..%2Fetc%2Fpasswd"),
    ]:
        r = client.get(f"/api/v1/research/stocks/{ticker}/score", headers=auth)
        check(f"stock score / {label}", r.status_code < 500, f"HTTP {r.status_code} {r.text[:120]}")

    print(f"\n{CHECKS} checks run")
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILED:\n")
        for f in FAILURES:
            print(f"  {f}")
        return 1
    print("all clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
