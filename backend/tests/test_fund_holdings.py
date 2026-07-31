"""Tests for reading AMC monthly portfolio disclosures.

Every case here is a trap that actually bit during development, not a
hypothetical. The parser reads spreadsheets written by hand at forty different
asset managers, so its job is to refuse confidently rather than to guess.
"""
import pytest

from app.services.marketdata import fund_holdings as fh
from app.services.marketdata.fund_holdings import (
    Holding,
    HoldingsUnavailable,
    SchemePortfolio,
    _match_key,
    _norm,
    _normalise_weights,
    _parse_sheet,
    _scheme_name,
    common_weight,
)


def _frame(rows):
    import pandas as pd

    return pd.DataFrame(rows)


def _sheet(*, weight_header="% to Net\n Assets",
           weights=(40.0, 25.0, 15.0, 10.0, 5.0),
           title_rows=None, scheme="Example Flexi Cap Fund"):
    """A minimal disclosure sheet in the shape the AMCs actually emit."""
    isins = [
        "INE040A01034", "INE002A01018", "INE154A01025",
        "INE009A01021", "INE090A01021", "INE237A01036",
    ]
    header = [None, "Name of the Instrument", "ISIN", "Industry / Rating",
              "Quantity", weight_header]
    rows = title_rows if title_rows is not None else [
        [scheme, None, None, None, None, None],
        [None, None, None, None, None, None],
    ]
    rows = list(rows) + [header]
    rows.append([None, "Equity & Equity related", None, None, None, None])
    for index, weight in enumerate(weights):
        rows.append([None, f"Company {index}", isins[index], "Banks", 100, weight])
    # A subtotal row with no ISIN, which must be skipped rather than parsed.
    rows.append([None, "Total", None, None, None, sum(weights)])
    return _frame(rows)


class TestNormalisation:
    def test_collapses_the_embedded_newlines_amcs_put_in_headers(self):
        # The real column name. Matching the raw string finds nothing, which is
        # how the first version of the parser silently returned no holdings.
        assert _norm("% to Net\n Assets") == "% TO NET ASSETS"
        assert _norm("Market/Fair Value\n (Rs. in Lakhs)") == (
            "MARKET/FAIR VALUE (RS. IN LAKHS)"
        )

    def test_scheme_key_survives_the_amc_and_amfi_spelling_it_apart(self):
        # AMFI files "SBI Small Cap Fund"; SBI's workbook says "SBI SmallCap Fund".
        assert _match_key("SBI Small Cap Fund") == _match_key("SBI SmallCap Fund")
        assert _match_key("SBI Banking and PSU Fund") == _match_key(
            "SBI Banking & PSU Fund"
        )
        assert _match_key("HDFC Flexi Cap Fund - Direct Plan - Growth") == _match_key(
            "HDFC Flexicap Fund"
        )

    def test_different_funds_still_get_different_keys(self):
        assert _match_key("SBI Small Cap Fund") != _match_key("SBI Mid Cap Fund")
        assert _match_key("SBI Contra Fund") != _match_key("SBI Flexicap Fund")


class TestWeightScale:
    def test_a_fraction_column_is_lifted_to_percent(self):
        scaled = _normalise_weights([0.5, 0.3, 0.15])
        assert scaled == pytest.approx([50.0, 30.0, 15.0])

    def test_a_percent_column_is_left_alone(self):
        assert _normalise_weights([50.0, 30.0, 15.0]) == [50.0, 30.0, 15.0]

    def test_a_column_that_totals_neither_is_refused(self):
        # This is the 100x bug the guard exists for. Returning these numbers
        # would scale every overlap figure in the product by a hundred.
        assert _normalise_weights([500.0, 300.0, 150.0]) is None
        assert _normalise_weights([0.005, 0.003]) is None


class TestSchemeName:
    def test_prefers_the_labelled_name_over_the_letterhead(self):
        frame = _sheet(title_rows=[
            ["SBI Mutual Fund", "017", "Back to Index", None, None, None],
            ["SCHEME NAME :", "SBI MNC Fund", None, None, None, None],
            ["PORTFOLIO STATEMENT AS ON :", "2026-06-30", None, None, None, None],
        ])
        assert _scheme_name(frame, 3) == "SBI MNC Fund"

    def test_letterhead_never_wins_the_unlabelled_fallback(self):
        # "SBI Mutual Fund" is 15 characters and "SBI MNC Fund" is 12, so a
        # plain longest-line-containing-fund rule picks the AMC, not the scheme.
        frame = _sheet(title_rows=[
            ["SBI Mutual Fund", None, None, None, None, None],
            ["SBI MNC Fund", None, None, None, None, None],
        ])
        assert _scheme_name(frame, 2) == "SBI MNC Fund"

    def test_strips_the_portfolio_of_x_as_on_date_wrapper(self):
        # Kotak's title. Left whole, the date lands inside the scheme key, so
        # the key changes every month and the fund never matches at all.
        frame = _sheet(title_rows=[
            ["Portfolio of Kotak Flexicap Fund as on 30 Jun 2026",
             None, None, None, None, None],
            [None, None, None, None, None, None],
        ])
        assert _scheme_name(frame, 2) == "Kotak Flexicap Fund"

    def test_drops_the_regulatory_parenthetical(self):
        frame = _sheet(title_rows=[
            ["Parag Parikh Flexi Cap Fund (An open-ended dynamic equity scheme)",
             None, None, None, None, None],
            [None, None, None, None, None, None],
        ])
        assert _scheme_name(frame, 2) == "Parag Parikh Flexi Cap Fund"


