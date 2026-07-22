"""Build the browsable NSE stock universe from NSE's own index constituent files.

The Research page had a stocks tab that only worked if you already knew an NSE
ticker, which meant it looked empty. This gives it something to browse.

NSE's JSON API (`/api/equity-stockIndices`) is cookie-gated and returns 404 to
a plain client, but the archives host serves the same constituent lists as
plain CSV with only a browser User-Agent required. Those files are the
authoritative membership list, so they are the source here.

Membership changes roughly twice a year, so this is a build step and the
result is committed. Re-run after an index review:

    python scripts/build_stock_universe.py

Output: app/data/stock_universe.json
"""

import csv
import io
import json
import sys
from pathlib import Path

import httpx

BASE = "https://nsearchives.nseindia.com/content/indices"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "stock_universe.json"

# Ordered widest-last so a stock's narrowest index wins as its headline tag.
INDEX_FILES = [
    ("NIFTY 50", "ind_nifty50list"),
    ("NIFTY 500", "ind_nifty500list"),
    ("NIFTY TOTAL MARKET", "ind_niftytotalmarket_list"),
]

_HEADERS = {
    # The archives host rejects non-browser clients outright.
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_index(client: httpx.Client, slug: str) -> list[dict]:
    response = client.get(f"{BASE}/{slug}.csv", timeout=60)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows or "Symbol" not in rows[0]:
        raise ValueError(f"{slug}: unexpected columns {list(rows[0]) if rows else []}")
    return rows


def main() -> int:
    stocks: dict[str, dict] = {}

    with httpx.Client(headers=_HEADERS, follow_redirects=True) as client:
        for index_name, slug in INDEX_FILES:
            try:
                rows = fetch_index(client, slug)
            except (httpx.HTTPError, ValueError) as exc:
                print(f"  skipped {index_name}: {exc}", file=sys.stderr)
                continue

            for row in rows:
                symbol = (row.get("Symbol") or "").strip()
                if not symbol:
                    continue
                entry = stocks.setdefault(
                    symbol,
                    {
                        # yfinance wants the .NS suffix; storing it here keeps
                        # the suffix in one place rather than at each call site.
                        "ticker": f"{symbol}.NS",
                        "symbol": symbol,
                        "name": (row.get("Company Name") or "").strip(),
                        "industry": (row.get("Industry") or "").strip() or None,
                        "isin": (row.get("ISIN Code") or "").strip() or None,
                        "indices": [],
                    },
                )
                if index_name not in entry["indices"]:
                    entry["indices"].append(index_name)
            print(f"  {index_name}: {len(rows)} constituents")

    if not stocks:
        print("No constituents fetched, refusing to write an empty universe.", file=sys.stderr)
        return 1

    ordered = sorted(stocks.values(), key=lambda s: s["name"] or s["symbol"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ordered, indent=1))

    print(f"\n{len(ordered)} stocks -> {OUT}")
    for index_name, _ in INDEX_FILES:
        count = sum(1 for s in ordered if index_name in s["indices"])
        print(f"  {count:4d}  {index_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
