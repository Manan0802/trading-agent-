import pytest

from app.services.advisor.fund_universe import (
    BENCHMARK_SCHEME_CODE,
    benchmark_for_category,
)


def test_large_cap_is_the_one_category_the_nifty_50_actually_fits():
    code, caveat = benchmark_for_category("Equity Scheme - Large Cap Fund")
    assert code == BENCHMARK_SCHEME_CODE
    assert caveat is None


@pytest.mark.parametrize(
    "category",
    [
        "Equity Scheme - Flexi Cap Fund",
        "Equity Scheme - Mid Cap Fund",
        "Equity Scheme - Small Cap Fund",
        "Equity Scheme - ELSS",
    ],
)
def test_broader_equity_categories_are_benchmarked_but_carry_a_caveat(category):
    """The Nifty 50 is large-cap only, so measuring a small-cap fund against it
    credits the size premium as manager skill."""
    code, caveat = benchmark_for_category(category)
    assert code == BENCHMARK_SCHEME_CODE
    assert caveat and "Nifty 50" in caveat


def test_the_small_cap_caveat_is_stronger_than_the_flexi_cap_one():
    """A single caveat string understated the problem: the gap for a small-cap
    fund is far larger than for a flexi cap."""
    _, flexi = benchmark_for_category("Equity Scheme - Flexi Cap Fund")
    _, small = benchmark_for_category("Equity Scheme - Small Cap Fund")
    assert flexi != small
    assert "small" in small.lower()


@pytest.mark.parametrize(
    "category",
    [
        "Debt Scheme - Corporate Bond Fund",
        "Debt Scheme - Liquid Fund",
        "Other Scheme - FoF Domestic",
        "Hybrid Scheme - Arbitrage Fund",
    ],
)
def test_non_equity_categories_are_not_benchmarked_against_an_equity_index(category):
    """Judging a liquid fund against the Nifty produces numbers that look
    damning and mean nothing: it is not trying to track equities."""
    code, caveat = benchmark_for_category(category)
    assert code is None
    assert caveat is None


def test_sectoral_funds_are_not_benchmarked_against_the_broad_market():
    """A pharma fund beating the Nifty says the sector ran, not that the
    manager picked well."""
    code, _ = benchmark_for_category("Equity Scheme - Sectoral/ Thematic")
    assert code is None


def test_index_funds_are_not_scored_against_an_index():
    """Alpha against the thing you are tracking is tracking error with a
    misleading name."""
    code, _ = benchmark_for_category("Other Scheme - Index Funds")
    assert code is None


def test_an_unknown_category_is_not_benchmarked():
    code, caveat = benchmark_for_category("Equity Scheme - Unicorn Fund")
    assert code is None
    assert caveat is None
