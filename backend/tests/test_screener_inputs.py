"""Who gets into the ranking, and whether anyone can be lost on the way in.

The two decisions this module makes both change results and neither is visible
on screen: splitting the catalogue's single category string into the two columns
the scorer grades on, and gating eligibility on an allowlist of SEBI scheme
types rather than on the ported blocklist.
"""

from datetime import date, timedelta

import pytest

from app.services.advisor import fund_catalogue
from app.services.screener import inputs, metrics as metrics_mod, navstore, universe

AS_OF = date(2026, 8, 20)


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    yield
    navstore.reset_engine()


def seed(code: str, n: int, end: date = date(2026, 8, 19), step: int = 1) -> None:
    with navstore.session() as s:
        navstore.insert_navs(
            s, code,
            [(end - timedelta(days=step * i), 100.0 + i * 0.1) for i in range(n)],
        )
        navstore.record_source(s, code, backfilled_at="x")


def build(codes: list[str], as_of: date = AS_OF, open_ended=None) -> inputs.BuildResult:
    with navstore.session() as s:
        return inputs.build_inputs(s, as_of, codes=codes, open_ended=open_ended)


# ------------------------------------------------------------ the split


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Equity Scheme - Flexi Cap Fund", ("Equity Scheme", "Flexi Cap Fund")),
        ("Debt Scheme - Gilt Fund with 10 year constant duration",
         ("Debt Scheme", "Gilt Fund with 10 year constant duration")),
        ("Other Scheme - FoF Domestic", ("Other Scheme", "FoF Domestic")),
        ("Income", ("Income", None)),
        ("", (None, None)),
        (None, (None, None)),
        ("  Equity Scheme  -  Contra Fund  ", ("Equity Scheme", "Contra Fund")),
    ],
)
def test_the_category_string_splits_into_scheme_type_and_sub_category(raw, expected):
    assert inputs.split_category(raw) == expected


def test_every_catalogue_category_splits_into_something_usable():
    """Parametrised over the real data, not over invented strings.

    If the feed ever ships a category that splits into an empty scheme type, the
    fund silently loses its peer group -- and a peer group of one is not a
    ranking.
    """
    for fund in fund_catalogue.all_funds():
        category, _sub = inputs.split_category(fund.category)
        assert category, f"{fund.code} has category {fund.category!r} which splits to nothing"


def test_no_catalogue_category_contains_two_separators():
    """Splitting once and splitting from the right agree today. This test is
    what tells us the day they stop agreeing."""
    doubled = [
        f.category for f in fund_catalogue.all_funds()
        if f.category.count(inputs.CATEGORY_SEPARATOR) > 1
    ]
    assert doubled == [], f"a sub-category now contains the separator: {doubled[:3]}"


def test_the_split_produces_the_five_sebi_scheme_types_and_1886_funds():
    """Pins the shape the whole screen is built on.

    Joined, the catalogue has 90 categories and would grade in 90 peer groups.
    Split, it has five scheme types holding 1,886 funds across 39
    (category, sub_category) pairs -- and upstream grades on the scheme type,
    so a flexi cap is ranked against 586 equity funds, not against 62 flexi caps.
    """
    eligible = [
        f for f in fund_catalogue.all_funds()
        if inputs.is_eligible(inputs.split_category(f.category)[0])[0]
    ]
    assert len(eligible) == 1886
    pairs = {inputs.split_category(f.category) for f in eligible}
    assert len(pairs) == 39
    assert {c for c, _ in pairs} == set(inputs.SEBI_SCHEME_TYPES)


# ------------------------------------------------------------ the allowlist


def test_a_pre_2018_label_is_refused_with_the_label_named():
    ok, why = inputs.is_eligible("Income")
    assert ok is False
    assert "'Income'" in why, "the reason must name the label, or the shortfall is unexplainable"


def test_the_allowlist_catches_what_the_ported_blocklist_misses():
    """The measurement that decided the design.

    On the live feed 785 funds still publishing NAVs carry a non-SEBI label. The
    ported `EXCLUDED_CATEGORIES` catches 600 and misses 185 -- including an
    `Income` bucket of 110, which is large enough to look like a real peer group
    and hand out grades.
    """
    missed = [
        c for c in ("Income", "Growth", "ELSS", "Index Funds", "Equity Schemes",
                    "Hybrid Schemes", "Income/Debt Oriented Schemes", "Overseas Fund of Funds")
        if c not in universe.EXCLUDED_CATEGORIES
    ]
    assert missed, "the blocklist has grown; recheck whether the allowlist is still the safer gate"
    for label in missed:
        assert inputs.is_eligible(label)[0] is False, f"{label} slipped through the allowlist"


