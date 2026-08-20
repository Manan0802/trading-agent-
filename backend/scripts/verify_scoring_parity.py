"""Cross-version proof that our port equals Bachatt on THEIR library versions.

`tests/test_scoring_parity.py` runs the reference source under our interpreter,
which proves the transcription is faithful. It cannot prove that pandas 3 /
numpy 2 (ours) compute the same numbers as pandas 2 / numpy 1 (theirs) -- and a
silent difference in `rank(pct=True)` or percentile interpolation would move
every fund on the page without erroring anywhere.

So this runs the same fixture twice:

    oracle : their source, under a venv pinned to pandas 2.2.2 / numpy 1.26.4
    port   : our module,   under traa's venv (pandas 3 / numpy 2)

and diffs the results. The fixture is built with stdlib `random.Random(seed)`
rather than numpy's Generator, because NumPy does not guarantee its Generator
stream across major versions -- using it would make the fixture itself the
variable under test.

    <pandas2-venv>/bin/python scripts/verify_scoring_parity.py --mode oracle --out /tmp/oracle.json
    venv/bin/python           scripts/verify_scoring_parity.py --mode port   --out /tmp/port.json
    venv/bin/python           scripts/verify_scoring_parity.py --compare /tmp/oracle.json /tmp/port.json
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.screener import reference  # noqa: E402  (stdlib-only, safe under any venv)

QUALITY_COLUMNS = ["roll1y", "roll6m", "roll3m", "roll1m", "ret3y", "ret1y", "ret3m", "vol"]

# Our field name -> theirs. Where they differ it is because theirs is actively
# misleading: `drawdown_score` (a 0-1 signal) and `max_drawdown` (a negative
# percent) are different numbers, and upstream names the rolling windows
# `rolling_ret_*`.
METRIC_FIELD_MAP = {
    "annualized_return": "annualized_return",
    "returns_1m": "returns_1m", "returns_3m": "returns_3m", "returns_6m": "returns_6m",
    "returns_1y": "returns_1y", "returns_3y": "returns_3y",
    "rolling_1m": "rolling_ret_1m", "rolling_3m": "rolling_ret_3m",
    "rolling_6m": "rolling_ret_6m", "rolling_1y": "rolling_ret_1y",
    "rolling_3y": "rolling_ret_3y",
    "volatility": "volatility", "sharpe": "sharpe_ratio", "sortino": "sortino_ratio",
    "max_drawdown": "max_drawdown",
    "best_30d": "best_30d_return", "worst_30d": "worst_30d_return",
    "negative_days_pct": "negative_days_pct",
}


def build_fixture() -> dict:
    """Deterministic inputs, identical under any numpy/pandas version."""
    rnd = random.Random(20260820)
    n = 60
    peers = {c: [rnd.gauss(12.0, 9.0) for _ in range(n)] for c in QUALITY_COLUMNS}
    peers["ret3y"][0] = 300.0                       # freak fund -> exercises the 0.95 cap
    for i in range(1, 5):
        peers["roll1y"][i] = 7.5                    # ties -> rank(method='average')
    peers["vol"] = [abs(v) + 0.5 for v in peers["vol"]]

    navs, level = [], 100.0
    for i in range(40):
        level *= math.exp(rnd.gauss(0.0006, 0.011))
        if i == 20:
            level *= 1.4                            # >25% day -> exercises the outlier cap
        navs.append(level)

    risk = {
        "volatility": [abs(rnd.gauss(14, 8)) + 0.2 for _ in range(70)],
        "drawdown_score": [max(0.0, rnd.gauss(0.15, 0.12)) for _ in range(70)],
        "sortino": [rnd.gauss(1.5, 2.0) for _ in range(70)],
        "momentum_score": [max(0.0, rnd.gauss(0.3, 0.15)) for _ in range(70)],
    }
    risk["sortino"][0] = 208.0                      # overnight-fund outlier

    tight = [0.5 + i * 0.0009 / 39 for i in range(40)]   # tight cluster -> gap floor fires

    # A separate, longer series for the metrics engine. It has to span more than
    # a year or the annualisation branches never run, and it carries one >25%
    # day so the outlier cap fires here too. `searchsorted`, `expanding().max()`
    # and `std(ddof=1)` are all places a pandas major could differ and error
    # nowhere -- this is the only thing that would catch that.
    metric_navs, level = [], 100.0
    for i in range(900):
        level *= math.exp(rnd.gauss(0.0004, 0.010))
        if i == 400:
            level *= 1.38
        metric_navs.append(round(level, 6))

    return {
        "peers": peers, "navs": navs, "risk": risk, "tight_scores": tight,
        "metric_navs": metric_navs,
    }


class _StubLogger:
    def __getattr__(self, _n):
        return lambda *a, **k: None


def _lift(rel_path: str, names: set[str], into: dict) -> dict:
    tree = ast.parse(reference.read_source(rel_path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            exec(compile(ast.Module([node], []), rel_path, "exec"), into)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in names for t in node.targets
        ):
            exec(compile(ast.Module([node], []), rel_path, "exec"), into)
    return into


def _shape_results(quality, quality_oos, mom, dd, risk_scores, cuts, tiers, t, grades, pd, np,
                   metrics=None):
    return {
        "quality": [float(v) for v in quality],
        "quality_oos": [float(v) for v in quality_oos],
        "momentum": mom, "drawdown": dd,
        "risk_scores": [float(v) for v in risk_scores],
        "risk_cutoffs": [float(v) for v in cuts], "risk_tiers": list(tiers),
        "grade_cutoffs": [float(v) for v in t], "grades": list(grades),
        "metrics": metrics or {},
        "versions": {"pandas": pd.__version__, "numpy": np.__version__},
    }


def run_oracle(fx: dict) -> dict:
    import numpy as np
    import pandas as pd

    ns = {"np": np, "pd": pd, "logger": _StubLogger(), "__name__": "oracle"}
    _lift("utils/helpers.py", {"nav_to_log_returns"}, ns)
    _lift("services/performance.py",
          {"calculate_performance_metrics", "_cap_log_returns_for_metrics",
           "_MAX_DAILY_SIMPLE_FOR_METRICS", "DEFAULT_RISK_FREE_RATE"}, ns)
    ns.setdefault("DEFAULT_RISK_FREE_RATE", 0.04)
    _lift("scripts/fill_metrics.py",
          {"_minmax", "_hybrid", "_make_oos_hybrid", "_compute_quality", "_grade_cutoffs",
           "_grade_from_cutoffs", "compute_momentum_drawdown", "LOOKBACK", "WARMUP",
           "_LINEAR_WEIGHTS", "_TOTAL_WEIGHT", "DRAWDOWN_THRESHOLD",
           "MOMENTUM_MAGNITUDE_CAP", "DRAWDOWN_MAGNITUDE_CAP", "GRADE_PCTL_VERY_GOOD",
           "GRADE_PCTL_GOOD", "GRADE_PCTL_AVG", "MIN_GRADE_CUTOFF_GAP"}, ns)
    _lift("scripts/fill_risk_scores.py",
          {"compute_bachatt_risk_score", "_tier_for_score", "W_VOLATILITY", "W_DRAWDOWN",
           "W_SORTINO", "W_MOMENTUM", "_TIER_LOW", "_TIER_LOW_MOD", "_TIER_MODERATE",
           "_TIER_MOD_HIGH", "_TIER_HIGH", "_TIER_VERY_HIGH"}, ns)

    peers = pd.DataFrame(fx["peers"])
    quality = ns["_compute_quality"](peers, ns["_hybrid"])
    ref = peers.iloc[:45].reset_index(drop=True)
    oos = peers.iloc[45:].reset_index(drop=True)
    quality_oos = ns["_compute_quality"](oos, ns["_make_oos_hybrid"](ref))

    dates = pd.bdate_range("2026-01-01", periods=len(fx["navs"]))
    rows = list(zip([d.date() for d in dates], fx["navs"]))

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return list(reversed(rows))

    mom, dd = ns["compute_momentum_drawdown"](1, _Cur())

    risk = pd.DataFrame(fx["risk"])
    risk_scores = ns["compute_bachatt_risk_score"](risk)
    cuts = [float(v) for v in np.percentile(risk_scores.to_numpy(), [15, 30, 50, 70, 85])]
    tiers = [ns["_tier_for_score"](float(s), *cuts) for s in risk_scores]

    tight = np.array(fx["tight_scores"])
    t = ns["_grade_cutoffs"](tight)
    grades = [ns["_grade_from_cutoffs"](float(s), *t) for s in tight]

    m_dates = pd.bdate_range("2022-01-03", periods=len(fx["metric_navs"]))
    m_nav = pd.Series(fx["metric_navs"], index=m_dates)
    m_log = ns["nav_to_log_returns"](m_nav)
    metrics = {k: float(v) for k, v in ns["calculate_performance_metrics"](m_log).items()}

    return _shape_results(quality, quality_oos, mom, dd, risk_scores, cuts, tiers, t, grades,
                          pd, np, metrics=metrics)


def run_port(fx: dict) -> dict:
    import numpy as np
    import pandas as pd

    from app.services.screener import scoring as b

    peers = pd.DataFrame(fx["peers"])
    quality = b.compute_quality(peers, b.hybrid)
    ref = peers.iloc[:45].reset_index(drop=True)
    oos = peers.iloc[45:].reset_index(drop=True)
    quality_oos = b.compute_quality(oos, b.make_oos_hybrid(ref))

    dates = pd.bdate_range("2026-01-01", periods=len(fx["navs"]))
    nav = pd.Series(fx["navs"], index=dates)
    log_ret = np.log(nav / nav.shift(1)).dropna()
    mom, dd = b.momentum_drawdown(log_ret)

    risk = pd.DataFrame(fx["risk"])
    risk_scores = b.risk_score(risk)
    cuts = list(b.risk_tier_cutoffs(risk_scores.to_numpy()))
    tiers = [b.risk_tier_for(float(s), tuple(cuts)) for s in risk_scores]

    tight = np.array(fx["tight_scores"])
    t = b.grade_cutoffs(tight)
    grades = [b.grade_from_cutoffs(float(s), *t) for s in tight]

    from app.services.screener import metrics as met

    m_dates = pd.bdate_range("2022-01-03", periods=len(fx["metric_navs"]))
    rows = [(d.date(), v) for d, v in zip(m_dates, fx["metric_navs"])]
    # `as_of` is pinned rather than taken from the clock, so this comparison is
    # reproducible on any day. The window is wide enough to hold the whole
    # series, because the point here is the arithmetic, not the cutoff.
    computed = met.compute(rows, date(2026, 1, 1))
    metrics = {their: float(getattr(computed, ours)) for ours, their in METRIC_FIELD_MAP.items()}

    return _shape_results(quality, quality_oos, mom, dd, risk_scores, cuts, tiers, t, grades,
                          pd, np, metrics=metrics)


def compare(a: dict, bb: dict, tol: float = 1e-12) -> int:
    print(f"oracle : pandas {a['versions']['pandas']} / numpy {a['versions']['numpy']}")
    print(f"port   : pandas {bb['versions']['pandas']} / numpy {bb['versions']['numpy']}")
    print()
    worst, failures = 0.0, []
    for key in ("quality", "quality_oos", "risk_scores", "risk_cutoffs", "grade_cutoffs"):
        for i, (x, y) in enumerate(zip(a[key], bb[key])):
            d = abs(x - y)
            worst = max(worst, d)
            if d > tol:
                failures.append(f"{key}[{i}]: {x!r} vs {y!r}  (delta {d:.3e})")
    for key in ("momentum", "drawdown"):
        d = abs(a[key] - bb[key])
        worst = max(worst, d)
        if d > tol:
            failures.append(f"{key}: {a[key]!r} vs {bb[key]!r}  (delta {d:.3e})")
    for key in sorted(set(a["metrics"]) | set(bb["metrics"])):
        if key not in a["metrics"] or key not in bb["metrics"]:
            failures.append(f"metrics.{key}: present on only one side")
            continue
        d = abs(a["metrics"][key] - bb["metrics"][key])
        worst = max(worst, d)
        if d > tol:
            failures.append(
                f"metrics.{key}: {a['metrics'][key]!r} vs {bb['metrics'][key]!r} (delta {d:.3e})"
            )
    for key in ("risk_tiers", "grades"):
        if a[key] != bb[key]:
            n = sum(1 for x, y in zip(a[key], bb[key]) if x != y)
            failures.append(f"{key}: {n} label(s) differ")

    n_vals = (len(a["quality"]) + len(a["quality_oos"]) + len(a["risk_scores"]) + 2
              + len(a["metrics"]))
    print(f"compared {n_vals} numeric values + "
          f"{len(a['risk_tiers']) + len(a['grades'])} labels")
    print(f"largest absolute difference: {worst:.3e}   (tolerance {tol:.0e})")
    if failures:
        print(f"\n{len(failures)} MISMATCH(ES):")
        for f in failures[:20]:
            print("  " + f)
        return 1
    print("\nIDENTICAL across library versions.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["oracle", "port"])
    ap.add_argument("--out")
    ap.add_argument("--compare", nargs=2, metavar=("ORACLE", "PORT"))
    args = ap.parse_args()

    if args.compare:
        return compare(json.loads(Path(args.compare[0]).read_text()),
                       json.loads(Path(args.compare[1]).read_text()))

    fx = build_fixture()
    result = run_oracle(fx) if args.mode == "oracle" else run_port(fx)
    out = Path(args.out).resolve()
    # Belt: our own output must never be written anywhere inside the reference tree.
    if reference.available() and out.is_relative_to(reference.root().resolve()):
        raise SystemExit(f"refusing to write inside the reference checkout: {out}")
    out.write_text(json.dumps(result, indent=1))
    print(f"{args.mode} written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
