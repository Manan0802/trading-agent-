"""Does ranking by expense ratio predict better than ranking by past record?

The composite score does not predict (see docs/does-the-score-work.md). Cost is
the one input with replicated predictive power in the literature, so before
rebuilding the product around it, it gets the same test the score just failed.

    python scripts/validate_cost_ranking.py
"""
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.advisor.backtest import forward_return  # noqa: E402
from app.services.advisor.fund_catalogue import (  # noqa: E402
    BROWSABLE_CATEGORIES,
    funds_in_category,
)
from app.services.advisor.fund_evidence import expense_ratios  # noqa: E402
from app.services.marketdata import mutual_fund  # noqa: E402

HOLD = 3


def _dates(n=6):
    latest = date.today() - timedelta(days=round(HOLD * 365.25) + 30)
    out = []
    for i in range(n):
        m = latest.month - (i * 12) % 12
        y = latest.year - (i * 12) // 12
        if m <= 0:
            m += 12
            y -= 1
        out.append(date(y, m, 1))
    return sorted(out)


def main() -> int:
    fees = expense_ratios()
    rows = []
    for cat in [c for c in BROWSABLE_CATEGORIES if c.startswith("Equity Scheme")]:
        entries = [e for e in funds_in_category(cat) if fees.get(e.code, {}).get("direct_ter")]
        if len(entries) < 12:
            continue

        def fetch(e):
            try:
                return e.code, mutual_fund.get_nav_history(e.code)
            except Exception:
                return e.code, []

        with ThreadPoolExecutor(24) as pool:
            navs = {c: n for c, n in pool.map(fetch, entries) if n}

        # Cheapest first. Cost is known on the decision date and does not move
        # much, so there is no lookahead in using today's filing.
        ranked = sorted(navs, key=lambda c: fees[c]["direct_ter"])

        for d in _dates():
            alive = [c for c in ranked if navs[c][0].date <= d]
            fwd = {c: forward_return(navs[c], d, HOLD) for c in alive}
            fwd = {k: v for k, v in fwd.items() if v is not None}
            if len(fwd) < 12:
                continue
            order = [c for c in ranked if c in fwd]
            q = max(2, len(order) // 4)
            cheap = [fwd[c] for c in order[:q]]
            dear = [fwd[c] for c in order[-q:]]
            rows.append((statistics.mean(cheap), statistics.mean(dear),
                         statistics.median(fwd.values())))

    if not rows:
        print("nothing measurable")
        return 1

    cheap = [r[0] for r in rows]
    dear = [r[1] for r in rows]
    med = [r[2] for r in rows]
    wins = sum(1 for r in rows if r[0] > r[1])
    print(f"{len(rows)} category-windows measured\n")
    print(f"cheapest quartile  : median forward return {statistics.median(cheap):+.1%}")
    print(f"category median    : {statistics.median(med):+.1%}")
    print(f"dearest quartile   : {statistics.median(dear):+.1%}")
    print(f"\ncheap minus dear   : {statistics.median(cheap) - statistics.median(dear):+.1%} a year")
    print(f"cheap beat dear in {wins}/{len(rows)} windows = {wins / len(rows):.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
