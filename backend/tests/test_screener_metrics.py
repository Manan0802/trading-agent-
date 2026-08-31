"""Differential test: the metrics engine must return exactly what the reference does.

`scoring.py` was proved this way and it caught real drift. The metrics layer is
the larger transcription -- five trailing windows, five rolling windows, a
non-standard sortino, a calendar-exact prefix-sum kernel and three separate
annualisation rules -- so it gets the same treatment: their **actual source**,
AST-lifted and executed as an oracle, held against our port to 1e-12 on
adversarial series.

What this catches that a hand-written fixture cannot:

1. Transcription drift -- `side='left'` for `side='right'`, `ddof=0` for
   `ddof=1`, `1/annualize_years` for `365.25/annualize_days`. All three produce
   plausible numbers and all three move every rank in the product.
2. Their drift -- if upstream changes a definition, this goes red on the next
   run instead of six months later.

The oracle needs their repo on disk. Absent it the differential tests skip and
the behavioural tests still run, so a machine without a checkout is green
without pretending it verified anything.
"""

import ast
import math
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.screener import metrics as port
from app.services.screener import reference

AS_OF = date.today()

# Every seeded series ends HERE, derived from AS_OF rather than written down.
#
# It used to be a literal `LAST_NAV` while `AS_OF` followed the wall
# clock. That works until the gap crosses the screener's freshness rule, and
# then a batch of tests fails on a day nobody changed anything — reporting
# `pool_size=0` as though the slot mapping had broken.
LAST_NAV = AS_OF - timedelta(days=1)


PERFORMANCE = "services/performance.py"
HELPERS = "utils/helpers.py"

oracle_required = pytest.mark.skipif(
    not reference.available(),
    reason=f"reference checkout not present at {reference.root()}",
)


def _lift(rel_path: str, names: set[str], into: dict) -> dict:
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
    ns: dict = {"np": np, "pd": pd, "logger": _StubLogger(), "__name__": "oracle"}
    _lift(HELPERS, {"nav_to_log_returns"}, ns)
    _lift(
        PERFORMANCE,
        {
            "calculate_performance_metrics",
            "_cap_log_returns_for_metrics",
            "_MAX_DAILY_SIMPLE_FOR_METRICS",
            "DEFAULT_RISK_FREE_RATE",
        },
        ns,
    )
    ns.setdefault("DEFAULT_RISK_FREE_RATE", 0.04)
    return ns


# ------------------------------------------------------------------ series

AS_OF = date(2026, 8, 20)


def series(
    start: date,
    n_business_days: int,
    seed: int = 1,
    drift: float = 0.0004,
    sigma: float = 0.009,
    first: float = 100.0,
) -> list[tuple[date, float]]:
    """A NAV series shaped like a real one: business days only, lognormal steps."""
    rng = random.Random(seed)
    out: list[tuple[date, float]] = []
    value, day = first, start
    while len(out) < n_business_days:
        if day.weekday() < 5:
            value *= math.exp(rng.gauss(drift, sigma))
            out.append((day, round(value, 4)))
        day += timedelta(days=1)
    return out


# The port's field name -> the oracle's dict key. Where they differ it is
# because the oracle's name is actively misleading (see metrics.FundMetrics).
FIELD_MAP = {
    "annualized_return": "annualized_return",
    "returns_1m": "returns_1m",
    "returns_3m": "returns_3m",
    "returns_6m": "returns_6m",
    "returns_1y": "returns_1y",
    "returns_3y": "returns_3y",
    "rolling_1m": "rolling_ret_1m",
    "rolling_3m": "rolling_ret_3m",
    "rolling_6m": "rolling_ret_6m",
    "rolling_1y": "rolling_ret_1y",
    "rolling_3y": "rolling_ret_3y",
    "volatility": "volatility",
    "sharpe": "sharpe_ratio",
    "sortino": "sortino_ratio",
    "max_drawdown": "max_drawdown",
    "best_30d": "best_30d_return",
    "worst_30d": "worst_30d_return",
    "negative_days_pct": "negative_days_pct",
}


def assert_matches_oracle(oracle, navs, label: str, tol: float = 1e-12):
    log_ret = oracle["nav_to_log_returns"](
        pd.Series(
            [n for _, n in navs],
            index=pd.DatetimeIndex([pd.Timestamp(d) for d, _ in navs]),
        )
    )
    theirs = oracle["calculate_performance_metrics"](log_ret)
    ours = port.compute(navs, AS_OF)
    for mine, key in FIELD_MAP.items():
        a, b = getattr(ours, mine), theirs[key]
        assert a == pytest.approx(b, abs=tol, rel=tol), (
            f"{label}: {mine} -> ours {a!r} vs reference {b!r}"
        )


