"""Give an account a portfolio to look at.

A signed-in account with nothing in it renders `StartHere` and nothing else,
which is correct and is not the page you want when you are judging a design.
This fills one account with a year of monthly buys so every panel on
`/portfolio` has something real to say.

    python scripts/seed_demo_portfolio.py you@example.com
    python scripts/seed_demo_portfolio.py you@example.com --clear

The four holdings are chosen so that no panel renders its empty state:

  SBI Small Cap        REGULAR plan -- the only reason `CostReview` has a
                       number instead of "nothing to fix"
  Parag Parikh Flexi   direct equity, the overlap counterparty
  ABSL Corporate Bond  debt, so the mix is not all equity
  Tata Steel           a stock, which is what `Announcements` reads filings
                       for and what the chart excludes from its fund line

An earlier demo account was built by hand and nothing in the repo could
rebuild it: the rows existed, the recipe did not. This is that recipe.
"""

import argparse
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine  # noqa: E402

# name, asset_type, identifier, category, units per month, opening price,
# monthly price step.
FUNDS = [
    ("SBI Small Cap Fund - Regular Plan - Growth", "MF", "125494", "Small Cap", 7.5, 130.0, 2.6),
    ("Parag Parikh Flexi Cap Fund - Direct Plan - Growth", "MF", "122639", "Flexi Cap", 25.0, 60.0, 1.2),
    (
        "Aditya Birla Sun Life Corporate Bond Fund - Growth - Direct Plan",
        "MF",
        "119533",
        "Corporate Bond",
        33.3333333333333,
        24.0,
        0.48,
    ),
    ("Tata Steel Ltd.", "STOCK", "TATASTEEL.NS", None, 16.6666666666667, 130.0, 2.6),
]

MONTHS = 12
YEAR = 2023


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("email", help="the account to fill")
    ap.add_argument(
        "--clear",
        action="store_true",
        help="remove this account's holdings instead of adding to them",
    )
    args = ap.parse_args()

    with engine.begin() as db:
        row = db.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": args.email}
        ).first()
        if row is None:
            print(f"no account {args.email!r}. Sign up in the app first.")
            return 1
        user_id = row[0]

        # Always clear first. Run twice without this and the page shows eight
        # holdings, half of them duplicates, and every total is doubled.
        ids = [r[0] for r in db.execute(
            text("SELECT id FROM holdings WHERE user_id = :u"), {"u": user_id}
        )]
        for hid in ids:
            db.execute(text("DELETE FROM transactions WHERE holding_id = :h"), {"h": hid})
        db.execute(text("DELETE FROM holdings WHERE user_id = :u"), {"u": user_id})
        if args.clear:
            print(f"cleared {len(ids)} holdings from {args.email}")
            return 0

        for name, asset_type, identifier, category, units, price0, step in FUNDS:
            hid = str(uuid.uuid4())
            db.execute(
                text(
                    "INSERT INTO holdings (id, user_id, name, asset_type, identifier, category)"
                    " VALUES (:i, :u, :n, :a, :d, :c)"
                ),
                {"i": hid, "u": user_id, "n": name, "a": asset_type, "d": identifier, "c": category},
            )
            for m in range(MONTHS):
                price = round(price0 + step * m, 2)
                db.execute(
                    text(
                        "INSERT INTO transactions"
                        " (id, holding_id, txn_date, txn_type, units, price, amount)"
                        " VALUES (:i, :h, :d, 'BUY', :u, :p, :a)"
                    ),
                    {
                        "i": str(uuid.uuid4()),
                        "h": hid,
                        "d": date(YEAR, m + 1, 5).isoformat(),
                        "u": units,
                        "p": price,
                        "a": round(units * price, 2),
                    },
                )

    print(f"{args.email}: {len(FUNDS)} holdings, {MONTHS} monthly buys each")
    print("reload /portfolio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
