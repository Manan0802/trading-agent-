"""`screener/fund_facts.py` assembles the fund page's cost section, untested.

The last module the pre-existing suite never named — found on pass 51 of the
Phase 1 review by mutation testing, confirmed on pass 53 after excluding the
test files written that day. 170 lines, used by `routers/screener.py`.

Its own docstring explains why that matters: it puts cost first because cost is
*"the one number this project has measured as predictive"* — separating future
winners from losers 87% of the time, against 68% for picking on past record with
three of seven years at or below chance.

Each test below pins a decision the module's comments argue for, and each was
checked by breaking the thing it guards.
"""

import pytest

from app.services.screener.fund_facts import CALCULATOR_AMOUNT, Cost, cost_for


def test_the_saving_is_compounded_not_multiplied():
    """The module: "A percentage point a year is not ten percentage points over
    ten years, and quoting it that way would be the same overstatement this
    project keeps catching elsewhere."

    103490 = QUANTUM VALUE FUND: direct 1.12, regular 2.15, gap 1.03pp.
    Multiplied would give ₹10,300 on a lakh. Compounded gives ~₹10,780 — and the
    two only diverge by 5% here, which is exactly why a wrong one would survive
    a glance.
    """
    cost = cost_for("103490")
    assert cost.direct_ter == 1.12
    assert cost.regular_ter == 2.15
    assert cost.saving_pct_per_year == pytest.approx(1.03)

    compounded = CALCULATOR_AMOUNT * ((1 + 1.03 / 100) ** 10 - 1)
    assert cost.saving_on_a_lakh_over_10y == pytest.approx(compounded, abs=1)
    # and it is NOT the naive figure
    assert cost.saving_on_a_lakh_over_10y != pytest.approx(CALCULATOR_AMOUNT * 0.1030, abs=1)


def test_an_unknown_fund_returns_nulls_not_zeros():
    """Section 14: missing cost is neutral, never dropped and never 0.0.

    A zero saving would read as "the direct plan saves nothing" — an answer,
    and the wrong one — where `None` reads as "we do not know", which is true.
    """
    cost = cost_for("000000")
    assert cost == Cost(None, None, None, None, None)
    assert cost.saving_pct_per_year is not 0.0  # noqa: F632 - identity is the point


def test_no_ten_year_figure_when_the_direct_plan_is_not_cheaper():
    """`over_ten` is computed only when the saving is positive.

    A negative or zero gap must not produce a rupee figure at all: "the direct
    plan saves you ₹-400" is arithmetic, not information, and the badge that
    renders it says the opposite of what it means.
    """
    for code, row in _rows_with_no_positive_gap():
        cost = cost_for(code)
        assert cost.saving_on_a_lakh_over_10y is None, f"{code} {row}"


def _rows_with_no_positive_gap():
    from app.services.advisor import fund_evidence

    out = []
    for code, row in fund_evidence.expense_ratios().items():
        d, r = row.get("direct_ter"), row.get("regular_ter")
        if d is not None and r is not None and float(r) - float(d) <= 0:
            out.append((code, row))
    return out[:5]


def test_the_two_expense_ratios_come_from_one_loader():
    """The module reuses `fund_evidence.expense_ratios()` rather than re-reading
    the file, so "the fund page and the verdict can never quote different
    expense ratios for the same fund" — its own words. A second copy of the
    loader is how two screens start disagreeing about one number.
    """
    from app.services.advisor import fund_evidence

    row = fund_evidence.expense_ratios()["103490"]
    cost = cost_for("103490")
    assert cost.direct_ter == row["direct_ter"]
    assert cost.as_of == row["as_of"]


# ---------------------------------------------------------------------------
# `rank_at_horizons` and `holdings_for` — the two functions pass 54 left behind
#
# Pass 54 tested `cost_for` and reported the module covered. Pass 55 profiled
# which functions the suite actually CALLS and found 1 of 4. "Named by a test"
# and "exercised by a test" are different claims, and only the second one is
# worth anything.
# ---------------------------------------------------------------------------


class _Fund:
    """A peer row, shaped like whatever the screener hands in."""

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_a_rank_counts_only_peers_that_have_the_number():
    """The module: "a rank is never inflated by peers with no data".

    "Rank 3 of 47" when 40 of those 47 have no three-year figure is a claim
    about a field of 47 that does not exist. Section 14: coverage is stated,
    not hidden — and a denominator is a coverage claim.
    """
    from app.services.screener.fund_facts import rank_at_horizons

    target = _Fund(returns_3y=12.0)
    peers = [_Fund(returns_3y=15.0), _Fund(returns_3y=8.0), _Fund(returns_3y=None)]
    out = rank_at_horizons(target, peers)

    assert out["3Y"]["of"] == 2, "the peer with no figure must not swell the field"
    assert out["3Y"]["rank"] == 2, "one peer is better, so this is second"
    assert out["3Y"]["value"] == 12.0


def test_a_horizon_the_fund_itself_lacks_is_omitted_not_ranked_last():
    """No number means no rank, not a rank of last.

    Ranking a fund that has no three-year history against funds that do would
    read as "worst of 47" when the truth is "not measurable" — the zero-versus-
    n/a confusion section 14 forbids, wearing a rank instead of a percentage.
    """
    from app.services.screener.fund_facts import rank_at_horizons

    # two peers with a 1Y figure, because a horizon also needs >=2 to rank at
    # all -- the first draft of this test gave one and blamed the code
    out = rank_at_horizons(
        _Fund(returns_3y=None, returns_1y=9.0),
        [_Fund(returns_3y=15.0, returns_1y=4.0), _Fund(returns_3y=11.0, returns_1y=12.0)],
    )
    assert "3Y" not in out, "no figure of its own means no rank, not a rank of last"
    assert out["1Y"]["of"] == 2
    assert out["1Y"]["rank"] == 2


def test_a_horizon_with_fewer_than_two_peers_is_omitted():
    """"Rank 1 of 1" is not information."""
    from app.services.screener.fund_facts import rank_at_horizons

    assert rank_at_horizons(_Fund(returns_1y=9.0), [_Fund(returns_1y=None)]) == {}


def test_an_unparsed_amc_reports_not_covered_rather_than_failing():
    """`holdings_for` turns an unavailable AMC into `covered=False`, not an error.

    The module's own comment: a fund page should say "we do not have this AMC's
    portfolio" rather than fail. The distinction that matters is between *this
    fund holds nothing* and *we cannot see what it holds*, which is the same
    n/a-versus-zero rule one level up.
    """
    from app.services.screener.fund_facts import holdings_for

    result = holdings_for("A Fund From An AMC Nobody Parses Yet")
    assert result.covered is False
    assert result.top == []
    assert result.as_of is None
