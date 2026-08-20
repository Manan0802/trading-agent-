"""Differential test: our stock port must return exactly what Bachatt returns.

Sibling of `test_scoring_parity.py`, same method for the same reason. Ten
weights, four benchmark medians, ten bonus/penalty magnitudes and five bucket
thresholds is far too much arithmetic to verify by reading it twice. So this
loads Bachatt's **actual** `services/stock_scorer.py`, executes their real
functions as an oracle, and asserts our module agrees to 1e-12 on randomised
and adversarial inputs.

Two things it catches that a hand-written fixture cannot:

1. **Transcription drift** -- an RSI Gaussian width typed 20 instead of 15, a
   `_clamp` whose default floor is 0 instead of -1.
2. **Their drift** -- if they retune a weight upstream, this goes red on the
   next run instead of six months later.

Price series here are built with stdlib `random.Random(seed)`, not
`numpy.random.Generator`. NumPy does not guarantee its stream across major
versions, and traa runs numpy 2 while the reference runs numpy 1; a numpy-seeded
fixture would make the fixture itself the variable under test.

The oracle needs their repo on disk. When it is absent the differential tests
skip and the behavioural tests below still run, so CI on another machine is
green without pretending it verified the port.
"""

import ast
import math
import random

import numpy as np
import pandas as pd
import pytest

from app.services.screener import reference
from app.services.screener import stock_scoring as port

STOCK_SCORER = "services/stock_scorer.py"

oracle_required = pytest.mark.skipif(
    not reference.available(),
    reason=f"reference checkout not present at {reference.root()}",
)

# Test fixtures, not ported data. The real table is built by
# `scripts/update_sector_benchmarks.py` from yfinance and NSE; see
# `SectorBenchmark` for what has to be in it and in which units.
BENCH = {"median_pe": 22.0, "median_pb": 3.5, "median_roe": 15.0, "median_div_yield": 1.0}
BENCH_RICH = {"median_pe": 53.4, "median_pb": 10.3, "median_roe": 35.0, "median_div_yield": 1.68}
BENCH_CHEAP = {"median_pe": 8.9, "median_pb": 1.14, "median_roe": 11.0, "median_div_yield": 1.88}
BENCHMARKS = [BENCH, BENCH_RICH, BENCH_CHEAP]


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
    """Bachatt's real stock-scoring functions, executed from their source.

    Their module imports `requests` and `yfinance` at the top and holds a
    module-level `threading.Lock`. Lifting only the nodes we name means none of
    that is executed and nothing here can reach the network.
    """
    ns: dict = {"np": np, "pd": pd, "logger": _StubLogger(), "__name__": "oracle"}
    _lift(
        STOCK_SCORER,
        {
            "_clamp",
            "_score_pe", "_score_eps_growth", "_score_roe", "_score_pb", "_score_div_yield",
            "_score_rsi", "_score_macd", "_score_ema_trend", "_score_delivery", "_score_support",
            "_compute_rsi", "_compute_macd", "_compute_ema", "_compute_support",
            "_check_profit_decay", "_check_dual_growth", "_check_promoter_holding",
            "_check_price_delivery_correlation",
            "WEIGHTS", "BP", "BUCKETS", "FACTOR_KEYS", "FACTOR_CATEGORIES",
        },
        ns,
    )
    return ns


def _price_series(seed: int, n: int = 300, start: float = 100.0) -> pd.Series:
    """Business-day closes on lognormal steps, from the stdlib RNG on purpose."""
    rng = random.Random(seed)
    px = start
    closes = []
    for _ in range(n):
        px *= math.exp(rng.gauss(0.0004, 0.012))
        closes.append(px)
    return pd.Series(closes, index=pd.bdate_range("2025-01-02", periods=n))


def _same(actual, expected):
    """Both functions return (score, detail). Compare the number tightly and
    the string exactly -- a detail line is what a user reads."""
    a_score, a_detail = actual
    e_score, e_detail = expected
    if isinstance(e_score, float) and math.isnan(e_score):
        assert math.isnan(a_score), f"{a_score} is not NaN, oracle gave NaN"
    else:
        assert a_score == pytest.approx(e_score, abs=1e-12), f"{a_score} != {e_score}"
    assert a_detail == e_detail


