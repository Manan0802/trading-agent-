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


def _merge_with_committed(out: dict[str, dict]) -> tuple[int, int]:
    """Keep a fund's last published TER when this run did not find it.

    The builder used to REPLACE the file, and a single crawl that missed a fund
    therefore deleted its cost. Measured on 2026-08-29: rebuilding dropped 469
    buyable funds and added 357, a net loss of 112 -- on the one axis §1.1 says
    this app has a real signal. Several of the dropped funds normalise to
    exactly the string AMFI had used for them, so the join was not the problem;
    AMFI simply did not serve them that day.

    A TER filed in July is still the TER filed in July. `as_of` already travels
    with every row, so the honest thing is to keep the older figure and say how
    old it is -- not to pretend the fund has no cost.

    Newer always wins: an entry from this run replaces a stored one, and a
    stored one survives only where this run found nothing at all.
    """
    try:
        previous = json.loads(OUT.read_text())
    except (OSError, ValueError):
        return len(out), 0
    fresh = len(out)
    kept = 0
    for code, row in previous.items():
        if code not in out:
            out[code] = row
            kept += 1
    return fresh, kept


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

    fresh, kept = _merge_with_committed(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    data_built.record("expense_ratios.json")
    print(f"\n{fresh} funds priced by this run; {kept} kept from the previous "
          "file because this crawl did not reach them")

    # What is NOT covered, measured against the funds a person can actually buy.
    #
    # Counting against the whole catalogue is technically true and thoroughly
    # misleading: ICICI shows 456 funds with no TER and exactly FOUR of them are
    # buyable, the rest being closed-ended series and wound-up schemes nobody can
    # purchase. Reported that way, a 97% buyable coverage reads like a disaster.
    #
    # The houses at zero tell the same story from the other side. `Reliance
    # Mutual Fund` has 236 funds and no TER because Reliance MF became Nippon
    # India in 2019 -- along with Deutsche, DHFL Pramerica, L&T, IDFC, IDBI,
    # JPMorgan, BNP Paribas, ING, Principal, Sahara and Baroda Pioneer, every one
    # of them renamed or wound up. An earlier version of this report told the
    # reader that a house at zero "is almost always the walk stopping short",
    # which sent the last investigation looking for a bug in the crawl.
    from app.services.advisor import buyable as _buyable

    buyable_codes = _buyable.buyable_codes()
    by_house: dict[str, list[int]] = {}
    for funds in catalogue.values():
        for fund in funds:
            if buyable_codes and fund["code"] not in buyable_codes:
                continue
            house = fund.get("fund_house") or "?"
            counts = by_house.setdefault(house, [0, 0])
            counts[0] += 1
            if fund["code"] in out:
                counts[1] += 1

    priced = sum(got for _n, got in by_house.values())
    total = sum(n for n, _got in by_house.values())
    print(
        f"\nbuyable coverage: {priced} of {total} funds "
        f"({priced / total * 100:.0f}%)" if total else "\nno buyable universe on disk"
    )
    short = {h: (n, got) for h, (n, got) in by_house.items() if got < n}
    if short:
        print(f"  {len(short)} houses are missing at least one buyable fund's TER:")
        for house, (n, got) in sorted(short.items(), key=lambda kv: kv[1][0] - kv[1][1])[::-1][:10]:
            print(f"    {n - got:4d} of {n:4d} missing   {house}")
        print(
            "  A house missing ALL of its buyable funds is worth investigating; "
            "a house missing a few is usually a scheme AMFI did not file that "
            "month, and the merge above keeps its last published figure."
        )
    else:
        print("  every buyable fund has an expense ratio")

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
