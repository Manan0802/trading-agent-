"""The sentences a fund page leads with.

They live in Python rather than JSX because they are claims about data, two
screens must not word the same fact differently, and the frontend has no test
runner. Most of these tests are about a sentence that would be wrong rather
than one that would be ugly.
"""

from dataclasses import dataclass

import pytest

from app.services.screener import plain_words as pw


@dataclass
class Cost:
    direct_ter: float | None = 1.12
    regular_ter: float | None = 2.20
    saving_pct_per_year: float | None = 1.08
    saving_on_a_lakh_over_10y: float | None = 11340.0


@dataclass
class Fund:
    max_drawdown: float | None = -0.15
    volatility: float | None = 0.14
    risk_tier: str | None = "Moderately High"


@dataclass
class Row:
    years: int = 3
    invested: float = 100000.0
    value: float | None = 221766.0
    actual_years: float | None = 2.88
    annualised: float | None = 0.319
    full_period: bool = False


@dataclass
class Holding:
    name: str
    weight: float
    industry: str | None = "Pharmaceuticals & Biotechnology"
    isin: str | None = None


@dataclass
class Holdings:
    covered: bool = True
    total_positions: int = 37
    top: list = None
    by_industry: list = None

    def __post_init__(self):
        if self.top is None:
            self.top = [Holding(f"C{i}", 10.0 - i) for i in range(15)]
        if self.by_industry is None:
            self.by_industry = [("Pharmaceuticals & Biotechnology", 71.18)]


# ------------------------------------------------- Indian digit grouping


@pytest.mark.parametrize(
    "amount,expected",
    [(100000, "1,00,000"), (221766, "2,21,766"), (1250000, "12,50,000"),
     (999, "999"), (1000, "1,000"), (11340, "11,340"), (10000000, "1,00,00,000")],
)
def test_rupees_group_the_indian_way(amount, expected):
    """12,50,000 and 1,250,000 are the same number and only one of them parses
    at a glance for the person this is for."""
    assert pw.rupees(amount) == f"₹{expected}"


def test_a_missing_amount_produces_no_string_rather_than_zero():
    assert pw.rupees(None) is None


# ------------------------------------------------- cost


def test_the_cost_sentence_leads_with_rupees_not_percentage_points():
    """A percentage point a year does not feel like anything. It is the number
    this project measured as most predictive, so it has to land."""
    s = pw.cost_sentence(Cost())
    assert "₹11,340" in s
    assert "1.12%" in s and "2.20%" in s
    assert "fees" in s


def test_a_fund_with_only_a_direct_ratio_says_only_that():
    s = pw.cost_sentence(Cost(regular_ter=None, saving_pct_per_year=None))
    assert "1.12%" in s
    assert "distributor" not in s, "it claimed a comparison it does not have"


def test_a_fund_with_no_expense_data_gets_no_sentence():
    """19% of ranked funds have no TER entry. A hedged sentence is worse than
    silence."""
    assert pw.cost_sentence(Cost(direct_ter=None)) is None


# ------------------------------------------------- the calculator


def test_a_young_fund_names_its_own_age_rather_than_a_period_it_never_lived():
    """An earlier version read "put in when it launched, 2.9 years ago would be
    worth", which is two clauses fighting over one comma."""
    s = pw.calculator_sentence([Row()])
    assert "at launch 2.9 years ago" in s
    assert "3 years ago" not in s
    # The old wording, checked directly. Counting commas does not work here --
    # the rupee figures carry two each.
    assert "launched," not in s
    assert ", 2.9 years ago" not in s


def test_a_fund_old_enough_names_the_period_asked_for():
    s = pw.calculator_sentence([Row(years=5, actual_years=5.0, full_period=True)])
    assert "5 years ago" in s and "launch" not in s


def test_a_fund_that_lost_money_does_not_say_it_would_be_worth():
    """"₹1,00,000 would be worth ₹62,000" reads as a gain at a glance."""
    s = pw.calculator_sentence([Row(value=62000.0)])
    assert "shrunk to" in s and "would be worth" not in s


def test_the_longest_lived_period_is_the_one_quoted():
    rows = [Row(years=1, actual_years=1.0, value=110000.0, full_period=True), Row()]
    assert "2.9 years" in pw.calculator_sentence(rows)


def test_no_usable_row_gives_no_sentence():
    assert pw.calculator_sentence([Row(value=None, actual_years=None)]) is None


# ------------------------------------------------- rolling returns