class TestAgainstReferenceSource:

    @oracle_required
    def test_the_weight_and_threshold_tables_are_theirs_verbatim(self, oracle):
        assert port.WEIGHTS == oracle["WEIGHTS"]
        assert port.BP == oracle["BP"]
        assert port.BUCKETS == oracle["BUCKETS"]
        assert port.FACTOR_KEYS == oracle["FACTOR_KEYS"]
        assert port.FACTOR_CATEGORIES == oracle["FACTOR_CATEGORIES"]

    @oracle_required
    def test_clamp_matches_including_its_negative_default_floor(self, oracle):
        for x in [-1e9, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 1e9]:
            assert port._clamp(x) == oracle["_clamp"](x)
            assert port._clamp(x, 0, 1) == oracle["_clamp"](x, 0, 1)
            assert port._clamp(x, -0.2, 0.2) == oracle["_clamp"](x, -0.2, 0.2)

    @oracle_required
    @pytest.mark.parametrize("bench", BENCHMARKS)
    def test_pe_scoring_matches_over_a_sweep_and_at_every_boundary(self, oracle, bench):
        m = bench["median_pe"]
        rng = random.Random(11)
        cases = [None, 0.0, -5.0, -0.0001, 0.0001, m / 2, m, 2 * m, 10 * m, 1e6]
        cases += [rng.uniform(-50, 400) for _ in range(200)]
        for pe in cases:
            _same(port._score_pe(pe, port.WEIGHTS["pe"], bench),
                  oracle["_score_pe"](pe, oracle["WEIGHTS"]["pe"], bench))

    @oracle_required
    def test_eps_growth_scoring_matches_including_growth_measured_off_a_loss(self, oracle):
        w = port.WEIGHTS["eps_growth"]
        rng = random.Random(23)
        cases = [
            (None, None), (5.0, None), (None, 5.0), (5.0, 0.0), (0.0, 5.0),
            (5.0, -10.0),        # "+150%" that is really a return to profit
            (-10.0, -5.0), (-5.0, -10.0),
            (10.0, 5.0), (0.0, 10.0), (20.0, 10.0), (5.0, 10.0),
            (0.0, 0.0), (1e-9, 1e-9),
        ]
        cases += [(rng.uniform(-80, 80), rng.uniform(-80, 80)) for _ in range(200)]
        for ttm, prev in cases:
            _same(port._score_eps_growth(ttm, prev, w),
                  oracle["_score_eps_growth"](ttm, prev, oracle["WEIGHTS"]["eps_growth"]))

    @oracle_required
    @pytest.mark.parametrize("bench", BENCHMARKS)
    def test_roe_scoring_matches_including_the_negative_scores_it_can_produce(self, oracle, bench):
        w = port.WEIGHTS["roe"]
        m = bench["median_roe"]
        rng = random.Random(42)
        cases = [None, 0.0, -0.30, m / 100, 2 * m / 100, -2 * m / 100, 10 * m / 100, -10.0, 10.0]
        cases += [rng.uniform(-2.0, 3.0) for _ in range(200)]
        for roe in cases:
            _same(port._score_roe(roe, w, bench),
                  oracle["_score_roe"](roe, oracle["WEIGHTS"]["roe"], bench))

    @oracle_required
    @pytest.mark.parametrize("bench", BENCHMARKS)
    def test_pb_scoring_matches_over_a_sweep_and_at_every_boundary(self, oracle, bench):
        w = port.WEIGHTS["pb"]
        m = bench["median_pb"]
        rng = random.Random(1234)
        cases = [None, 0.0, -3.0, 1e-9, m / 2, m, 2 * m, 10 * m, 1e6]
        cases += [rng.uniform(-5, 60) for _ in range(200)]
        for pb in cases:
            _same(port._score_pb(pb, w, bench),
                  oracle["_score_pb"](pb, oracle["WEIGHTS"]["pb"], bench))

    @oracle_required
    @pytest.mark.parametrize("bench", BENCHMARKS)
    def test_div_yield_scoring_matches_including_the_haircut_above_eight_percent(self, oracle, bench):
        w = port.WEIGHTS["div_yield"]
        m = bench["median_div_yield"]
        target = max(m * 2, 1.5)
        rng = random.Random(99999)
        cases = [None, 0.0, -1.0, m, target, 2 * m, 10 * m,
                 7.9999, 8.0, 8.0001, 9.0, 13.0, 100.0]
        cases += [rng.uniform(0, 20) for _ in range(200)]
        for dy in cases:
            _same(port._score_div_yield(dy, w, bench),
                  oracle["_score_div_yield"](dy, oracle["WEIGHTS"]["div_yield"], bench))

    @oracle_required
    def test_rsi_scoring_matches_across_the_whole_zero_to_hundred_range(self, oracle):
        w = port.WEIGHTS["rsi"]
        rng = random.Random(7)
        cases = [None, 0.0, 29.999, 30.0, 50.0, 70.0, 70.001, 100.0, -10.0, 150.0]
        cases += [rng.uniform(0, 100) for _ in range(300)]
        for rsi in cases:
            _same(port._score_rsi(rsi, w), oracle["_score_rsi"](rsi, oracle["WEIGHTS"]["rsi"]))

    @oracle_required
    def test_macd_scoring_matches_including_a_macd_line_sitting_on_zero(self, oracle):
        w = port.WEIGHTS["macd"]
        rng = random.Random(555)
        cases = [(None, None), (1.0, None), (None, 1.0),
                 (0.0, 0.0), (0.0, 1.0), (0.0, -1.0), (1e-12, 1.0),
                 (2.0, 1.0), (1.0, 2.0), (-2.0, -1.0), (-1.0, -2.0)]
        cases += [(rng.uniform(-50, 50), rng.uniform(-50, 50)) for _ in range(200)]
        for macd_val, sig in cases:
            _same(port._score_macd(macd_val, sig, w),
                  oracle["_score_macd"](macd_val, sig, oracle["WEIGHTS"]["macd"]))

    @oracle_required
    def test_ema_trend_scoring_matches_for_golden_cross_death_cross_and_no_ema50(self, oracle):
        w = port.WEIGHTS["ema_trend"]
        rng = random.Random(64)
        cases = [
            (None, None, None), (100.0, 95.0, None), (None, 95.0, 90.0),
            (100.0, None, 90.0),        # fewer than 50 closes: no bonus, no label
            (100.0, 95.0, 90.0),        # golden cross
            (100.0, 85.0, 90.0),        # death cross
            (100.0, 90.0, 90.0),        # a tie, which they call a death cross
            (100.0, 95.0, 100.0),       # exactly on the 200-day EMA
            (80.0, 70.0, 100.0),        # -20%, the clamp floor
            (120.0, 130.0, 100.0),      # +20%, the clamp ceiling, with the bonus capped
            (1000.0, 130.0, 100.0),     # far past the ceiling
        ]
        cases += [(rng.uniform(10, 500), rng.uniform(10, 500), rng.uniform(10, 500))
                  for _ in range(200)]
        for price, ema50, ema200 in cases:
            _same(port._score_ema_trend(price, ema50, ema200, w),
                  oracle["_score_ema_trend"](price, ema50, ema200, oracle["WEIGHTS"]["ema_trend"]))

    @oracle_required
    def test_delivery_scoring_matches_including_the_neutral_it_always_takes(self, oracle):
        w = port.WEIGHTS["delivery"]
        rng = random.Random(808)
        cases = [None, 0.0, -5.0, 40.0, 65.0, 80.0, 100.0]
        cases += [rng.uniform(0, 100) for _ in range(200)]
        for d in cases:
            _same(port._score_delivery(d, w), oracle["_score_delivery"](d, oracle["WEIGHTS"]["delivery"]))

    @oracle_required
    def test_support_scoring_matches_including_a_price_below_its_support(self, oracle):
        w = port.WEIGHTS["support"]
        rng = random.Random(2026)
        cases = [(None, None), (100.0, None), (None, 50.0), (0.0, 50.0),
                 (100.0, 100.0), (100.0, 80.0), (100.0, 40.0), (40.0, 50.0), (-100.0, 50.0)]
        cases += [(rng.uniform(1, 500), rng.uniform(1, 500)) for _ in range(200)]
        for price, support in cases:
            _same(port._score_support(price, support, w),
                  oracle["_score_support"](price, support, oracle["WEIGHTS"]["support"]))

    @oracle_required
    @pytest.mark.parametrize("seed", [1, 7, 42, 1234, 99999])
    def test_the_four_indicators_match_on_a_real_shaped_price_series(self, oracle, seed):
        close = _price_series(seed, n=300)
        assert port._compute_rsi(close) == pytest.approx(oracle["_compute_rsi"](close), abs=1e-12)
        p_macd, p_sig = port._compute_macd(close)
        o_macd, o_sig = oracle["_compute_macd"](close)
        assert p_macd == pytest.approx(o_macd, abs=1e-12)
        assert p_sig == pytest.approx(o_sig, abs=1e-12)
        for span in (12, 26, 50, 200):
            assert port._compute_ema(close, span) == pytest.approx(
                oracle["_compute_ema"](close, span), abs=1e-12)
        assert port._compute_support(close) == pytest.approx(
            oracle["_compute_support"](close), abs=1e-12)

    @oracle_required
    @pytest.mark.parametrize("n", [1, 2, 5, 13, 14, 15, 21, 25, 26, 49, 50, 90, 199, 200])
    def test_the_indicators_match_on_series_shorter_than_their_own_windows(self, oracle, n):
        """Short series must never raise, and must agree with the oracle -- NaN
        included, because on RSI the oracle's answer is NaN."""
        close = _price_series(3, n=n)
        p_rsi, o_rsi = port._compute_rsi(close), oracle["_compute_rsi"](close)
        if math.isnan(o_rsi):
            assert math.isnan(p_rsi)
        else:
            assert p_rsi == pytest.approx(o_rsi, abs=1e-12)
        assert port._compute_macd(close) == pytest.approx(oracle["_compute_macd"](close), abs=1e-12)
        assert port._compute_ema(close, 200) == pytest.approx(
            oracle["_compute_ema"](close, 200), abs=1e-12)
        assert port._compute_support(close) == pytest.approx(
            oracle["_compute_support"](close), abs=1e-12)

    @oracle_required
    def test_profit_decay_matches_including_the_gaps_it_treats_as_consecutive(self, oracle):
        def q(*profits):
            return {"quarterly": [{"profit": p} for p in profits]}
        cases = [
            {}, {"quarterly": []}, q(10.0), q(10.0, 8.0),
            q(10.0, 8.0, 6.0),                       # the penalty
            q(10.0, 8.0, 8.0),                       # a flat quarter is not a decline
            q(6.0, 8.0, 10.0),
            q(10.0, None, 8.0, None, 6.0),           # gaps closed up by the None filter
            q(-5.0, -8.0, -12.0),                    # losses deepening
            q(10.0, -2.0, -20.0),
            {"quarterly": [{"revenue": 1.0}, {"revenue": 2.0}, {"revenue": 3.0}]},
        ]
        for fin in cases:
            assert port._check_profit_decay(fin) == oracle["_check_profit_decay"](fin)

    @oracle_required
    def test_dual_growth_matches_at_every_tier_boundary(self, oracle):
        def rows(*pairs):
            return [{"revenue": r, "profit": p} for r, p in pairs]
        cases = [
            {}, {"annual": []}, {"annual": rows((100.0, 10.0))},
            {"annual": rows((100.0, 10.0), (114.9, 20.0))},     # just under 15
            {"annual": rows((100.0, 10.0), (115.0, 20.0))},     # exactly 15
            {"annual": rows((100.0, 10.0), (130.0, 13.0))},     # exactly 30
            {"annual": rows((100.0, 10.0), (150.0, 15.0))},     # exactly 50
            {"annual": rows((100.0, 10.0), (300.0, 11.0))},     # profit is the binding leg
            {"annual": rows((100.0, -10.0), (150.0, 5.0))},     # growth off a loss
            {"annual": rows((0.0, 10.0), (150.0, 15.0))},       # zero base, skipped
            {"annual": rows((100.0, 10.0), (None, 15.0))},
            {"quarterly": rows((100.0, 10.0), (120.0, 14.0))},  # the zero-point info row
            {"annual": rows((100.0, 10.0), (150.0, 15.0)),
             "quarterly": rows((50.0, 5.0), (40.0, 3.0))},
        ]
        for fin in cases:
            assert port._check_dual_growth(fin) == oracle["_check_dual_growth"](fin)

    @oracle_required
    def test_promoter_holding_matches_including_the_insider_fallback(self, oracle):
        cases = [
            (None, None), (None, 0.62), (None, 0.05),
            ({"latest": 74.0, "history": [74.0, 74.0]}, None),
            ({"latest": 50.0, "history": [50.0, 50.0]}, None),      # exactly 50: not "very healthy"
            ({"latest": 40.0, "history": [40.0, 40.0]}, None),      # exactly 40: "moderate"
            ({"latest": 20.0, "history": []}, None),                # exactly 20: "moderate"
            ({"latest": 19.9, "history": []}, None),
            ({"latest": 0.0, "history": []}, None),
            ({"latest": 45.0, "history": [50.0, 48.0, 47.0, 45.0]}, None),   # -5pp, selling
            ({"latest": 45.0, "history": [43.0, 45.0]}, None),               # +2pp exactly
            ({"latest": 45.0, "history": [47.0, 45.0]}, None),               # -2pp exactly
            ({"latest": 45.0, "history": [44.0, 45.0]}, None),               # under the bar
            ({"latest": 45.0, "history": [45.0]}, None),                     # one quarter, no change
        ]
        for promoter, insider in cases:
            assert port._check_promoter_holding(promoter, insider) == \
                oracle["_check_promoter_holding"](promoter, insider)

    @oracle_required
    def test_price_delivery_correlation_matches_in_all_four_quadrants(self, oracle):
        rising = pd.Series([100.0] * 5 + [100.0 + i for i in range(21)])
        falling = pd.Series([100.0] * 5 + [100.0 - i for i in range(21)])
        flat = pd.Series([100.0] * 26)
        short = pd.Series([100.0] * 24)
        for close in (rising, falling, flat, short):
            for delivery in (None, 0.0, 39.9, 40.0, 64.9, 65.0, 90.0):
                assert port._check_price_delivery_correlation(close, delivery) == \
                    oracle["_check_price_delivery_correlation"](close, delivery)

    @oracle_required
    @pytest.mark.parametrize("seed", [5, 88, 777])
    def test_every_factor_in_the_composition_is_wired_to_the_right_function(self, oracle, seed):
        """Catches a mis-wiring the per-function tests cannot: the pe weight
        handed to the pb function, or ema50 and ema200 swapped."""
        rng = random.Random(seed)
        close = _price_series(seed, n=300)
        fundamentals = {
            "trailing_pe": rng.uniform(5, 90), "price_to_book": rng.uniform(0.3, 20),
            "roe": rng.uniform(-0.2, 0.6), "div_yield": rng.uniform(0, 12),
            "eps_ttm": rng.uniform(-20, 90), "eps_prev": rng.uniform(-20, 90),
            "current_price": float(close.iloc[-1]),
            "name": "Test Co", "sector": "Technology", "industry": "IT Services",
            "insider_pct": None,
        }
        result = port.score_stock(fundamentals, close, BENCH)
        scores = {f["key"]: f["score"] for f in result["factors"]}

        w = oracle["WEIGHTS"]
        rsi = oracle["_compute_rsi"](close)
        macd_val, sig = oracle["_compute_macd"](close)
        expected = {
            "pe": oracle["_score_pe"](fundamentals["trailing_pe"], w["pe"], BENCH)[0],
            "eps_growth": oracle["_score_eps_growth"](
                fundamentals["eps_ttm"], fundamentals["eps_prev"], w["eps_growth"])[0],
            "roe": oracle["_score_roe"](fundamentals["roe"], w["roe"], BENCH)[0],
            "pb": oracle["_score_pb"](fundamentals["price_to_book"], w["pb"], BENCH)[0],
            "div_yield": oracle["_score_div_yield"](
                fundamentals["div_yield"], w["div_yield"], BENCH)[0],
            "rsi": oracle["_score_rsi"](rsi, w["rsi"])[0],
            "macd": oracle["_score_macd"](macd_val, sig, w["macd"])[0],
            "ema_trend": oracle["_score_ema_trend"](
                fundamentals["current_price"], oracle["_compute_ema"](close, 50),
                oracle["_compute_ema"](close, 200), w["ema_trend"])[0],
            "delivery": oracle["_score_delivery"](None, w["delivery"])[0],
            "support": oracle["_score_support"](
                fundamentals["current_price"], oracle["_compute_support"](close), w["support"])[0],
        }
        for key, value in expected.items():
            assert scores[key] == pytest.approx(round(value, 2), abs=1e-12), key
        assert result["base_total"] == pytest.approx(round(sum(expected.values()), 2), abs=1e-12)


