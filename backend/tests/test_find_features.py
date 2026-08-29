"""`Find`'s two genuinely absent features, and the zero that would undo one of them.

Everything else §3.3 asks for already shipped: category-first, a stated reason
per fund, facets, sorting, coverage including `unscorable`. What did not exist
was overlap at the moment of CHOOSING, and any way to hold two funds side by side.

Structural, and the docstring says so — no React test runner here.
"""

from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read(rel: str) -> str:
    return (SRC / rel).read_text()


class TestOverlapAtTheMomentOfChoosing:
    def test_the_fund_page_asks_how_much_of_it_you_already_own(self):
        assert "<AlreadyOwn schemeCode={data.scheme_code} />" in _read(
            "pages/FundAnalysis.tsx"
        )

    def test_it_renders_n_a_and_never_zero_when_unmeasured(self):
        """§14. 0% reads as perfectly diversified, which is the opposite of "we
        could not tell" — and it is the more attractive of the two readings, so
        a silent zero encourages the purchase it should have questioned."""
        panel = _read("components/AlreadyOwn.tsx")
        assert "data.share_pct !== null" in panel
        assert "'n/a'" in panel
        assert "toFixed(0)}%" in panel

    def test_the_type_allows_null_so_the_zero_cannot_sneak_back(self):
        api = _read("lib/portfolio-api.ts")
        assert "share_pct: number | null" in api

    def test_it_comes_before_the_holdings_list_on_the_page(self):
        """"Does this add anything" is asked before "what is in it"."""
        page = _read("pages/FundAnalysis.tsx")
        assert page.index("<AlreadyOwn") < page.index("<HoldingsPanel")


class TestTheCompareTray:
    def test_it_exists_and_is_capped(self):
        tray = _read("components/CompareTray.tsx")
        assert "export const COMPARE_LIMIT = 4" in tray, (
            "not a rendering limit — a comparison of eight funds is a table, "
            "and a table is what they were already looking at"
        )

    def test_past_return_is_last_and_says_why(self):
        """Putting it at the top would undo §1.1 with layout."""
        tray = _read("components/CompareTray.tsx")
        rows = tray[tray.index("export const COMPARE_ROWS") :]
        assert rows.index("Past 3 years") > rows.index("Category rank")
        assert "put the worse quartile on top" in rows

    def test_a_missing_figure_is_n_a_not_zero(self):
        tray = _read("components/CompareTray.tsx")
        assert "const NA = 'n/a'" in tray
        assert "v === null || v === undefined ? NA" in tray

    def test_nothing_is_marked_best_against_a_single_known_value(self):
        tray = _read("components/CompareTray.tsx")
        assert "known.length >= 2" in tray, (
            "one known value among three blanks is not a winner"
        )

    def test_a_full_tray_can_still_be_emptied(self):
        """A checkbox you cannot uncheck is a trap, and the tray fills in four
        clicks."""
        screener = _read("pages/Screener.tsx")
        assert "disabled={!compared && compareFull}" in screener

    def test_the_shortlist_survives_a_filter_change(self):
        """Whole rows, not codes: looking a fund back up in the filtered list
        silently empties the comparison the moment somebody narrows the search."""
        screener = _read("pages/Screener.tsx")
        assert "useState<ScreenedFund[]>([])" in screener

    def test_the_header_and_the_row_agree_on_the_column_count(self):
        screener = _read("pages/Screener.tsx")
        assert "compare?: boolean" in screener, "HeadRow never learned about it"
        assert "const span = columns.length + 2" in screener, (
            "the expanded DetailRow spans one column short and leaves a gap"
        )
