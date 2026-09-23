"""Where each holding's money actually sits: equity, overseas, debt, gold.

The traps are all in AMFI's filing, not in the funds. An index fund is filed as
"Other Scheme" whether it tracks the Nifty or government bonds. A US fund can
be filed as an Indian "Sectoral/ Thematic" fund. A gold fund of funds is "FoF
Domestic". Reading the scheme type alone puts each of these in the wrong slice
of the pie, and the pie is the one chart somebody uses to decide whether they
hold too much of something.
"""

from app.services.portfolio.asset_class import classify, from_category


class TestTheObviousCases:
    def test_a_stock_is_equity(self):
        p = from_category("STOCK", "HDFC Bank Ltd.", None)
        assert (p.asset_class, p.category) == ("equity", "Stocks")

    def test_an_equity_scheme_keeps_its_own_category(self):
        p = from_category("MF", "Axis ELSS Tax Saver Fund", "Equity Scheme - ELSS")
        assert (p.asset_class, p.category) == ("equity", "ELSS")

    def test_the_word_fund_is_dropped_from_the_label(self):
        p = from_category("MF", "Parag Parikh Flexi Cap Fund", "Equity Scheme - Flexi Cap Fund")
        assert p.category == "Flexi Cap"

    def test_a_debt_scheme_is_debt(self):
        p = from_category("MF", "ICICI Prudential Corporate Bond Fund", "Debt Scheme - Corporate Bond Fund")
        assert (p.asset_class, p.category) == ("debt", "Corporate Bond")

    def test_a_liquid_fund_is_debt_and_says_liquid(self):
        p = from_category("MF", "HDFC Liquid Fund", "Debt Scheme - Liquid Fund")
        assert (p.asset_class, p.category) == ("debt", "Liquid")

    def test_a_hybrid_is_its_own_slice(self):
        # Neither half. Filing an aggressive hybrid as equity overstates the
        # equity by up to a third of its value; filing it as debt, by two thirds.
        p = from_category("MF", "ICICI Prudential Equity & Debt Fund", "Hybrid Scheme - Aggressive Hybrid Fund")
        assert (p.asset_class, p.category) == ("hybrid", "Aggressive Hybrid")


class TestWhatTheSchemeTypeGetsWrong:
    def test_a_nifty_index_fund_is_equity(self):
        p = from_category("MF", "UTI Nifty 50 Index Fund", "Other Scheme - Index Funds")
        assert (p.asset_class, p.category) == ("equity", "Index Fund")

    def test_a_nasdaq_index_fund_is_overseas_not_indian_equity(self):
        p = from_category("MF", "ICICI Prudential NASDAQ 100 Index Fund", "Other Scheme - Index Funds")
        assert p.asset_class == "international"

    def test_a_us_fund_filed_as_indian_thematic_is_still_overseas(self):
        p = from_category(
            "MF", "ICICI Prudential US Bluechip Equity Fund", "Equity Scheme - Sectoral/ Thematic"
        )
        assert p.asset_class == "international"

    def test_a_government_bond_index_fund_is_debt(self):
        # Filed beside the Nifty trackers as "Index Funds". It holds state
        # government bonds, and a pie that calls it equity is wrong by its
        # entire value.
        p = from_category("MF", "Nippon India Nifty SDL Plus G-Sec Index Fund", "Other Scheme - Index Funds")
        assert p.asset_class == "debt"

    def test_a_debt_etf_is_debt(self):
        p = from_category("MF", "Bharat Bond ETF April 2030", "Exchange Traded Funds (ETFs) - Debt ETF")
        assert p.asset_class == "debt"

    def test_a_gold_fund_of_funds_is_gold(self):
        p = from_category("MF", "Nippon India Gold Savings Fund", "Other Scheme - FoF Domestic")
        assert (p.asset_class, p.category) == ("gold", "Gold")

    def test_a_silver_etf_is_in_the_precious_metals_slice(self):
        p = from_category("MF", "ICICI Prudential Silver ETF", "Exchange Traded Funds (ETFs) - Silver ETF")
        assert (p.asset_class, p.category) == ("gold", "Silver")

    def test_an_overseas_fund_of_funds_is_overseas(self):
        p = from_category("MF", "Franklin India Feeder Franklin US Opportunities Fund", "Other Scheme - FoF Overseas")
        assert p.asset_class == "international"


class TestItRefusesRatherThanGuesses:
    """Unknown goes in its own slice. Guessing equity for an unread holding
    moves real money from one side of the pie to the other and looks exactly
    like a measurement."""

    def test_no_category_at_all(self):
        p = from_category("MF", "Some Fund", None)
        assert (p.asset_class, p.category) == ("other", "Unclassified")

    def test_a_junk_category_from_the_catalogue(self):
        # The catalogue carries a few rows whose category was parsed from the
        # wrong column -- "1100 Days", "Payout".
        assert from_category("MF", "Some FMP", "1100 Days").asset_class == "other"
        assert from_category("MF", "Some Fund", "Payout").asset_class == "other"


class TestResolvingACode:
    def test_a_direct_plan_is_read_from_the_catalogue(self):
        p = classify("MF", "118834", "Mirae Asset Large & Midcap Fund - Direct Plan - Growth")
        assert (p.asset_class, p.category) == ("equity", "Large & Mid Cap")

    def test_a_regular_plan_is_read_through_its_direct_twin(self):
        # The catalogue holds no regular plans. The twin is the same portfolio,
        # so it has the same category -- which the typed-in text cannot promise.
        p = classify("MF", "125494", "SBI SMALL CAP FUND - Regular Plan - Growth")
        assert (p.asset_class, p.category) == ("equity", "Small Cap")

    def test_an_unknown_code_is_unclassified_not_guessed_from_its_name(self):
        p = classify("MF", "999999", "My Mystery Flexi Cap Fund")
        assert p.asset_class == "other"

    def test_a_stock_needs_no_lookup(self):
        p = classify("STOCK", "INFY.NS", "Infosys Ltd.")
        assert (p.asset_class, p.category) == ("equity", "Stocks")
