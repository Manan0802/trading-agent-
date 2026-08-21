"""The reference class: how often this kind of fund has lost money.

The one thing on the screen that is neither a forecast nor an opinion. These
tests are mostly about the ways a base rate stops being one — a widened peer
class, a survivor-only sample, a percentage where a rupee figure was needed.
"""

import json

import pytest

from app.services.screener import base_rates as br
from app.services.screener import plain_words as pw


def rate(name="Small Cap Fund"):
    got = br.for_category("Equity Scheme", name)
    assert got is not None, f"{name} missing from the built table"
    return got


# ------------------------------------------------------------ the table


def test_the_headline_finding_holds_in_every_equity_category():
    """Holding period decides whether you lose money; fund choice does not.

    This is the claim the whole file exists to support, so it is asserted over
    every category rather than the two I happened to look at."""
    checked = 0
    for r in br.all_rates():
        if r.category != "Equity Scheme":
            continue
        one, five = r.horizon("1y"), r.horizon("5y")
        if not one or not five:
            continue
        checked += 1
        assert five.loss_share <= one.loss_share, (
            f"{r.sub_category}: five years lost money more often "
            f"({five.loss_share}) than one ({one.loss_share})"
        )
    assert checked >= 8, f"only {checked} equity categories had both horizons"


def test_equity_is_riskier_over_one_year_than_gilt():
    """A sanity check that would catch a category mix-up, which no amount of
    internal consistency would."""
    gilt = br.for_category("Debt Scheme", "Gilt Fund")
    assert gilt is not None
    assert rate().horizon("1y").loss_share > gilt.horizon("1y").loss_share


def test_a_thin_category_gets_no_base_rate_at_all():
    """The fund screen refuses to rank a group under eight funds. A base rate
    quoted off six funds would be the same overclaim in a different place."""
    for r in br.all_rates():
        assert r.funds >= 8, f"{r.sub_category} rated on {r.funds} funds"


def test_every_horizon_rests_on_enough_windows_to_have_percentiles():
    for r in br.all_rates():
        for h in r.horizons:
            assert h.windows >= 200, f"{r.sub_category} {h.key}: {h.windows} windows"


def test_horizons_are_ordered_shortest_first():
    """`shortest`, `longest` and `first_safe_horizon` all index off this order,
    and a dict that lost its ordering would silently return the wrong one."""
    for r in br.all_rates():
        keys = [h.key for h in r.horizons]
        assert keys == [k for k in br.HORIZON_ORDER if k in keys]


def test_wound_up_funds_are_counted_not_dropped():
    """Most published fund studies quietly exclude schemes that no longer
    exist, which flatters every number in them. Ours are in — the backfill
    pulled dead scheme codes too."""
    total_dead = sum(r.funds_wound_up for r in br.all_rates())
    assert total_dead > 50, f"only {total_dead} wound-up funds across the whole table"


# ------------------------------------------------- the class is never widened


def test_an_unknown_category_returns_nothing_rather_than_a_broader_class():
    """"Equity funds lost money in 18% of years" is a different claim from
    "Small Cap funds did". Quietly substituting one for the other is the exact
    silent widening this project reports rather than performs."""
    assert br.for_category("Equity Scheme", "Imaginary Fund") is None
    assert br.for_category("Nonsense Scheme", "Small Cap Fund") is None
    assert br.for_joined("Nonsense Scheme - Imaginary Fund") is None


def test_a_fund_with_no_sub_category_does_not_borrow_another_ones():
    assert br.for_category("Equity Scheme", None) is None
    assert br.for_category("Equity Scheme", "") is None


# ---------------------------------------------------------------- rupees


def test_the_worst_fall_is_converted_to_this_persons_money():
    r = rate()
    at_risk = br.rupees_at_risk(r, 800000)
    assert at_risk == pytest.approx(800000 * abs(r.worst_fall), abs=1)
    assert 300000 < at_risk < 600000


def test_no_amount_means_no_rupee_figure_rather_than_zero():
    assert br.rupees_at_risk(rate(), 0) is None
    assert br.rupees_at_risk(rate(), -5) is None


# -------------------------------------------------------------- sentences


def test_the_base_rate_sentence_counts_out_of_a_hundred():
    """"20 of every 100" is read correctly by more people than "20.3%", and the
    decimal is spurious precision on overlapping windows."""
    said = pw.base_rate_sentence(rate())
    assert "of every 100" in said
    assert "%" not in said


def test_the_base_rate_sentence_names_the_holding_period_that_fixed_it():
    said = pw.base_rate_sentence(rate())
    assert "Held for five years" in said
    assert "how long you hold" in said


def test_the_worst_fall_sentence_gives_rupees_when_it_knows_the_amount():
    said = pw.worst_fall_sentence(rate(), 800000)
    assert "₹8,00,000" in said and "gone" in said
    assert "months to get back" in said


def test_the_worst_fall_sentence_omits_rupees_rather_than_inventing_them():
    said = pw.worst_fall_sentence(rate())
    assert "₹" not in said
    assert "%" in said


def test_the_coverage_sentence_admits_the_dead_funds():
    said = pw.base_rate_coverage_sentence(rate())
    assert "no longer exist" in said
    assert "brochure" in said


def test_no_sentence_uses_jargon():
    """The same rule the rest of `plain_words` is held to."""
    banned = ("percentile", "standard deviation", "drawdown", "volatility",
              "annualised", "cagr", "sigma")
    for r in br.all_rates()[:12]:
        for said in (pw.base_rate_sentence(r), pw.worst_fall_sentence(r, 500000),
                     pw.base_rate_coverage_sentence(r)):
            if said:
                low = said.lower()
                assert not any(word in low for word in banned), said


# ----------------------------------------------------------- the built file


def test_the_committed_table_records_what_it_excluded():
    cov = br.coverage()
    assert cov["skipped_segregated"] >= 40, cov
    assert cov["min_funds"] == 8
    assert cov["as_of"]


def test_the_table_covers_the_categories_the_screen_can_show():
    """A base rate that exists for six categories is not a feature."""
    assert len(br.all_rates()) >= 40


def test_a_small_but_real_risk_is_not_rounded_down_to_never():
    """Flexi Cap lost money in 0.4% of five-year stretches. Rounded, that is
    "0 of every 100" — which reads as *it cannot happen*. It is about one
    stretch in 250, and somebody is in it."""
    assert pw._out_of_hundred(0.004) == "fewer than 1"
    assert pw._out_of_hundred(0.0) == "none"
    assert pw._out_of_hundred(0.203) == "20"
    # 0.6% rounds to 1, and "1 of every 100" is a fair rendering of it.
    assert pw._out_of_hundred(0.006) == "1"
    assert pw._out_of_hundred(0.0049) == "fewer than 1"
    # And it shows up in the sentence a reader actually sees.
    flexi = br.for_category("Equity Scheme", "Flexi Cap Fund")
    said = pw.base_rate_sentence(flexi)
    assert "0 of every 100" not in said, said
