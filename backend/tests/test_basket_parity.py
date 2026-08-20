"""Differential test: our portfolio optimiser must return what Bachatt's returns.

Same discipline as `test_scoring_parity.py`. This does not eyeball the port --
it loads Bachatt's **actual source** for `services/optimizer.py`,
`config/portfolio_baskets.py` and `config/settings.py`, executes their real
functions as an oracle, and asserts our module agrees on randomised inputs.

**Why the tolerance is 1e-6 on weights and exact everywhere else.** The
deterministic pieces -- `bucket_factor`, `parse_slot_key`,
`weight_bounds_for_slot`, `max_weight_for_slot`, the basket dictionaries, the
strategy bounds -- are compared with `==`, because a lookup table has no reason
to drift by an ulp and a floating-point tolerance there would only hide a typo.
Weights come out of SLSQP, which stops on `ftol=1e-8` in the *objective*; near
an optimum the objective is flat, so the weights themselves are only pinned to
roughly the square root of that, about 1e-4, and any reordering of a
floating-point sum inside BLAS can move the iterate path. On this machine the
two implementations agree bit-for-bit, so 1e-6 has enormous headroom while still
being far tighter than anything that could matter: 1e-6 of a ₹1,00,000 portfolio
is ten paise. What 1e-6 will not tolerate is a changed constant -- every
sabotage in the pass that accompanied this port moved at least one weight by
more than 0.001.

**Fixtures come from stdlib `random.Random(seed)`, not `numpy.random`.** NumPy
does not guarantee its stream across major versions, so a numpy-seeded fixture
would make the random number generator the variable under test the next time
numpy is upgraded. `random.Random` is specified to be reproducible.

NOTE ON LIBRARY VERSIONS: traa runs pandas 3 / numpy 2 / scipy 1.18, Bachatt
runs pandas 2 / numpy 1. Their `optimize_portfolio` does `cov_matrix +=
np.eye(n) * 1e-8` in place on `returns.cov().values`, and under pandas 3 that
array is **read-only**, so their function raises `ValueError: output array is
read-only` before it reaches the solver. `_WritableCov` below hands the oracle a
writable copy so the rest of their arithmetic can be tested at all; it is the
same kind of shim as the stub cursor in `test_scoring_parity.py`. That is a real
incompatibility in their code, not in ours -- our `covariance()` builds a new
array instead of mutating one.
"""

import ast
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize

from app.services.screener import basket as port
from app.services.screener import reference

OPTIMIZER = "services/optimizer.py"
BASKETS = "config/portfolio_baskets.py"
SETTINGS = "config/settings.py"

MODULE_PATH = Path(__file__).parent.parent / "app/services/screener/basket.py"

oracle_required = pytest.mark.skipif(
    not reference.available(),
    reason=f"reference checkout not present at {reference.root()}",
)

WEIGHT_TOL = 1e-6

STRATEGIES = ("conservative", "balanced", "aggressive")
REGIMES = ("bullish", "bearish", "neutral")


def _lift(rel_path: str, names: set[str], into: dict) -> dict:
    """Exec the named module-level functions/constants from a reference file.

    Read through `reference.read_source` -- the only door to that tree, and one
    with no write side. Handles `AnnAssign` as well as `Assign`, which
    `test_scoring_parity._lift` does not need to: `PORTFOLIO_BASKETS: Dict[str,
    dict] = {...}` is an annotated assignment and would otherwise be skipped
    silently, leaving the oracle with no baskets and every basket test passing
    vacuously.
    """
    source = reference.read_source(rel_path)
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            exec(compile(ast.Module([node], []), rel_path, "exec"), into)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                exec(compile(ast.Module([node], []), rel_path, "exec"), into)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in names:
                exec(compile(ast.Module([node], []), rel_path, "exec"), into)
    return into


class _StubLogger:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class _CovFrame:
    """Just enough of a DataFrame for `cov_matrix = returns.cov().values`."""

    def __init__(self, values):
        self.values = values


class _WritableCov:
    """A returns frame whose `.cov().values` is writable. See the module docstring."""

    def __init__(self, frame: pd.DataFrame):
        self._frame = frame

    def __getattr__(self, name):
        return getattr(self._frame, name)

    def cov(self):
        return _CovFrame(self._frame.cov().values.copy())


@pytest.fixture(scope="module")
def oracle():
    """Bachatt's real functions, executed from their source.

    `Dict` and `Tuple` are injected because their annotations are evaluated when
    a single node is compiled without the module's `from __future__ import
    annotations`.
    """
    ns: dict = {
        "np": np,
        "pd": pd,
        "minimize": minimize,
        "logger": _StubLogger(),
        "__name__": "oracle",
        "Dict": dict,
        "Tuple": tuple,
    }
    _lift(SETTINGS, {"RISK_FREE_RATE", "STRATEGY_BOUNDS"}, ns)
    _lift(
        BASKETS,
        {
            "PORTFOLIO_BASKETS", "MIN_BASKET_SIZE", "RANK_POOL_LIMIT",
            "MAX_WEIGHT_DEFAULT", "MAX_WEIGHT_COMMODITY",
            "MIN_WEIGHT_DEBT", "MIN_WEIGHT_FLEXI",
            "parse_slot_key", "weight_bounds_for_slot", "max_weight_for_slot",
            "get_basket", "basket_cat_composition",
        },
        ns,
    )
    _lift(
        OPTIMIZER,
        {
            "LOOKBACK", "_LINEAR_WEIGHTS", "_TOTAL_WEIGHT",
            "MOMENTUM_MAX_SCALE", "DRAWDOWN_MAX_SCALE",
            "MOMENTUM_MAGNITUDE_CAP", "DRAWDOWN_MAGNITUDE_CAP",
            "MOMENTUM_BUCKETS", "DRAWDOWN_BUCKETS", "NEUTRAL_BUCKETS",
            "bucket_factor", "detect_momentum_drawdown", "optimize_portfolio",
        },
        ns,
    )
    return ns


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures, built with the standard library
# ─────────────────────────────────────────────────────────────────────────────

