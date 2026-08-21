"""How much of a portfolio is actually in equity.

The input to the equity-share trade, and the one thing about a portfolio that
decides more of the outcome than every fund choice in it. These tests are
mostly about it refusing to answer rather than guessing.
"""

from dataclasses import dataclass

from app.services.advisor import asset_mix


@dataclass
class H:
    name: str
    asset_type: str
    identifier: str
    category: str | None
    current_value: float


def test_a_stock_is_equity_whatever_else_is_known_about_it():
    mix = asset_mix.classify([H("Reliance", "STOCK", "RELIANCE.NS", None, 100_000)])
    assert mix.equity_share == 1.0


def test_a_debt_fund_is_not_equity():
    mix = asset_mix.classify([
        H("Gilt", "MF", "x", "Debt Scheme - Gilt Fund", 100_000),
        H("Flexi", "MF", "y", "Equity Scheme - Flexi Cap Fund", 100_000),
    ])
    assert mix.equity_share == 0.5


def test_an_aggressive_hybrid_counts_as_equity_risk():
    """SEBI defines it as 65-80% equity. Filing it under Hybrid does not make
    the money behave like debt when the market falls."""
    mix = asset_mix.classify([
        H("Hyb", "MF", "x", "Hybrid Scheme - Aggressive Hybrid Fund", 100_000),
    ])
    assert mix.equity_share == 1.0


def test_an_index_fund_is_equity_however_amfi_files_it():
    mix = asset_mix.classify([H("Nifty", "MF", "x", "Other Scheme - Index Funds", 50_000)])
    assert mix.equity_share == 1.0


def test_the_real_catalogue_category_beats_whatever_the_user_typed():
    """The stored category is free text from a creation form. 122639 is PPFAS
    Flexi Cap; a user who typed "Debt" into the box must not turn it into one."""
    mix = asset_mix.classify([H("PPFAS", "MF", "122639", "Debt", 100_000)])
    assert mix.equity_share == 1.0


def test_too_much_unclassified_money_means_no_answer_rather_than_a_guess():
    """Assuming the unknown part matches the known part produces a number that
    looks like a measurement and is a guess — and a trade built on it tells
    someone to move real money."""
    mix = asset_mix.classify([
        H("Known", "MF", "x", "Equity Scheme - Flexi Cap Fund", 100_000),
        H("Mystery", "MF", "zzz", None, 50_000),
    ])
    assert mix.unclassified_share > asset_mix.MAX_UNCLASSIFIED
    assert mix.equity_share is None
    assert "Mystery" in mix.unclassified_names


def test_a_little_unclassified_money_is_tolerated():
    mix = asset_mix.classify([
        H("Known", "MF", "x", "Equity Scheme - Flexi Cap Fund", 100_000),
        H("Tiny", "MF", "zzz", None, 5_000),
    ])
    assert mix.equity_share == 1.0


def test_an_empty_portfolio_has_no_share_rather_than_zero():
    """Zero equity and no portfolio are different facts, and one of them would
    tell someone to move everything into stocks."""
    assert asset_mix.classify([]).equity_share is None
    assert asset_mix.classify([H("x", "MF", "x", "Debt Scheme - Gilt Fund", 0)]).equity_share is None


def test_unpriced_holdings_do_not_drag_the_share():
    mix = asset_mix.classify([
        H("Priced", "MF", "x", "Equity Scheme - Flexi Cap Fund", 100_000),
        H("Unpriced", "MF", "y", "Debt Scheme - Gilt Fund", 0),
    ])
    assert mix.equity_share == 1.0
