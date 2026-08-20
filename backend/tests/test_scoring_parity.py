"""Differential test: our port must return exactly what Bachatt returns.

Reading a formula and re-typing it is how transcription bugs get in, and this
one is 20-odd constants deep. So this does not eyeball the port -- it loads
Bachatt's **actual source** from their repo, executes their real functions as
an oracle, and asserts our module agrees to floating-point equality on
randomised inputs.

Two things it therefore catches that a hand-written fixture cannot:

1. **Transcription drift** -- a weight typed 0.15 instead of 0.155.
2. **Their drift** -- if they change the formula upstream, this goes red and we
   find out on the next run instead of six months later. That already happened
   once: commit 3a09adc added MIN_GRADE_CUTOFF_GAP on 19 Aug 2026.

The oracle needs their repo on disk. When it is absent the differential tests
skip and the behavioural tests below still run, so CI on another machine is
green without pretending it verified the port.

NOTE ON LIBRARY VERSIONS: traa runs pandas 3 / numpy 2, Bachatt runs pandas 2 /
numpy 1. This file executes their source under *our* interpreter, so it proves
the transcription is faithful. It does not prove pandas 2 and pandas 3 agree --
that is checked separately by scripts/verify_scoring_parity.py, which runs the
oracle under their own venv.
"""

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.screener import reference
from app.services.screener import scoring as port

FILL_METRICS = "scripts/fill_metrics.py"
PERFORMANCE = "services/performance.py"
HELPERS = "utils/helpers.py"
FILL_RISK = "scripts/fill_risk_scores.py"

oracle_required = pytest.mark.skipif(
    not reference.available(),
    reason=f"reference checkout not present at {reference.root()}",
)

_QUALITY_COLUMNS = ["roll1y", "roll6m", "roll3m", "roll1m", "ret3y", "ret1y", "ret3m", "vol"]


def _lift(rel_path: str, names: set[str], into: dict) -> dict:
    """Exec the named module-level functions/constants from a reference file.

    Read through `reference.read_source` -- the only door to that tree, and one
    with no write side.
    """
    source = reference.read_source(rel_path)
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            exec(compile(ast.Module([node], []), rel_path, "exec"), into)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                exec(compile(ast.Module([node], []), rel_path, "exec"), into)
    return into


class _StubLogger:
    def __getattr__(self, _name):
        return lambda *a, **k: None


@pytest.fixture(scope="module")
def oracle():
    """Bachatt's real functions, executed from their source."""
    ns: dict = {"np": np, "pd": pd, "logger": _StubLogger(), "__name__": "oracle"}
    _lift(HELPERS, {"nav_to_log_returns"}, ns)
    _lift(PERFORMANCE, {"_cap_log_returns_for_metrics", "_MAX_DAILY_SIMPLE_FOR_METRICS"}, ns)
    _lift(
        FILL_METRICS,
        {
            "_minmax", "_hybrid", "_make_oos_hybrid", "_compute_quality",
            "_grade_cutoffs", "_grade_from_cutoffs", "compute_momentum_drawdown",
            "LOOKBACK", "WARMUP", "_LINEAR_WEIGHTS", "_TOTAL_WEIGHT",
            "DRAWDOWN_THRESHOLD", "MOMENTUM_MAGNITUDE_CAP", "DRAWDOWN_MAGNITUDE_CAP",
            "GRADE_PCTL_VERY_GOOD", "GRADE_PCTL_GOOD", "GRADE_PCTL_AVG",
            "MIN_GRADE_CUTOFF_GAP",
        },
        ns,
    )
    _lift(
        FILL_RISK,
        {"compute_bachatt_risk_score", "_tier_for_score",
         "W_VOLATILITY", "W_DRAWDOWN", "W_SORTINO", "W_MOMENTUM",
         "_TIER_LOW", "_TIER_LOW_MOD", "_TIER_MODERATE", "_TIER_MOD_HIGH",
         "_TIER_HIGH", "_TIER_VERY_HIGH"},
        ns,
    )
    ns["_hybrid"] = ns["_hybrid"]  # fill_risk's compute_bachatt_risk_score closes over it
    return ns