ALL_SLOT_KEYS = sorted(
    {key for basket in port.PORTFOLIO_BASKETS.values() for key in basket["slots"]}
)


def _frame(seed: int, mus, sds, rows: int) -> pd.DataFrame:
    """Daily log returns, one column per fund, from stdlib `random.Random`."""
    rnd = random.Random(seed)
    codes = [f"F{i}" for i in range(len(mus))]
    return pd.DataFrame(
        {c: [rnd.gauss(mus[i], sds[i]) for _ in range(rows)] for i, c in enumerate(codes)}
    )


def _six_fund_book() -> tuple[pd.DataFrame, list, dict]:
    """A realistic MAXX-shaped book: two equity, one flexi, gold, silver, debt."""
    df = _frame(
        11,
        mus=[0.0006, 0.0005, 0.0007, 0.0003, 0.0004, 0.0002],
        sds=[0.0080, 0.0100, 0.0120, 0.0090, 0.0140, 0.0008],
        rows=200,
    )
    bounds = [(0.0, 0.4), (0.0, 0.4), (0.1, 0.4), (0.0, 0.15), (0.0, 0.15), (0.1, 0.4)]
    scores = {c: 0.30 + 0.09 * i for i, c in enumerate(df.columns)}
    return df, bounds, scores


def _regime_sensitive_book() -> tuple[pd.DataFrame, list, dict]:
    """A book where the 30-day loss floor actually binds.

    Found by search, and the search itself is the finding: with equal scores the
    linear score term is a constant, so the solve is min-variance plus the
    penalty, and only then does moving `max_loss_threshold` move the answer. The
    isolated six-day slump in fund F1 is what makes the max-softmin portfolio
    differ from the min-variance one.
    """
    df = _frame(
        61,
        mus=[0.0022, 0.0020, 0.0021, 0.0019],
        sds=[0.0030, 0.0032, 0.0031, 0.0033],
        rows=60,
    )
    df.iloc[10:16, 1] = [-0.010, -0.012, -0.009, -0.011, -0.008, -0.010]
    bounds = [(0.0, 0.4)] * 4
    scores = {c: 0.55 for c in df.columns}
    return df, bounds, scores


def _near_zero_variance_book() -> tuple[pd.DataFrame, list, dict]:
    """One arbitrage/liquid fund with a nearly flat NAV.

    This is the case the linear objective exists to survive: a ratio objective
    divides by a volatility that is collapsing to zero, so score/vol runs away
    and the solver puts everything in the flattest thing it can find.
    """
    df = _frame(
        29,
        mus=[0.0006, 0.0005, 0.00018, 0.0004],
        sds=[0.0090, 0.0110, 0.0000004, 0.0100],
        rows=200,
    )
    bounds = [(0.0, 0.4), (0.0, 0.4), (0.0, 0.4), (0.0, 0.4)]
    scores = {"F0": 0.62, "F1": 0.55, "F2": 0.48, "F3": 0.60}
    return df, bounds, scores


def _both(oracle, df, bounds, strategy, regime, objective, scores, current_portfolio=None):
    """Run oracle and port on identical inputs; return both `(w, ok, raw)` triples."""
    expected = oracle["optimize_portfolio"](
        _WritableCov(df),
        list(bounds),
        strategy,
        regime,
        objective,
        current_portfolio=current_portfolio,
        return_raw=True,
        bachatt_scores=scores,
        silent=True,
    )
    actual = port.optimize_portfolio(
        df,
        list(bounds),
        strategy,
        regime,
        objective,
        scores=scores,
        current_portfolio=current_portfolio,
        return_raw=True,
    )
    return expected, actual


def _assert_same(expected, actual, tol=WEIGHT_TOL):
    assert actual[1] == expected[1], "success flag differs"
    np.testing.assert_allclose(actual[0], np.asarray(expected[0]), atol=tol, rtol=0)
    np.testing.assert_allclose(actual[2], np.asarray(expected[2]), atol=tol, rtol=0)


