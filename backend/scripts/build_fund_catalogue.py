"""Build the fund catalogue that the recommendation universe is derived from.

mfapi's list endpoint gives 75,000 scheme names but no SEBI category, and the
category only appears on the per-scheme detail call. So the mapping from
category to scheme codes has to be crawled once and committed, rather than
fetched at request time.

This is deliberately a build step, not runtime code. Run it when funds are
launched, merged or wound up:

    python scripts/build_fund_catalogue.py

Output: app/data/fund_catalogue.json
"""

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

BASE = "https://api.mfapi.in"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "fund_catalogue.json"

# Direct plans only: a regular plan of the same fund carries a distributor
# commission inside the NAV, so recommending one is recommending a worse
# version of the same portfolio. Growth only: dividend and IDCW variants are
# the same portfolio with a different payout, and including them would let one
# fund occupy several ranks.
_DIRECT = re.compile(r"\bdirect\b", re.I)
_GROWTH = re.compile(r"\bgrowth\b", re.I)
_PAYOUT = re.compile(r"dividend|idcw|payout|reinvest|bonus", re.I)

# Politeness: this is a free API doing us a favour, and the crawl is one-off.
_WORKERS = 8
_PAUSE_SECONDS = 0.02

# Scheme codes verified by hand against AMFI, spanning three categories and
# several fund houses. Used only as a completeness check on the crawl.
_INTEGRITY_CODES = [
    "122639",  # Parag Parikh Flexi Cap
    "118955",  # HDFC Flexi Cap
    "118814",  # Nippon India Corporate Bond
    "119788",  # SBI Gold
    "120716",  # UTI Nifty 50 Index, the benchmark
]


def candidates(client: httpx.Client) -> list[dict]:
    schemes = client.get(f"{BASE}/mf", timeout=120).json()
    return [
        s
        for s in schemes
        if _DIRECT.search(s["schemeName"])
        and _GROWTH.search(s["schemeName"])
        and not _PAYOUT.search(s["schemeName"])
    ]


def fetch_meta(client: httpx.Client, code: int) -> dict | None:
    for attempt in range(3):
        try:
            response = client.get(f"{BASE}/mf/{code}", timeout=30)
            if response.status_code != 200:
                return None
            payload = response.json()
            meta = payload.get("meta") or {}
            if not meta.get("scheme_category"):
                return None
            # A scheme with no NAV history cannot be scored, so it does not
            # belong in a catalogue whose only purpose is ranking.
            if not payload.get("data"):
                return None
            return {
                "code": str(meta["scheme_code"]),
                "name": meta["scheme_name"],
                "category": meta["scheme_category"],
                "fund_house": meta.get("fund_house"),
                "latest_nav_date": payload["data"][0]["date"],
            }
        except (httpx.HTTPError, ValueError):
            if attempt == 2:
                return None
            time.sleep(1 + attempt)
    return None


def main() -> int:
    with httpx.Client(headers={"User-Agent": "NexTrade/1.0"}) as client:
        pending = candidates(client)
        print(f"{len(pending)} direct-growth candidates", flush=True)

        found: list[dict] = []
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            for i, meta in enumerate(
                pool.map(lambda s: fetch_meta(client, s["schemeCode"]), pending), 1
            ):
                if meta:
                    found.append(meta)
                if i % 500 == 0:
                    print(f"  {i}/{len(pending)} checked, {len(found)} kept", flush=True)
                time.sleep(_PAUSE_SECONDS)

    by_category: dict[str, list[dict]] = {}
    for fund in found:
        by_category.setdefault(fund["category"], []).append(fund)
    for funds in by_category.values():
        funds.sort(key=lambda f: f["name"])

    # mfapi's list endpoint has returned materially different totals between
    # runs (75,372 schemes once, 37,689 minutes later), so a crawl that looks
    # successful can still be built on half a list. The hand-verified codes are
    # the canary: if any of them vanished, the source was incomplete and the
    # existing catalogue is better than the one we just built.
    present = {f["code"] for funds in by_category.values() for f in funds}
    missing = [code for code in _INTEGRITY_CODES if code not in present]
    if missing:
        print(
            f"\nRefusing to write: {len(missing)} known-good scheme codes are "
            f"absent, so the source list was partial. Missing: {missing}",
            file=sys.stderr,
        )
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(by_category, indent=1, sort_keys=True))

    print(f"\n{len(found)} funds across {len(by_category)} categories -> {OUT}")
    for category, funds in sorted(
        by_category.items(), key=lambda kv: -len(kv[1])
    )[:20]:
        print(f"  {len(funds):4d}  {category}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
