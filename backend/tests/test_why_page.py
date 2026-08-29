"""`Why` — where every figure on the front page comes from.

§14's coverage rule turned on the app's own dashboard. The content already
existed and was scattered: the track record renders inside `Decide`, the factor
evidence inside `Research`, the coverage numbers inside `Screener`. Scattered,
none of it answers the question somebody actually has — *why should I believe
the number I am looking at* — because that question is asked about the front
page, not about whichever page happens to hold the evidence.

✅ **`Today` is built too, and the split it needed is decided.** `Today` and
`Holdings` were one file, `Portfolio.tsx`, and splitting it is decision 2 in
BUILD.md — a product call about which of the two keeps `/portfolio`. The call:
**`/portfolio` keeps Today**, because `/` redirects there, so it is the app's
front door — and a front door should answer *how am I doing* rather than open
onto a table. Holdings lives at `/portfolio/holdings`, which is where a
deliberate destination belongs: you go there to add a purchase or correct a unit
count, not to glance.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read(rel: str) -> str:
    return (SRC / rel).read_text()


def test_the_page_exists_and_is_routed():
    app = _read("App.tsx")
    assert 'path="/why"' in app
    assert "import('@/pages/Why')" in app


def test_it_is_reachable_from_the_nav_and_from_command_k():
    """One list feeds both, so it cannot be in the nav and missing from ⌘K."""
    app = _read("App.tsx")
    block = app[app.index("const NAV = [") :]
    block = block[: block.index("]")]
    assert "'/why'" in block


class TestEveryFigureNamesItsSource:
    def test_the_sources_are_data_rather_than_prose(self):
        """A paragraph claiming "everything is sourced" is not a coverage rule.
        A list with a row per figure is."""
        page = _read("pages/Why.tsx")
        assert "export const SOURCES" in page

    def test_it_covers_what_the_front_page_actually_shows(self):
        page = _read("pages/Why.tsx")
        rows = page[page.index("export const SOURCES") : page.index("export function Why")]
        for figure in (
            "worth",  # portfolio value
            "XIRR",
            "Expense ratio",
            "fund score",
            "Base rates",
            "Tax",
            "own through your funds",
            "Factor evidence",
        ):
            assert figure in rows, f"no source given for {figure!r}"

    def test_a_source_is_a_file_an_endpoint_or_a_named_study(self):
        """"Our model" is not a source."""
        page = _read("pages/Why.tsx")
        rows = page[page.index("export const SOURCES") : page.index("export function Why")]
        assert "AMFI" in rows
        assert "SEBI" in rows
        assert "IIM Ahmedabad" in rows
        assert "Income Tax Act" in rows
        for weasel in ("our model", "our algorithm", "proprietary"):
            assert weasel not in rows.lower(), f"{weasel!r} is not a source"

    def test_each_figure_also_says_what_it_is_worth(self):
        page = _read("pages/Why.tsx")
        rows = page[page.index("export const SOURCES") : page.index("export function Why")]
        assert rows.count("worth:") == rows.count("figure:"), (
            "a source without a caveat is half the answer"
        )


class TestItLeadsWithTheUncomfortableHalf:
    def test_what_the_app_cannot_do_comes_first(self):
        """A scoreboard that leads with its wins is marketing, and this app's
        central finding is a negative one."""
        page = _read("pages/Why.tsx")
        assert page.index("What this app cannot do") < page.index(
            "How often we have actually been right"
        )

    def test_the_negative_result_is_stated_with_its_numbers(self):
        page = _read("pages/Why.tsx")
        assert "0.9 percentage points" in page
        assert "19 of 44" in page

    def test_the_denominator_travels_with_the_hit_rate(self):
        """43 of 52 and 43 of 44 are different claims."""
        page = _read("pages/Why.tsx")
        assert "{record.wins} of {record.windows} windows" in page

    def test_it_says_when_the_score_is_no_better_than_a_coin(self):
        page = _read("pages/Why.tsx")
        assert "no better than a coin" in page

    def test_it_explains_why_n_a_appears_so_often(self):
        page = _read("pages/Why.tsx")
        assert "0% overlap looks like perfect" in page
        assert "sorts as the cheapest fund" in page


class TestTheHonestyStatesSurviveTheSplit:
    """The three §14 states, checked on the page that now owns the rows.

    This is the acceptance for splitting `Portfolio.tsx`: a rewrite is the most
    reliable way to lose things learned expensively, and each of these was added
    because a real number went wrong quietly.
    """

    def test_a_misnamed_holding_still_says_so(self):
        page = _read("pages/Holdings.tsx")
        assert "misnamed_as" in page, (
            "the scheme code drives every figure and the name is a label; when "
            "they disagree the row is about a different fund and looks correct"
        )

    def test_a_stale_price_still_says_the_value_is_not_current(self):
        page = _read("pages/Holdings.tsx")
        assert re.search(r"not current", page, re.I), (
            "a NAV keeps being served after a scheme stops publishing, so a "
            "frozen price reads as today's value — the most confident wrong "
            "number this app can show"
        )

    def test_a_holding_whose_price_failed_is_still_excluded_by_name(self):
        page = _read("pages/Holdings.tsx")
        assert "price_error" in page

    def test_the_old_single_page_is_gone_rather_than_left_behind(self):
        """A dead copy is a place for the next edit to land unnoticed."""
        assert not (SRC / "pages" / "Portfolio.tsx").exists()

    def test_today_and_holdings_share_one_cached_response(self):
        """Same query key, same fetch: moving between them costs no request."""
        for page in ("pages/Today.tsx", "pages/Holdings.tsx"):
            assert "queryKey: ['portfolio']" in _read(page), page

    def test_today_links_to_the_list_where_somebody_wonders(self):
        today = _read("pages/Today.tsx")
        assert 'to="/portfolio/holdings"' in today

    def test_the_front_door_still_answers_how_am_i_doing(self):
        """`/` redirects to `/portfolio`, so whatever is there is the app's
        opening statement. It keeps the summary and the levers."""
        app = _read("App.tsx")
        assert '<Today />' in app
        today = _read("pages/Today.tsx")
        assert "<Levers />" in today
        assert "Portfolio value" in today