# ─────────────────────────────────────────────────────────────────────────────
# The lookup tables: exact
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigAgainstReferenceSource:
    @oracle_required
    def test_strategy_bounds_and_risk_free_rate_match(self, oracle):
        assert port.STRATEGY_BOUNDS == oracle["STRATEGY_BOUNDS"]
        assert port.RISK_FREE_RATE == oracle["RISK_FREE_RATE"]

    @oracle_required
    def test_basket_definitions_match(self, oracle):
        assert port.PORTFOLIO_BASKETS == oracle["PORTFOLIO_BASKETS"]
        assert port.MAX_WEIGHT_DEFAULT == oracle["MAX_WEIGHT_DEFAULT"]
        assert port.MAX_WEIGHT_COMMODITY == oracle["MAX_WEIGHT_COMMODITY"]
        assert port.MIN_WEIGHT_DEBT == oracle["MIN_WEIGHT_DEBT"]
        assert port.MIN_WEIGHT_FLEXI == oracle["MIN_WEIGHT_FLEXI"]
        assert port.MIN_BASKET_SIZE == oracle["MIN_BASKET_SIZE"]
        assert port.RANK_POOL_LIMIT == oracle["RANK_POOL_LIMIT"]

    @oracle_required
    @pytest.mark.parametrize("slot_key", ALL_SLOT_KEYS + [
        "Hybrid Scheme::Aggressive Hybrid Fund",   # a slot neither basket uses
        "Something Nobody Defined",                # unknown, bare
        "Commodity",                               # bare commodity
        "",                                        # empty
    ])
    def test_slot_bounds_and_parsing_match(self, oracle, slot_key):
        assert port.parse_slot_key(slot_key) == oracle["parse_slot_key"](slot_key)
        assert port.weight_bounds_for_slot(slot_key) == oracle["weight_bounds_for_slot"](slot_key)
        assert port.max_weight_for_slot(slot_key) == oracle["max_weight_for_slot"](slot_key)

    @oracle_required
    @pytest.mark.parametrize("basket_id", ["MAXX", "BALANCED", "INSTA_FD", "maxx",
                                           "  balanced  ", "NOPE", ""])
    def test_get_basket_and_composition_match(self, oracle, basket_id):
        assert port.get_basket(basket_id) == oracle["get_basket"](basket_id)
        assert port.basket_cat_composition(basket_id) == oracle["basket_cat_composition"](basket_id)

    @oracle_required
    def test_optimizer_constants_match(self, oracle):
        assert port.LOOKBACK == oracle["LOOKBACK"]
        np.testing.assert_array_equal(port.LINEAR_WEIGHTS, oracle["_LINEAR_WEIGHTS"])
        assert port.TOTAL_WEIGHT == oracle["_TOTAL_WEIGHT"]
        assert port.MOMENTUM_MAX_SCALE == oracle["MOMENTUM_MAX_SCALE"]
        assert port.DRAWDOWN_MAX_SCALE == oracle["DRAWDOWN_MAX_SCALE"]
        assert port.MOMENTUM_MAGNITUDE_CAP == oracle["MOMENTUM_MAGNITUDE_CAP"]
        assert port.DRAWDOWN_MAGNITUDE_CAP == oracle["DRAWDOWN_MAGNITUDE_CAP"]
        assert port.MOMENTUM_BUCKETS == oracle["MOMENTUM_BUCKETS"]
        assert port.DRAWDOWN_BUCKETS == oracle["DRAWDOWN_BUCKETS"]
        assert port.NEUTRAL_BUCKETS == oracle["NEUTRAL_BUCKETS"]


# ─────────────────────────────────────────────────────────────────────────────
# The arithmetic: exact where it is deterministic
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalsAgainstReferenceSource:
    @oracle_required
    @pytest.mark.parametrize("bucket_name", ["MOMENTUM_BUCKETS", "DRAWDOWN_BUCKETS",
                                             "NEUTRAL_BUCKETS"])
    def test_bucket_factor_matches_exactly(self, oracle, bucket_name):
        ratios = [
            -5.0, -0.001, 0.0, 0.25, 0.4999, 0.5, 0.75, 0.9, 1.0, 1.0999, 1.1,
            1.4999, 1.5, 1.9999, 2.0, 2.9999, 3.0, 12.0, 1e9, float("inf"),
        ]
        ours = port.__dict__[bucket_name]
        theirs = oracle[bucket_name]
        for ratio in ratios:
            assert port.bucket_factor(ratio, ours) == oracle["bucket_factor"](ratio, theirs), ratio

    @oracle_required
    @pytest.mark.parametrize("seed", [4, 64, 2026])
    def test_detect_momentum_drawdown_matches(self, oracle, seed):
        df = _frame(
            seed,
            mus=[0.0009, -0.0006, 0.0002, 0.0000, 0.0015],
            sds=[0.0090, 0.0130, 0.0040, 0.0000001, 0.0110],
            rows=45,
        )
        exp = oracle["detect_momentum_drawdown"](df)
        act = port.detect_momentum_drawdown(df)
        assert act[0] == exp[0], "momentum set"
        assert act[1] == exp[1], "drawdown set"
        for i in (2, 3, 4):
            assert act[i] == pytest.approx(exp[i], abs=1e-15)

    @oracle_required
    def test_detect_momentum_drawdown_matches_on_a_short_window(self, oracle):
        """Fewer rows than lookback+warmup. Neither implementation refuses; both
        shorten the weight vector and score whatever is there."""
        df = _frame(5, mus=[0.001, -0.001], sds=[0.01, 0.012], rows=9)
        exp = oracle["detect_momentum_drawdown"](df)
        act = port.detect_momentum_drawdown(df)
        assert act[0] == exp[0] and act[1] == exp[1]
        assert act[4] == pytest.approx(exp[4], abs=1e-15)