def _peer_frame(rng, n=60) -> pd.DataFrame:
    """A plausible peer group: wide spread, a couple of outliers, some ties."""
    df = pd.DataFrame(
        {c: rng.normal(loc=12.0, scale=9.0, size=n) for c in _QUALITY_COLUMNS}
    )
    df.loc[0, "ret3y"] = 300.0           # freak fund -- exercises the 0.95 cap
    df.loc[1:4, "roll1y"] = 7.5          # ties -- exercises rank(method='average')
    df["vol"] = np.abs(df["vol"]) + 0.5
    return df


class TestAgainstReferenceSource:
    @oracle_required
    @pytest.mark.parametrize("seed", [1, 7, 42, 1234, 99999])
    def test_hybrid_matches(self, oracle, seed):
        rng = np.random.default_rng(seed)
        s = pd.Series(rng.normal(size=80) * 20)
        for w_rank, w_mag in [(0.70, 0.30), (0.75, 0.25), (0.80, 0.20),
                              (0.85, 0.15), (0.90, 0.10), (0.60, 0.40), (1.0, 0.0)]:
            expected = oracle["_hybrid"](s, w_rank, w_mag)
            actual = port.hybrid(s, w_rank, w_mag)
            pd.testing.assert_series_equal(actual, expected, check_names=False)

    @oracle_required
    def test_minmax_matches_including_degenerate(self, oracle):
        rng = np.random.default_rng(3)
        for s in [pd.Series(rng.normal(size=50)),
                  pd.Series([4.2] * 12),                 # hi == lo
                  pd.Series([0.0, 1e9, 1.0, 2.0])]:      # extreme outlier
            pd.testing.assert_series_equal(
                port.minmax(s), oracle["_minmax"](s), check_names=False
            )

    @oracle_required
    @pytest.mark.parametrize("seed", [2, 11, 555])
    def test_quality_matches(self, oracle, seed):
        df = _peer_frame(np.random.default_rng(seed))
        pd.testing.assert_series_equal(
            port.compute_quality(df, port.hybrid),
            oracle["_compute_quality"](df, oracle["_hybrid"]),
            check_names=False,
        )

    @oracle_required
    def test_out_of_sample_quality_matches(self, oracle):
        rng = np.random.default_rng(17)
        ref = _peer_frame(rng, n=90)
        other = _peer_frame(rng, n=25)
        pd.testing.assert_series_equal(
            port.compute_quality(other, port.make_oos_hybrid(ref)),
            oracle["_compute_quality"](other, oracle["_make_oos_hybrid"](ref)),
            check_names=False,
        )

    @oracle_required
    @pytest.mark.parametrize("seed", [5, 23, 777])
    def test_grade_cutoffs_and_labels_match(self, oracle, seed):
        rng = np.random.default_rng(seed)
        for scores in [rng.uniform(0.2, 0.9, size=40),
                       rng.normal(0.5, 0.0004, size=30),   # tight cluster -> gap floor fires
                       np.full(15, 0.61)]:                 # all identical
            assert port.grade_cutoffs(scores) == oracle["_grade_cutoffs"](scores)
            t = port.grade_cutoffs(scores)
            for s in scores:
                assert port.grade_from_cutoffs(s, *t) == oracle["_grade_from_cutoffs"](s, *t)

    @oracle_required
    @pytest.mark.parametrize("seed", [4, 64, 2026])
    def test_momentum_drawdown_matches(self, oracle, seed):
        """Runs their real compute_momentum_drawdown via a stub cursor."""
        rng = np.random.default_rng(seed)
        dates = pd.bdate_range("2026-01-01", periods=40)
        navs = 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.011, size=40)))
        navs[20] *= 1.4                       # a >25% day -- exercises the outlier cap
        rows = list(zip(dates.date, navs))

        class _Cur:
            def execute(self, *_a, **_k): pass
            def fetchall(self): return list(reversed(rows))   # their SQL is ORDER BY DESC

        expected = oracle["compute_momentum_drawdown"](1, _Cur())
        log_ret = np.log(pd.Series(navs, index=dates) / pd.Series(navs, index=dates).shift(1)).dropna()
        actual = port.momentum_drawdown(log_ret)
        assert actual == pytest.approx(expected, abs=1e-12), f"{actual} != {expected}"

    @oracle_required
    @pytest.mark.parametrize("seed", [8, 88, 808])
    def test_risk_score_and_tiers_match(self, oracle, seed):
        rng = np.random.default_rng(seed)
        n = 70
        df = pd.DataFrame({
            "volatility": np.abs(rng.normal(14, 8, n)) + 0.2,
            "drawdown_score": np.clip(rng.normal(0.15, 0.12, n), 0, None),
            "sortino": rng.normal(1.5, 2.0, n),
            "momentum_score": np.clip(rng.normal(0.3, 0.15, n), 0, None),
        })
        df.loc[0, "sortino"] = 208.0          # overnight-fund outlier
        pd.testing.assert_series_equal(
            port.risk_score(df), oracle["compute_bachatt_risk_score"](df), check_names=False
        )
        scores = port.risk_score(df).to_numpy()
        cuts = port.risk_tier_cutoffs(scores)
        for s in scores:
            assert port.risk_tier_for(s, cuts) == oracle["_tier_for_score"](s, *cuts)


