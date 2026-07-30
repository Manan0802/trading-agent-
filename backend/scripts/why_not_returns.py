"""Head-to-head: which signal available today predicts the next three years?

Manan's objection, and it is the right one: "cost ka kya hai, humein toh returns
matter karte hain." Correct. Returns are the goal. The question this script asks
is narrower and is the only one that can actually be settled with data:

    Of the things we can see on the day we choose, which one predicts the
    returns we are about to get?

Four candidates, ranked on each decision date using only what was knowable then,
then scored on the forward three years:

    past_3y     the number every investor looks at
    cost        direct-plan TER
    nav_level   NAV per unit -- the "10 rupee fund is cheaper" idea
    blend       average of the past_3y rank and the cost rank

Reported per signal: mean forward return of the top quartile vs the bottom
quartile, how often top beat bottom, and the rank IC across the whole
cross-section. The IC matters more than the quartile spread -- it uses every
fund in the window instead of collapsing them into one win-or-lose bit.

    python scripts/why_not_returns.py
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
from app.services.marketdata.mutual_fund import nav_on_or_before  # noqa: E402

HOLD = 3
LOOKBACK = 3
MIN_FUNDS = 12


def _dates(n=6):
    """Decision dates, oldest first, each with a full forward window behind it."""
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


def _rank_ic(pairs: list[tuple[float, float]]) -> float | None:
    """Spearman correlation between signal rank and forward return."""
    if len(pairs) < MIN_FUNDS:
        return None
    n = len(pairs)

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            shared = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = shared
            i = j + 1
        return out

    a = ranks([p[0] for p in pairs])
    b = ranks([p[1] for p in pairs])
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else None


def _percentile_ranks(values: dict[str, float], *, ascending: bool) -> dict[str, float]:
    """0.0 = most attractive. `ascending` means a smaller raw value is better."""
    order = sorted(values, key=lambda c: values[c], reverse=not ascending)
    last = max(1, len(order) - 1)
    return {c: i / last for i, c in enumerate(order)}


def main() -> int:
    fees = expense_ratios()
    # signal -> list of (top mean, bottom mean, top>bottom, ic)
    tally: dict[str, list[tuple[float, float, bool, float | None]]] = {
        "past_3y": [], "cost": [], "nav_level": [], "blend": [],
    }

    for cat in [c for c in BROWSABLE_CATEGORIES if c.startswith("Equity Scheme")]:
        entries = [e for e in funds_in_category(cat) if fees.get(e.code, {}).get("direct_ter")]
        if len(entries) < MIN_FUNDS:
            continue

        def fetch(e):
            try:
                return e.code, mutual_fund.get_nav_history(e.code)
            except Exception:
                return e.code, []

        with ThreadPoolExecutor(24) as pool:
            navs = {c: n for c, n in pool.map(fetch, entries) if n}

        for d in _dates():
            fwd = {}
            for code, series in navs.items():
                if series[0].date > d:
                    continue  # not born yet on the decision date
                r = forward_return(series, d, HOLD)
                if r is not None:
                    fwd[code] = r
            if len(fwd) < MIN_FUNDS:
                continue

            # --- signals, using only what was visible on `d` ---
            past = {}
            level = {}
            for code in fwd:
                p = forward_return(navs[code], d - timedelta(days=round(LOOKBACK * 365.25)), LOOKBACK)
                point = nav_on_or_before(navs[code], d)
                if p is not None and point is not None and point.nav > 0:
                    past[code] = p
                    level[code] = point.nav

            cost = {c: fees[c]["direct_ter"] for c in fwd}

            common = set(past) & set(level) & set(cost)
            if len(common) < MIN_FUNDS:
                continue

            past = {c: past[c] for c in common}
            level = {c: level[c] for c in common}
            cost = {c: cost[c] for c in common}

            past_rank = _percentile_ranks(past, ascending=False)   # higher return better
            cost_rank = _percentile_ranks(cost, ascending=True)    # lower TER better
            level_rank = _percentile_ranks(level, ascending=True)  # the myth: lower NAV better
            blend_rank = {c: (past_rank[c] + cost_rank[c]) / 2 for c in common}

            for name, rank in (
                ("past_3y", past_rank), ("cost", cost_rank),
                ("nav_level", level_rank), ("blend", blend_rank),
            ):
                order = sorted(common, key=lambda c: rank[c])
                q = max(2, len(order) // 4)
                top = statistics.fmean(fwd[c] for c in order[:q])
                bottom = statistics.fmean(fwd[c] for c in order[-q:])
                # IC is signed so that positive always means "the signal helped".
                ic = _rank_ic([(-rank[c], fwd[c]) for c in common])
                tally[name].append((top, bottom, top > bottom, ic))

    if not any(tally.values()):
        print("nothing measurable")
        return 1

    windows = len(tally["cost"])
    print(f"\n{windows} category-windows, {HOLD}y hold, decision dates {_dates()[0]}..{_dates()[-1]}\n")
    print(f"{'signal':<12} {'top q':>8} {'bottom q':>9} {'spread':>8} {'top>bot':>9} {'rank IC':>9}")
    print("-" * 60)
    for name, rows in tally.items():
        top = statistics.fmean(r[0] for r in rows)
        bottom = statistics.fmean(r[1] for r in rows)
        wins = sum(1 for r in rows if r[2])
        ics = [r[3] for r in rows if r[3] is not None]
        ic = statistics.fmean(ics) if ics else float("nan")
        print(f"{name:<12} {top:>7.1%} {bottom:>8.1%} {top - bottom:>+7.1%} "
              f"{wins:>5}/{len(rows):<3} {ic:>+9.3f}")

    print("\nrank IC is the average Spearman correlation between signal rank and")
    print("forward return. 0.00 means the signal carried no information.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