# ─────────────────────────────────────────────────────────────────────────────
# The solve
# ─────────────────────────────────────────────────────────────────────────────

class TestOptimizerAgainstReferenceSource:
    @oracle_required
    @pytest.mark.parametrize("strategy", STRATEGIES)
    @pytest.mark.parametrize("regime", REGIMES)
    def test_weights_match_for_every_strategy_and_regime(self, oracle, strategy, regime):
        df, bounds, scores = _six_fund_book()
        expected, actual = _both(oracle, df, bounds, strategy, regime, "bachatt", scores)
        _assert_same(expected, actual)
        assert actual[0].sum() == pytest.approx(1.0)

    @oracle_required
    @pytest.mark.parametrize("strategy", STRATEGIES)
    @pytest.mark.parametrize("regime", REGIMES)
    def test_weights_match_when_the_loss_floor_actually_binds(self, oracle, strategy, regime):
        df, bounds, scores = _regime_sensitive_book()
        expected, actual = _both(oracle, df, bounds, strategy, regime, "bachatt", scores)
        _assert_same(expected, actual)

    @oracle_required
    @pytest.mark.parametrize("objective", ["bachatt", "sharpe", "sortino", "anything-else"])
    def test_weights_match_for_every_objective(self, oracle, objective):
        df, bounds, scores = _six_fund_book()
        expected, actual = _both(oracle, df, bounds, "balanced", "neutral", objective, scores)
        _assert_same(expected, actual)

    @oracle_required
    def test_weights_match_with_a_near_zero_variance_fund(self, oracle):
        df, bounds, scores = _near_zero_variance_book()
        expected, actual = _both(oracle, df, bounds, "aggressive", "neutral", "bachatt", scores)
        _assert_same(expected, actual)

    @oracle_required
    @pytest.mark.parametrize(
        "label,scores",
        [
            ("every score missing", None),
            ("empty score map", {}),
            ("every score identical", {f"F{i}": 0.5 for i in range(6)}),
            ("one fund dominating", {"F0": 0.1, "F1": 0.1, "F2": 0.1,
                                     "F3": 0.1, "F4": 0.1, "F5": 9.9}),
            ("half the codes unknown", {"F0": 0.7, "F3": 0.4}),
        ],
    )
    def test_weights_match_on_every_score_fallback(self, oracle, label, scores):
        df, bounds, _ = _six_fund_book()
        expected, actual = _both(oracle, df, bounds, "balanced", "neutral", "bachatt", scores)
        _assert_same(expected, actual)

    @oracle_required
    @pytest.mark.parametrize(
        "label,bounds",
        [
            ("lower bounds sum above 1", [(0.3, 0.4)] * 4),
            ("upper bounds sum below 1", [(0.0, 0.15)] * 4),
            ("both at once", [(0.28, 0.30)] * 4),
        ],
    )
    def test_weights_match_when_the_bounds_are_infeasible(self, oracle, label, bounds):
        df, _, _ = _near_zero_variance_book()
        scores = {"F0": 0.62, "F1": 0.55, "F2": 0.48, "F3": 0.60}
        expected, actual = _both(oracle, df, bounds, "balanced", "neutral", "bachatt", scores)
        _assert_same(expected, actual)

    @oracle_required
    def test_weights_match_with_a_current_portfolio(self, oracle):
        """The tactical overlay with real ratios, not the all-ones default."""
        df, bounds, scores = _six_fund_book()
        current = {"F0": 40000.0, "F1": 0.0, "F2": 5000.0,
                   "F3": 25000.0, "F4": 1000.0, "F5": 9000.0}
        expected, actual = _both(
            oracle, df, bounds, "aggressive", "bullish", "bachatt", scores,
            current_portfolio=current,
        )
        _assert_same(expected, actual)

    @oracle_required
    def test_weights_match_on_four_funds(self, oracle):
        """The BALANCED shape: four slots, one of them debt with a floor."""
        df = _frame(77, mus=[0.0006, 0.0007, 0.0003, 0.00018],
                    sds=[0.0095, 0.0115, 0.0085, 0.0006], rows=180)
        bounds = [(0.0, 0.4), (0.1, 0.4), (0.0, 0.15), (0.1, 0.4)]
        scores = {"F0": 0.58, "F1": 0.66, "F2": 0.51, "F3": 0.44}
        expected, actual = _both(oracle, df, bounds, "balanced", "bearish", "bachatt", scores)
        _assert_same(expected, actual)

    @oracle_required
    def test_weights_match_on_eight_funds(self, oracle):
        df = _frame(
            303,
            mus=[0.0006, 0.0005, 0.0007, 0.0003, 0.0004, 0.0002, 0.0008, 0.0001],
            sds=[0.008, 0.010, 0.012, 0.009, 0.014, 0.0008, 0.016, 0.003],
            rows=200,
        )
        bounds = [(0.0, 0.4)] * 6 + [(0.1, 0.4), (0.0, 0.15)]
        scores = {f"F{i}": 0.25 + 0.07 * i for i in range(8)}
        expected, actual = _both(oracle, df, bounds, "aggressive", "neutral", "bachatt", scores)
        _assert_same(expected, actual)


