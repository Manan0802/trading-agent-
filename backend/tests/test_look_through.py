"""The look-through, and the number that stops it from lying by omission.

Someone holding five equity funds owns a few hundred companies, several of them
through four funds at once. HDFC Bank at 7% of one fund, 9% of another and 6% of
a third is ONE bet, and it is invisible on every screen they have.
"""

import pytest

from app.services.marketdata import holdings_store
from app.services.marketdata.fund_holdings import Holding, SchemePortfolio
from app.services.portfolio.look_through import concentrated, look_through

from datetime import date


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_HOLDINGS_DB", str(tmp_path / "holdings.db"))
    holdings_store.save(
        SchemePortfolio(
            scheme_name="Fund A",
            as_of=date(2026, 7, 31),
            covered=95.0,
            holdings=[
                Holding("INE040A01034", "HDFC Bank", "Financial", 10.0),
                Holding("INE002A01018", "Reliance", "Energy", 5.0),
            ],
        )
    )
    holdings_store.save(
        SchemePortfolio(
            scheme_name="Fund B",
            as_of=date(2026, 7, 31),
            covered=95.0,
            holdings=[
                Holding("INE040A01034", "HDFC Bank", "Financial", 8.0),
                Holding("INE009A01021", "Infosys", "IT", 6.0),
            ],
        )
    )
    yield


class TestOneBetNotThree:
    def test_a_company_held_through_two_funds_is_summed(self):
        result = look_through([("Fund A", 100_000.0), ("Fund B", 100_000.0)])
        top = result.companies[0]
        assert top.name == "HDFC Bank"
        # 10% of 1L + 8% of 1L
        assert top.value == pytest.approx(18_000.0)
        assert top.fund_count == 2

    def test_it_names_the_funds_the_exposure_arrives_through(self):
        result = look_through([("Fund A", 100_000.0), ("Fund B", 100_000.0)])
        via = dict(result.companies[0].via)
        assert via == {"Fund A": pytest.approx(10_000.0), "Fund B": pytest.approx(8_000.0)}
        assert result.companies[0].via[0][0] == "Fund A", "heaviest first"

    def test_companies_are_ordered_by_money_not_by_weight(self):
        """A 5% position in a large holding beats a 6% position in a small one."""
        result = look_through([("Fund A", 1_000_000.0), ("Fund B", 10_000.0)])
        assert [c.name for c in result.companies][:2] == ["HDFC Bank", "Reliance"]

    def test_the_uncovered_part_of_a_fund_becomes_no_company(self):
        """Cash, debt and derivatives are not equity in anything."""
        result = look_through([("Fund A", 100_000.0)])
        equity = sum(c.value for c in result.companies)
        assert equity == pytest.approx(15_000.0), "15% of the fund is disclosed equity"
        assert result.covered_value == 100_000.0, (
            "the whole fund was READ; it simply holds 85% in things that are not "
            "named companies — a different fact from not being able to open it"
        )


class TestWhatItCouldNotSee:
    def test_a_fund_with_no_stored_holdings_is_named_not_dropped(self):
        result = look_through([("Fund A", 100_000.0), ("Unknown Fund", 300_000.0)])
        assert result.unopened == ("Unknown Fund",)
        assert result.unopened_value == 300_000.0
        assert result.covered_share == pytest.approx(25.0)

    def test_a_share_is_measured_against_the_whole_portfolio(self):
        """Dividing by the opened part inflates every position by exactly how
        much was missed — worst precisely when coverage is worst."""
        result = look_through([("Fund A", 100_000.0), ("Unknown Fund", 300_000.0)])
        hdfc = result.companies[0]
        assert hdfc.value == pytest.approx(10_000.0)
        assert result.share_of_portfolio(hdfc) == pytest.approx(2.5), (
            "10,000 of 400,000. Against the opened 100,000 it would read 10% — "
            "four times the truth, and indistinguishable from a full answer"
        )

    def test_a_portfolio_we_could_not_open_at_all_reports_zero_coverage(self):
        result = look_through([("Unknown Fund", 500_000.0)])
        assert result.companies == ()
        assert result.covered_share == 0.0
        assert result.unopened_value == 500_000.0

    def test_an_empty_portfolio_is_not_a_division_by_zero(self):
        result = look_through([])
        assert result.covered_share == 0.0
        assert result.total_value == 0.0


class TestConcentration:
    def test_a_stock_past_five_percent_of_everything_is_surfaced(self):
        result = look_through([("Fund A", 100_000.0), ("Fund B", 100_000.0)])
        found = concentrated(result)
        assert [c.name for c in found] == ["HDFC Bank"], (
            "9% of the whole portfolio through two funds that each looked "
            "diversified — a concentration chosen by accident"
        )

    def test_it_does_not_fire_on_a_diversified_portfolio(self):
        result = look_through([("Fund A", 10_000.0), ("Unknown Fund", 990_000.0)])
        assert concentrated(result) == (), (
            "HDFC Bank is 0.1% of this portfolio; firing here would train the "
            "user to ignore the warning"
        )
