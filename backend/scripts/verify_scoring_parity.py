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
from pathlib import Path

BACHATT_SERVER = Path.home() / "BachattDev" / "sip-optimizer" / "server"
QUALITY_COLUMNS = ["roll1y", "roll6m", "roll3m", "roll1m", "ret3y", "ret1y", "ret3m", "vol"]


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
    return {"peers": peers, "navs": navs, "risk": risk, "tight_scores": tight}


class _StubLogger:
    def __getattr__(self, _n):
        return lambda *a, **k: None


def _lift(path: Path, names: set[str], into: dict) -> dict:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            exec(compile(ast.Module([node], []), str(path), "exec"), into)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in names for t in node.targets
        ):
            exec(compile(ast.Module([node], []), str(path), "exec"), into)
    return into


def _shape_results(quality, quality_oos, mom, dd, risk_scores, cuts, tiers, t, grades, pd, np):
    return {
        "quality": [float(v) for v in quality],
        "quality_oos": [float(v) for v in quality_oos],
        "momentum": mom, "drawdown": dd,
        "risk_scores": [float(v) for v in risk_scores],
        "risk_cutoffs": [float(v) for v in cuts], "risk_tiers": list(tiers),
        "grade_cutoffs": [float(v) for v in t], "grades": list(grades),
        "versions": {"pandas": pd.__version__, "numpy": np.__version__},
    }


def run_oracle(fx: dict) -> dict:
    import numpy as np
    import pandas as pd

    ns = {"np": np, "pd": pd, "logger": _StubLogger(), "__name__": "oracle"}
    _lift(BACHATT_SERVER / "utils" / "helpers.py", {"nav_to_log_returns"}, ns)
    _lift(BACHATT_SERVER / "services" / "performance.py",
          {"_cap_log_returns_for_metrics", "_MAX_DAILY_SIMPLE_FOR_METRICS"}, ns)
    _lift(BACHATT_SERVER / "scripts" / "fill_metrics.py",
          {"_minmax", "_hybrid", "_make_oos_hybrid", "_compute_quality", "_grade_cutoffs",
           "_grade_from_cutoffs", "compute_momentum_drawdown", "LOOKBACK", "WARMUP",
           "_LINEAR_WEIGHTS", "_TOTAL_WEIGHT", "DRAWDOWN_THRESHOLD",
           "MOMENTUM_MAGNITUDE_CAP", "DRAWDOWN_MAGNITUDE_CAP", "GRADE_PCTL_VERY_GOOD",
           "GRADE_PCTL_GOOD", "GRADE_PCTL_AVG", "MIN_GRADE_CUTOFF_GAP"}, ns)
    _lift(BACHATT_SERVER / "scripts" / "fill_risk_scores.py",
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
    return _shape_results(quality, quality_oos, mom, dd, risk_scores, cuts, tiers, t, grades, pd, np)


def run_port(fx: dict) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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
    return _shape_results(quality, quality_oos, mom, dd, risk_scores, cuts, tiers, t, grades, pd, np)


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
    for key in ("risk_tiers", "grades"):
        if a[key] != bb[key]:
            n = sum(1 for x, y in zip(a[key], bb[key]) if x != y)
            failures.append(f"{key}: {n} label(s) differ")

    n_vals = len(a["quality"]) + len(a["quality_oos"]) + len(a["risk_scores"]) + 2
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
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"{args.mode} written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
