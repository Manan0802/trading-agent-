"""Which funds are actually buyable, and which of them merely track an index.

The product's first constraint is that it only ever recommends funds Manan can
buy on Groww. Without this file the screener ranks 4,957 catalogue funds, most
of which he cannot purchase, which makes a correct ranking useless advice.

**Two files come out of this, and the split is deliberate.**

Groww's `/v1/api/*` is `Disallow:` in their robots.txt. No auth is required;
that is not permission. So the full pull -- returns, ratings, AUM, manager
names, verdict scores, TER -- stays in `.growwcache/`, which is gitignored, and
is retained locally so every figure below can be re-checked.

What gets COMMITTED is the minimum the product cannot work without:

    scheme_code    an AMFI code. A fact about the market, not Groww's content
    buyable        whether it can be purchased
    is_passive     whether it tracks an index
    sub_category   which funds are its peers

That is the smallest thing that satisfies the product constraint, and it leaves
Groww's own measurements where they were pulled. Everything else the app reads
from Groww degrades the way §2.1 already specifies: with the cache cold, cost
falls back to AMFI alone and is labelled `cost from one source` rather than
silently ranked as if verified.

**`index` comes from the `st_filter` listing, and only from there.** The
per-scheme detail endpoint does not carry it -- 0 of 39 cached payloads have the
field -- so a build that pulled only scheme detail left `is_passive` as a name
test wearing two signals' worth of confidence. Measured on this pull: 3,412 of
3,417 listing rows carry it.

    python scripts/build_groww_universe.py
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from app.services import data_built
from app.services.advisor.fund_evidence import expense_ratios
from app.services.marketdata.groww import (
    UNIVERSE_URL,
    GrowwUnavailable,
    _get_json,
    _write_disk,
    parse_universe,
)

_ROOT = Path(__file__).resolve().parent.parent
OUT = _ROOT / "app" / "data" / "groww_buyable.json"
RAW = _ROOT / ".growwcache"

# The two-source TER gate's tolerance, restated here because this script is
# what measures agreement across the whole universe.
_TOLERANCE_PP = 0.10

# A pull that collapses is indistinguishable from a market where most funds
# were delisted overnight, unless something says so. Measured live at 1,659.
_MIN_EXPECTED = 1_200


def _joinable(scheme_code: str) -> bool:
    """Whether this row carries an AMFI code, which is the only key we have.

    Groww's listing now includes **Specialised Investment Funds**, keyed
    `SIF-14` rather than by an AMFI scheme code. 38 rows in the pull that built
    this, 30 of them passing every other buyability filter. They cannot join to
    the NAV store, the catalogue or the TER table -- zero of the 30 appear in
    AMFI's expense file -- so the app can compute nothing about them: no NAV, no
    cost, no category rank, no score.

    They also are not the same product. Every one carries a **₹10,00,000**
    minimum against a ₹1,000 median for ordinary funds, so surfacing them in a
    ranking of mutual funds offers something a thousand times out of reach and
    says nothing true about it.

    Excluded, and counted rather than dropped quietly.
    """
    return str(scheme_code).isdigit()


def main() -> int:
    try:
        payload = _get_json(UNIVERSE_URL, {"page": 0, "size": 6000})
    except GrowwUnavailable as exc:
        print(f"Refusing to write: {exc}", file=sys.stderr)
        return 1

    rows = payload.get("content") or []
    parsed = parse_universe(payload)  # parse before anything else: never keep garbage
    funds = [f for f in parsed if _joinable(f.scheme_code)]
    excluded = len(parsed) - len(funds)

    if len(funds) < _MIN_EXPECTED:
        print(
            f"Refusing to write: {len(funds)} buyable funds, expected at least "
            f"{_MIN_EXPECTED}. A short pull reads as a shrinking market.",
            file=sys.stderr,
        )
        return 1

    # The raw pull, retained. Gitignored, and the reason the figures below can
    # be re-checked rather than merely believed.
    _write_disk(f"universe-{date.today().isoformat()}", payload)

    index_flag = {str(r.get("scheme_code")): r.get("index") for r in rows}
    missing_flag = sum(1 for f in funds if index_flag.get(f.scheme_code) is None)

    out = {
        f.scheme_code: {
            "buyable": True,
            "is_passive": bool(index_flag.get(f.scheme_code)),
            # None, not False, when Groww did not say. A fund we cannot classify
            # must not be silently filed as active.
            "passive_known": index_flag.get(f.scheme_code) is not None,
            "sub_category": f.sub_category,
        }
        for f in funds
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    data_built.record("groww_buyable.json")

    _report(funds, index_flag, missing_flag)
    print(
        f"excluded, no AMFI code       {excluded}   "
        "(Specialised Investment Funds — ₹10,00,000 minimum, and nothing in "
        "this app can join to them)"
    )
    print(f"\n-> {OUT}   ({len(out)} funds)")
    print(f"   raw pull retained in {RAW}/ (gitignored)")
    return 0


def _report(funds, index_flag, missing_flag) -> None:
    """Re-print §2's four headline figures, which is this step's acceptance.

    None of the four was reproducible from this repo: the inputs were measured
    live and thrown away, which §11.4 calls worse than no record.
    """
    amfi = expense_ratios()
    both = agree = 0
    for fund in funds:
        filed = (amfi.get(fund.scheme_code) or {}).get("direct_ter")
        if filed in (None, "") or fund.expense_ratio is None:
            continue
        both += 1
        if abs(float(filed) - fund.expense_ratio) <= _TOLERANCE_PP + 1e-9:
            agree += 1

    large_cap = [f for f in funds if f.sub_category == "Large Cap"]
    passive_lc = sum(1 for f in large_cap if index_flag.get(f.scheme_code))

    print(f"buyable direct-growth funds     {len(funds)}")
    if both:
        print(
            f"carry both TER sources          {both}"
            f"   agree within {_TOLERANCE_PP}pp: {agree} "
            f"({agree / both * 100:.1f}%)   disagree: {both - agree}"
        )
    print(f"Large Cap                       {len(large_cap)}   of which index: {passive_lc}")
    print(f"no `index` field from Groww     {missing_flag}")

    by_category = Counter(f.category or "(blank)" for f in funds)
    print("\nby category:")
    for name, count in by_category.most_common():
        print(f"  {count:5d}  {name}")


if __name__ == "__main__":
    sys.exit(main())
