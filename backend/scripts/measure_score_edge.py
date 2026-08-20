"""Does the ported fund score rank funds better than a coin?

The reference implementation never asks this. Its backtests -- basket_backtest,
export_bachatt_backtest, run_weekly_lumpsum_sim, sip_simulation_v2 -- all
measure portfolio value over time. Not one of them checks whether the score
that chooses the funds has any forward information at all. That is the single
largest gap in the method we ported, so this is the test that fills it.

Method. Pick a formation date. Build every eligible fund's inputs from the
four-year window ending that day, run the real `universe.run()`, then measure
what each fund actually returned over the following year. Compare **within
(category, sub_category)**, so this measures fund selection rather than which
asset class happened to run.

Two controls, in the spirit of the factor harness: a random score and the
reversed score, both through the identical pipeline. Random must land at
chance and reversed must mirror the real column. If they do not, the harness
is broken and its verdict means nothing -- which is the failure this codebase
has hit twice before.

    venv/bin/python scripts/measure_score_edge.py
    venv/bin/python scripts/measure_score_edge.py --from-year 2015 --horizon-days 730

Not wired into check.sh: it needs a fully backfilled store and takes minutes.
It is evidence, not a gate.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.advisor import fund_catalogue  # noqa: E402
from app.services.screener import inputs as inputs_mod  # noqa: E402
from app.services.screener import metrics as metrics_mod  # noqa: E402
from app.services.screener import navstore, universe  # noqa: E402

# A peer group smaller than this cannot support a quartile comparison.
MIN_PEERS = 8
# Enough NAVs on the formation side to compute a four-year window's metrics,
# and enough on the forward side that the return is a year and not a fortnight.
MIN_FORMATION_ROWS = 200
MIN_FORWARD_ROWS = 180

SEED = 20260820


def gather(session, form: date, end: date):
    """Every fund scoreable at `form`, with what it actually returned by `end`."""
    catalogue = fund_catalogue.all_funds()
    cutoff = metrics_mod.window_start(form)
    built, forward = [], {}

    for fund in catalogue:
        category, sub_category = inputs_mod.split_category(fund.category)
        if not inputs_mod.is_eligible(category)[0] or not sub_category:
            continue
        window = navstore.nav_window(session, fund.code, start=cutoff, end=form)
        if len(window) < MIN_FORMATION_ROWS:
            continue
        after = navstore.nav_window(session, fund.code, start=form, end=end)
        if len(after) < MIN_FORWARD_ROWS:
            continue

        # The momentum tail is taken as of the formation date, not today --
        # otherwise the score would be built partly from the future it is being
        # asked to predict.
        m = metrics_mod.compute(
            window, form, momentum_navs=window[-metrics_mod.MOMENTUM_NAV_ROWS:]
        )
        built.append(
            universe.FundInputs(
                code=fund.code, category=category, sub_category=sub_category,
                roll1y=m.rolling_1y, roll6m=m.rolling_6m,
                roll3m=m.rolling_3m, roll1m=m.rolling_1m,
                ret3y=m.returns_3y, ret1y=m.returns_1y, ret3m=m.returns_3m,
                vol=m.volatility, sortino=m.sortino,
                momentum=m.momentum, drawdown=m.drawdown,
                # Freshness is asserted rather than measured: the fund published
                # on both sides of the window, so it was alive throughout.
                nav_fresh=True,
            )
        )
        forward[fund.code] = (after[-1][1] / after[0][1] - 1) * 100

    scored, _ = universe.run(built)
    return scored, forward


def measure(groups) -> tuple[int, int, list[float]]:
    """Quartile hit rate and rank IC, per peer group."""
    hits = total = 0
    ics: list[float] = []
    for rows in groups.values():
        if len(rows) < MIN_PEERS:
            continue
        rows.sort(key=lambda r: -r[0])
        k = max(1, len(rows) // 4)
        top = float(np.mean([r[1] for r in rows[:k]]))
        bottom = float(np.mean([r[1] for r in rows[-k:]]))
        hits += top > bottom
        total += 1
        s = np.array([r[0] for r in rows])
        f = np.array([r[1] for r in rows])
        ics.append(float(np.corrcoef(s.argsort().argsort(), f.argsort().argsort())[0, 1]))
    return hits, total, ics


def z_score(hits: int, total: int) -> float:
    if total == 0:
        return float("nan")
    return (hits - total * 0.5) / float(np.sqrt(total * 0.25))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=2019)
    ap.add_argument("--to-year", type=int, default=2025)
    ap.add_argument("--horizon-days", type=int, default=364)
    args = ap.parse_args()

    navstore.ensure_schema()
    windows = [
        (date(y, 8, 20), date(y, 8, 20) + timedelta(days=args.horizon_days))
        for y in range(args.from_year, args.to_year + 1)
    ]

    rng = random.Random(SEED)
    totals = {k: [0, 0, []] for k in ("score", "random", "reversed")}

    print(f"{'formation':<12}{'funds':>8}{'groups':>8}{'top>bottom':>14}{'rank IC':>10}")
    print("-" * 52)
    with navstore.session() as session:
        for form, end in windows:
            scored, forward = gather(session, form, end)
            if not scored:
                print(f"{str(form):<12}{'no data':>8}")
                continue

            columns = {k: defaultdict(list) for k in totals}
            for f in scored:
                if f.code not in forward:
                    continue
                key = (f.category, f.sub_category)
                actual = forward[f.code]
                columns["score"][key].append((f.score, actual))
                columns["random"][key].append((rng.random(), actual))
                columns["reversed"][key].append((-f.score, actual))

            for name, groups in columns.items():
                hits, total, ics = measure(groups)
                totals[name][0] += hits
                totals[name][1] += total
                totals[name][2] += ics

            hits, total, ics = measure(columns["score"])
            if total:
                print(
                    f"{str(form):<12}{len(scored):>8,}{total:>8}"
                    f"{f'{hits}/{total} = {hits / total:.0%}':>14}{np.mean(ics):>+10.3f}"
                )

    print()
    print(f"{'column':<26}{'top>bottom':>16}{'rank IC':>11}{'z':>8}")
    print("-" * 61)
    for name in ("score", "random", "reversed"):
        hits, total, ics = totals[name]
        if not total:
            continue
        label = {"score": "the ported score", "random": "random  (control)",
                 "reversed": "reversed (control)"}[name]
        print(
            f"{label:<26}{f'{hits}/{total} = {hits / total:.0%}':>16}"
            f"{np.mean(ics):>+11.3f}{z_score(hits, total):>8.1f}"
        )
    print("-" * 61)

    r_hits, r_total, _ = totals["random"]
    control_ok = r_total and abs(z_score(r_hits, r_total)) < 2.0
    print(
        "control: random lands at chance"
        if control_ok
        else "BROKEN: the random control did NOT land at chance, so nothing above means anything"
    )
    print()
    print("Survivorship: only funds with NAVs on BOTH sides of a window are")
    print("included, so a fund wound up during the year is absent. That inflates")
    print("every column, controls included.")
    return 0 if control_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