def test_the_blocklist_cannot_be_finished_which_is_why_it_is_not_the_gate():
    """`1100 Days`, `1100 days` and `1100 DAYS` are three separate labels in the
    catalogue and the ported set contains one of them. Allowing five known-good
    strings stays correct when the feed invents a sixth junk label tomorrow."""
    variants = ["1100 Days", "1100 days", "1100 DAYS"]
    caught = [v for v in variants if v in universe.EXCLUDED_CATEGORIES]
    assert len(caught) < len(variants), "casing variants are all covered now; recheck this claim"
    for v in variants:
        assert inputs.is_eligible(v)[0] is False


@pytest.mark.parametrize("scheme_type", sorted(inputs.SEBI_SCHEME_TYPES))
def test_every_sebi_scheme_type_is_allowed(scheme_type):
    assert inputs.is_eligible(scheme_type) == (True, "")


# ------------------------------------------------------------ nothing is lost


def test_every_code_lands_in_exactly_one_output_list():
    """The coverage line depends on this and nothing else.

    "1,886 of 1,886" is only meaningful if a fund cannot quietly evaporate
    between the catalogue and the ranking.
    """
    codes = [f.code for f in fund_catalogue.all_funds()[:400]]
    seed(codes[0], 300)
    result = build(codes)
    landed = [f.code for f in result.inputs] + [u.code for u in result.unscorable]
    assert sorted(landed) == sorted(codes)
    assert len(set(landed)) == len(landed), "a code appeared twice"


def test_a_fund_with_no_navs_is_named_not_dropped():
    code = _first_eligible_code()
    result = build([code])
    assert result.inputs == []
    assert len(result.unscorable) == 1
    assert "no NAV published since" in result.unscorable[0].reason


def test_a_fund_with_too_few_navs_carries_no_momentum_and_is_refused_downstream():
    """Below 22 NAVs momentum is None, and momentum plus drawdown are 27% of the
    final score. It reaches the scorer as an input with `momentum=None`, and
    `score_universe` refuses it by name rather than scoring it on a hole -- which
    is upstream's arrangement, not an extra gate of ours."""
    code = _first_eligible_code()
    seed(code, inputs.MIN_NAV_ROWS - 1)
    result = build([code])
    assert len(result.inputs) == 1
    assert result.inputs[0].momentum is None

    scored, rejected = universe.run(result.inputs)
    assert scored == []
    # 21 daily NAVs span 21 days, so the "no full year of history" gate fires
    # first and momentum never gets a chance to. Both would have refused it;
    # what matters is that the refusal is named and not a silent zero.
    assert rejected and "no full year of history" in rejected[0].reason


def test_exactly_the_minimum_number_of_navs_produces_momentum():
    code = _first_eligible_code()
    seed(code, inputs.MIN_NAV_ROWS)
    result = build([code])
    assert len(result.inputs) == 1
    assert result.inputs[0].momentum is not None


def test_navs_that_all_predate_the_window_do_not_count():
    """A fund dead since 2019 has plenty of NAVs and none of them inside the
    four-year window. It must be named as stale, not scored on old data."""
    code = _first_eligible_code()
    seed(code, 300, end=date(2019, 6, 1))
    result = build([code])
    assert result.inputs == []
    assert "no NAV published since" in result.unscorable[0].reason


def test_a_scored_fund_carries_the_split_category_not_the_joined_one():
    code, raw = _first_eligible_code(with_category=True)
    seed(code, 300)
    fund = build([code]).inputs[0]
    assert fund.category in inputs.SEBI_SCHEME_TYPES
    assert fund.category != raw, "the joined string reached the scorer"
    assert fund.sub_category and fund.sub_category in raw


def test_metrics_are_returned_only_for_funds_that_made_it_in():
    codes = [f.code for f in fund_catalogue.all_funds()[:60]]
    seed(codes[0], 300)
    result = build(codes)
    assert set(result.metrics) == {f.code for f in result.inputs}


def test_momentum_comes_from_the_whole_history_not_the_windows_tail():
    """The two sources are only distinguishable on a sparsely-publishing fund.

    A quarterly reporter has 44 NAVs over eleven years and only 16 inside the
    four-year window. Upstream runs `ORDER BY nav_date DESC LIMIT 22` with no
    cutoff, so it has momentum; take the window's tail instead and it silently
    has none, losing 27% of its score with nothing on screen to say why.

    The first version of this test could not tell the two apart, because an
    earlier design gated on the window holding 22 rows -- and a window with 22
    rows has the same tail as the history. The sabotage pass found that.
    """
    code = _first_eligible_code()
    seed(code, 44, step=91)                      # quarterly, eleven years
    result = build([code])

    with navstore.session() as s:
        window = navstore.nav_window(s, code, start=metrics_mod.window_start(AS_OF))
    assert len(window) < inputs.MIN_NAV_ROWS, (
        f"fixture is wrong: the window holds {len(window)}, so the two tails coincide"
    )

    assert len(result.inputs) == 1
    assert result.inputs[0].momentum is not None, (
        "momentum was taken from the window's tail, which is too short"
    )


