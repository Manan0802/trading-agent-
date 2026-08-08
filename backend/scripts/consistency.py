"""Does the app tell the same story in every place it tells it?

A wrong number is a bug you can find. Two different right-looking numbers for
the same thing is worse: nothing errors, nothing logs, and the reader quietly
stops believing any of it. This checks the seams where the same fact is computed
by more than one path.

    python scripts/consistency.py [--api http://127.0.0.1:8020]
"""

import argparse
import sys
from datetime import date, timedelta

from _ratelimit import PatientClient

FAILURES: list[str] = []
CHECKS = 0


def check(what: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(f"{what}: {detail}")


def close(a: float | None, b: float | None, tol: float = 1.0) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= tol


def main() -> int:
    parser = argparse.ArgumentParser()
    # 8000 and 8010 are other projects on this machine. A wrong default does not
    # error -- it runs the whole harness against a different app and passes.
    parser.add_argument("--api", default="http://127.0.0.1:8020")
    args = parser.parse_args()
    # Patient, because this harness runs third in ./check.sh and the two before
    # it have usually spent the minute's anonymous budget. A 429 body has no
    # "regime" key, so the old client turned a rate limit into a KeyError
    # traceback halfway through the run. See scripts/_ratelimit.py.
    client = PatientClient(base_url=args.api.rstrip("/"), timeout=180)

    email = f"consistency{id(client)}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "consistency-pw", "name": "C", "phone": "+919000007777"},
    )
    token = client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "consistency-pw"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    client.patch(
        "/api/v1/profile",
        json={
            "annual_income": 2_400_000,
            "monthly_expenses": 70_000,
            "is_salaried": True,
            "current_tax_regime": "old",
            "years_to_goal": 15,
        },
        headers=auth,
    )

    # --- the tax saving, three ways --------------------------------------
    profile = client.get("/api/v1/profile", headers=auth).json()
    saving_from_profile = profile["tax"]["saving"]
    plan = client.post(
        "/api/v1/advisor/tax-saving",
        json={"annual_income": 2_400_000, "is_salaried": True},
    ).json()
    levers = client.get("/api/v1/portfolio/levers", headers=auth).json()
    tax_lever = next((l for l in levers["levers"] if l["key"] == "tax_regime"), None)

    check(
        "tax saving agrees between /profile and /advisor/tax-saving",
        close(saving_from_profile, plan["regime"]["saving"]),
        f"{saving_from_profile} vs {plan['regime']['saving']}",
    )
    check(
        "the tax lever's annual value is that same saving",
        tax_lever is not None and close(tax_lever["annual_value"], saving_from_profile),
        f"{tax_lever and tax_lever['annual_value']} vs {saving_from_profile}",
    )

    # --- a goal, priced by the goal and by the calculator -----------------
    today = date.today()
    goal = client.post(
        "/api/v1/goals",
        json={
            "goal_type": "education",
            "goal_name": "Consistency",
            "target_amount": 5_000_000,
            "current_savings": 300_000,
            "target_date": str(today + timedelta(days=365 * 15)),
            "years": 15,
            "risk_profile": "moderate",
        },
        headers=auth,
    ).json()
    direct = client.post(
        "/api/v1/advisor/calculate-sip",
        json={
            "target_amount": goal["target_amount"],
            "years": goal["years"],
            "current_savings": goal["current_savings"],
            "inflation_rate": goal["inflation_rate"],
        },
    ).json()
    check(
        "a goal's stored SIP matches the calculator on the same inputs",
        close(goal["required_monthly_sip"], direct["required_monthly_sip"]),
        f"{goal['required_monthly_sip']} vs {direct['required_monthly_sip']}",
    )

    check(
        "a goal's allocation sums to 100",
        (goal["equity_allocation"] or 0)
        + (goal["debt_allocation"] or 0)
        + (goal["gold_allocation"] or 0)
        == 100,
        str(goal),
    )

    # --- the fund plan against the goal it implements ---------------------
    rec = client.get(f"/api/v1/goals/{goal['id']}/recommendations", headers=auth).json()
    placed = sum(r["monthly_amount"] for r in rec["recommendations"])
    check(
        "the fund plan spends the whole SIP",
        close(placed, goal["required_monthly_sip"], tol=2),
        f"placed {placed} of {goal['required_monthly_sip']}",
    )
    check(
        "the plan's reported mix matches the amounts it actually places",
        all(
            close(
                pct,
                sum(
                    r["monthly_amount"]
                    for r in rec["recommendations"]
                    if r["asset_class"] == cls
                )
                / placed
                * 100,
                tol=0.2,
            )
            for cls, pct in rec["actual_mix"].items()
        )
        if placed
        else True,
        str(rec["actual_mix"]),
    )

    # --- the goal, and that goal inside the commitment total --------------
    commitment = client.get("/api/v1/goals/commitment", headers=auth).json()
    check(
        "the commitment total is the sum of the goals it lists",
        close(commitment["total_monthly"], sum(g["monthly_sip"] for g in commitment["goals"])),
        f"{commitment['total_monthly']} vs its own list",
    )
    check(
        "the commitment total includes this goal",
        close(commitment["total_monthly"], goal["required_monthly_sip"]),
        f"{commitment['total_monthly']} vs {goal['required_monthly_sip']}",
    )

    # --- a fund's score, on the Research page and inside a goal plan ------
    if rec["recommendations"]:
        pick = rec["recommendations"][0]
        ranking = client.get(
            f"/api/v1/research/fund-rankings/{pick['category']}",
            params={"monthly_sip": goal["required_monthly_sip"], "years": 15},
            headers=auth,
        )
        if ranking.status_code == 200:
            listed = next(
                (
                    f
                    for f in ranking.json()["ranked"]
                    if f["scheme_code"] == pick["scheme_code"]
                ),
                None,
            )
            check(
                "a fund scores the same in a goal plan and on the research page",
                listed is not None and close(listed["score"], pick["score"], tol=0.01),
                f"plan {pick['score']} vs research {listed and listed['score']}",
            )
            check(
                "and holds the same rank in both",
                listed is not None and listed["rank"] == pick["rank"],
                f"plan {pick['rank']} vs research {listed and listed['rank']}",
            )

    # --- the portfolio total against its own rows ------------------------
    holding = client.post(
        "/api/v1/portfolio/holdings",
        json={"asset_type": "MF", "identifier": "122639", "name": "PPFAS", "category": "Flexi Cap"},
        headers=auth,
    ).json()
    for i in range(6):
        client.post(
            f"/api/v1/portfolio/holdings/{holding['id']}/transactions",
            json={
                "txn_type": "BUY",
                "txn_date": str(date(2024, 1 + i, 5)),
                "units": 100,
                "price": 60 + i,
            },
            headers=auth,
        )
    portfolio = client.get("/api/v1/portfolio", headers=auth).json()
    check(
        "the portfolio's invested total is the sum of its rows",
        close(portfolio["total_invested"], sum(h["invested"] for h in portfolio["holdings"])),
        f"{portfolio['total_invested']} vs rows",
    )
    check(
        "the portfolio's current value is the sum of its rows",
        close(
            portfolio["total_current_value"],
            sum(h["current_value"] or 0 for h in portfolio["holdings"]),
        ),
        f"{portfolio['total_current_value']} vs rows",
    )
    check(
        "unrealised gain is value minus invested, on the priced rows only",
        close(
            portfolio["total_unrealised_gain"],
            sum(h["unrealised_gain"] or 0 for h in portfolio["holdings"]),
        ),
        f"{portfolio['total_unrealised_gain']} vs rows",
    )

    # --- the cost review and the lever built from it ----------------------
    review = client.get("/api/v1/portfolio/cost-review", headers=auth).json()
    levers = client.get("/api/v1/portfolio/levers", headers=auth).json()
    switch = next((l for l in levers["levers"] if l["key"] == "plan_switch"), None)
    if review["flagged"]:
        check(
            "the plan-switch lever's annual value matches the cost review",
            switch is not None and close(switch["annual_value"], review["annual_cost"], tol=2),
            f"{switch and switch['annual_value']} vs {review['annual_cost']}",
        )
    else:
        check(
            "no regular holdings means no plan-switch lever",
            switch is None,
            "lever present with nothing flagged",
        )

    # --- the name on a holding against the fund it actually is -------------
    # The gap that let scheme code 119533 sit in the demo data labelled "ICICI
    # Prudential Corporate Bond Fund" while AMFI publishes it as Aditya Birla.
    # Nothing errored; every figure was right, about the wrong fund. Two
    # separate things are checked, because both were broken.
    rows = client.get("/api/v1/portfolio", headers=auth).json()["holdings"]
    funds = [r for r in rows if r["asset_type"] == "MF"]
    check(
        "no holding is labelled as a fund it is not",
        all(r.get("misnamed_as") is None for r in funds),
        "; ".join(
            f"{r['name']} ({r['identifier']}) is really {r['misnamed_as']}"
            for r in funds
            if r.get("misnamed_as")
        ),
    )

    # The portfolio table renders the typed name and the cost review renders
    # AMFI's, so a mismatch showed two names for one holding on adjacent
    # screens. Comparing them here is what makes that impossible to reintroduce.
    reviewed = {f["name"] for f in review.get("flagged", [])} | set(
        review.get("unpriced", [])
    )
    listed = {r["name"] for r in funds}
    stray = reviewed - listed
    check(
        "the cost review names the same holdings the portfolio does",
        not stray,
        f"cost review mentions {sorted(stray)}, which the portfolio does not list",
    )

    # --- the chart against the headline it sits under ----------------------
    # A portfolio holding one stock drew a chart 29% below the total printed
    # directly above it, because the line covers funds only and said so
    # nowhere. Two plausible numbers disagreeing is worse than one visible
    # error: neither looks wrong.
    history = client.get("/api/v1/portfolio/history", headers=auth).json()
    portfolio = client.get("/api/v1/portfolio", headers=auth).json()
    if history["points"]:
        drawn = history["points"][-1]["portfolio_value"]
        check(
            "the chart plus what it excludes equals the headline total",
            close(drawn + history["excluded_value"], portfolio["total_current_value"], tol=2),
            f"chart {drawn} + excluded {history['excluded_value']} "
            f"vs headline {portfolio['total_current_value']}",
        )
        # Same word, two meanings, one above the other: the headline is the
        # FIFO cost of units still held, the chart used to be net cash in.
        check(
            "'Invested' means the same thing in the chart as in the header",
            close(history["points"][-1]["invested"], portfolio["total_invested"], tol=2),
            f"chart {history['points'][-1]['invested']} "
            f"vs header {portfolio['total_invested']}",
        )

    print(f"\n{CHECKS} consistency checks run")
    if FAILURES:
        print(f"\n{len(FAILURES)} DISAGREE:\n")
        for f in FAILURES:
            print(f"  {f}")
        return 1
    print("everything agrees with itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
