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

from app.services import data_built  # noqa: E402
from scripts.build_expense_ratios import normalise  # noqa: E402

BASE = "https://api.mfapi.in"
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "fund_catalogue.json"

# Direct plans only: a regular plan of the same fund carries a distributor
# commission inside the NAV, so recommending one is recommending a worse
# version of the same portfolio. Growth only: dividend and IDCW variants are
# the same portfolio with a different payout, and including them would let one
# fund occupy several ranks.
_DIRECT = re.compile(r"\bdirect\b", re.I)

# "Cumulative" is what several houses call the growth option -- ICICI and Tata
# both use it. Excluding it dropped `ICICI Prudential Nifty 50 Index Fund -
# Direct Plan - Cumulative`, which is a growth plan by any other name.
_GROWTH = re.compile(r"\b(growth|cumulative)\b", re.I)

# `dividend` must NOT match "Dividend Yield". That is an equity sub-category --
# funds that buy high-dividend-yield stocks -- not a payout option, and the
# plain word killed the WHOLE category: Franklin, Aditya Birla, UTI, ICICI,
# Tata and HDFC Dividend Yield funds, 11 in all, every one of them a growth
# plan Groww sells. The lookahead is the entire fix.
_PAYOUT = re.compile(r"dividend(?!\s+yield)|idcw|payout|reinvest|bonus", re.I)

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


_REGULAR = re.compile(r"\bregular\b", re.I)
PAIRS_OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "plan_pairs.json"


def candidates(client: httpx.Client) -> list[dict]:
    """Every direct-growth scheme worth a detail call.

    Two ways in, and the second exists because the first is a name parser.

    **By name**, which works for the vast majority. **Or by being on Groww's
    buyable list**, which is the answer rather than a guess about it: that feed
    is already filtered to direct plans, growth option, available for
    investment, so a code on it IS a direct growth plan whatever mfapi called
    it. Measured: 16 buyable funds fail the name test and are real -- five
    Motilal Oswal index funds whose mfapi name omits the plan word entirely
    (`Motilal Oswal BSE Low Volatility Index Fund`), and eleven whose option is
    spelled `Cumulative`, `Defined Maturity Date Option`, or nothing at all
    (`Tata Nifty 50 Index Fund - Direct Plan`).

    Payout variants are still excluded on both paths: a dividend or IDCW row is
    the same portfolio with a different payout and would let one fund occupy
    several ranks.
    """
    schemes = client.get(f"{BASE}/mf", timeout=120).json()
    _write_plan_pairs(schemes)

    buyable_codes = _buyable_codes()
    picked, by_name, by_universe = [], 0, 0
    for scheme in schemes:
        name = scheme["schemeName"]
        if _PAYOUT.search(name):
            continue
        named = bool(_DIRECT.search(name) and _GROWTH.search(name))
        listed = str(scheme["schemeCode"]) in buyable_codes
        if not (named or listed):
            continue
        picked.append(scheme)
        by_name += named
        by_universe += listed and not named

    print(
        f"{len(picked)} candidates: {by_name} matched by name, "
        f"{by_universe} by being on Groww's buyable list and not by name"
    )
    return picked


def _buyable_codes() -> frozenset[str]:
    """Groww's buyable universe, if it has been built. Empty is not an error."""
    from app.services.advisor import buyable

    return buyable.buyable_codes()


def _write_plan_pairs(schemes: list[dict]) -> None:
    """regular scheme code -> the direct plan of the same fund.

    Built from rows this crawl already fetched and was about to throw away. The
    catalogue keeps direct plans only, which is right -- it is the
    recommendation universe. But a person holding a REGULAR plan types its code,
    and without this edge the app has never heard of it, so the badge §11.7
    calls the largest number it will ever show cannot fire for the one person it
    exists for.

    Joined on the same normalised name `build_expense_ratios.py` uses for its
    own join, so both sides strip plan and option suffixes identically. Measured
    at 3,762 of 4,136 regular growth plans, 91%.
    """
    direct: dict[str, str] = {}
    regular: dict[str, str] = {}
    for scheme in schemes:
        name = scheme["schemeName"]
        if not _GROWTH.search(name) or _PAYOUT.search(name):
            continue
        key = normalise(name)
        if not key:
            continue
        if _DIRECT.search(name):
            direct.setdefault(key, str(scheme["schemeCode"]))
        elif _REGULAR.search(name):
            regular.setdefault(key, str(scheme["schemeCode"]))

    pairs = {code: direct[key] for key, code in regular.items() if key in direct}
    PAIRS_OUT.parent.mkdir(parents=True, exist_ok=True)
    PAIRS_OUT.write_text(json.dumps(pairs, indent=1, sort_keys=True))
    data_built.record("plan_pairs.json")
    matched = len(pairs) / len(regular) * 100 if regular else 0.0
    print(
        f"plan pairs: {len(pairs)} of {len(regular)} regular growth plans "
        f"matched to a direct twin ({matched:.0f}%) -> {PAIRS_OUT}"
    )


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
        dropped: list[str] = []
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            for i, (scheme, meta) in enumerate(
                zip(
                    pending,
                    pool.map(lambda s: fetch_meta(client, s["schemeCode"]), pending),
                ),
                1,
            ):
                if meta:
                    found.append(meta)
                else:
                    dropped.append(str(scheme["schemeCode"]))
                if i % 500 == 0:
                    print(f"  {i}/{len(pending)} checked, {len(found)} kept", flush=True)
                time.sleep(_PAUSE_SECONDS)

    # A candidate that passed every name filter and then vanished is either a
    # scheme with no category or no NAV -- fine -- or a request that failed
    # three times. Those are indistinguishable here and were previously
    # indistinguishable from "not a fund", which is how 47 funds including
    # `HDFC Nifty 50 Index Fund` and `SBI Arbitrage Fund` left the catalogue
    # with nothing recorded. Counting them is the difference between a gap and
    # a silence.
    if dropped:
        buyable_dropped = sorted(_buyable_codes() & set(dropped))
        print(
            f"\n{len(dropped)} candidates returned no usable detail; "
            f"{len(buyable_dropped)} of them are funds Groww sells"
        )
        if buyable_dropped:
            print(f"  buyable and dropped: {' '.join(buyable_dropped[:25])}")

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
    data_built.record("fund_catalogue.json")

    print(f"\n{len(found)} funds across {len(by_category)} categories -> {OUT}")
    for category, funds in sorted(
        by_category.items(), key=lambda kv: -len(kv[1])
    )[:20]:
        print(f"  {len(funds):4d}  {category}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