# ------------------------------------------------------------------ parity


@oracle_required
@pytest.mark.parametrize(
    "label,navs",
    [
        ("thirteen years of business days", series(date(2013, 1, 1), 3300, seed=1)),
        ("a four-year window", series(date(2022, 8, 22), 1000, seed=2)),
        ("four hundred rows", series(date(2024, 1, 1), 400, seed=3)),
        ("twenty five rows", series(date(2026, 7, 1), 25, seed=4)),
        ("exactly thirty rows", series(date(2026, 7, 1), 30, seed=5)),
        ("exactly twenty nine rows", series(date(2026, 7, 1), 29, seed=6)),
        ("exactly twenty two navs", series(date(2026, 7, 1), 22, seed=7)),
        ("a high volatility fund", series(date(2020, 1, 1), 1200, seed=9, sigma=0.035)),
        ("a falling fund", series(date(2020, 1, 1), 1200, seed=10, drift=-0.0008)),
    ],
)
def test_every_metric_equals_the_reference(oracle, label, navs):
    assert_matches_oracle(oracle, navs, label)


@oracle_required
def test_the_reference_crashes_on_a_two_nav_fund_and_we_do_not(oracle):
    """The module's one deliberate divergence, proved rather than asserted.

    Two NAVs is one log return, which trips upstream's `len(series) < 2` guard.
    That path returns a dict of only eight keys -- `returns_1m`, `rolling_1y`
    and every other window are simply absent -- so any caller reading one gets a
    KeyError rather than a zero. A newly-launched fund with two published NAVs
    is not hypothetical.

    Reproducing a crash is not fidelity, so our port returns a complete record
    of zeros. This test pins both halves: that theirs really does raise, and
    that ours really does not.
    """
    navs = series(date(2026, 8, 18), 2, seed=8)
    log_ret = oracle["nav_to_log_returns"](
        pd.Series(
            [n for _, n in navs],
            index=pd.DatetimeIndex([pd.Timestamp(d) for d, _ in navs]),
        )
    )
    theirs = oracle["calculate_performance_metrics"](log_ret)
    with pytest.raises(KeyError):
        theirs["returns_1m"]

    ours = port.compute(navs, AS_OF)
    assert ours.returns_1m == 0.0 and ours.rolling_1y == 0.0
    # On the eight keys upstream does return, we still agree exactly.
    for mine, key in FIELD_MAP.items():
        if key in theirs:
            assert getattr(ours, mine) == pytest.approx(theirs[key], abs=1e-12)


@oracle_required
def test_a_forty_percent_day_is_capped_identically(oracle):
    """One bad NAV day must be neutralised the same way on both sides.

    The 25% cap exists because a split or a restatement otherwise wrecks every
    trailing metric. If our cap fired on a different set of days, the returns
    would still look plausible.
    """
    navs = series(date(2024, 1, 1), 400, seed=11)
    d, v = navs[200]
    navs[200] = (d, round(v * 1.40, 4))
    assert_matches_oracle(oracle, navs, "a +40% day")
    assert port.compute(navs, AS_OF).capped_days >= 1, "the cap did not fire at all"


@oracle_required
def test_a_flat_month_with_no_negative_days_uses_the_same_downside_floor(oracle):
    """With zero negative returns, downside deviation is floored at 0.0001 and
    sortino explodes. Reproduced rather than clamped, because clamping would
    change a rank."""
    navs = [
        (date(2026, 1, 1) + timedelta(days=i), round(100 * (1.0004 ** i), 6))
        for i in range(40)
    ]
    assert_matches_oracle(oracle, navs, "no negative days")
    # The magnitude is the point, not the sign: dividing by 0.0001 puts sortino
    # in the hundreds either way, and which way depends only on whether the fund
    # cleared 4%. A number this unstable must never carry magnitude weight, and
    # in `scoring.risk_score` it does not -- it is ranked and nothing else.
    assert abs(port.compute(navs, AS_OF).sortino) > 100


@oracle_required
def test_a_series_with_a_zero_nav_in_the_middle_drops_it_the_same_way(oracle):
    """AMFI serves zero-NAV placeholder rows. Dropping before differencing --
    rather than after -- produces one return spanning the gap instead of two
    broken ones, and that is what upstream does."""
    navs = series(date(2024, 1, 1), 300, seed=12)
    navs[150] = (navs[150][0], 0.0)
    assert_matches_oracle(oracle, navs, "a zero NAV mid-series")


