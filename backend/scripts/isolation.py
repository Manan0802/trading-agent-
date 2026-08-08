"""Can one account reach another account's data, or reach anything unauthenticated?

Everything else in this app is about being honest with one person's numbers.
Showing them somebody else's would be a different and much worse kind of
dishonesty, so this walks every route that takes an id or reads a session and
tries it as a stranger and as nobody.

    python scripts/isolation.py [--api http://127.0.0.1:8020]
"""

import argparse
import sys
from datetime import date, timedelta

import httpx

from _ratelimit import PatientClient

FAILURES: list[str] = []
# A check the rate limiter would not let us run. Kept apart from FAILURES on
# purpose: "we could not test this" and "this leaked" are different sentences,
# and printing the second one for the first would send someone hunting a breach
# that never happened.
INCONCLUSIVE: list[str] = []
CHECKS = 0


def check(what: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(f"{what}: {detail}")


def untestable(what: str, detail: str) -> None:
    """Counted as attempted, reported apart from a leak."""
    global CHECKS
    CHECKS += 1
    INCONCLUSIVE.append(f"{what}: {detail}")


def account(client: httpx.Client, tag: str) -> dict:
    email = f"iso-{tag}-{id(client)}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "isolation-pw", "name": tag, "phone": "+919000008888"},
    )
    token = client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "isolation-pw"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    # 8000 and 8010 are other projects on this machine. A wrong default does not
    # error -- it runs the whole harness against a different app and passes.
    parser.add_argument("--api", default="http://127.0.0.1:8020")
    args = parser.parse_args()
    # Patient: these routes are meant to answer 401, and a 429 from our own
    # earlier harnesses would be recorded as a leak. See scripts/_ratelimit.py.
    client = PatientClient(base_url=args.api.rstrip("/"), timeout=90)

    owner = account(client, "owner")
    stranger = account(client, "stranger")
    today = date.today()

    goal = client.post(
        "/api/v1/goals",
        json={
            "goal_type": "education",
            "goal_name": "Private",
            "target_amount": 3_000_000,
            "current_savings": 100_000,
            "target_date": str(today + timedelta(days=365 * 10)),
            "years": 10,
            "risk_profile": "moderate",
        },
        headers=owner,
    ).json()
    holding = client.post(
        "/api/v1/portfolio/holdings",
        json={"asset_type": "MF", "identifier": "122639", "name": "Private Fund", "category": "Flexi Cap"},
        headers=owner,
    ).json()
    client.post(
        f"/api/v1/portfolio/holdings/{holding['id']}/transactions",
        json={"txn_type": "BUY", "txn_date": "2024-01-05", "units": 100, "price": 60},
        headers=owner,
    )
    client.patch(
        "/api/v1/profile",
        json={"annual_income": 5_000_000, "monthly_expenses": 100_000},
        headers=owner,
    )

    # --- a stranger, holding a valid session of their own -----------------
    forbidden = [
        ("GET", f"/api/v1/goals/{goal['id']}"),
        ("GET", f"/api/v1/goals/{goal['id']}/recommendations"),
        ("PATCH", f"/api/v1/goals/{goal['id']}"),
        ("DELETE", f"/api/v1/goals/{goal['id']}"),
        ("GET", f"/api/v1/portfolio/holdings/{holding['id']}"),
        ("DELETE", f"/api/v1/portfolio/holdings/{holding['id']}"),
        ("POST", f"/api/v1/portfolio/holdings/{holding['id']}/transactions"),
    ]
    for method, path in forbidden:
        body = {"txn_type": "BUY", "txn_date": "2024-02-01", "units": 1, "price": 1} if "transactions" in path else {"goal_name": "hijacked"}
        r = client.request(method, path, json=body, headers=stranger)
        check(
            f"a stranger {method} {path.split('/api/v1')[-1][:44]}",
            r.status_code == 404,
            f"HTTP {r.status_code}",
        )

    # --- and their own views must not contain the owner's things ---------
    for path, key in [
        ("/api/v1/goals", None),
        ("/api/v1/portfolio/holdings", None),
    ]:
        rows = client.get(path, headers=stranger).json()
        check(f"a stranger's {path} is empty", rows == [], f"{len(rows)} rows")

    summary = client.get("/api/v1/portfolio", headers=stranger).json()
    check(
        "a stranger's portfolio totals are zero",
        summary["total_invested"] == 0 and summary["total_current_value"] == 0,
        str(summary["total_invested"]),
    )
    commitment = client.get("/api/v1/goals/commitment", headers=stranger).json()
    check(
        "a stranger's commitment is zero",
        commitment["total_monthly"] == 0,
        str(commitment["total_monthly"]),
    )
    profile = client.get("/api/v1/profile", headers=stranger).json()
    check(
        "a stranger's profile carries none of the owner's income",
        profile["annual_income"] in (None, 0),
        str(profile["annual_income"]),
    )

    # --- and nobody at all ------------------------------------------------
    anonymous = [
        ("GET", "/api/v1/goals"),
        ("GET", f"/api/v1/goals/{goal['id']}"),
        ("GET", "/api/v1/goals/commitment"),
        ("GET", "/api/v1/profile"),
        ("PATCH", "/api/v1/profile"),
        ("GET", "/api/v1/portfolio"),
        ("GET", "/api/v1/portfolio/holdings"),
        ("GET", "/api/v1/portfolio/levers"),
        ("GET", "/api/v1/portfolio/overlap"),
        ("GET", "/api/v1/portfolio/announcements"),
        ("GET", "/api/v1/portfolio/cost-review"),
        ("GET", "/api/v1/research/stocks/ranked"),
        ("GET", "/api/v1/research/fund-categories"),
        ("DELETE", f"/api/v1/goals/{goal['id']}"),
    ]
    for method, path in anonymous:
        label = f"unauthenticated {method} {path.split('/api/v1')[-1][:44]}"
        r = client.request(method, path, json={})
        if r.status_code == 429:
            untestable(label, "still rate limited after waiting")
            continue
        check(label, r.status_code in (401, 403), f"HTTP {r.status_code}")

    # --- a forged token must not open anything ---------------------------
    for label, header in [
        ("a garbage token", {"Authorization": "Bearer not-a-token"}),
        # "Bearer " with a trailing space is not sendable — httpx refuses it as
        # an illegal header value — so the empty case is the bare scheme.
        ("a bare scheme with no token", {"Authorization": "Bearer"}),
        ("a token with the algorithm stripped", {"Authorization": "Bearer eyJhbGciOiJub25lIn0.e30."}),
    ]:
        r = client.get("/api/v1/profile", headers=header)
        if r.status_code == 429:
            untestable(f"{label} is rejected", "still rate limited after waiting")
            continue
        check(f"{label} is rejected", r.status_code in (401, 403), f"HTTP {r.status_code}")

    # --- the owner still has everything ----------------------------------
    check(
        "the owner's goal survived every attempt on it",
        client.get(f"/api/v1/goals/{goal['id']}", headers=owner).status_code == 200,
        "owner lost their own goal",
    )
    check(
        "the owner's holding survived too",
        client.get(f"/api/v1/portfolio/holdings/{holding['id']}", headers=owner).status_code == 200,
        "owner lost their own holding",
    )

    print(f"\n{CHECKS} isolation checks run")
    if FAILURES:
        print(f"\n{len(FAILURES)} LEAKED:\n")
        for f in FAILURES:
            print(f"  {f}")
        return 1
    if INCONCLUSIVE:
        # Still a non-zero exit. An isolation check that did not run is not an
        # isolation check that passed, and this is the one harness where
        # assuming the best is unacceptable.
        print(f"\n{len(INCONCLUSIVE)} COULD NOT BE TESTED (rate limited, not leaked):\n")
        for f in INCONCLUSIVE:
            print(f"  {f}")
        print("\nRe-run in a minute, or restart the API to clear its buckets.")
        return 1
    print("nothing crosses between accounts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
