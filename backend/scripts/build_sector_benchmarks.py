"""Per-sector median P/E, P/B, ROE and dividend yield for the stock screen.

Why the median and not an index number: NSE publishes a P/E per index, but it
is **market-cap weighted**. Nifty IT reads around 21 because TCS and Infosys
dominate the weight, so a mid-cap IT company at P/E 30 looks expensive against
it when it is sitting exactly at what its peers trade on. The question a screen
asks is "is this company cheap relative to its peers", and that needs the
median across constituents.

Computed from our own NSE universe, so the peer set is the one we actually
score against. Written to disk because sector medians move slowly and 750
yfinance calls is not something to do inside a request.

    python scripts/build_sector_benchmarks.py

Output: app/data/sector_benchmarks.json
"""

import json
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yfinance as yf

from app.services import data_built  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "data" / "sector_benchmarks.json"

_FETCH_WORKERS = 16

# Below this a "median" is one or two companies having a strange year, so the
# sector falls back to the all-market figure rather than inventing a peer group.
_MIN_PEERS = 6

# Ratios outside these bands are filing artefacts or loss-making years, not
# valuations, and one of them drags a small sector's median badly.
#
# dividend_yield is banded in PERCENT because that is what yfinance returns
# (ITC comes back as 5.64, meaning 5.64%). The band used to be (0.0, 0.12) — a
# fraction-shaped band applied to percentages — so every company that actually
# paid a dividend was discarded as an outlier and the surviving "median" was
# the median of near-zero yielders. Downstream that made not publishing a
# dividend score better than paying one. See _SCALE below.
_BOUNDS = {
    "pe": (0.5, 200.0),
    "pb": (0.05, 40.0),
    "roe": (-1.0, 2.0),
    "dividend_yield": (0.0, 15.0),
}

# Written to disk in the unit the scorer compares against. The scorer receives
# company yields as fractions, so the sector median must be a fraction too.
_SCALE = {"dividend_yield": 0.01}


def _clean(values: list[float], key: str) -> list[float]:
    low, high = _BOUNDS[key]
    return [v for v in values if v is not None and low <= v <= high]


def main() -> int:
    universe = json.loads((ROOT / "app" / "data" / "stock_universe.json").read_text())
    # Nifty 500 rather than the full Total Market: the tail of the 750 is
    # thinly covered by the data source and would only add noise to a median.
    sample = [s for s in universe if "NIFTY 500" in s.get("indices", [])]
    print(f"{len(sample)} constituents to sample")

    by_sector: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    failures = 0

    def fetch(entry: dict) -> dict | None:
        try:
            return yf.Ticker(entry["ticker"]).info
        except Exception:
            return None

    # Entirely network latency, so concurrency turns a ten-minute crawl into
    # about a minute. Results are collected in the main thread, which keeps the
    # sector buckets free of locks.
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        for i, info in enumerate(pool.map(fetch, sample), 1):
            sector = info.get("sector") if info else None
            if not sector:
                failures += 1
                continue
            bucket = by_sector[sector]
            bucket["pe"].append(info.get("trailingPE"))
            bucket["pb"].append(info.get("priceToBook"))
            bucket["roe"].append(info.get("returnOnEquity"))
            bucket["dividend_yield"].append(info.get("dividendYield"))
            if i % 50 == 0:
                print(f"  {i}/{len(sample)} sampled, {len(by_sector)} sectors", flush=True)

    out: dict[str, dict] = {}
    all_values: dict[str, list[float]] = defaultdict(list)
    for sector, metrics in by_sector.items():
        entry: dict = {"n": 0}
        for key in _BOUNDS:
            values = _clean(metrics[key], key)
            all_values[key].extend(values)
            if len(values) >= _MIN_PEERS:
                entry[key] = round(
                    statistics.median(values) * _SCALE.get(key, 1.0), 5
                )
        entry["n"] = max(len(_clean(metrics[k], k)) for k in _BOUNDS)
        if entry["n"] >= _MIN_PEERS:
            out[sector] = entry

    out["_ALL"] = {
        key: round(statistics.median(values) * _SCALE.get(key, 1.0), 5)
        for key, values in all_values.items()
        if len(values) >= _MIN_PEERS
    }
    out["_ALL"]["n"] = len(all_values["pe"])

    if len(out) < 2:
        print("Too few sectors resolved; refusing to write.", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    data_built.record("sector_benchmarks.json")

    print(f"\n{len(out) - 1} sectors -> {OUT}  ({failures} lookups failed)")
    for sector, entry in sorted(out.items()):
        if sector == "_ALL":
            continue
        print(
            f"  {sector:<24} n={entry['n']:>3}  "
            f"PE {entry.get('pe', '-')!s:>7}  PB {entry.get('pb', '-')!s:>6}  "
            f"ROE {entry.get('roe', '-')!s:>7}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
