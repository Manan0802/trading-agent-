"""Sector medians for the stock scorer: PE, P/B, ROE and dividend yield.

Four of the ten stock factors ask "is this cheap against its peers", and the
answer needs a peer median. This builds them.

Two source decisions inherited from the reference, both of which are correct
and neither of which is obvious:

**The medians come from yfinance, not from NSE's index PE.** NSE's `allIndices`
returns a market-cap *weighted* PE -- NIFTY IT sits near 21 because TCS and
Infosys dominate the weighting. For a scorer asking whether a stock is cheap
against its peers, a weighted average is the wrong statistic: it makes a mid-cap
IT company at PE 30 look expensive when 30 is the sector's median. So each
sector's PE, P/B and ROE is the true median across a basket of individual
constituents.

**Dividend yield is the exception and comes from NSE.** yfinance's dividend
yield for Indian names is unreliable -- it returns figures like 13% for banks.
The index-level yield is the more trustworthy of two imperfect numbers.

The basket is deliberately large-and-mid cap rather than every listed name: a
median over the whole exchange is dragged around by illiquid microcaps whose
reported PE is noise.

    venv/bin/python scripts/build_sector_benchmarks.py
    venv/bin/python scripts/build_sector_benchmarks.py --dry-run

Writes app/data/sector_benchmarks.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import httpx

warnings.filterwarnings("ignore")

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "sector_benchmarks.json"

# Matches build_fund_catalogue.py, which crawls a much larger universe at the
# same settings without trouble.
_WORKERS = 8
_PAUSE_SECONDS = 0.02
_TIMEOUT_SECONDS = 20

_ALL_INDICES = "https://www.nseindia.com/api/allIndices"
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/",
}

# A median over fewer than this many usable constituents is not a median, it is
# a small sample wearing one. Those sectors fall back rather than publishing a
# number the basket cannot support -- and the report says which did.
_MIN_CONSTITUENTS = 3

BASKET = {
    'Financial Services': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN', 'BAJFINANCE', 'BAJAJFINSV', 'INDUSINDBK', 'FEDERALBNK'],
    # LTIM dropped: LTIMindtree 404s on yfinance under every symbol it has
    # traded as. OFSS keeps the basket at nine.
    'Technology': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM', 'OFSS', 'PERSISTENT', 'COFORGE', 'MPHASIS'],
    'Consumer Defensive': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'DABUR', 'MARICO', 'COLPAL', 'BRITANNIA', 'GODREJCP'],
    # TATAMOTORS dropped: it demerged in 2025 and both TATAMOTORS.NS and
    # TMPV.NS now 404 on yfinance. TVSMOTOR keeps the basket at eight.
    'Consumer Cyclical': ['MARUTI', 'M&M', 'TVSMOTOR', 'BAJAJ-AUTO', 'HEROMOTOCO', 'TITAN', 'EICHERMOT', 'TRENT'],
    'Healthcare': ['SUNPHARMA', 'CIPLA', 'DRREDDY', 'DIVISLAB', 'APOLLOHOSP', 'TORNTPHARM', 'LUPIN', 'MANKIND'],
    'Basic Materials': ['TATASTEEL', 'HINDALCO', 'JSWSTEEL', 'COALINDIA', 'PIDILITIND', 'GRASIM', 'AMBUJACEM', 'SHREECEM'],
    'Energy': ['RELIANCE', 'ONGC', 'BPCL', 'IOC', 'GAIL'],
    'Industrials': ['LT', 'SIEMENS', 'ABB', 'ADANIPORTS', 'HAVELLS', 'CUMMINSIND', 'BHEL'],
    # Widened from the two the reference carries. Two constituents is not a
    # median, and it fell below this script's own _MIN_CONSTITUENTS floor, so
    # the whole sector was publishing hardcoded numbers. VI is deliberately
    # left out -- a distressed telco at PE 4 is not a peer, it is an outlier.
    'Communication Services': ['BHARTIARTL', 'INDUSTOWER', 'TATACOMM', 'SUNTV', 'ZEEL'],
    'Utilities': ['NTPC', 'POWERGRID', 'TATAPOWER', 'ADANIPOWER', 'NHPC', 'TORNTPOWER'],
    'Real Estate': ['DLF', 'LODHA', 'GODREJPROP', 'OBEROIRLTY', 'PRESTIGE', 'PHOENIXLTD', 'BRIGADE'],
}

SECTOR_INDEX = {
    'Financial Services': 'NIFTY FINANCIAL SERVICES',
    'Technology': 'NIFTY IT',
    'Consumer Defensive': 'NIFTY FMCG',
    'Consumer Cyclical': 'NIFTY AUTO',
    'Healthcare': 'NIFTY PHARMA',
    'Basic Materials': 'NIFTY METAL',
    'Energy': 'NIFTY ENERGY',
    'Industrials': 'NIFTY INFRASTRUCTURE',
    'Communication Services': 'NIFTY MEDIA',
    'Utilities': 'NIFTY PSE',
    'Real Estate': 'NIFTY REALTY',
}

ROE_FALLBACK = {
    'Financial Services': 14.0,
    'Technology': 23.0,
    'Consumer Defensive': 35.0,
    'Consumer Cyclical': 20.0,
    'Healthcare': 16.0,
    'Basic Materials': 13.0,
    'Energy': 11.0,
    'Industrials': 19.0,
    'Communication Services': 21.0,
    'Utilities': 14.0,
    'Real Estate': 9.0,
}

# Used when a sector's basket comes back too thin to trust. Inherited values;
# they are round numbers because they are judgement, not measurement, and the
# report names every sector that had to use one.
PE_FALLBACK = 22.0
PB_FALLBACK = 3.0
DIV_YIELD_FALLBACK = 1.2

# The scorer treats an unknown sector as neutral rather than guessing, so this
# is the record every unmapped stock gets.
DEFAULT_SECTOR = "Unknown"


def _median_of(values: list[float]) -> float | None:
    usable = [v for v in values if v is not None and v == v and v > 0]
    if len(usable) < _MIN_CONSTITUENTS:
        return None
    return round(float(statistics.median(usable)), 4)


def _fetch_one(symbol: str) -> dict:
    """One stock's fundamentals. Never raises -- a bad ticker must not fail a sector.

    ROE has two sources and the second one matters. Measured on 2026-08-21,
    yfinance returns `returnOnEquity` as None for 8 of 12 major Indian names --
    HINDUNILVR, ITC, SUNPHARMA, RELIANCE, LT, NTPC, TATASTEEL and MARUTI all
    come back empty, while P/E and P/B come through for every one of them. With
    only the reported field, nine of eleven sectors fell through to a hardcoded
    judgement number, and ROE is 10% of the stock score.

    But ROE is P/B divided by P/E. Both are price over something, the price
    cancels, and what is left is earnings over book -- the definition. Checked
    against every basket stock that does report ROE, the identity lands within
    2.3 percentage points: TCS 47.7 vs 45.4, INFY 32.0 vs 34.2, HDFCBANK 13.8
    vs 11.6, WIPRO 16.1 vs 16.1. The gap is trailing earnings against a
    current book value, and it is far smaller than the error in assigning one
    hardcoded number to a whole sector.

    So: reported if present, derived if not, hardcoded only if neither. Which
    one was used is recorded per sector, because a median built from derived
    values is a weaker number than one built from reported values and the
    report should not hide that.
    """
    import yfinance as yf

    try:
        info = yf.Ticker(f"{symbol}.NS").info
        pe, pb = info.get("trailingPE"), info.get("priceToBook")
        reported = info.get("returnOnEquity")

        roe, roe_source = None, None
        if reported is not None:
            # yfinance reports it as a decimal; the scorer compares percentages.
            roe, roe_source = float(reported) * 100, "reported"
        elif pe and pb and float(pe) > 0:
            roe, roe_source = (float(pb) / float(pe)) * 100, "derived"

        return {
            "symbol": symbol, "pe": pe, "pb": pb,
            "roe": roe, "roe_source": roe_source, "error": None,
        }
    except Exception as exc:  # noqa: BLE001 -- one bad ticker is not a failed run
        return {
            "symbol": symbol, "pe": None, "pb": None,
            "roe": None, "roe_source": None, "error": str(exc),
        }


def _index_yields() -> dict[str, float]:
    """Dividend yield per NSE index, or an empty map if NSE is unreachable."""
    try:
        response = httpx.get(_ALL_INDICES, headers=_NSE_HEADERS, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        rows = response.json().get("data", [])
    except Exception as exc:  # noqa: BLE001
        print(f"  NSE allIndices unreachable ({exc}); dividend yields will fall back")
        return {}
    out = {}
    for row in rows:
        name, dy = row.get("index"), row.get("dy")
        try:
            value = float(dy)
        except (TypeError, ValueError):
            continue
        if value > 0:
            out[str(name).strip().upper()] = value
    return out


def build() -> tuple[dict, list[str]]:
    yields = _index_yields()
    print(f"  {len(yields)} index yields from NSE")

    sectors: dict[str, dict] = {}
    notes: list[str] = []

    for sector, symbols in BASKET.items():
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            rows = list(pool.map(_fetch_one, symbols))
        time.sleep(_PAUSE_SECONDS)

        pe = _median_of([r["pe"] for r in rows])
        pb = _median_of([r["pb"] for r in rows])
        roe = _median_of([r["roe"] for r in rows])
        index_name = SECTOR_INDEX.get(sector, "").upper()
        div_yield = yields.get(index_name)

        for label, value, fallback in (
            ("median_pe", pe, PE_FALLBACK),
            ("median_pb", pb, PB_FALLBACK),
            ("median_roe", roe, ROE_FALLBACK.get(sector)),
            ("median_div_yield", div_yield, DIV_YIELD_FALLBACK),
        ):
            if value is None:
                notes.append(f"{sector}: {label} fell back to {fallback}")

        usable = sum(1 for r in rows if r["pe"])
        derived = sum(1 for r in rows if r.get("roe_source") == "derived")
        reported = sum(1 for r in rows if r.get("roe_source") == "reported")
        sectors[sector] = {
            "median_pe": pe if pe is not None else PE_FALLBACK,
            "median_pb": pb if pb is not None else PB_FALLBACK,
            "median_roe": roe if roe is not None else ROE_FALLBACK.get(sector, 15.0),
            "median_div_yield": div_yield if div_yield is not None else DIV_YIELD_FALLBACK,
            "constituents": len(symbols),
            "constituents_usable": usable,
            # A median built mostly from the P/B-over-P/E identity is a weaker
            # number than one built from reported figures. Recorded rather than
            # hidden.
            "roe_reported": reported,
            "roe_derived": derived,
            "index_for_yield": SECTOR_INDEX.get(sector),
        }
        print(
            f"  {sector:<24} pe {sectors[sector]['median_pe']:>7.2f}  "
            f"pb {sectors[sector]['median_pb']:>6.2f}  "
            f"roe {sectors[sector]['median_roe']:>6.2f}%  "
            f"dy {sectors[sector]['median_div_yield']:>5.2f}%  "
            f"({usable}/{len(symbols)} usable, roe {reported} reported + {derived} derived)",
            flush=True,
        )

    sectors[DEFAULT_SECTOR] = {
        "median_pe": PE_FALLBACK,
        "median_pb": PB_FALLBACK,
        "median_roe": 15.0,
        "median_div_yield": DIV_YIELD_FALLBACK,
        "constituents": 0,
        "constituents_usable": 0,
        "roe_reported": 0,
        "roe_derived": 0,
        "index_for_yield": None,
        "note": "no sector mapping; the scorer compares such a stock against neutral values",
    }
    return {"built_on": date.today().isoformat(), "sectors": sectors}, notes


def canary(payload: dict) -> list[str]:
    """Refuse to write numbers that cannot be right.

    Same idea as build_fund_catalogue.py: a crawl that half-fails must not
    quietly replace good data with bad. Ranges are wide on purpose -- this is
    catching a broken fetch, not expressing a view on valuations.
    """
    problems = []
    sectors = payload["sectors"]
    for name, row in sectors.items():
        if name == DEFAULT_SECTOR:
            continue
        if not (3.0 <= row["median_pe"] <= 120.0):
            problems.append(f"{name}: median_pe {row['median_pe']} is outside 3-120")
        if not (0.2 <= row["median_pb"] <= 40.0):
            problems.append(f"{name}: median_pb {row['median_pb']} is outside 0.2-40")
        if not (0.5 <= row["median_roe"] <= 90.0):
            problems.append(f"{name}: median_roe {row['median_roe']} is outside 0.5-90")
        if not (0.0 < row["median_div_yield"] <= 12.0):
            problems.append(f"{name}: median_div_yield {row['median_div_yield']} is outside 0-12")

    real = [n for n in sectors if n != DEFAULT_SECTOR]
    if len(real) != len(BASKET):
        problems.append(f"{len(real)} sectors built, expected {len(BASKET)}")
    thin = [n for n in real if sectors[n]["constituents_usable"] < _MIN_CONSTITUENTS]
    if len(thin) > 3:
        problems.append(f"{len(thin)} sectors had too few usable constituents: {thin}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="build and check, write nothing")
    args = ap.parse_args()

    print(f"building sector benchmarks from {sum(len(v) for v in BASKET.values())} tickers "
          f"across {len(BASKET)} sectors")
    payload, notes = build()

    if notes:
        print("\nfell back rather than publishing a number the basket could not support:")
        for note in notes:
            print(f"  {note}")

    problems = canary(payload)
    if problems:
        print("\nREFUSING TO WRITE:")
        for p in problems:
            print(f"  {p}")
        return 1

    thin = [
        n for n, r in payload["sectors"].items()
        if n != DEFAULT_SECTOR and r["constituents"] < 5
    ]
    if thin:
        print(f"\nthin baskets, medians are weak here: {', '.join(thin)}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1))
    tmp.replace(OUT)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