# ─────────────────────────────────────────────────────────────────────────────
# Properties that hold whether or not their source is on this machine
# ─────────────────────────────────────────────────────────────────────────────

class TestBehaviour:
    def test_raw_weights_sum_to_one_and_respect_every_bound(self):
        df, bounds, scores = _six_fund_book()
        for strategy in STRATEGIES:
            for regime in REGIMES:
                w, ok, raw = port.optimize_portfolio(
                    df, list(bounds), strategy, regime, "bachatt", scores, return_raw=True
                )
                assert ok
                assert raw.sum() == pytest.approx(1.0, abs=1e-9)
                assert w.sum() == pytest.approx(1.0, abs=1e-9)
                for weight, (low, high) in zip(raw, bounds):
                    assert low - 1e-9 <= weight <= high + 1e-9, (strategy, regime, weight)

    def test_the_tactical_overlay_can_breach_a_bound_the_solver_respected(self):
        """Documented, not fixed: the overlay runs after the solve and nothing
        re-checks the caps, so the returned weights are not a mandate."""
        df, bounds, scores = _six_fund_book()
        w, _ok, raw = port.optimize_portfolio(
            df, list(bounds), "aggressive", "neutral", "bachatt", scores, return_raw=True
        )
        breaches = [
            (i, float(w[i]), high)
            for i, (_low, high) in enumerate(bounds)
            if w[i] > high + 1e-9
        ]
        assert breaches, (
            "if this ever goes green the overlay stopped breaching caps, which "
            "would be an improvement worth noticing rather than a passing test"
        )
        assert all(raw[i] <= high + 1e-9 for i, _w, high in breaches)

    @pytest.mark.parametrize(
        "strategy,regime,expected",
        [
            ("aggressive", "bullish", -0.015),
            ("aggressive", "bearish", -0.005),
            ("aggressive", "neutral", -0.010),
            ("balanced", "bullish", -0.0075),
            ("balanced", "bearish", -0.0025),
            ("balanced", "neutral", -0.005),
            ("conservative", "bullish", 0.0),
            ("conservative", "bearish", 0.0),
            ("conservative", "neutral", 0.0),
        ],
    )
    def test_the_regime_scales_the_loss_floor_the_right_way(self, strategy, regime, expected):
        """Bullish loosens the floor, bearish tightens it. Swapping the two is
        silent in the weights whenever the constraint is already violated, which
        is nearly always -- so it has to be pinned here."""
        assert port.loss_threshold(strategy, regime) == pytest.approx(expected, abs=1e-12)

    def test_strategy_and_regime_are_inert_while_the_penalty_is_violated(self):
        """A finding, pinned so it is not rediscovered.

        `violation = max(0, threshold - softmin)`. While that is positive the
        threshold is an additive constant in the objective, so its gradient is
        the same for every strategy and regime and the optimum does not move.
        With ~170 thirty-day windows the softmin sits about 0.10 below the true
        minimum whatever the portfolio does, so the constraint is essentially
        always violated and the strategy label changes nothing at all.
        """
        df, bounds, scores = _six_fund_book()
        weights = {
            (s, r): port.optimize_portfolio(
                df, list(bounds), s, r, "bachatt", scores, return_raw=True
            )[2]
            for s in STRATEGIES
            for r in REGIMES
        }
        base = weights[("aggressive", "bullish")]
        spread = max(float(np.abs(np.asarray(w) - base).max()) for w in weights.values())
        assert spread < 1e-9, "the loss floor started to bind; re-read this test"
        assert port.rolling_30d_min_return(df.values, base) < min(
            port.loss_threshold(s, r) for s in STRATEGIES for r in REGIMES
        )

    def test_the_loss_floor_does_move_the_answer_when_it_binds(self):
        """The other half: with the floor inside reach, the strategy matters."""
        df, bounds, scores = _regime_sensitive_book()
        weights = {
            (s, r): port.optimize_portfolio(
                df, list(bounds), s, r, "bachatt", scores, return_raw=True
            )[2]
            for s in STRATEGIES
            for r in REGIMES
        }
        base = weights[("aggressive", "bullish")]
        spread = max(float(np.abs(np.asarray(w) - base).max()) for w in weights.values())
        assert spread > 0.05

    def test_the_covariance_nudge_makes_a_singular_matrix_solvable(self):
        """Why the 1e-8 is there, and why dropping it is not cosmetic.

        A fund with a flat NAV -- an overnight fund, or a column filled by a
        backfill hole -- contributes an all-zero row and column to the sample
        covariance, which makes it singular. Whether a singular matrix comes back
        with a tiny positive or a tiny negative eigenvalue is up to the BLAS, and
        Accelerate on macOS and OpenBLAS on Linux do not have to agree.
        """
        df = _frame(9, mus=[0.0006, 0.0004, 0.0], sds=[0.009, 0.011, 0.0], rows=120)
        raw_cov = df.cov().values
        nudged = port.covariance(df)

        assert float(np.linalg.eigvalsh(raw_cov).min()) <= 0.0
        assert float(np.linalg.eigvalsh(nudged).min()) > 0.0
        np.testing.assert_allclose(
            np.diag(nudged) - np.diag(raw_cov),
            np.full(3, port.COVARIANCE_RIDGE),
            rtol=0, atol=1e-18,
        )
        np.testing.assert_allclose(
            nudged - np.eye(3) * port.COVARIANCE_RIDGE, raw_cov, rtol=0, atol=1e-18
        )

    def test_softmin_approximates_min_and_is_not_min(self):
        """Both halves matter: if it equalled `np.min` the alpha would be untested,
        and if it were far from it the constraint would be measuring nothing.
        """
        rnd = random.Random(3)
        series = np.array([rnd.gauss(0.0004, 0.010) for _ in range(200)])
        rolling = np.expm1(np.convolve(series, np.ones(30), mode="valid"))
        true_min = float(rolling.min())
        smooth = port.softmin(rolling)

        # Analytic: min - log(k)/alpha <= softmin <= min, for any alpha.
        gap = true_min - smooth
        assert 0 < gap <= math.log(len(rolling)) / port.SOFTMIN_ALPHA + 1e-12

        # Concrete, and this is what pins alpha=50: at alpha=5 the gap is ~0.94.
        assert gap < 0.10
        assert smooth != true_min
        assert port.softmin(rolling, alpha=5.0) < smooth < port.softmin(rolling, alpha=500.0)

    def test_softmin_converges_to_min_as_alpha_grows(self):
        values = np.array([-0.12, -0.05, 0.01, 0.04])
        # Above ~5900 `exp(-alpha * -0.12)` overflows, so this is as sharp as the
        # formula goes on real return magnitudes.
        assert port.softmin(values, alpha=2000.0) == pytest.approx(values.min(), abs=1e-3)

    def test_a_short_history_is_measured_as_one_window_repeated_not_skipped(self):
        """The dead guard, pinned.

        `np.convolve(x, ones(30), "valid")` slides the shorter array when x is
        shorter than the kernel, so 20 rows yield 11 windows that are all the
        same number: the whole 20-day record. The `len == 0` early return is
        unreachable, and the "30-day" loss constraint is measuring a 20-day one.
        """
        df = _frame(2, mus=[0.001, -0.002], sds=[0.01, 0.01], rows=20)
        weights = np.array([0.5, 0.5])
        windows = np.convolve(np.sum(df.values * weights, axis=1), np.ones(30), mode="valid")
        assert len(windows) == 11
        assert len(set(np.round(windows, 12))) == 1

        whole_history = float(np.expm1(windows[0]))
        got = port.rolling_30d_min_return(df.values, weights)
        assert got != 0.0
        assert got == pytest.approx(whole_history - math.log(11) / port.SOFTMIN_ALPHA, abs=1e-12)

    def test_score_normalisation_falls_back_to_mean_returns(self):
        means = np.array([0.001, -0.002, 0.003])
        out = port.normalised_scores(["A", "B", "C"], None, means)
        np.testing.assert_allclose(out, [0.6, 0.0, 1.0])
        np.testing.assert_allclose(
            port.normalised_scores(["A", "B", "C"], {}, means), out
        )

    def test_score_normalisation_is_uniform_when_every_score_is_equal(self):
        out = port.normalised_scores(["A", "B", "C", "D"], {c: 0.5 for c in "ABCD"},
                                     np.array([0.0, 0.0, 0.0, 0.0]))
        np.testing.assert_allclose(out, [0.25] * 4)

    def test_score_normalisation_gives_the_leader_one_and_the_laggard_zero(self):
        out = port.normalised_scores(["A", "B", "C"], {"A": 0.10, "B": 0.101, "C": 0.9},
                                     np.array([0.0, 0.0, 0.0]))
        np.testing.assert_allclose(out, [0.0, 0.00125, 1.0])

    def test_score_normalisation_reads_a_missing_code_as_zero(self):
        out = port.normalised_scores(["A", "B"], {"A": 0.8}, np.array([0.0, 0.0]))
        np.testing.assert_allclose(out, [1.0, 0.0])

    def test_feasible_bounds_rescales_only_when_it_has_to(self):
        ok = [(0.0, 0.4), (0.1, 0.4), (0.0, 0.4), (0.0, 0.15)]
        assert port.feasible_bounds(ok) == ok

        lowers_too_high = port.feasible_bounds([(0.3, 0.4)] * 4)
        assert sum(b[0] for b in lowers_too_high) == pytest.approx(0.999)

        uppers_too_low = port.feasible_bounds([(0.0, 0.15)] * 4)
        assert sum(b[1] for b in uppers_too_low) == pytest.approx(1.001)
        # And the caps the caller asked for are gone: 0.15 became 0.25.
        assert uppers_too_low[0][1] > 0.15

    def test_infeasible_bounds_return_weights_rather_than_raising(self):
        """Asserting what it does, not what it ought to do."""
        df, _, _ = _near_zero_variance_book()
        scores = {"F0": 0.62, "F1": 0.55, "F2": 0.48, "F3": 0.60}
        for bounds in ([(0.3, 0.4)] * 4, [(0.0, 0.15)] * 4):
            w, ok, raw = port.optimize_portfolio(
                df, list(bounds), "balanced", "neutral", "bachatt", scores, return_raw=True
            )
            assert np.isfinite(w).all()
            assert w.sum() == pytest.approx(1.0, abs=1e-9)
            assert ok is True
            # The original caps are breached, because they were rewritten first.
            assert max(raw) > bounds[0][1] or min(raw) < bounds[0][0]

    def test_a_single_fund_in_a_directional_regime_still_raises(self):
        """Their starting points divide by `n - 1`. Ported as written."""
        df = _frame(1, mus=[0.0005], sds=[0.01], rows=60)
        with pytest.raises(ZeroDivisionError):
            port.optimize_portfolio(df, [(0.0, 1.0)], "balanced", "bullish", "bachatt",
                                    {"F0": 0.5})

    def test_starting_points_are_reproducible(self):
        bounds = [(0.0, 0.4), (0.1, 0.4), (0.0, 0.15), (0.1, 0.4)]
        first = port.starting_points(bounds, "neutral")
        second = port.starting_points(bounds, "neutral")
        for a, b in zip(first, second):
            np.testing.assert_array_equal(a, b)
        assert all(w.sum() == pytest.approx(1.0) for w in first)


