from app.services.advisor.fund_recommender import _rationale
from app.services.advisor.fund_metrics import FundMetrics
from app.services.advisor.fund_scorer import ScoredFund


def _fund(**overrides) -> ScoredFund:
    defaults = dict(
        cagr_3y=0.146,
        sortino=1.40,
        consistency=0.926,
        downside_capture=0.40,
        alpha=0.071,
        max_drawdown=None,
        volatility=None,
    )
    defaults.update(overrides)
    metrics = FundMetrics(**{k: v for k, v in defaults.items() if k in FundMetrics.__dataclass_fields__})
    return ScoredFund(
        scheme_code="122639",
        scheme_name="Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        category="Equity Scheme - Flexi Cap Fund",
        score=98.0,
        metrics=metrics,
        breakdown={},
    )


def test_no_sentence_starts_with_a_lowercase_letter():
    """The parts were joined with '. ', which turned clause fragments into
    sentences beginning 'beat its benchmark' and 'gave up'."""
    text = _rationale(_fund(), rank=1, peers=9)
    for sentence in [s.strip() for s in text.split('.') if s.strip()]:
        first = sentence[0]
        assert not first.isalpha() or first.isupper(), f"lowercase sentence: {sentence!r}"


def test_a_low_downside_capture_reads_as_good_news():
    """0.40 means the fund fell less than the market, which is the point of the
    metric. 'Gave up 40% of market falls' reads as a loss."""
    text = _rationale(_fund(downside_capture=0.40), rank=1, peers=9)
    assert 'gave up' not in text.lower()
    assert '40%' in text


def test_a_high_downside_capture_is_not_dressed_up_as_good():
    text = _rationale(_fund(downside_capture=1.20), rank=3, peers=9)
    assert '120%' in text


def test_a_fund_that_rose_while_the_market_fell_is_described_not_negated():
    text = _rationale(_fund(downside_capture=-0.6), rank=1, peers=9)
    assert 'rose' in text.lower()
    assert '-60%' not in text


def test_missing_metrics_are_omitted_rather_than_printed_as_none():
    text = _rationale(
        _fund(sortino=None, consistency=None, alpha=None, downside_capture=None),
        rank=2,
        peers=4,
    )
    assert 'None' not in text
    assert 'Ranked 2 of 4' in text


def test_the_text_ends_in_a_single_full_stop():
    text = _rationale(_fund(), rank=1, peers=9)
    assert text.endswith('.')
    assert not text.endswith('..')