class TestBehaviour:
    """Properties that must hold whether or not their source is on this machine."""

    def test_the_ten_weights_still_sum_to_one_hundred(self):
        assert sum(port.WEIGHTS.values()) == 100
        assert set(port.WEIGHTS) == {k for _, k in port.FACTOR_KEYS}
        assert set(port.WEIGHTS) == set(port.FACTOR_CATEGORIES)

    def test_half_the_hundred_points_are_chart_reading(self):
        """The disclosure has to have numbers behind it, so they are asserted."""
        technical = sum(w for k, w in port.WEIGHTS.items()
                        if port.FACTOR_CATEGORIES[k] == "technical")
        assert technical == 50
        oscillators = sum(port.WEIGHTS[k] for k in ("rsi", "macd", "ema_trend", "support"))
        assert oscillators == 41

    def test_bucket_boundaries_land_on_exactly_eighty_sixty_forty_twenty(self):
        def bucket(total):
            return next(lbl for t, lbl in port.BUCKETS if total >= t)
        assert bucket(80.0) == "Strong Buy"
        assert bucket(79.999) == "Buy"
        assert bucket(60.0) == "Buy"
        assert bucket(59.999) == "Hold"
        assert bucket(40.0) == "Hold"
        assert bucket(39.999) == "Weak / Avoid"
        assert bucket(20.0) == "Weak / Avoid"
        assert bucket(19.999) == "Bearish"
        assert bucket(0.0) == "Bearish"

    def test_a_stock_with_nothing_fetched_at_all_scores_47_5_and_reads_as_hold(self):
        """This is the number every un-fetchable stock silently receives.

        Not an error, not a blank -- a "Hold", above the 40 boundary, printed
        with the same confidence as a score built from real data. 7.5 + 6 + 5 +
        4 + 0 + 6 + 6 + 5 + 4.5 + 3.5. Anything that changes it changes what a
        user is told about a company we know nothing about.
        """
        empty = {"name": "Unknown", "sector": None, "industry": None}
        result = port.score_stock(empty, pd.Series([100.0]), BENCH)
        assert result["total"] == pytest.approx(47.5, abs=1e-12)
        assert result["bucket"] == "Hold"
        assert result["fundamental"] == pytest.approx(22.5, abs=1e-12)
        assert result["technical"] == pytest.approx(25.0, abs=1e-12)

    def test_delivery_is_always_neutral_because_its_source_is_dead(self):
        """NSE's `quote-equity?section=trade_info` returns 403 -- checked again
        on 20 Aug 2026, for us and for them. Their fetcher catches the exception
        and returns None, so this branch is not an edge case: it is the value
        the delivery factor takes for every stock on every run. Nine points of
        every hundred are a constant, and upstream's UI shows it as a scored
        factor at 50% rather than saying so.
        """
        weight = port.WEIGHTS["delivery"]
        score, detail = port._score_delivery(None, weight)
        assert score == weight * 0.5 == 4.5
        assert detail == "Market closed / data unavailable"

    def test_missing_data_scores_half_marks_everywhere_except_dividend_yield(self):
        """The asymmetry is deliberate upstream and worth keeping visible.

        Nine factors read an absent input as "we do not know" and pay half. The
        tenth reads it as "there is no dividend" and pays nothing -- which is
        right when yfinance omits the field because none is paid, and wrong when
        the fetch simply failed. Five points hang on which of those it was.
        """
        w = port.WEIGHTS
        assert port._score_pe(None, w["pe"], BENCH)[0] == w["pe"] * 0.5
        assert port._score_eps_growth(None, None, w["eps_growth"])[0] == w["eps_growth"] * 0.5
        assert port._score_roe(None, w["roe"], BENCH)[0] == w["roe"] * 0.5
        assert port._score_pb(None, w["pb"], BENCH)[0] == w["pb"] * 0.5
        assert port._score_rsi(None, w["rsi"])[0] == w["rsi"] * 0.5
        assert port._score_macd(None, None, w["macd"])[0] == w["macd"] * 0.5
        assert port._score_ema_trend(None, None, None, w["ema_trend"])[0] == w["ema_trend"] * 0.5
        assert port._score_delivery(None, w["delivery"])[0] == w["delivery"] * 0.5
        assert port._score_support(None, None, w["support"])[0] == w["support"] * 0.5

        assert port._score_div_yield(None, w["div_yield"], BENCH) == (0.0, "No dividend")

    def test_a_high_dividend_yield_is_haircut_by_thirty_percent(self):
        """A double-digit yield in India is usually a collapsed price. Above 8%
        the factor keeps 0.7 of what it earned -- strictly above, so 8.00 does
        not lose it."""
        w = port.WEIGHTS["div_yield"]
        at_eight = port._score_div_yield(8.0, w, BENCH)[0]
        just_over = port._score_div_yield(8.0001, w, BENCH)[0]
        assert at_eight == pytest.approx(w, abs=1e-12)
        assert just_over == pytest.approx(w * 0.7, abs=1e-12)

    def test_the_rsi_curve_peaks_at_fifty_with_a_width_of_fifteen(self):
        """Added after the sabotage pass, which found this unguarded.

        Retyping the Gaussian width as 20 was caught only by the differential
        tests -- so on a machine without the reference checkout it would have
        shipped green. The width is what decides how fast a stock loses its 12
        points for trending, so it gets pinned without the oracle: one standard
        deviation is exactly 15 RSI points.
        """
        w = port.WEIGHTS["rsi"]
        assert port._score_rsi(50.0, w)[0] == pytest.approx(w, abs=1e-12)
        assert port._score_rsi(65.0, w)[0] == pytest.approx(w * math.exp(-0.5), abs=1e-12)
        assert port._score_rsi(35.0, w)[0] == pytest.approx(w * math.exp(-0.5), abs=1e-12)
        assert port._score_rsi(80.0, w)[0] == pytest.approx(w * math.exp(-2.0), abs=1e-12)

    def test_only_return_on_equity_can_push_a_factor_below_zero(self):
        """`_clamp`'s default floor is -1 and `_score_roe` uses the result
        directly, so a loss-making company loses 10 points on a 10-point factor.
        Every other factor is bounded to [0, weight]. If this ever stops being
        true, the -1 default has been changed and `_score_pe` moved with it.
        """
        w = port.WEIGHTS
        assert port._score_roe(-0.30, w["roe"], BENCH)[0] == pytest.approx(-10.0, abs=1e-12)
        assert port._score_pe(1e6, w["pe"], BENCH)[0] == pytest.approx(0.0, abs=1e-12)
        assert port._score_pb(1e6, w["pb"], BENCH)[0] == pytest.approx(0.0, abs=1e-12)
        assert port._score_support(40.0, 50.0, w["support"])[0] == pytest.approx(0.0, abs=1e-12)
        assert port._score_delivery(-5.0, w["delivery"])[0] == pytest.approx(0.0, abs=1e-12)

    def test_earnings_growth_measured_off_a_loss_takes_full_marks(self):
        """-10 to +5 is a return to profit, not 150% growth, and the denominator
        is `abs(eps_prev)` so the scorer cannot tell. traa's own stock scorer
        refuses this calculation and says so in words; this one pays out the
        whole twelve points. Recorded, not fixed -- fixing it would break parity.
        """
        w = port.WEIGHTS["eps_growth"]
        score, detail = port._score_eps_growth(5.0, -10.0, w)
        assert score == pytest.approx(w, abs=1e-12)
        assert "+150.0%" in detail

    def test_a_company_with_fourteen_days_of_history_scores_a_perfect_hundred(self):
        """The worst thing found in the port, and it is arithmetic, not opinion.

        `_compute_rsi` needs 14 non-null deltas, which needs 15 closes. Their
        `score_stock` guards with `len(close) >= 14` -- one short. At exactly 14
        closes RSI is NaN, `_score_rsi` carries it through `np.exp`, and
        `base_total` is NaN.

        Then the display clamp: `max(0.0, min(100.0, nan))`. Python's `min`
        returns 100.0, because `nan < 100.0` is False. The NaN does not surface
        as missing data or as an error -- it surfaces as **100.0, "Strong Buy"**,
        the highest score the model can award, on a company about which it has
        computed nothing. Newly listed companies are exactly the ones holding 14
        days of history.

        Pinned here rather than fixed: the port's job is parity, and a screen
        that ranks on `total` without checking for this is the thing that has to
        change.
        """
        assert math.isnan(port._compute_rsi(_price_series(3, n=14)))
        assert not math.isnan(port._compute_rsi(_price_series(3, n=15)))

        fundamentals = {"name": "Freshly Listed", "current_price": 100.0}
        result = port.score_stock(fundamentals, _price_series(3, n=14), BENCH)
        assert math.isnan(result["base_total"])
        assert result["total"] == 100.0
        assert result["bucket"] == "Strong Buy"

        fifteen = port.score_stock(fundamentals, _price_series(3, n=15), BENCH)
        assert not math.isnan(fifteen["base_total"])
        assert fifteen["total"] < 100.0

    def test_macd_ema_and_support_return_real_numbers_below_their_windows(self):
        """Only RSI degrades to NaN. The other three answer at any length --
        which is its own problem, since a 5-day 200-day EMA is a number with no
        meaning, but it is a number and it does not poison the total."""
        for n in (1, 2, 5, 13, 25, 49, 199):
            close = _price_series(3, n=n)
            macd_val, sig = port._compute_macd(close)
            assert math.isfinite(macd_val) and math.isfinite(sig)
            assert math.isfinite(port._compute_ema(close, 200))
            assert math.isfinite(port._compute_support(close))

    def test_an_unknown_sector_silently_falls_back_to_the_default_benchmark(self):
        """No field in the output says it happened, which is why traa's own
        scorer returns `benchmark_used` and this one does not."""
        table = {"Technology": BENCH_RICH}
        assert port.resolve_benchmark("Technology", table, BENCH) is BENCH_RICH
        assert port.resolve_benchmark(None, table, BENCH) is BENCH
        assert port.resolve_benchmark("Fintech", table, BENCH) is BENCH

    def test_price_history_can_arrive_as_pairs_or_as_a_series(self):
        series = _price_series(9, n=60)
        pairs = list(zip(series.index, series.to_numpy()))
        assert port.to_close_series(pairs).to_numpy() == pytest.approx(
            port.to_close_series(series).to_numpy(), abs=1e-12)

    def test_nulls_are_dropped_before_the_length_guards_are_applied(self):
        """`len(close)` after the dropna is what every indicator guard tests, so
        a series with holes in it can fall below a window it looks long enough
        for."""
        holed = pd.Series([100.0, np.nan, 101.0, np.nan, 102.0])
        assert len(port.to_close_series(holed)) == 3

    def test_the_module_imports_nothing_that_can_reach_the_world(self):
        """No network, no database, no clock -- the whole reason this port can
        be differentially tested and theirs cannot.

        Checked on the import graph, not on the text. The first version of this
        matched strings and flagged the module's own docstring for the word
        "yfinance", which is exactly the lesson
        `test_reference_repo_is_read_only.py` already wrote down: source read as
        text cannot tell a promise from a call.
        """
        import ast
        import inspect

        impure = {"requests", "yfinance", "yf", "urllib", "http", "httpx", "socket",
                  "datetime", "time", "sqlalchemy", "app.database", "os", "pathlib"}
        tree = ast.parse(inspect.getsource(port))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        offenders = sorted(imported & impure)
        assert not offenders, f"a pure module imported {offenders}"