# ─────────────────────────────────────────────────────────────────────────────
# The candidate pool: our rule, not theirs
# ─────────────────────────────────────────────────────────────────────────────

def _pool_fund(code, category, sub_category=None, score=0.5, peer_size=20,
               nav_fresh=True, nav_rows=500) -> port.PoolFund:
    return port.PoolFund(
        code=code, category=category, sub_category=sub_category, score=score,
        peer_size=peer_size, nav_fresh=nav_fresh, nav_rows=nav_rows,
    )


class TestCandidatePool:
    def test_the_pool_ranks_by_score_and_cuts_to_the_limit(self):
        funds = [_pool_fund(f"C{i:03d}", "Debt Scheme", "Liquid Fund", score=i / 100)
                 for i in range(60)]
        pool = port.slot_pool("Debt Scheme::Liquid Fund", funds)
        assert len(pool) == port.SLOT_POOL_LIMIT
        assert [f.code for f in pool[:3]] == ["C059", "C058", "C057"]
        assert [f.score for f in pool] == sorted((f.score for f in pool), reverse=True)

    def test_ties_break_on_code_so_the_pool_is_deterministic(self):
        funds = [_pool_fund("ZZZ", "Debt Scheme", "Liquid Fund", score=0.7),
                 _pool_fund("AAA", "Debt Scheme", "Liquid Fund", score=0.7)]
        assert [f.code for f in port.slot_pool("Debt Scheme::Liquid Fund", funds)] == ["AAA", "ZZZ"]

    def test_a_thin_peer_group_is_excluded(self):
        """The floor the sabotage pass removes. A 'best of four' is not a ranking."""
        thin = _pool_fund("THIN", "Debt Scheme", "Liquid Fund", score=0.99, peer_size=7)
        fat = _pool_fund("FAT", "Debt Scheme", "Liquid Fund", score=0.10, peer_size=8)
        pool = port.slot_pool("Debt Scheme::Liquid Fund", [thin, fat])
        assert [f.code for f in pool] == ["FAT"], "the top scorer had 7 peers and must be out"
        ok, why = port.pool_eligibility(thin)
        assert not ok and "peer group of 7" in why

    def test_a_stale_nav_is_excluded(self):
        stale = _pool_fund("STALE", "Debt Scheme", "Liquid Fund", score=0.99, nav_fresh=False)
        assert port.slot_pool("Debt Scheme::Liquid Fund", [stale]) == []
        assert "wound up" in port.pool_eligibility(stale)[1]

    def test_too_little_history_is_excluded(self):
        short = _pool_fund("SHORT", "Debt Scheme", "Liquid Fund", score=0.99,
                           nav_rows=port.MIN_NAV_ROWS_FOR_POOL - 1)
        just = _pool_fund("JUST", "Debt Scheme", "Liquid Fund", score=0.10,
                          nav_rows=port.MIN_NAV_ROWS_FOR_POOL)
        assert [f.code for f in port.slot_pool("Debt Scheme::Liquid Fund", [short, just])] == ["JUST"]
        assert "209 NAVs" in port.pool_eligibility(short)[1]

    def test_a_bare_slot_key_accepts_every_sub_category_in_the_category(self):
        funds = [
            _pool_fund("A", "Debt Scheme", "Liquid Fund", score=0.4),
            _pool_fund("B", "Debt Scheme", "Overnight Fund", score=0.6),
            _pool_fund("C", "Equity Scheme", "Flexi Cap Fund", score=0.9),
        ]
        assert [f.code for f in port.slot_pool("Debt Scheme", funds)] == ["B", "A"]
        assert [f.code for f in port.slot_pool("Debt Scheme::Liquid Fund", funds)] == ["A"]

    def test_a_slot_whose_category_has_too_few_funds_comes_back_empty(self):
        """Every candidate in the category is individually ineligible, so the
        slot is empty rather than filled with whatever was left."""
        funds = [_pool_fund(f"S{i}", "Other Scheme", "Contra Fund", score=0.8, peer_size=4)
                 for i in range(4)]
        assert port.slot_pool("Other Scheme::Contra Fund", funds) == []

    def test_basket_slot_pools_names_every_slot_including_the_empty_ones(self):
        funds = [
            _pool_fund(f"L{i}", "Debt Scheme", "Liquid Fund", score=0.5 + i / 100)
            for i in range(3)
        ]
        pools = port.basket_slot_pools("BALANCED", funds)
        assert set(pools) == set(port.PORTFOLIO_BASKETS["BALANCED"]["slots"])
        assert [f.code for f in pools["Debt Scheme::Liquid Fund"]] == ["L2", "L1", "L0"]
        assert pools["Commodity::Gold"] == []
        assert port.basket_slot_pools("NOPE", funds) == {}
        assert port.basket_slot_pools("INSTA_FD", funds) == {}

    def test_bachatts_slot_keys_do_not_exist_in_traas_taxonomy(self):
        """Recorded so it is not rediscovered by accident.

        Upstream's slot keys are its own vocabulary -- `Commodity::Gold`,
        `Equity Index Fund`, `Flexi / Multi` -- and none of them is a traa
        category string. Matched literally against traa categories, every MAXX
        slot and two of BALANCED's four come back empty.

        **That is a naming mismatch, not a missing universe.** The funds all
        exist: 364 index funds, 246 sectoral, 44 flexi cap, 23 gold and 19
        silver. `basket_slots.py` is the one place that translates, and
        `test_basket_slots.py` asserts every slot resolves. An earlier version of
        this docstring concluded the funds were absent, which was wrong -- AMFI
        simply has no Commodity category, and gold and silver sit inside
        `Other Scheme - FoF Domestic` separated only by name.
        """
        sebi = ["Equity Scheme", "Debt Scheme", "Hybrid Scheme",
                "Other Scheme", "Solution Oriented Scheme"]
        subs = {
            "Equity Scheme": ["Flexi Cap Fund", "Large & Mid Cap Fund", "Sectoral/ Thematic"],
            "Debt Scheme": ["Liquid Fund", "Overnight Fund"],
            "Hybrid Scheme": ["Aggressive Hybrid Fund"],
            "Other Scheme": ["Index Funds", "FoF Domestic"],
            "Solution Oriented Scheme": ["Retirement Fund"],
        }
        funds = [
            _pool_fund(f"{c[:3]}{s[:3]}{i}", c, s, score=0.5 + i / 100)
            for c in sebi for s in subs[c] for i in range(10)
        ]

        maxx = port.basket_slot_pools("MAXX", funds)
        assert all(pool == [] for pool in maxx.values()), {
            k: len(v) for k, v in maxx.items()
        }

        balanced = port.basket_slot_pools("BALANCED", funds)
        filled = {k for k, v in balanced.items() if v}
        assert filled == {
            "Equity Scheme::Large & Mid Cap Fund",
            "Debt Scheme::Liquid Fund",
        }


