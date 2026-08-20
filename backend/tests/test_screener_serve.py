"""Reading a run back out: units, ranks, coverage, and the claims we refuse.

The unit boundary is the highest-risk thing in this file. The pipeline stores
percents because that is what the reference stores; `formatPercent()` on the
frontend takes a fraction. Hand it 12.6 and it renders "+1260.0%", which is the
same percent-against-fraction mistake this codebase has now made four times.
"""

from datetime import date, timedelta

import pytest

from app.services.advisor import fund_catalogue
from app.services.screener import inputs as inputs_mod
from app.services.screener import navstore, pipeline, serve, universe

AS_OF = date.today()


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    yield
    navstore.reset_engine()


CATALOGUE = {f.code: f for f in fund_catalogue.all_funds()}


def eligible_codes(n: int) -> list[str]:
    out = []
    for f in fund_catalogue.all_funds():
        category, sub = inputs_mod.split_category(f.category)
        if inputs_mod.is_eligible(category)[0] and sub:
            out.append(f.code)
            if len(out) == n:
                return out
    raise AssertionError("not enough eligible funds")


def seed_and_run(codes, rows: int = 900):
    with navstore.session() as s:
        for i, code in enumerate(codes):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.05 + i * 3)
                 for d in range(rows)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    return pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)


def served(codes=None, rows: int = 900):
    seed_and_run(codes or eligible_codes(30), rows=rows)
    with navstore.session() as s:
        return serve.build(s, CATALOGUE)


# ------------------------------------------------------------------ units


FRACTION_FIELDS = (
    "returns_1m", "returns_3m", "returns_6m", "returns_1y", "returns_3y",
    "rolling_1m", "rolling_3m", "rolling_6m", "rolling_1y", "rolling_3y",
    "volatility", "max_drawdown", "worst_30d",
)
UNIT_INTERVAL_FIELDS = ("fund_score", "momentum_signal", "drawdown_signal", "risk_score")


def test_every_ratio_leaves_as_a_fraction_not_a_percent():
    """The bug this catches renders "+1260.0%" on screen.

    A uniform unit slip is invisible to the scorer: `minmax` and `rank(pct=True)`
    are both scale-invariant, so quality, grades and risk tiers all come out
    identical whether volatility is 12.6 or 0.126. Only an absolute range can
    tell.
    """
    funds, new, _ = served()
    assert funds
    for f in funds + new:
        for field in FRACTION_FIELDS:
            value = getattr(f, field)
            if value is None:
                continue
            assert abs(value) < 2.0, (
                f"{f.scheme_code}.{field} = {value} -- that is a percent, not a fraction"
            )


def test_every_zero_to_one_signal_stays_inside_zero_to_one():
    funds, _, _ = served()
    for f in funds:
        for field in UNIT_INTERVAL_FIELDS:
            value = getattr(f, field)
            if value is None:
                continue
            assert 0.0 <= value <= 1.0, f"{f.scheme_code}.{field} = {value}"


def test_a_nan_becomes_none_rather_than_reaching_the_wire():
    assert serve._pct(float("nan")) is None
    assert serve._pct(float("inf")) is None
    assert serve._plain(float("nan")) is None
    assert serve._pct(12.6) == pytest.approx(0.126)
    assert serve._pct(None) is None


def test_sortino_is_not_divided_by_a_hundred():
    """It is a bare ratio, not a percent. Running it through the percent
    conversion would turn 1.59 into 0.0159 and quietly make every fund look
    identical on the one column that separates them."""
    funds, _, _ = served()
    assert any(abs(f.sortino) > 0.1 for f in funds if f.sortino is not None)


# ------------------------------------------------------------------ ranks


def test_the_rank_is_over_the_whole_universe_and_is_contiguous():
    funds, _, _ = served()
    assert [f.rank for f in funds] == list(range(1, len(funds) + 1))


def test_funds_come_back_ordered_by_score_descending():
    funds, _, _ = served()
    scores = [f.fund_score for f in funds]
    assert scores == sorted(scores, reverse=True)