class TestParseSheet:
    def test_reads_a_normal_sheet_and_skips_the_non_holding_rows(self):
        parsed = _parse_sheet(_sheet())
        assert parsed is not None
        assert [h.isin for h in parsed.holdings] == [
            "INE040A01034", "INE002A01018", "INE154A01025",
            "INE009A01021", "INE090A01021",
        ]
        # Section header and Total row carry no ISIN and must not appear.
        assert len(parsed.holdings) == 5
        assert parsed.covered == pytest.approx(95.0)

    def test_accepts_the_sbi_column_name_too(self):
        assert _parse_sheet(_sheet(weight_header="% to AUM")) is not None

    def test_finds_the_header_when_the_column_is_isin_code_not_isin(self):
        # Kotak's spelling. An equality test found no header row here, which
        # reads downstream as "this 118-sheet workbook contains no portfolios".
        frame = _sheet()
        frame.iloc[2, 2] = "ISIN Code"
        parsed = _parse_sheet(frame)
        assert parsed is not None
        assert len(parsed.holdings) == 5

    def test_a_sheet_with_no_isin_column_is_not_a_portfolio(self):
        frame = _frame([
            ["Index", None, None],
            ["Scheme Code", "Scheme Short code", "Scheme Name"],
            ["007", "SMEEF", "SBI ESG Fund"],
        ])
        assert _parse_sheet(frame) is None

    def test_a_sheet_whose_weights_are_nonsense_is_refused_not_rescaled(self):
        assert _parse_sheet(
            _sheet(weights=(400.0, 250.0, 150.0, 100.0, 50.0))
        ) is None

    def test_a_fraction_sheet_is_read_without_being_told_the_amc(self):
        # Nippon and ICICI file fractions, HDFC files percentages, and this
        # parser is never told which. The scale is inferred per sheet, so all
        # three read correctly with no per-AMC branch to keep in sync.
        parsed = _parse_sheet(_sheet(weights=(0.40, 0.25, 0.15, 0.10, 0.05)))
        assert parsed is not None
        assert parsed.holdings[0].weight == pytest.approx(40.0)
        assert parsed.covered == pytest.approx(95.0)

    def test_too_few_holdings_to_be_a_real_portfolio(self):
        assert _parse_sheet(_sheet(weights=(60.0, 35.0))) is None


class TestWorkbook:
    def test_an_unreadable_blob_says_so_rather_than_raising_something_odd(self):
        with pytest.raises(HoldingsUnavailable, match="unreadable workbook"):
            fh._open_workbook(b"this is not a spreadsheet")

    def test_an_uncovered_amc_is_named_in_the_refusal(self):
        with pytest.raises(HoldingsUnavailable, match="Quant"):
            fh.portfolio_for("Quant Small Cap Fund")

    def test_covered_amcs_is_not_empty_so_the_ui_can_say_what_it_reads(self):
        assert fh.covered_amcs()


class TestPerSchemeSources:
    """HDFC files one document per scheme instead of one workbook per AMC."""

    def test_the_cache_key_includes_the_scheme_or_one_fund_answers_for_all(self):
        # The download holds only the named fund. Keyed on the AMC alone, the
        # first HDFC fund fetched would be returned as every other HDFC fund's
        # holdings — a wrong portfolio that looks entirely plausible.
        assert fh._AMCS["HDFC"].per_scheme is True
        assert fh._AMCS["SBI"].per_scheme is False

    def test_the_url_carries_the_scheme_name_without_its_plan_suffix(self):
        urls = fh._hdfc_url(fh.date(2026, 6, 30), "HDFC Flexi Cap Fund - Direct Plan - Growth")
        assert "Monthly%20HDFC%20Flexi%20Cap%20Fund%20-%2030%20June%202026.xlsx" in urls[0]
        assert "Direct" not in urls[0] and "Growth" not in urls[0]

    def test_it_looks_under_the_publication_month_not_the_as_on_month(self):
        # The 30 June report is published in July and hosted under 2026-07.
        assert "/2026-07/" in fh._hdfc_url(fh.date(2026, 6, 30), "HDFC Small Cap Fund")[0]

    def test_a_december_report_rolls_into_the_next_year(self):
        assert "/2027-01/" in fh._hdfc_url(fh.date(2026, 12, 31), "HDFC Small Cap Fund")[0]

    def test_display_name_keeps_casing_because_these_urls_are_case_sensitive(self):
        assert fh._display_name("HDFC Flexi Cap Fund - Direct Plan") == "HDFC Flexi Cap Fund"


class TestCommonWeight:
    def _portfolio(self, pairs):
        return SchemePortfolio(
            scheme_name="X",
            as_of=fh.date.today(),
            holdings=[Holding(isin, isin, None, weight) for isin, weight in pairs],
            covered=sum(w for _, w in pairs),
        )

    def test_takes_the_smaller_weight_because_only_that_much_is_doubled_up(self):
        a = self._portfolio([("INE040A01034", 8.0), ("INE002A01018", 5.0)])
        b = self._portfolio([("INE040A01034", 3.0), ("INE002A01018", 6.0)])
        # 3 doubled up in the first, 5 in the second.
        assert common_weight(a, b) == pytest.approx(8.0)

    def test_no_shared_securities_is_zero(self):
        a = self._portfolio([("INE040A01034", 50.0)])
        b = self._portfolio([("INE009A01021", 50.0)])
        assert common_weight(a, b) == 0.0

    def test_identical_portfolios_return_their_whole_equity_weight(self):
        a = self._portfolio([("INE040A01034", 8.0), ("INE002A01018", 5.0)])
        assert common_weight(a, a) == pytest.approx(13.0)
