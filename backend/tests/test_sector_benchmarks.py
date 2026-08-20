"""The sector-median adapter: units, completeness, and the crash it prevents.

There is one sector table in this codebase -- traa's own, built from its NSE
universe -- and this adapter puts it in the units the ported stock scorer
compares against. It is not a second source, and a test below asserts that.
"""

import pytest

from app.services.advisor import stock_analysis
from app.services.screener import sector_benchmarks as sb

KEYS = ("median_pe", "median_pb", "median_roe", "median_div_yield")


@pytest.fixture(autouse=True)
def fresh():
    sb.clear_cache()
    yield
    sb.clear_cache()


def test_there_is_only_one_sector_table_and_this_reads_it():
    """Written after building a second one by mistake.

    traa already had `scripts/build_sector_benchmarks.py`, computing medians
    across its own NSE universe -- 961 constituents, against a hand-picked
    80-ticker basket -- and carrying the same weighted-versus-median reasoning.
    A parallel table was built anyway and overwrote it. This test is the thing
    that makes the duplication visible next time.
    """
    assert sb._traa_table is stock_analysis.sector_benchmarks
    assert set(sb.sectors()) <= set(stock_analysis.sector_benchmarks())


def test_roe_and_dividend_yield_are_converted_to_percent():
    """The whole reason this adapter exists.

    traa stores both as decimal fractions; `_score_roe` and `_score_div_yield`
    compare against percents. Feed 0.15 where 15.0 is expected and every
    company looks a hundred times more profitable than its sector -- and
    nothing downstream errors.
    """
    raw = stock_analysis.sector_benchmarks()
    for name in sb.sectors():
        adapted = sb.resolve(name)
        assert adapted["median_roe"] == pytest.approx(raw[name]["roe"] * 100, abs=1e-3)
        assert adapted["median_div_yield"] == pytest.approx(
            raw[name]["dividend_yield"] * 100, abs=1e-3
        )


def test_pe_and_pb_are_passed_through_unchanged():
    """Only two of the four need scaling. Scaling all four would be the same
    bug in the other direction."""
    raw = stock_analysis.sector_benchmarks()
    for name in sb.sectors():
        assert sb.resolve(name)["median_pe"] == pytest.approx(raw[name]["pe"], abs=1e-3)
        assert sb.resolve(name)["median_pb"] == pytest.approx(raw[name]["pb"], abs=1e-3)


def test_the_percent_values_land_in_a_plausible_range():
    """A guard that survives a rebuild of the underlying file. An Indian sector
    ROE median is a number like 15, not 0.15 and not 1500."""
    roes = [sb.resolve(n)["median_roe"] for n in sb.sectors()]
    assert max(roes) > 1.5, f"these look like fractions, not percents: {roes}"
    assert max(roes) < 90.0, f"these look like they were scaled twice: {roes}"
    yields = [sb.resolve(n)["median_div_yield"] for n in sb.sectors()]
    assert 0.0 < max(yields) <= 12.0, yields


def test_every_sector_comes_back_complete():
    """`_score_pe` and `_score_pb` divide by these without checking. A None is a
    TypeError at scoring time, not a neutral score."""
    for name in sb.sectors() + [None, "", "Interdimensional Widgets"]:
        row = sb.resolve(name)
        for key in KEYS:
            assert row.get(key) is not None, f"{name}.{key} is None"
            assert isinstance(row[key], (int, float))


def test_an_unknown_sector_falls_back_to_the_all_stocks_median_not_a_guess():
    """traa's table carries an `_ALL` row computed across every stock it scores.
    That is a real measurement and a far better default than a round number."""
    unknown = sb.resolve("Interdimensional Widgets")
    all_stocks = sb.resolve(ALL := sb.ALL_STOCKS)
    assert unknown["median_pe"] == all_stocks["median_pe"]
    assert unknown["constituents"] > 100, "the default should be measured, not invented"
    assert unknown != sb._LAST_RESORT


def test_a_partial_row_is_completed_rather_than_passed_through(monkeypatch):
    """A sector with a thin sample can be missing one field. Dropping it would
    hand a None to a function that divides by it."""
    monkeypatch.setattr(
        sb, "_traa_table",
        lambda: {
            "_ALL": {"pe": 30.0, "pb": 4.0, "roe": 0.15, "dividend_yield": 0.007, "n": 400},
            "Thin": {"pe": None, "pb": 2.0, "roe": None, "dividend_yield": 0.01, "n": 2},
        },
    )
    sb._table.cache_clear()
    row = sb.resolve("Thin")
    assert row["median_pb"] == 2.0, "its own value must survive"
    assert row["median_pe"] == 30.0, "the missing one comes from the all-stocks row"
    assert row["median_roe"] == pytest.approx(15.0)
    sb._table.cache_clear()


def test_a_missing_table_raises_rather_than_inventing_medians(monkeypatch):
    """Scoring every stock against invented numbers produces a full,
    plausible-looking ranking built on nothing."""
    monkeypatch.setattr(sb, "_traa_table", dict)
    sb._table.cache_clear()
    with pytest.raises(sb.SectorBenchmarksUnavailable, match="build_sector_benchmarks"):
        sb.resolve("Technology")
    sb._table.cache_clear()


def test_the_sample_size_is_available_for_the_screen_to_disclose():
    """"Cheap versus peers" means nothing without knowing how many peers."""
    assert sb.built_from() > 100
    assert sb.resolve("Technology")["constituents"] > 0


def test_the_all_stocks_row_is_not_offered_as_a_sector():
    """It is a fallback, not a sector anyone can pick from a filter."""
    assert sb.ALL_STOCKS not in sb.sectors()


def test_the_table_is_only_built_once():
    """It is on every scored stock's path; rebuilding per stock would be
    hundreds of dict comprehensions a run."""
    sb.clear_cache()
    sb.resolve("Technology")
    before = sb._table.cache_info().misses
    sb.resolve("Energy")
    sb.resolve("Healthcare")
    assert sb._table.cache_info().misses == before