def test_the_category_rank_restarts_within_each_peer_group():
    funds, _, _ = served()
    seen: dict[tuple, list[int]] = {}
    for f in funds:
        seen.setdefault((f.category, f.sub_category), []).append(f.category_rank)
    for key, ranks in seen.items():
        assert ranks == list(range(1, len(ranks) + 1)), f"{key} ranks are {ranks}"


def test_the_rank_does_not_move_when_a_group_is_filtered_out():
    """If the client derived the rank, "rank 3" would silently become "third of
    whatever is showing" the moment anyone applied a filter."""
    funds, _, _ = served()
    before = {f.scheme_code: f.rank for f in funds}
    equity = [f for f in funds if f.asset_class == "Equity"]
    for f in equity:
        assert f.rank == before[f.scheme_code]


# --------------------------------------------------------------- coverage


def test_nothing_is_lost_between_the_universe_and_the_screen():
    """The coverage line is the only claim on the page that is about the page
    itself. If it does not add up, nothing else on it can be trusted."""
    funds, new, cov = served()
    assert cov.shown == len(funds)
    assert cov.new_funds == len(new)
    assert cov.scored == len(funds) + len(new)
    assert cov.scored + len(cov.unscorable) == cov.universe


def test_the_shortfall_is_named_per_fund():
    _, _, cov = served()
    assert cov.unscorable
    for code, reason in cov.unscorable:
        assert reason and len(reason) > 10, f"{code} has no usable reason"


def test_the_columns_we_cannot_build_are_stated_not_hidden():
    """A column of dashes is worse than no column. AMFI's average-AUM endpoint
    needs a strType parameter and returns empty for the current quarter, and
    per-fund minimum investment lives only in a distributor feed."""
    _, _, cov = served()
    assert "Fund size (AUM)" in cov.missing_columns
    assert "Minimum investment" in cov.missing_columns


def test_the_age_of_the_data_is_always_reported():
    """A nightly precompute that silently goes stale returns 200 with old numbers
    and nothing catches it. This is the most likely production failure of the
    whole feature.

    Asserting `stale_days == 0` on a fresh run proves nothing -- a hardcoded zero
    passes it too, which a sabotage confirmed. The run has to be backdated.
    """
    served()
    with navstore.session() as s:
        s.execute(
            navstore.text("UPDATE screener_run SET as_of = :d WHERE completed_at IS NOT NULL"),
            {"d": (date.today() - timedelta(days=9)).isoformat()},
        )
    with navstore.session() as s:
        _, _, cov = serve.build(s, CATALOGUE)
    assert cov.stale_days == 9, "the screen would show nine-day-old numbers as current"
    assert cov.as_of == date.today() - timedelta(days=9)


def test_a_run_dated_in_the_future_reports_zero_rather_than_a_negative_age():
    """A clock skew between the job host and the web host must not render as
    "-2 days old"."""
    served()
    with navstore.session() as s:
        s.execute(
            navstore.text("UPDATE screener_run SET as_of = :d WHERE completed_at IS NOT NULL"),
            {"d": (date.today() + timedelta(days=2)).isoformat()},
        )
    with navstore.session() as s:
        _, _, cov = serve.build(s, CATALOGUE)
    assert cov.stale_days == 0


def test_an_empty_store_refuses_to_serve_an_empty_ranking():
    """Zero rows behind a 200 is the silent failure this codebase keeps writing
    tests against. The caller has to be able to say "rebuilding", with progress."""
    with navstore.session() as s:
        with pytest.raises(serve.NoCompletedRun) as exc:
            serve.build(s, CATALOGUE)
    assert "rebuilding" in str(exc.value)
    assert "funds" in exc.value.progress


# --------------------------------------------------------- thin categories