@oracle_required
def test_a_completely_flat_series_does_not_produce_nan(oracle):
    """Zero volatility divides into sharpe and sortino. Both sides must return
    0.0, not NaN, or the score becomes NaN and NaN sorts first."""
    navs = [(date(2026, 1, 1) + timedelta(days=i), 100.0) for i in range(60)]
    assert_matches_oracle(oracle, navs, "a flat series")
    m = port.compute(navs, AS_OF)
    assert m.volatility == 0.0 and m.sharpe == 0.0
    # Not zero: with no negative days the downside floor of 0.0001 divides into
    # a CAGR of 0 minus the 4% risk-free rate, giving exactly -400. Upstream
    # returns the same number. It is absurd and it is theirs, which is why
    # `scoring.risk_score` only ever ranks sortino and never uses its magnitude.
    assert m.sortino == pytest.approx(-400.0)


@oracle_required
@pytest.mark.parametrize("n", [3, 5, 10, 21, 22, 23, 29, 30, 31, 60, 91, 182, 365, 366])
def test_no_length_produces_nan_or_infinity(oracle, n):
    """Every boundary a window can straddle. A NaN reaching the scorer becomes a
    NaN score, and `safe_float` turns that into 0.0 -- a silent last place."""
    navs = series(date(2024, 1, 1), n, seed=100 + n)
    assert_matches_oracle(oracle, navs, f"{n} rows")
    m = port.compute(navs, AS_OF)
    for f in FIELD_MAP:
        v = getattr(m, f)
        assert not math.isnan(v) and not math.isinf(v), f"{f} is {v} at n={n}"


# ------------------------------------------- behaviour, without the oracle


def test_a_single_nav_is_unmeasurable_but_not_a_crash():
    """Upstream's early return hands back a dict of eight keys, missing
    returns_1y and every rolling field -- so a caller reading one gets a
    KeyError. This is the module's one deliberate divergence: a complete record
    of zeros, because reproducing a crash is not fidelity."""
    m = port.compute([(LAST_NAV, 10.0)], AS_OF)
    assert m.nav_rows == 1 and m.returns_1y == 0.0 and m.rolling_1y == 0.0
    assert m.momentum is None and m.drawdown is None


def test_an_empty_series_is_unmeasurable_but_not_a_crash():
    m = port.compute([], AS_OF)
    assert m.nav_rows == 0 and m.first_nav_date is None and m.nav_fresh is False


def test_units_are_percent_not_fraction():
    """The bug this catches renders "+1260.0%" on screen.

    `formatPercent()` takes a fraction and multiplies by 100. Volatility leaves
    here as 12.6, not 0.126. A uniform unit slip is invisible to the scorer --
    `minmax` and `rank(pct=True)` are both scale-invariant, so quality and risk
    are unchanged -- which makes an absolute-range assertion the only thing that
    can catch it.
    """
    m = port.compute(series(date(2022, 1, 1), 1000, seed=21, sigma=0.009), AS_OF)
    assert 1.0 < m.volatility < 60.0, m.volatility
    assert abs(m.returns_1y) > 0.01, "a percent return of 0.001 means someone dropped a x100"
    assert -100.0 <= m.max_drawdown <= 0.0


def test_the_four_year_window_is_load_bearing():
    """Undocumented upstream, and it changes every rank.

    This exists so that "simplifying" the window away -- using full history
    because it seems more honest -- fails loudly rather than silently
    re-ranking the product.
    """
    # A regime change, which is the realistic case: a fund that compounded hard
    # for its first eight years and has been flat since. Full history flatters
    # it; the four-year window does not. If someone "simplifies" the window away
    # this fund's roll1y roughly doubles and it climbs the table.
    boom = series(date(2013, 1, 1), 2200, seed=22, drift=0.0009)
    last = boom[-1][1]
    bust = series(date(2021, 8, 1), 1300, seed=23, drift=0.00002, first=last)
    full = boom + bust
    cut = port.window_start(AS_OF)
    windowed = [(d, n) for d, n in full if d >= cut]
    assert 0 < len(windowed) < len(full) / 2
    a = port.compute(windowed, AS_OF).rolling_1y
    b = port.compute(full, AS_OF).rolling_1y
    assert abs(a - b) > 1.0, f"window {a} vs full history {b} -- the window is not doing anything"


