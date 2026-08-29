"""Build the expense-ratio table from AMFI's public TER disclosure.

Expense ratio is the most replicated predictor of future fund returns there is,
and AMFI publishes it for every scheme. It is not in mfapi's feed, so it has to
come from here.

The catch is the join. AMFI's TER rows are keyed on `NSDLSchemeCode`, which
appears nowhere in the NAV feed our catalogue is built from, so scheme names are
the only bridge. Names are matched on a normalised form (plan and option
suffixes stripped, punctuation collapsed) within the same fund house, which
resolves the great majority.

This used to say the unresolved were "mostly ETFs and closed-ended schemes that
are not in our universe anyway". That was false, and it is what made the hole
invisible: on 2026-08-28, **297 live open-ended funds across 23 whole fund
houses** had no row here -- Groww's own AMC among them -- because the AMC walk
stopped at a hardcoded id. The run now prints its own coverage, so the next
version of that sentence has to survive a number.

Both plans are kept. `regular_ter - direct_ter` is the annual cost of buying the
same portfolio through a distributor, which is a number worth showing a user.

Run when TER filings update (AMFI publishes monthly):

    python scripts/build_expense_ratios.py

Output: app/data/expense_ratios.json
"""

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx

from app.services import data_built  # noqa: E402

BASE = "https://www.amfiindia.com/api/populate-te-rdata-revised"
ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "app" / "data" / "fund_catalogue.json"
OUT = ROOT / "app" / "data" / "expense_ratios.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.amfiindia.com/",
}

# AMFI numbers its AMCs as they register, so any fixed ceiling goes stale the
# day a new house arrives above it. `_MAX_MF_ID = 55` did exactly that: probed
# on 2026-08-28, ids 56-86 held at least 24 live houses -- 63 Groww, 64 Parag
# Parikh, 77 Zerodha, 82 JioBlackRock -- and every one of them was invisible to
# this table, leaving 297 live funds with no expense ratio at all. The scorer
# does not drop those funds; it gives them a NEUTRAL cost, which reads exactly
# like a measured one.
#
# So the walk stops on evidence rather than on a number. Eight consecutive empty
# ids is four times the largest gap ever observed inside the live range (56-57,
# 59-60 and 65-66 are empty while 86 still answers), and costs nine wasted
# requests a month against a run that already makes hundreds.
_STOP_AFTER_EMPTY = 8
_ID_HARD_CEILING = 400  # a runaway guard, not the expected end
_PAGE_SIZE = 500
_PAGE_SIZE = 500
_MAX_PAGES = 12
_PAUSE = 0.15

_PLAN_SUFFIX = re.compile(r"\b(direct|regular)\b.*$", re.I)
# Words that appear in one feed's name and not the other's. "Fund" itself is
# dropped because AMFI writes "Parag Parikh Flexi Cap Fund" where the NAV feed
# writes "Parag Parikh Flexi Cap Fund - Direct Plan - Growth", and a handful of
# schemes differ only by its presence.
_NOISE = re.compile(
    r"\b(plan|growth|option|scheme|fund|funds|of|the"
    r"|idcw|dividend|payout|reinvestment|cum|capital|withdrawal|distribution)\b",
    re.I,
)