def test_a_category_too_small_to_rank_is_excluded_and_named():
    """A top-3 of four funds is the category with one member left out, not a
    ranking. Contra Fund has 4 members and Balanced Hybrid has 4."""
    funds, _, cov = served(eligible_codes(30))
    groups = serve.group_by_category(funds, per_category=5)
    ranked = {(g.category, g.sub_category) for g in groups}
    for thin in cov.thin_categories:
        assert (thin.category, thin.sub_category) not in ranked
        assert thin.peer_size < serve.MIN_PEERS_TO_RANK


def test_the_thin_categories_and_the_ranked_ones_add_up():
    funds, _, cov = served()
    groups = serve.group_by_category(funds, per_category=5)
    assert len(groups) == cov.categories_ranked
    assert cov.categories_ranked + len(cov.thin_categories) == cov.categories_total


def test_the_two_mega_buckets_carry_a_caveat():
    """A Nifty 50 tracker and a Nifty Smallcap 250 Momentum tracker are both
    "Index Funds", so the top of that group says which segment ran, not which
    fund is better run."""
    assert serve.CAVEATED_SUB_CATEGORIES.get("Index Funds")
    assert serve.CAVEATED_SUB_CATEGORIES.get("Sectoral/ Thematic")


def test_a_group_returns_at_most_the_requested_number_of_leaders():
    funds, _, _ = served()
    for group in serve.group_by_category(funds, per_category=3):
        assert len(group.funds) <= 3
        assert [f.category_rank for f in group.funds] == list(range(1, len(group.funds) + 1))


# ------------------------------------------------------------- dominance


def test_dominance_is_size_adjusted_so_a_big_group_is_not_news():
    """Measured on the real universe: the unadjusted rule fires for "Retirement
    Fund, 8 of the top 10 Solution Oriented funds" -- but Retirement Fund IS 74%
    of that class, so 8 of 10 is a lift of 1.1x and the banner would be
    reporting arithmetic as news.
    """
    assert serve.DOMINANCE_MIN_LIFT >= 2.0
    funds, _, _ = served()
    for d in serve.dominance(funds):
        assert d.lift >= serve.DOMINANCE_MIN_LIFT
        assert d.count >= serve.DOMINANCE_MIN_COUNT
        assert d.share >= serve.DOMINANCE_MIN_SHARE


def test_an_asset_class_with_fewer_than_ten_funds_makes_no_dominance_claim():
    """"3 of the top 4" is not a boom, it is a small class."""
    funds, _, _ = served(eligible_codes(30))
    by_class: dict[str, int] = {}
    for f in funds:
        by_class[f.asset_class] = by_class.get(f.asset_class, 0) + 1
    claimed = {d.asset_class for d in serve.dominance(funds)}
    for asset_class in claimed:
        assert by_class[asset_class] >= serve.DOMINANCE_TOP_N


def test_dominance_is_computed_per_asset_class_not_globally():
    """Globally it is a tautology on our universe: a top ten over a list holding
    Overnight, Liquid, Gilt and Arbitrage funds is structurally guaranteed to be
    whichever equity sub-category ran hardest, every week."""
    funds, _, _ = served()
    for d in serve.dominance(funds):
        assert d.asset_class in set(serve.ASSET_CLASS_OF.values())


# ------------------------------------------------------------- new funds


def test_the_reason_string_the_new_fund_list_depends_on_still_exists():
    """`_new_fund_rows` matches on a reason string produced in `universe.py`.
    Reword it there and the new-funds list goes quietly empty again -- which is
    exactly the bug this whole section exists because of."""
    import inspect

    source = inspect.getsource(universe.is_scoreable)
    assert serve.NEW_FUND_REASON in source, (
        f"{serve.NEW_FUND_REASON!r} is no longer the reason universe.py gives; "
        "the new-funds list will be empty until serve.NEW_FUND_REASON is updated"
    )


