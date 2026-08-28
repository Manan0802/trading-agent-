"""Does a fund's past return say anything about its next stretch?

WHY THIS SCRIPT EXISTS
----------------------
The product wants to tell its owner when to stop putting money into something.
The obvious rule -- "it has been behind, get out" -- is the one every app
implements and the one this repo has now failed to find support for four times.
This is the fourth measurement, and unlike the earlier three it was written up
in a plan before it existed as code. An adversarial review made the point that
the single most load-bearing number in the plan was the only one a reviewer
could not rerun. So here it is.

WHAT THE FIRST VERSION GOT WRONG, AND HOW IT WAS CAUGHT
--------------------------------------------------------
Version one compared each group's MEDIAN forward return to the cohort median.
The random control came back at 59%, which is impossible -- a random pick cannot
beat the median 59% of the time. Cause: `q = n // 5`, so on small cohorts the
"median of the group" was the median of two or three values, and on a
right-skewed return distribution that sits above the cohort median by
construction.

The fix is the percentile-rank form used below: a fund's forward return is
converted to its rank within its own cohort, and a group's score is the mean of
those ranks. A random group then scores 0.500 by construction, which is what
makes the control meaningful.

WHAT THE SECOND VERSION GOT WRONG
----------------------------------
Reading every row against 0.500 while its own controls landed between 0.477 and
0.539. Every row is now reported as **group minus its own control**.

Also missing: any statement of sample size. Twenty-one cohorts of eight-year
spans over a twenty-year store is not twenty-one independent tests -- it is
about two and a half. Both an overlapping and a NON-OVERLAPPING pass are run,
and the second is the one to believe.

WHAT THE THIRD VERSION GOT WRONG, AND WHY IT IS THE INSTRUCTIVE ONE
--------------------------------------------------------------------
It saw those drifting controls and concluded the estimator was biased at small
cohort sizes. It is not. `prank = i/(n-1)` gives a random q-subset an
expectation of exactly 0.500, and simulating every cohort count used here over
3,000 runs returns 0.4999 each time. The drift was **variance from drawing one
control per cohort** -- at five cohorts a single draw swings +/-0.10 at 95%.
`_CONTROL_DRAWS` fixes it, and every control now lands within 0.003 of 0.500.

The tempting alternative was widening `_CONTROL_BAND` until the run went green.
That would have turned the only instrument check in the file into decoration,
which is the failure this repo has caught in its own tooling four times.

SURVIVORSHIP
------------
Reads `.navstore/nav.db`, the untrimmed store: 5,187,035 rows across 4,939
schemes, of which roughly 64% are wound up or merged. `nav.db.trimmed` holds
only 1,723 live schemes and must NOT be used here -- dropping dead funds
removes exactly the losers whose fate the question is about, and would bias the
result toward "losers recover". The script refuses to run against a store with
fewer than `_MIN_SCHEMES` schemes for that reason.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import random
import sqlite3
import statistics as st
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_NAV_DB = _ROOT / ".navstore" / "nav.db"
_CATALOGUE = _ROOT / "app" / "data" / "fund_catalogue.json"

# The trimmed store has 1,723. Anything near that is the wrong file.
_MIN_SCHEMES = 3_000

# A cohort smaller than this cannot support quintiles: q = n // 5 would be three
# or fewer, and a "group" of three funds is a coin flip with extra steps.
_MIN_COHORT = 20

# NAV lookup tolerance. Weekends, festival clusters and the odd missing print
# mean an exact date match loses real observations for no reason.
_TOLERANCE_DAYS = 10

_CONTROL_BAND = (0.470, 0.530)

# Below this many DISTINCT formation dates, no interval is printed.
#
# The mistake this prevents was the worst one in the file. A "cohort" is one
# (category, date) pair, and an earlier version bootstrapped the flat list of
# them -- so five equity categories measured on 2013-01-01 were resampled as
# five independent draws of Indian equity. They are one.
#
#     non-overlapping distinct dates:  1y/1y 8   1y/3y 4   3y/1y 4
#                                      3y/3y 2   5y/3y 2   3y/5y 2
#
# The intervals those two-date rows printed (+/-0.10 to +/-0.22) were
# cross-category spread inside one or two market episodes wearing the clothes of
# sampling uncertainty over time.
_MIN_DATES = 4

# How many random subsets to average for each cohort's control.
#
# THE FIRST VERSION DREW ONE, AND MISDIAGNOSED THE RESULT. Controls came back at
# 0.534-0.539 on the five-cohort rows and the script called the estimator
# "biased at this cohort size". It is not. `prank = i/(n-1)` gives a random
# q-subset an expectation of exactly 0.500, and a simulation confirms it: over
# 3,000 runs at every cohort count used here the mean lands on 0.4999.
#
#     cohorts=5   sd 0.0495   95% of runs land in [0.403, 0.597]
#     cohorts=73  sd 0.0118   95% of runs land in [0.477, 0.523]
#
# So a single draw over five cohorts swings +/-0.10 and 0.539 is ordinary noise.
# Averaging many draws collapses that variance, which does two things: the band
# check becomes a real instrument check rather than a coin flip, and the
# group-minus-control differences stop carrying the control's noise on top of
# their own.
_CONTROL_DRAWS = 200


def _load(db: Path) -> dict[str, dict[str, float]]:
    con = sqlite3.connect(db)
    schemes = con.execute("SELECT COUNT(DISTINCT scheme_code) FROM nav_history").fetchone()[0]
    if schemes < _MIN_SCHEMES:
        raise SystemExit(
            f"{db} holds only {schemes:,} schemes. That is the trimmed store, which "
            "contains live funds only. Measuring persistence on survivors removes the "
            "losers the question is about. Point this at the untrimmed nav.db."
        )
    series: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for code, day, nav in con.execute("SELECT scheme_code, nav_date, nav FROM nav_history WHERE nav > 0"):
        series[str(code)][day] = nav
    return series


def _categories() -> dict[str, str]:
    out: dict[str, str] = {}
    for category, funds in json.loads(_CATALOGUE.read_text()).items():
        for f in funds:
            out[str(f["code"])] = category
    return out


def _nav_at(series: dict[str, float], day: dt.date) -> float | None:
    for k in range(_TOLERANCE_DAYS + 1):
        for d in (day - dt.timedelta(days=k), day + dt.timedelta(days=k)):
            v = series.get(d.isoformat())
            if v:
                return v
    return None


def _ret(series: dict[str, float], a: dt.date, b: dt.date) -> float | None:
    x, y = _nav_at(series, a), _nav_at(series, b)
    return None if not x or not y else (y / x) - 1


def _bootstrap_ci(
    by_date: "dict[dt.date, list[float]]", iters: int = 2000, seed: int = 11
) -> tuple[float, float]:
    """CLUSTER bootstrap, resampling formation DATES rather than cohorts.

    The unit of independence is the date, not the category. Funds inside a
    cohort share a market; so do the categories measured on the same day.
    Resampling dates makes the interval describe uncertainty about time, which
    is the thing the question is actually about.
    """
    rng = random.Random(seed)
    dates = list(by_date)
    means = []
    for _ in range(iters):
        drawn = rng.choices(dates, k=len(dates))
        vals = [v for d in drawn for v in by_date[d]]
        means.append(st.mean(vals))
    means.sort()
    return means[int(iters * 0.025)], means[int(iters * 0.975)]


def run(series, cats, lb_years: int, fw_years: int, *, overlapping: bool, seed: int = 11):
    eq = [c for c in cats.values() if c.startswith(("Equity Scheme", "Equity Schemes"))]
    keep = {c for c, n in collections.Counter(eq).items() if n >= 12}
    by_cat: dict[str, list[str]] = collections.defaultdict(list)
    for code, c in cats.items():
        if c in keep:
            by_cat[c].append(code)

    look = dt.timedelta(days=365 * lb_years)
    fwd = dt.timedelta(days=365 * fw_years)
    step = 1 if overlapping else (lb_years + fw_years)
    last = 2026 - fw_years
    forms = [dt.date(y, 1, 1) for y in range(2010 + lb_years, last + 1, step)]

    rng = random.Random(seed)
    groups: dict[str, dict] = {k: collections.defaultdict(list)
                               for k in ("losers", "winners", "control")}
    cohorts = obs = dead = 0
    dates_used: set = set()

    for cat in sorted(by_cat):
        for t in forms:
            pool = []
            for code in by_cat[cat]:
                s = series.get(code)
                if not s:
                    continue
                past = _ret(s, t - look, t)
                if past is None:
                    continue
                pool.append((code, past, _ret(s, t, t + fwd)))
            alive = [p for p in pool if p[2] is not None]
            dead += len(pool) - len(alive)
            if len(alive) < _MIN_COHORT:
                continue
            cohorts += 1
            obs += len(alive)
            n = len(alive)
            q = n // 5
            fwd_sorted = sorted(alive, key=lambda p: p[2])
            prank = {p[0]: i / (n - 1) for i, p in enumerate(fwd_sorted)}
            past_sorted = sorted(alive, key=lambda p: p[1])
            dates_used.add(t)
            for name, grp in (("losers", past_sorted[:q]), ("winners", past_sorted[-q:])):
                groups[name][t].append(sum(prank[p[0]] for p in grp) / len(grp))
            # The control is averaged over many draws, not taken once -- see
            # _CONTROL_DRAWS. A single draw is a coin flip wearing a lab coat.
            draws = [
                sum(prank[p[0]] for p in rng.sample(alive, q)) / q
                for _ in range(_CONTROL_DRAWS)
            ]
            groups["control"][t].append(sum(draws) / len(draws))

    if cohorts < 3:
        return None

    flat = {k: [v for vals in d.values() for v in vals] for k, d in groups.items()}
    out = {
        "lookback": lb_years, "forward": fw_years, "cohorts": cohorts,
        "dates": len(dates_used), "observations": obs,
        "dropped_no_forward_nav": dead, "control": st.mean(flat["control"]),
    }
    for name in ("losers", "winners"):
        by_date = {t: [a - b for a, b in zip(groups[name][t], groups["control"][t])]
                   for t in groups[name]}
        flat_diffs = [v for vals in by_date.values() for v in vals]
        out[name] = {
            "raw": st.mean(flat[name]),
            "minus_control": st.mean(flat_diffs),
            "ci95": _bootstrap_ci(by_date, seed=seed) if len(dates_used) >= _MIN_DATES else None,
        }
    # losers + winners sums to ~1.000 UNDER THE NULL ONLY. Any asymmetric
    # relation between past and forward return moves it, so this is an asymmetry
    # indicator and NOT an error detector. An earlier draft used it to discard a
    # row, which was wrong.
    out["tails_sum"] = out["losers"]["raw"] + out["winners"]["raw"]
    return out


COMBOS = ((1, 1), (3, 3), (3, 1), (1, 3), (5, 3), (3, 5))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_NAV_DB)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    series = _load(args.db)
    cats = _categories()
    print(f"store {args.db}  ·  {len(series):,} schemes with NAV  ·  seed {args.seed}\n")

    failures = []
    for overlapping in (True, False):
        label = "OVERLAPPING (formation dates 1 year apart)" if overlapping else "NON-OVERLAPPING (believe this one)"
        print(f"=== {label}")
        print(f"{'lb/fwd':>7s} {'dates':>6s} {'cohorts':>7s} {'obs':>6s} {'died':>5s} "
              f"{'ctrl':>6s} {'LOSE-ctrl':>10s} {'95% CI':>18s} "
              f"{'WIN-ctrl':>9s} {'95% CI':>18s} {'tails':>6s}")
        for lb, fw in COMBOS:
            r = run(series, cats, lb, fw, overlapping=overlapping, seed=args.seed)
            if r is None:
                print(f"{lb}y/{fw}y".rjust(7) + "   too few cohorts")
                continue
            L, W = r["losers"], r["winners"]
            def _ci(g):
                return (f"[{g['ci95'][0]:+.3f},{g['ci95'][1]:+.3f}]" if g["ci95"]
                        else f"<{_MIN_DATES} dates")
            print(f"{lb}y/{fw}y".rjust(7)
                  + f" {r['dates']:6d} {r['cohorts']:7d} {r['observations']:6d}"
                  + f" {r['dropped_no_forward_nav']:5d} {r['control']:6.3f}"
                  + f" {L['minus_control']:+10.3f} {_ci(L):>18s}"
                  + f" {W['minus_control']:+9.3f} {_ci(W):>18s}"
                  + f" {r['tails_sum']:6.3f}")
            lo, hi = _CONTROL_BAND
            if not lo <= r["control"] <= hi:
                failures.append(
                    f"{lb}y/{fw}y control {r['control']:.3f} outside {lo}-{hi}. "
                    f"With {_CONTROL_DRAWS} draws per cohort this is no longer "
                    "sampling noise, so the estimator really is off for this "
                    "cohort shape and nothing in the row can be read."
                )
        print()

    print("A group's score is the mean forward percentile rank of its members inside")
    print("their own cohort. 0.500 is no information BY CONSTRUCTION, which is what")
    print("makes the control column a real check rather than decoration.")
    print("`tails` is losers+winners: two opposite quintiles should average to about")
    print("1.000. A row far from that is describing its own construction, not funds.\n")

    if failures:
        print("CONTROL OUT OF BAND -- this is a failure, not a caveat:")
        for f in failures:
            print("  " + f)
        return 1
    print("Controls all inside the band.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