# ─────────────────────────────────────────────────────────────────────────────
# The things we deliberately did not port
# ─────────────────────────────────────────────────────────────────────────────

def _identifiers(tree: ast.AST) -> set[str]:
    """Every name the module actually references, prose excluded.

    Text matching cannot tell a rejection from a use -- the docstring explains
    at length why the preferred-AMC swap is gone, and would trip a grep. The AST
    can tell them apart.
    """
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))

    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docstrings):
            # A string literal is data the module can act on, so it counts --
            # a dict key or a category name would slip past a check on Names
            # alone. Docstrings are prose and are excluded above.
            names.add(node.value)
    return names


def test_preferred_amc_logic_is_absent():
    """The one thing we most deliberately did not port."""
    src = MODULE_PATH.read_text()
    prose_free = (
        src.replace("`PREFERRED_AMCS`", "")
        .replace("`PREFERRED_AMC_SCORE_DELTA`", "")
    )
    assert "PREFERRED_AMC" not in prose_free
    assert not [n for n in _identifiers(ast.parse(src)) if "PREFERRED_AMC" in str(n)]


def test_the_minimum_investment_prefilter_is_absent():
    """Non-port number two: it reads a distributor feed traa does not have."""
    identifiers = _identifiers(ast.parse(MODULE_PATH.read_text()))
    for banned in ("PRE_FILTER_RATIO", "PREFILTER_MIN_BUCKETS",
                   "pre_filter_threshold_for", "min_lumpsum", "effective_min"):
        assert not [n for n in identifiers if banned in str(n)], banned


def test_the_module_docstring_says_the_pool_is_unfiltered_by_minimum_investment():
    """The disclosure is the mitigation, so it is a test, not a comment."""
    doc = port.__doc__ or ""
    assert "unfiltered by minimum investment" in doc


def test_the_fixed_isin_basket_round_trips_but_is_not_optimised():
    insta = port.get_basket("INSTA_FD")
    assert [row["isin"] for row in insta["fixed_isins"]] == ["INF846K01412", "INF209K01RU9"]
    assert sum(row["weight"] for row in insta["fixed_isins"]) == pytest.approx(1.0)
    assert insta["slots"] == {}
    assert port.basket_cat_composition("INSTA_FD") == []