def test_a_recently_launched_fund_is_shown_as_new_rather_than_as_junk():
    """It was landing in the same undifferentiated bucket as 1,640 funds labelled
    `Income`. A fund with four months of history is not junk; it is a fund with a
    short record, and it has real three-month numbers."""
    codes = eligible_codes(30)
    with navstore.session() as s:
        for i, code in enumerate(codes[:25]):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.05 + i * 3)
                 for d in range(900)],
            )
            navstore.record_source(s, code, backfilled_at="x")
        for i, code in enumerate(codes[25:]):          # four months old
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i)
                 for d in range(120)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)

    with navstore.session() as s:
        funds, new, cov = serve.build(s, CATALOGUE)

    young = {f.scheme_code for f in new}
    assert young == set(codes[25:]), f"expected the five young funds, got {young}"
    for f in new:
        assert f.is_new is True
        assert f.rank == 0, "a new fund has no rank; it was not ranked"
        assert f.returns_3m is not None, "a new fund still has real three-month numbers"
        assert f.history_years is not None and f.history_years < 1.0
        assert f.sub_category, "a new fund still knows its category, from the catalogue"


def test_new_funds_are_ordered_by_sortino():
    """With no year of record, risk-adjusted return over what history there is
    is the best available signal. The reference orders them the same way."""
    _, new, _ = served()
    if len(new) > 1:
        values = [f.sortino or 0.0 for f in new]
        assert values == sorted(values, reverse=True)


def test_a_new_fund_is_not_counted_twice():
    funds, new, cov = served()
    assert not ({f.scheme_code for f in funds} & {f.scheme_code for f in new})


# ------------------------------------------- a window never lived is unknown


def test_a_rolling_window_the_fund_never_lived_is_unknown_not_zero():
    """Found by looking at the actual screen.

    `_rolling` returns 0.0 when no complete window exists. That is upstream's
    sentinel and harmless inside the scorer, where `safe_float` would have made
    it 0.0 anyway. On a screen it is a lie: 364 funds in the real universe were
    rendering "Roll 3Y +0.0%", and every one of them was under three years old.
    A reader sees a fund that returned nothing over three years. The truth is
    that it has not existed for three years.
    """
    codes = eligible_codes(30)
    with navstore.session() as s:
        for i, code in enumerate(codes[:25]):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.05 + i * 3)
                 for d in range(900)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)

    with navstore.session() as s:
        funds, _, _ = serve.build(s, CATALOGUE)

    assert funds
    for f in funds:
        # 900 days is under three years, so no fund here has a 3Y window.
        assert f.history_years < 3.0
        assert f.rolling_3y is None, (
            f"{f.scheme_code} shows Roll 3Y {f.rolling_3y} on "
            f"{f.history_years:.1f} years of history"
        )
        # It HAS lived a year, so that one is a real number.
        assert f.rolling_1y is not None


def test_a_genuine_zero_rolling_return_is_still_shown():
    """The suppression keys on the fund being too young, not on the value being
    zero. A fund with four years of history that genuinely went nowhere must
    still report 0.0% rather than disappearing behind a dash."""
    assert serve._rolling(0.0, "roll3y", 4.0) == 0.0
    assert serve._rolling(0.0, "roll3y", 1.0) is None
    assert serve._rolling(12.6, "roll3y", 1.0) == pytest.approx(0.126), (
        "a young fund with a real non-zero number is not the sentinel case"
    )
    assert serve._rolling(None, "roll3y", 9.0) is None


def test_a_fund_of_unknown_age_reports_no_rolling_figure():
    assert serve._rolling(0.0, "roll1y", None) is None


def test_the_page_leads_with_equity():
    """Sorting groups by asset-class name put "Debt - Banking and PSU Fund" at
    the top of a fund screen. Alphabetical order is not an opinion about what
    anyone came here to look at."""
    funds, _, _ = served()
    groups = serve.group_by_category(funds, per_category=5)
    if not groups:
        pytest.skip("the seed produced no rankable group")
    order = [serve.ASSET_CLASS_ORDER.get(g.asset_class, 99) for g in groups]
    assert order == sorted(order), "asset classes are out of the intended order"
    assert serve.ASSET_CLASS_ORDER["Equity"] == 0