def test_the_rolling_sentence_counts_entry_dates_not_one():
    """A headline "1-year return" is whatever happened to one person who bought
    on one day."""
    s = pw.rolling_sentence(
        {"windows": 1204, "worst": 0.004, "best": 1.307, "median": 0.221,
         "positive_share": 1.0}
    )
    assert "1,204 days" in s
    assert "Every single one of them made money" in s


def test_a_fund_that_lost_money_in_some_years_says_the_split():
    s = pw.rolling_sentence(
        {"windows": 900, "worst": -0.31, "best": 0.62, "median": 0.08,
         "positive_share": 0.72}
    )
    assert "72% of them made money and 28% lost" in s
    assert "-31.0%" in s


def test_a_fund_that_never_made_money_says_so_plainly():
    s = pw.rolling_sentence(
        {"windows": 300, "worst": -0.4, "best": -0.02, "median": -0.2,
         "positive_share": 0.0}
    )
    assert "Not one of them made money" in s


def test_a_fund_too_short_to_roll_gets_no_sentence():
    assert pw.rolling_sentence({"windows": 0}) is None


# ------------------------------------------------- drawdown, risk, peers


def test_the_drawdown_sentence_puts_the_fall_in_rupees():
    """A percentage does not convey sitting through it."""
    s = pw.drawdown_sentence(Fund(max_drawdown=-0.15))
    assert "15%" in s and "₹85,000" in s


def test_a_fund_that_has_barely_fallen_says_that_instead():
    assert "never fallen more than 2%" in pw.drawdown_sentence(Fund(max_drawdown=-0.005))


def test_volatility_is_expressed_as_a_swing_not_a_statistic():
    """"Volatility 17.5%" means nothing to most readers."""
    s = pw.risk_sentence(Fund(volatility=0.14))
    assert "moves about 14% either way" in s
    assert "volatility" not in s.lower()


def test_the_peer_sentence_compares_against_the_category_not_an_index():
    s = pw.peer_sentence(1.218, 0.774, 40, clipped=False)
    assert "middle fund in its category" in s
    assert "ahead of 40 funds" in s
    assert "Nifty" not in s


def test_a_clipped_comparison_says_the_window_was_shortened():
    """Without it a reader compares a fifteen-month record against a three-year
    one and reads the gap backwards."""
    s = pw.peer_sentence(1.2, 0.6, 40, clipped=True)
    assert "shorter than the range you picked" in s


def test_a_fund_behind_its_category_says_behind():
    s = pw.peer_sentence(0.10, 0.25, 30, clipped=False)
    assert "behind" in s and "ahead of" not in s


def test_no_peer_data_gives_no_comparison_sentence():
    assert pw.peer_sentence(0.5, None, 0, clipped=False) is None
    assert pw.peer_sentence(0.5, 0.3, 0, clipped=False) is None


# ------------------------------------------------- holdings


def test_the_holdings_sentence_says_how_concentrated_it_is():
    s = pw.holdings_sentence(Holdings())
    assert "37 companies" in s
    assert "pharmaceuticals & biotechnology" in s


def test_a_concentrated_fund_is_called_concentrated():
    top = [Holding(f"C{i}", 12.0) for i in range(15)]
    s = pw.holdings_sentence(Holdings(top=top))
    assert "concentrated" in s


def test_an_amc_we_cannot_parse_gets_no_holdings_sentence():
    assert pw.holdings_sentence(Holdings(covered=False)) is None


# ------------------------------------------------- the shared rule


def test_no_sentence_contains_a_statistic_name_a_reader_would_not_know():
    """The rule for this whole module: say what happened before naming the
    formula. These words are all fine in the metrics grid and wrong in a
    sentence."""
    sentences = [
        pw.cost_sentence(Cost()),
        pw.calculator_sentence([Row()]),
        pw.rolling_sentence({"windows": 500, "worst": 0.0, "best": 1.0,
                             "median": 0.2, "positive_share": 1.0}),
        pw.drawdown_sentence(Fund()),
        pw.risk_sentence(Fund()),
        pw.peer_sentence(0.5, 0.3, 20, clipped=False),
        pw.holdings_sentence(Holdings()),
    ]
    banned = ("sortino", "sharpe", "alpha", "beta", "standard deviation",
              "cagr", "annualised volatility", "drawdown", "percentile")
    for s in sentences:
        assert s
        for word in banned:
            assert word not in s.lower(), f"{word!r} leaked into: {s}"
