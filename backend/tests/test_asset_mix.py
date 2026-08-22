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


# --------------------------------------------------- what they actually put in

from datetime import date as _date  # noqa: E402


@dataclass
class T:
    txn_type: str
    txn_date: _date
    units: float
    price: float


def test_the_monthly_contribution_is_derived_rather_than_asked_for():
    """Every caller had to supply `monthly_sip`, and the decision screen passed
    a hardcoded zero — which silently removed the single largest lever on it."""
    txns = [T("BUY", _date(2026, m, 5), 100, 100) for m in range(1, 13)]
    assert asset_mix.monthly_contribution(txns, _date(2026, 12, 31)) == 10_000.0


def test_sells_are_not_netted_off_the_contribution():
    """Someone who bought ₹20,000 and sold ₹20,000 of something else is still
    adding ₹20,000 a month. The question is what they are putting in."""
    txns = [
        T("BUY", _date(2026, 6, 5), 100, 100),
        T("SELL", _date(2026, 6, 6), 100, 100),
    ]
    assert asset_mix.monthly_contribution(txns, _date(2026, 12, 31)) > 0


def test_a_lump_sum_does_not_become_a_monthly_habit():
    """Averaged over the window, so one big purchase is not read as a standing
    instruction twelve times its size."""
    lump = [T("BUY", _date(2026, 6, 5), 1000, 100)]
    assert asset_mix.monthly_contribution(lump, _date(2026, 12, 31)) == pytest_approx(
        100_000 / 12
    )


def test_old_transactions_do_not_count():
    stale = [T("BUY", _date(2020, 6, 5), 1000, 100)]
    assert asset_mix.monthly_contribution(stale, _date(2026, 12, 31)) == 0.0


def test_no_transactions_means_zero_not_a_crash():
    assert asset_mix.monthly_contribution([], _date(2026, 12, 31)) == 0.0


def pytest_approx(value):
    import pytest
    return pytest.approx(value, abs=1)


def test_the_dominant_category_is_where_the_money_is():
    """Which reference class the decision screen should show."""
    got = asset_mix.dominant_category([
        H("PPFAS", "MF", "122639", None, 300_000),      # Flexi Cap
        H("HDFC", "MF", "118955", None, 500_000),       # also Flexi Cap
    ])
    assert got is not None
    category, value = got
    assert "Flexi Cap" in category
    assert value == 800_000


def test_categories_are_not_blended_into_one_number():
    """Averaging Small Cap's 20% losing years with Gilt's 5% produces a figure
    that describes neither. The largest category wins outright."""
    got = asset_mix.dominant_category([
        H("Gilt", "MF", "x", "Debt Scheme - Gilt Fund", 900_000),
        H("PPFAS", "MF", "122639", None, 100_000),
    ])
    # 'x' is not in the catalogue, so only the classifiable one counts.
    assert got is not None and "Flexi Cap" in got[0]


def test_stocks_do_not_claim_a_fund_category():
    assert asset_mix.dominant_category([H("REL", "STOCK", "RELIANCE.NS", None, 900_000)]) is None


def test_nothing_classifiable_means_no_reference_class():
    assert asset_mix.dominant_category([]) is None
    assert asset_mix.dominant_category([H("?", "MF", "zzz", None, 500_000)]) is None