def test_the_window_is_measured_from_as_of_not_from_the_last_nav():
    """A fund dead for two years gets a two-year window, not four years of its
    own history. Theirs uses now(); ours uses as_of, which is the same rule and
    additionally repeatable for a past date."""
    assert port.window_start(date(2026, 8, 20)) == date(2022, 8, 20)
    assert port.window_start(date(2024, 2, 29)) == date(2020, 2, 29)


def test_momentum_reads_the_whole_history_not_a_tail_of_the_window():
    """Upstream runs `ORDER BY nav_date DESC LIMIT 22` with no window cutoff.

    This is only distinguishable on a fund that publishes sparsely enough that
    the four-year window holds fewer than 22 NAVs while its whole history holds
    more -- a quarterly-reporting fund, of which the feed has plenty. Take the
    tail of the window instead of the tail of the history and that fund's
    momentum silently becomes None, which is a 12% swing in its final score
    (0.15 momentum + a shifted drawdown term) with nothing on screen to say why.

    The first version of this test passed with the bug present, because the
    fixture let both arguments resolve to the same rows. That is the failure
    mode a sabotage pass exists to find.
    """
    # Quarterly NAVs across eleven years: 44 rows in total, but only 16 of them
    # fall inside the four-year window.
    history = [
        (date(2015, 1, 1) + timedelta(days=91 * i), round(100 * (1.01 ** i), 4))
        for i in range(44)
    ]
    cut = port.window_start(AS_OF)
    windowed = [(d, n) for d, n in history if d >= cut]
    assert len(windowed) < port.MOMENTUM_NAV_ROWS < len(history), (
        f"fixture is wrong: window has {len(windowed)}, history has {len(history)}"
    )

    from_history = port.compute(windowed, AS_OF, momentum_navs=history[-port.MOMENTUM_NAV_ROWS:])
    from_window = port.compute(windowed, AS_OF, momentum_navs=None)

    assert from_history.momentum is not None, "the whole history is long enough to score"
    assert from_window.momentum is None, "the window alone is too short -- the two must differ"


def test_fewer_than_twenty_two_navs_yields_no_momentum():
    """21 NAVs is 20 returns, one short of the 14-day window plus its 7-day
    warm-up. `None` rather than 0.0, because zero momentum is a claim."""
    assert port.compute(series(date(2026, 6, 1), 21, seed=23), AS_OF).momentum is None
    assert port.compute(series(date(2026, 6, 1), 22, seed=23), AS_OF).momentum is not None


def test_freshness_is_measured_in_calendar_days_against_as_of():
    assert port.is_fresh(date(2026, 8, 10), AS_OF) is True
    assert port.is_fresh(date(2026, 8, 9), AS_OF) is False
    assert port.is_fresh(None, AS_OF) is False


def test_unsorted_input_is_sorted_rather_than_producing_nonsense():
    """The store returns rows ordered, but a caller assembling a series by hand
    should not silently get a reversed set of returns."""
    navs = series(date(2024, 1, 1), 200, seed=24)
    assert port.compute(list(reversed(navs)), AS_OF) == port.compute(navs, AS_OF)


def test_duplicate_dates_do_not_crash_the_calendar_kernel():
    """The store's primary key makes this impossible, but the function is pure
    and public, and `searchsorted` on a non-unique index is where a silent
    off-by-one would live."""
    navs = series(date(2024, 1, 1), 100, seed=25)
    m = port.compute(navs + [navs[50]], AS_OF)
    assert not math.isnan(m.rolling_1m)


def test_below_thirty_returns_the_thirty_day_figures_are_the_whole_lifetime():
    """A numpy quirk upstream ships and we reproduce.

    `np.convolve(returns, ones(30), 'valid')` swaps its arguments when the
    series is shorter than the kernel, so every output is the sum of the entire
    series. A fund with three returns therefore reports its whole lifetime
    return as both its best and its worst thirty-day move -- identical numbers,
    which is the tell. Guarding against it would break parity with the scorer
    the product ranks on, so it is reproduced, named here, and disclosed through
    `history_years`.
    """
    m = port.compute(series(date(2026, 8, 1), 5, seed=27), AS_OF)
    assert m.best_30d == m.worst_30d, "the quirk has stopped happening; check numpy"
    long = port.compute(series(date(2024, 1, 1), 300, seed=27), AS_OF)
    assert long.best_30d > long.worst_30d


def test_history_years_is_recorded_so_a_short_record_can_be_disclosed():
    """`returns_3y` for a two-year-old fund is its two-year CAGR wearing a
    three-year label. We reproduce that, so the screen needs this field to be
    able to say so."""
    m = port.compute(series(date(2024, 8, 20), 500, seed=26), AS_OF)
    assert 1.9 < m.history_years < 2.1
