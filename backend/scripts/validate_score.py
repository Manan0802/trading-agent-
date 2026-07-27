"""Does the fund score actually pick funds that go on to do better?

Runs the real scorer over real NAV history at a series of past decision dates,
using only what was knowable on each, and measures what the picks returned
afterwards against the median fund in the same category.

    python scripts/validate_score.py "Equity Scheme - Flexi Cap Fund"
    python scripts/validate_score.py --all

The honest reading of whatever comes out is in the survivorship note the result
carries: our catalogue holds funds that are alive today, so funds wound up
since a decision date are missing, and those are disproportionately the ones
that did badly. Every number here is therefore an upper bound.
"""

import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.advisor.backtest import run_backtest  # noqa: E402
from app.services.advisor.fund_catalogue import (  # noqa: E402
    BROWSABLE_CATEGORIES,
    funds_in_category,
)
from app.services.advisor.fund_evidence import build_evidence  # noqa: E402
from app.services.advisor.fund_score import score_peer_group_v2  # noqa: E402
from app.services.marketdata import mutual_fund  # noqa: E402

HOLDING_YEARS = 3
TOP_N = 2
_WORKERS = 24


def _decision_dates(count: int = 6, gap_months: int = 12) -> list[date]:
    """One decision a year, far enough back that the holding period has closed."""
    latest = date.today() - timedelta(days=round(HOLDING_YEARS * 365.25) + 30)
    out = []
    for i in range(count):
        months = i * gap_months
        year = latest.year - months // 12
        month = latest.month - months % 12
        if month <= 0:
            month += 12
            year -= 1
        out.append(date(year, month, 1))
    return sorted(out)


def _load(category: str) -> dict[str, list]:
    entries = funds_in_category(category)

    def fetch(entry):
        try:
            return entry.code, mutual_fund.get_nav_history(entry.code)
        except mutual_fund.MutualFundDataError:
            return entry.code, []

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        return {code: navs for code, navs in pool.map(fetch, entries) if navs}


def _make_picker(category: str):
    """The real scorer, handed only truncated history."""

    def pick(navs_by_code: dict[str, list]) -> list[str]:
        evidence = []
        for code, navs in navs_by_code.items():
            built = build_evidence(code, code, category, navs)
            if built is not None:
                evidence.append(built)
        result = score_peer_group_v2(evidence)
        return [f.scheme_code for f in result.ranked]

    return pick


def validate(category: str) -> dict | None:
    universe = _load(category)
    if len(universe) < 5:
        print(f"  {category}: only {len(universe)} funds with NAV, skipping")
        return None

    result = run_backtest(
        universe,
        decision_dates=_decision_dates(),
        holding_years=HOLDING_YEARS,
        picker=_make_picker(category),
        top_n=TOP_N,
    )

    if result.windows_measured == 0:
        print(f"  {category}: no window closed, skipping")
        return None

    print(f"\n{category}  ({len(universe)} funds)")
    for w in result.windows:
        if w.spread is None:
            print(f"  {w.decision_date}  not measurable ({w.candidates} candidates)")
            continue
        print(
            f"  {w.decision_date}  picks {w.picked_return:+7.1%}  "
            f"category median {w.category_median_return:+7.1%}  "
            f"spread {w.spread:+6.1%}  ({w.candidates} candidates)"
        )
    print(
        f"  => beat the median in {result.hit_rate:.0%} of "
        f"{result.windows_measured} windows, median spread "
        f"{result.median_spread:+.1%}"
    )
    return {
        "category": category,
        "hit_rate": result.hit_rate,
        "median_spread": result.median_spread,
        "windows": result.windows_measured,
        "note": result.survivorship_note,
    }


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    categories = (
        [c for c in BROWSABLE_CATEGORIES if c.startswith("Equity Scheme")]
        if args[0] == "--all"
        else [args[0]]
    )

    summaries = [s for s in (validate(c) for c in categories) if s]
    if not summaries:
        print("\nNothing measurable.")
        return 1

    print("\n" + "=" * 72)
    hit_rates = [s["hit_rate"] for s in summaries]
    spreads = [s["median_spread"] for s in summaries]
    total_windows = sum(s["windows"] for s in summaries)
    print(
        f"Across {len(summaries)} categories and {total_windows} windows: "
        f"median hit rate {statistics.median(hit_rates):.0%}, "
        f"median spread {statistics.median(spreads):+.1%} a year"
    )
    print("\n" + summaries[0]["note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