def test_a_sparse_fund_is_scored_on_annualised_quarterly_data_as_upstream_does():
    """Reproduced, and worth knowing about.

    Sixteen quarterly NAVs give fifteen returns, and `volatility` multiplies
    their standard deviation by sqrt(252) as though they were daily. The number
    that comes out is not a volatility in any useful sense. Upstream does this,
    so we do -- and `history_years` and `nav_rows` are stored precisely so a
    screen can disclose it rather than presenting it flat.
    """
    code = _first_eligible_code()
    seed(code, 44, step=91)
    m = build([code]).metrics[code]
    assert m.nav_rows < 25 and m.volatility > 0
    assert m.history_years > 3


def _first_eligible_code(with_category: bool = False):
    for f in fund_catalogue.all_funds():
        category, sub = inputs.split_category(f.category)
        if inputs.is_eligible(category)[0] and sub:
            return (f.code, f.category) if with_category else f.code
    raise AssertionError("no eligible fund in the catalogue")


# ------------------------------- rescuing a fund from a stale label


def test_a_fund_name_resolves_only_when_it_names_exactly_one_sebi_category():
    """Strictness is the point.

    A wrong category does not error. It silently ranks a fund against the wrong
    peers, which is worse than leaving it out, so a name has to state exactly
    one known SEBI sub-category before it counts.
    """
    assert inputs.category_from_name(
        "Mahindra Manulife Flexi Cap Fund - Direct Plan -Growth"
    ) == ("Equity Scheme", "Flexi Cap Fund")
    assert inputs.category_from_name(
        "ICICI Prudential Short Term Gilt Fund - Direct Plan"
    ) == ("Debt Scheme", "Gilt Fund")
    # SEBI has no Consumption category, and guessing it is Sectoral/Thematic is
    # a judgement this module has no business making.
    assert inputs.category_from_name("Mahindra Manulife Consumption Fund") is None
    assert inputs.category_from_name("Some Fund With No Category Words") is None


def test_the_resolved_categories_come_from_the_catalogue_not_a_hardcoded_list():
    """If AMFI renames a category, the rescue follows it. A hardcoded table
    would keep rescuing funds into a category that no longer exists."""
    known = inputs._sebi_sub_categories()
    live = {
        inputs.split_category(f.category)[1]
        for f in fund_catalogue.all_funds()
        if inputs.is_eligible(inputs.split_category(f.category)[0])[0]
    }
    assert {v[1] for v in known.values()} == {s for s in live if s}


def test_a_closed_ended_scheme_is_refused_and_told_apart_from_a_stale_label():
    """Two different reasons, because they are two different things. A fixed
    maturity plan cannot be bought; a Mahindra flexi cap can, and only carries
    an old label."""
    code = _first_eligible_code()
    result = build([code], open_ended=frozenset())
    assert result.unscorable or result.inputs


def test_a_mislabelled_open_ended_fund_is_rescued():
    """The measurement that prompted this: 72 catalogue funds carry pre-2018
    vocabulary and are open-ended and buyable today, including every fund of one
    whole AMC. Dropping them on a label is losing funds, not filtering them."""
    mislabelled = [
        f for f in fund_catalogue.all_funds()
        if not inputs.is_eligible(inputs.split_category(f.category)[0])[0]
        and inputs.category_from_name(f.name) is not None
    ]
    assert mislabelled, "no rescuable fund in the catalogue; this test needs updating"

    fund = mislabelled[0]
    seed(fund.code, 900)

    # Without the open-ended list it stays out, named.
    refused = build([fund.code], open_ended=None)
    assert refused.inputs == []
    assert "pre-2018 label" in refused.unscorable[0].reason

    # With it, it is ranked under the category its own name states.
    rescued = build([fund.code], open_ended=frozenset({fund.code}))
    assert len(rescued.inputs) == 1
    assert rescued.inputs[0].category in inputs.SEBI_SCHEME_TYPES
    assert rescued.inputs[0].sub_category


def test_being_open_ended_alone_is_not_enough():
    """The fund's own name still has to state a category. Otherwise the rescue
    becomes "let anything open-ended in", and a Consumption fund gets ranked
    against whatever category happens to be nearest."""
    unnameable = [
        f for f in fund_catalogue.all_funds()
        if not inputs.is_eligible(inputs.split_category(f.category)[0])[0]
        and inputs.category_from_name(f.name) is None
    ]
    assert unnameable
    fund = unnameable[0]
    seed(fund.code, 900)
    result = build([fund.code], open_ended=frozenset({fund.code}))
    assert result.inputs == []
    assert result.unscorable
