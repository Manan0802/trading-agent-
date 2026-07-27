import pytest

from app.services.advisor.stock_score import (
    FACTOR_WEIGHTS,
    StockInputs,
    score_stock,
)


def _inputs(**kw) -> StockInputs:
    d = dict(
        ticker="TEST.NS",
        name="Test Ltd.",
        sector="Technology",
        price=1000.0,
        pe=22.0,
        pb=4.0,
        roe=0.24,
        dividend_yield=0.015,
        eps_ttm=45.0,
        eps_prev=38.0,
        week52_high=1200.0,
        week52_low=800.0,
        promoter_history=[50.0, 50.0, 50.0, 50.0],
    )
    d.update(kw)
    return StockInputs(**d)


_BENCH = {
    "Technology": {"pe": 23.2, "pb": 5.4, "roe": 0.23, "dividend_yield": 0.018, "n": 40},
    "Energy": {"pe": 8.9, "pb": 1.14, "roe": 0.11, "dividend_yield": 0.019, "n": 20},
    "_ALL": {"pe": 22.0, "pb": 3.5, "roe": 0.15, "dividend_yield": 0.012, "n": 400},
}


def test_the_weights_are_declared_and_sum_to_one_hundred():
    assert sum(FACTOR_WEIGHTS.values()) == 100


def test_valuation_is_judged_against_the_sector_not_an_absolute_bar():
    """P/E 22 is cheap for Technology and dear for Energy. An absolute screen
    in India is a sector bet wearing a valuation costume."""
    tech = score_stock(_inputs(sector="Technology", pe=22.0), _BENCH)
    energy = score_stock(_inputs(sector="Energy", pe=22.0), _BENCH)
    assert tech.factors["pe"].score > energy.factors["pe"].score


def test_an_unknown_sector_falls_back_to_the_whole_market():
    result = score_stock(_inputs(sector="Interplanetary Mining"), _BENCH)
    assert result.benchmark_used == "_ALL"
    assert result.total > 0


def test_a_missing_figure_scores_neutral_not_zero():
    """A gap in the feed is not evidence against the company. Scoring it zero
    would quietly rank every well-covered stock above every thinly-covered one."""
    known = score_stock(_inputs(), _BENCH)
    unknown = score_stock(_inputs(pe=None), _BENCH)
    assert unknown.factors["pe"].score == pytest.approx(FACTOR_WEIGHTS["pe"] * 0.5)
    assert unknown.factors["pe"].detail.lower().startswith("not")
    assert abs(unknown.total - known.total) < FACTOR_WEIGHTS["pe"]


def test_a_loss_making_company_is_not_scored_as_infinitely_cheap():
    """A negative P/E is not a bargain, and treating it as a low number would
    put every loss-maker at the top of a value screen."""
    result = score_stock(_inputs(pe=-14.0), _BENCH)
    assert result.factors["pe"].score <= FACTOR_WEIGHTS["pe"] * 0.5


def test_earnings_growth_rewards_the_direction_not_the_level():
    grew = score_stock(_inputs(eps_ttm=50.0, eps_prev=40.0), _BENCH)
    shrank = score_stock(_inputs(eps_ttm=40.0, eps_prev=50.0), _BENCH)
    assert grew.factors["eps_growth"].score > shrank.factors["eps_growth"].score


def test_promoter_selling_is_a_penalty_and_buying_a_bonus():
    """India's dominant equity risk is governance, not valuation. A promoter
    cutting their stake is the signal most worth surfacing."""
    selling = score_stock(_inputs(promoter_history=[62.0, 61.0, 59.0, 56.0]), _BENCH)
    buying = score_stock(_inputs(promoter_history=[56.0, 58.0, 60.0, 62.0]), _BENCH)
    assert any(a.points < 0 for a in selling.adjustments)
    assert any(a.points > 0 for a in buying.adjustments)
    assert buying.total > selling.total


def test_a_small_promoter_move_is_not_flagged():
    steady = score_stock(_inputs(promoter_history=[50.0, 50.2, 50.1, 50.4]), _BENCH)
    assert not any("promoter" in a.name.lower() for a in steady.adjustments)


def test_a_promoterless_company_is_not_penalised():
    """Many of India's largest listed companies have no promoter at all."""
    result = score_stock(_inputs(promoter_history=[]), _BENCH)
    assert not any("promoter" in a.name.lower() for a in result.adjustments)


def test_every_adjustment_is_named_and_carries_its_points():
    result = score_stock(_inputs(promoter_history=[62.0, 60.0, 58.0, 55.0]), _BENCH)
    for adjustment in result.adjustments:
        assert adjustment.name and adjustment.detail
        assert adjustment.points != 0


def test_the_base_and_the_adjustment_are_reported_separately():
    """An adjustment hidden inside a total cannot be questioned."""
    result = score_stock(_inputs(promoter_history=[62.0, 58.0, 56.0, 54.0]), _BENCH)
    assert result.base_total != result.total
    assert result.adjustment_total == pytest.approx(result.total - result.base_total)


def test_the_score_is_bounded():
    great = score_stock(_inputs(pe=5.0, pb=0.6, roe=0.6, eps_ttm=90.0, eps_prev=30.0,
                                promoter_history=[50.0, 54.0, 58.0, 62.0]), _BENCH)
    awful = score_stock(_inputs(pe=180.0, pb=30.0, roe=-0.3, eps_ttm=1.0, eps_prev=40.0,
                                promoter_history=[62.0, 58.0, 54.0, 50.0]), _BENCH)
    assert 0.0 <= awful.total <= great.total <= 100.0


def test_the_position_in_the_52_week_range_is_reported_not_scored_as_momentum():
    """Where a price sits in its range is context for a buyer, not a claim that
    the trend continues."""
    result = score_stock(_inputs(price=1180.0), _BENCH)
    assert result.range_position is not None
    assert 0.9 < result.range_position <= 1.0
    assert "range" not in FACTOR_WEIGHTS
