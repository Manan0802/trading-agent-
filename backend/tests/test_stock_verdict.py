"""`build_stock_verdict` turns a score into the sentence a buyer reads — untested.

Found on pass 55 of the Phase 1 review, by measuring which functions the suite
actually *calls* rather than which modules it *names*. Pass 54 had reported "72
of 72 service modules named by a test", which was true and misleading: six
modules exercise under a third of their functions, and four pure-logic
functions are never named at all. This is one of them, and it is the one that
speaks.

It matters more than its size. `nextrade-stock-scorer-findings` records that a
company with fourteen days of price history once scored 100/100 and was labelled
**"Strong Buy"** — the model awarding its best grade to the thing it had
computed nothing about. `is_scoreable()` now refuses that input, but the verdict
layer is what turns any score into words, and nothing checked what it says.
"""

import pytest

from app.services.advisor.stock_analysis import build_stock_verdict
from app.services.advisor.stock_score import Adjustment, Factor, StockScore


def _score(**over) -> StockScore:
    base = dict(
        ticker="TEST", name="Test Ltd", sector="Energy", benchmark_used="Energy",
        base_total=60.0, adjustment_total=0.0, total=60.0,
        factors={"pe": Factor(score=10.0, detail="P/E of 12.0, below the Energy median of 14.")},
        adjustments=[], range_position=None,
    )
    base.update(over)
    return StockScore(**base)


def test_the_headline_names_the_peer_group_it_was_scored_against():
    """A score out of 100 means nothing without saying "against what".

    Section 14: stocks are scored SECTOR-RELATIVE, never absolute, because this
    project's own medians run from Energy at P/E 10.9 to Consumer Defensive at
    49.3 — an absolute screen is a sector bet wearing a valuation label. The
    verdict has to carry that, or the screen's honesty stops at the API.
    """
    v = build_stock_verdict(_score())
    assert "60" in v.headline
    assert "Energy" in v.headline


def test_a_thin_peer_group_says_so_instead_of_pretending():
    """`_ALL` means the sector had too few peers to median against.

    Silently comparing an Energy company to the whole market and printing the
    same sentence would be the base-rate class widening that section 14 forbids.
    """
    v = build_stock_verdict(_score(benchmark_used="_ALL"))
    assert "whole listed market" in v.headline
    assert "too few peers" in v.headline


def test_unpublished_measures_are_named_in_a_caveat_not_scored_silently():
    """The 100/100 failure lives here in words.

    A company with nothing published scores neutral on everything, and neutral
    across the board can total well. The caveat is what stops the reader taking
    that as evidence — it must say how many measures were missing, out of how
    many, and that they were scored neutral rather than guessed.
    """
    v = build_stock_verdict(_score(factors={
        "pe": Factor(score=5.0, detail="Not published for this company."),
        "roe": Factor(score=5.0, detail="Not published for this company."),
        "pb": Factor(score=8.0, detail="P/B of 1.4, below the Energy median."),
    }))
    assert v.caveat is not None
    assert "2 of 3" in v.caveat
    assert "neutral rather than guessed" in v.caveat
    # and the unpublished ones never appear as if they were findings
    assert not any(p.startswith("Not published") for p in v.points)


def test_a_fully_covered_company_gets_no_caveat():
    assert build_stock_verdict(_score()).caveat is None


def test_the_52_week_position_is_stated_as_a_position_not_a_forecast():
    """"That is where the price sits, not a view on where it goes next."

    Section 5: no tool returns a forecast, so there is nothing to narrate. A
    range position one sentence away from a buy verdict is exactly where a
    forecast would slip in.
    """
    v = build_stock_verdict(_score(range_position=0.83))
    line = next(p for p in v.points if "52-week" in p)
    assert "83%" in line
    assert "not a view on where it goes next" in line


def test_adjustments_carry_their_sign_and_their_reason():
    v = build_stock_verdict(_score(
        adjustments=[Adjustment(name="promoter", points=-5, detail="Promoter holding fell 4pp in a year")],
    ))
    line = next(p for p in v.points if "Promoter" in p)
    assert "(-5 points)" in line