class TestBehaviour:
    """Properties that must hold whether or not their source is on this machine."""

    def test_final_score_weights_sum_to_one(self):
        assert port.W_QUALITY + port.W_MOMENTUM + port.W_DRAWDOWN == pytest.approx(1.0)
        assert sum(port.PILLAR_WEIGHTS.values()) == pytest.approx(1.0)
        assert sum(w for *_, w in port.CONSISTENCY_TERMS) == pytest.approx(1.0)
        assert sum(w for *_, w in port.PERFORMANCE_TERMS) == pytest.approx(1.0)
        assert (port.W_RISK_VOLATILITY + port.W_RISK_DRAWDOWN
                + port.W_RISK_SORTINO + port.W_RISK_MOMENTUM) == pytest.approx(1.0)

    def test_drawdown_is_subtracted_not_added(self):
        """A deeper drawdown must lower the score, never raise it."""
        calm = port.final_score(quality=0.6, momentum=0.3, drawdown=0.0)
        rough = port.final_score(quality=0.6, momentum=0.3, drawdown=0.9)
        assert rough < calm

    def test_grade_gap_floor_widens_tight_clusters(self):
        """The 19 Aug fix: near-identical scores must not split across distant grades."""
        tight = np.full(40, 0.5) + np.linspace(0, 0.0009, 40)
        t_vg, t_g, t_a = port.grade_cutoffs(tight)
        assert t_vg - t_g >= port.MIN_GRADE_CUTOFF_GAP - 1e-12
        assert t_g - t_a >= port.MIN_GRADE_CUTOFF_GAP - 1e-12

    def test_short_history_returns_none_not_a_partial_number(self):
        short = pd.Series(np.random.default_rng(0).normal(0, 0.01, 15))
        assert port.momentum_drawdown(short) == (None, None)

    def test_outlier_day_is_neutralised(self):
        rng = np.random.default_rng(0)
        base = pd.Series(rng.normal(0.0004, 0.004, 30))
        spiked = base.copy()
        spiked.iloc[15] = np.log(1.60)        # +60% day
        capped, n = port.cap_log_returns(spiked)
        assert n == 1 and capped.iloc[15] == pytest.approx(0.0)
        assert len(capped) == len(spiked), "index must be preserved, not dropped"

    def test_grade_peer_key_splits_debt_by_sub_category(self):
        assert port.grade_peer_key("Debt Scheme", "Liquid Fund") == ("Debt Scheme", "Liquid Fund")
        assert port.grade_peer_key("Equity Scheme", "Flexi Cap Fund") == ("Equity Scheme", None)

    def test_preferred_amc_logic_is_absent(self):
        """The one thing we deliberately did not port."""
        src = (Path(__file__).parent.parent / "app/services/screener/scoring.py").read_text()
        assert "PREFERRED_AMC" not in src.replace("PREFERRED_AMCS`", "")
