"""The catalogue is the recommendation universe, so what it drops it can never rank.

74 funds Groww sells had no NAV history in this repo, and none of them was in
the catalogue -- so the backfill, which walks the catalogue, could never reach
them. Four separate causes, each measured against mfapi's own scheme list.
"""

import pytest

from scripts.build_fund_catalogue import _DIRECT, _GROWTH, _PAYOUT


class TestDividendYieldIsACategoryNotAPayout:
    """`dividend` matched "Dividend Yield" and killed the whole sub-category.

    Funds that BUY high-dividend-yield stocks are an equity category. They are
    not the dividend payout option of another fund. Eleven growth plans across
    Franklin, Aditya Birla, UTI, ICICI, Tata and HDFC were excluded from the
    recommendation universe by one word.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "Franklin India Dividend Yield Fund - Direct Plan - Growth",
            "Aditya Birla Sun Life Dividend Yield Fund - Direct Plan - GROWTH",
            "UTI - Dividend Yield Fund - Direct Plan - Growth",
            "ICICI Prudential Dividend Yield Fund - Direct Plan - Growth",
            "Tata Dividend Yield Fund - Direct Plan - Growth Option",
            "HDFC DIVIDEND YIELD FUND - Direct Plan - Growth Option",
        ],
    )
    def test_a_dividend_yield_fund_survives_the_filters(self, name):
        assert not _PAYOUT.search(name), f"{name} was excluded as a payout variant"
        assert _DIRECT.search(name) and _GROWTH.search(name)

    @pytest.mark.parametrize(
        "name",
        [
            "HDFC Flexi Cap Fund - Direct Plan - Dividend",
            "Some Fund - Direct Plan - IDCW Payout",
            "Some Fund - Direct Plan - Dividend Reinvestment",
            "Some Fund - Direct Plan - Bonus",
        ],
    )
    def test_a_real_payout_variant_is_still_excluded(self, name):
        """Otherwise one fund occupies several ranks with the same portfolio."""
        assert _PAYOUT.search(name)


class TestCumulativeIsGrowth:
    @pytest.mark.parametrize(
        "name",
        [
            "ICICI Prudential Nifty 50 Index Fund - Direct Plan - Cumulative",
            "ICICI Prudential Equity Savings Fund - Direct Plan - Cumulative",
        ],
    )
    def test_the_word_several_houses_use_for_the_growth_option_counts(self, name):
        assert _GROWTH.search(name), (
            "ICICI and Tata both spell the growth option 'Cumulative'; requiring "
            "the literal word 'Growth' drops a growth plan by any other name"
        )


def test_the_name_filters_are_not_the_only_way_in():
    """The union with Groww's buyable list is what makes the parser optional.

    Five Motilal Oswal index funds carry no plan word in mfapi's name at all --
    `Motilal Oswal BSE Low Volatility Index Fund` -- and no name test can
    recover that. Groww's listing is already filtered to direct plans, growth
    option and available-for-investment, so membership IS the answer rather
    than a guess about it.
    """
    import inspect

    from scripts import build_fund_catalogue

    source = inspect.getsource(build_fund_catalogue.candidates)
    assert "_buyable_codes()" in source, (
        "candidates() must consult the buyable universe, or 16 funds Groww "
        "sells stay outside the catalogue and so outside the backfill"
    )
    assert "_PAYOUT.search(name)" in source, (
        "payout variants must still be excluded on BOTH paths"
    )


def test_a_dropped_candidate_is_counted_rather_than_lost():
    """47 funds passed every filter and vanished at the detail call.

    HDFC Nifty 50 Index Fund, HDFC BSE Sensex Index Fund, SBI Arbitrage Fund —
    all three have thousands of NAV rows at mfapi when probed directly, so
    those were failed requests, not absent funds. Nothing recorded it.
    """
    import inspect

    from scripts import build_fund_catalogue

    source = inspect.getsource(build_fund_catalogue.main)
    assert "dropped" in source and "buyable_dropped" in source, (
        "a candidate that vanishes at the detail call must be counted, and the "
        "count must say how many of them are funds Groww actually sells"
    )