def normalise(name: str) -> str:
    """A scheme name reduced to the part both feeds agree on."""
    s = _PLAN_SUFFIX.sub("", name or "")
    s = _NOISE.sub(" ", s)
    s = re.sub(r"[^a-zA-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _months_to_try() -> list[str]:
    """Current month first, then back a few — AMFI publishes with a lag."""
    today = date.today()
    out = []
    year, month = today.year, today.month
    for _ in range(4):
        out.append(f"{month:02d}-{year}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return out


def fetch_amc(client: httpx.Client, mf_id: int, month: str) -> list[dict]:
    rows: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        try:
            response = client.get(
                BASE,
                params={
                    "MF_ID": str(mf_id),
                    "Month": month,
                    "strCat": "-1",
                    "strType": "-1",
                    "page": str(page),
                    "pageSize": str(_PAGE_SIZE),
                },
                timeout=45,
            )
            if response.status_code != 200:
                break
            batch = (response.json() or {}).get("data") or []
        except (httpx.HTTPError, ValueError):
            break
        if not batch:
            break
        rows.extend(batch)
        time.sleep(_PAUSE)
    return rows


def _as_float(raw) -> float | None:
    try:
        value = float(str(raw).replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    # A TER above 3% for a direct plan is a filing artefact, not a fee: SEBI
    # caps total expenses well below that.
    return value if 0 < value < 3.5 else None


def main() -> int:
    catalogue = json.loads(CATALOGUE.read_text())
    by_name: dict[str, list[dict]] = {}
    for funds in catalogue.values():
        for fund in funds:
            by_name.setdefault(normalise(fund["name"]), []).append(fund)
    print(f"catalogue: {sum(len(v) for v in catalogue.values())} funds, "
          f"{len(by_name)} normalised names")

    latest: dict[str, dict] = {}
    with httpx.Client(headers=_HEADERS) as client:
        for month in _months_to_try():
            found_this_month = 0
            empty_run = 0
            highest_live = 0
            for mf_id in range(1, _ID_HARD_CEILING + 1):
                rows = fetch_amc(client, mf_id, month)
                if not rows:
                    empty_run += 1
                    if empty_run >= _STOP_AFTER_EMPTY:
                        break
                    continue
                empty_run = 0
                highest_live = mf_id
                for row in rows:
                    key = normalise(row.get("Scheme_Name", ""))
                    if not key:
                        continue
                    seen = latest.get(key)
                    if seen is None or row.get("TER_Date", "") > seen.get("TER_Date", ""):
                        latest[key] = row
                        found_this_month += 1
            print(f"  {month}: {found_this_month} scheme rows, {len(latest)} unique so far "
                  f"(highest live AMC id {highest_live})")
            # Every month is merged, keeping the newest TER_Date per scheme. A
            # scheme absent from the latest filing is still worth its last
            # published figure, and stopping at the first productive month left
            # whole fund houses uncovered.

    if not latest:
        print("No TER rows fetched; refusing to write an empty table.", file=sys.stderr)
        return 1

    out: dict[str, dict] = {}
    for key, row in latest.items():
        for fund in by_name.get(key, []):
            direct = _as_float(row.get("D_TER"))
            regular = _as_float(row.get("R_TER"))
            if direct is None and regular is None:
                continue
            out[fund["code"]] = {
                "direct_ter": direct,
                "regular_ter": regular,
                "as_of": (row.get("TER_Date") or "")[:10],
                "amfi_name": row.get("Scheme_Name"),
            }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    data_built.record("expense_ratios.json")

    # What this run did NOT cover, per fund house. The hole that `_MAX_MF_ID`
    # left was 23 houses at zero for eleven review passes, and nothing here
    # said so -- the run reported how many schemes it wrote and never how many
    # it missed. A gap that announces itself does not need to be found.
    by_house: dict[str, list[int]] = {}
    for funds in catalogue.values():
        for fund in funds:
            house = fund.get("fund_house") or "?"
            counts = by_house.setdefault(house, [0, 0])
            counts[0] += 1
            if fund["code"] in out:
                counts[1] += 1
    uncovered = {h: n for h, (n, got) in by_house.items() if got == 0 and n > 0}
    print(
        f"\ncoverage: {len(out)} schemes across "
        f"{sum(1 for _, (n, got) in by_house.items() if got)} fund houses"
    )
    if uncovered:
        print(
            f"  {len(uncovered)} houses with NO expense ratio at all, "
            f"covering {sum(uncovered.values())} catalogue funds:"
        )
        for house, n in sorted(uncovered.items(), key=lambda kv: -kv[1])[:12]:
            print(f"    {n:4d}  {house}")
        print(
            "  A house at zero is almost always the walk stopping short, not "
            "AMFI withholding: check the highest live AMC id printed above."
        )
    else:
        print("  every fund house in the catalogue has at least one TER")

    with_direct = [v["direct_ter"] for v in out.values() if v["direct_ter"]]
    gaps = [
        v["regular_ter"] - v["direct_ter"]
        for v in out.values()
        if v["direct_ter"] and v["regular_ter"]
    ]
    print(f"\n{len(out)} of our funds matched a TER -> {OUT}")
    if with_direct:
        with_direct.sort()
        print(f"  direct TER median {with_direct[len(with_direct) // 2]:.2f}%")
    if gaps:
        gaps.sort()
        print(f"  regular minus direct, median {gaps[len(gaps) // 2]:.2f}pp "
              f"over {len(gaps)} funds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
