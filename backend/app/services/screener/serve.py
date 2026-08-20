"""Reading the latest accepted run back out, in the shape a screen needs.

The pipeline writes percents, because that is what the reference stores and what
the scorer's normalisation was tuned against. Everything leaving this module is
a **fraction**, because `formatPercent()` on the frontend takes a fraction and
multiplies by 100 itself. Hand it 12.6 and it renders "+1260.0%".

That conversion happens here, once, at the boundary -- the same discipline
`advisor/fund_evidence.py` already uses for TER. It matters more than it looks:
a uniform unit slip is invisible to the scorer, because `minmax` and
`rank(pct=True)` are both scale-invariant, so quality, grades and risk tiers all
come out identical. Only an absolute-range assertion catches it, and there is
one in `tests/test_screener_units.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from app.services.screener import navstore

# Below this, a category's "top 3" is not a ranking -- it is the category with a
# fund left out. Contra Fund has 4 members and Balanced Hybrid has 4; publishing
# leaders for them would be a claim the data cannot support. They are named in
# `thin_categories` with their size instead of being silently dropped.
MIN_PEERS_TO_RANK = 8

# Two mega-buckets that are not peer groups in any useful sense. A Nifty 50
# tracker and a Nifty Smallcap 250 Momentum tracker are both "Index Funds", so
# the top of that group tells you which market segment ran, not which fund is
# good. Same for Sectoral/Thematic. The screen says so rather than pretending.
CAVEATED_SUB_CATEGORIES = {
    "Index Funds": (
        "These track different indices, so this ranks which segment ran, not "
        "which fund is better run."
    ),
    "Sectoral/ Thematic": (
        "These bet on different sectors, so this ranks which sector ran, not "
        "which fund is better run."
    ),
    "FoF Domestic": (
        "These invest in different underlying funds, so they are not really "
        "competing with each other."
    ),
}

# Columns the reference shows that we cannot build. Stated on screen rather than
# rendered as a column of dashes: AMFI's average-AUM endpoint needs a strType
# parameter and returns empty for the current quarter, and per-fund minimum
# investment only exists in a distributor feed we have no equivalent of.
MISSING_COLUMNS = ("Fund size (AUM)", "Minimum investment")

# A nightly precompute that silently goes stale serves 200s with old numbers and
# nothing notices. Past this, the screen says how old the data is.
STALE_AFTER_DAYS = 3

# The order categories appear on the page.
ASSET_CLASS_ORDER = {
    "Equity": 0, "Hybrid": 1, "Debt": 2, "Solution Oriented": 3, "Other": 4,
}

ASSET_CLASS_OF = {
    "Equity Scheme": "Equity",
    "Hybrid Scheme": "Hybrid",
    "Debt Scheme": "Debt",
    "Other Scheme": "Other",
    "Solution Oriented Scheme": "Solution Oriented",
}

# The dominance banner fires per asset class, not globally. Globally it is a
# tautology on our universe: the top ten of a list that contains Overnight,
# Liquid, Gilt and Arbitrage funds is structurally guaranteed to be whichever
# equity sub-category ran hardest, every single week. Within a class it is a
# real observation. Note also that at N=10 the reference's own two conditions
# collapse into one -- count >= 3 IS share >= 30% -- so its share clause is dead
# code. Per class with a peer-size floor, both clauses do work.
DOMINANCE_TOP_N = 10
DOMINANCE_MIN_COUNT = 3
DOMINANCE_MIN_SHARE = 0.25

# And a size-adjusted bar, which the reference does not have and which measurement
# said was necessary. On the real universe the unadjusted rule fires for
# "Retirement Fund, 8 of the top 10 Solution Oriented funds" -- but Retirement
# Fund IS 74% of that class, so 8 of 10 is very slightly better than chance
# (lift 1.1x) and the banner would be reporting arithmetic as news.
#
# Lift is the sub-category's share of the top ten divided by its share of the
# class. At 2.0 a group has to be twice as concentrated at the top as it is in
# the population. That keeps Credit Risk Fund (17.2x) and Multi Asset Allocation
# (5.0x), and drops Retirement Fund. Sectoral/Thematic at 2.1x survives, which is
# right -- it is 43% of equity and takes 90% of the top ten.
DOMINANCE_MIN_LIFT = 2.0


class NoCompletedRun(Exception):
    """Nothing has finished scoring yet. The caller must say so, not serve zero rows."""

    def __init__(self, progress: dict):
        self.progress = progress
        funds = progress.get("funds", 0)
        super().__init__(
            f"the fund screener is rebuilding its NAV history "
            f"({funds:,} of 4,957 funds so far)"
        )


def _pct(value) -> float | None:
    """A stored percent to a wire fraction. None and NaN stay None."""
    if value is None:
        return None
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        return None
    return v / 100.0


# `_rolling` returns 0.0 when no complete window exists, which is upstream's
# sentinel and fine inside the scorer -- `safe_float` would have made it 0.0
# anyway. It is not fine on a screen. Measured on the real universe: 364 funds
# show "Roll 3Y +0.0%", and all 364 of them are under three years old. A reader
# sees a fund that returned nothing over three years; the truth is that it has
# not existed for three years.
#
# So a horizon the fund has not lived through comes back None and renders as a
# dash. Same discipline as `reasons._MIN_YEARS_FOR`, and for the same reason.
_ROLLING_NEEDS_YEARS = {
    "roll3y": 3.0,
    "roll1y": 1.0,
    "roll6m": 0.5,
    "roll3m": 0.25,
    "roll1m": 1.0 / 12,
}


def _rolling(value, column: str, history_years) -> float | None:
    """A rolling figure as a fraction, or None if the window never completed."""
    if value is None:
        return None
    needed = _ROLLING_NEEDS_YEARS.get(column)
    if needed is not None:
        if history_years is None:
            return None
        if float(history_years) < needed and float(value) == 0.0:
            return None
    return _pct(value)


def _plain(value) -> float | None:
    """A stored value that is already unitless. NaN still becomes None."""
    if value is None:
        return None
    v = float(value)
    return None if (math.isnan(v) or math.isinf(v)) else v


@dataclass(frozen=True)
class ScreenedFund:
    scheme_code: str
    name: str
    fund_house: str
    category: str
    sub_category: str | None
    asset_class: str
    rank: int
    category_rank: int
    fund_score: float
    grade: str | None
    peer_median: float | None
    peer_size: int | None
    returns_1m: float | None
    returns_3m: float | None
    returns_6m: float | None
    returns_1y: float | None
    returns_3y: float | None
    rolling_1m: float | None
    rolling_3m: float | None
    rolling_6m: float | None
    rolling_1y: float | None
    rolling_3y: float | None
    sortino: float | None
    volatility: float | None
    max_drawdown: float | None
    worst_30d: float | None
    momentum_signal: float | None
    drawdown_signal: float | None
    risk_score: float | None
    risk_tier: str | None
    history_years: float | None
    nav_rows: int | None
    is_new: bool


@dataclass(frozen=True)
class CategoryGroup:
    category: str
    sub_category: str | None
    asset_class: str
    peer_size: int
    caveat: str | None
    funds: list[ScreenedFund]


@dataclass(frozen=True)
class ThinCategory:
    category: str
    sub_category: str | None
    peer_size: int


@dataclass(frozen=True)
class Dominance:
    asset_class: str
    sub_category: str
    count: int
    of: int
    share: float
    # How much more concentrated at the top than in the population. Below 2.0
    # the "boom" is the sub-category simply being large.
    lift: float


@dataclass(frozen=True)
class Coverage:
    universe: int
    scored: int
    shown: int
    new_funds: int
    categories_total: int
    categories_ranked: int
    unscorable: list[tuple[str, str]]
    thin_categories: list[ThinCategory]
    missing_columns: list[str] = field(default_factory=lambda: list(MISSING_COLUMNS))
    as_of: date | None = None
    stale_days: int = 0


def latest_run(session) -> dict:
    """The newest accepted run's header, or raise `NoCompletedRun`.

    `completed_at IS NOT NULL` is enforced in `navstore.latest_run_id`; this adds
    the header the coverage line needs.
    """
    run_id = navstore.latest_run_id(session)
    if run_id is None:
        raise NoCompletedRun(navstore.store_stats(session))
    row = session.execute(
        navstore.text(
            "SELECT id, as_of, universe_size, scored, unscorable, note "
            "FROM screener_run WHERE id = :i"
        ),
        {"i": run_id},
    ).one()
    return {
        "id": int(row[0]),
        "as_of": date.fromisoformat(str(row[1])[:10]),
        "universe_size": row[2] or 0,
        "scored": row[3] or 0,
        "unscorable": row[4] or 0,
        "note": row[5],
    }


def _rows(session, run_id: int) -> list[dict]:
    """Every scored fund in the run, joined to the metrics that produced it.

    A LEFT JOIN, not an inner one: a fund could in principle be scored without a
    `screener_input` row if a future change writes them separately, and losing
    rows to a join is exactly the silent shortfall the coverage line exists to
    make impossible.
    """
    return [
        dict(r._mapping)
        for r in session.execute(
            navstore.text(
                "SELECT s.code, s.category, s.sub_category, s.score, s.grade,"
                "       s.peer_median, s.peer_size, s.momentum, s.drawdown,"
                "       s.risk_score, s.risk_tier,"
                "       i.roll1y, i.roll6m, i.roll3m, i.roll1m, i.roll3y,"
                "       i.ret3y, i.ret1y, i.ret6m, i.ret3m, i.ret1m, i.vol, i.sortino,"
                "       i.max_dd, i.worst_30d, i.history_years, i.nav_rows "
                "FROM screener_score s "
                "LEFT JOIN screener_input i ON i.run_id = s.run_id AND i.code = s.code "
                "WHERE s.run_id = :r"
            ),
            {"r": run_id},
        ).all()
    ]


# The reason string `universe.is_scoreable` gives a fund with under a year of
# history. Matching on it is brittle, so `test_screener_serve.py` asserts the
# string still exists in that module -- if it is reworded, that test goes red
# rather than the new-funds list going quietly empty again.
NEW_FUND_REASON = "no full year of history"


def _new_fund_rows(session, run_id: int) -> list[dict]:
    """Funds refused a rank purely for being too young, with their real numbers.

    Joined to `screener_input`, which the pipeline now writes for every fund it
    could measure rather than only for every fund it could score -- a fund with
    four months of history has genuine three-month returns, and a list of names
    with no numbers is not worth showing.

    An INNER join here, deliberately: a fund with no measurable metrics at all is
    not a "new fund", it is a fund with no data, and it belongs in the unscorable
    list where its reason is printed.
    """
    return [
        dict(r._mapping)
        for r in session.execute(
            navstore.text(
                "SELECT u.code, NULL AS category, NULL AS sub_category,"
                "       NULL AS score, NULL AS grade, NULL AS peer_median,"
                "       NULL AS peer_size, NULL AS momentum, NULL AS drawdown,"
                "       NULL AS risk_score, NULL AS risk_tier,"
                "       i.roll1y, i.roll6m, i.roll3m, i.roll1m, i.roll3y,"
                "       i.ret3y, i.ret1y, i.ret6m, i.ret3m, i.ret1m, i.vol, i.sortino,"
                "       i.max_dd, i.worst_30d, i.history_years, i.nav_rows "
                "FROM screener_unscorable u "
                "JOIN screener_input i ON i.run_id = u.run_id AND i.code = u.code "
                "WHERE u.run_id = :r AND u.reason LIKE :like"
            ),
            {"r": run_id, "like": f"%{NEW_FUND_REASON}%"},
        ).all()
    ]


def _is_new(row: dict) -> bool:
    """A fund with no meaningful one-year rolling return has not been around long
    enough to be ranked on its record.

    Note where these actually come from. Upstream scores such funds and then
    splits them out of the table. Ours never reach `screener_score` at all --
    `universe.is_scoreable` refuses them earlier, with the reason "1-year rolling
    return is zero, so there is no full year of history" -- so they arrive
    through `screener_unscorable` instead.

    That difference cost a real bug: this predicate ran over scored rows only,
    where by construction nothing matches, so the new-funds list was always
    empty and 223 recently-launched funds sat in the same undifferentiated
    "unscorable" bucket as 1,640 funds labelled `Income`. A recently launched
    fund is not junk; it is a fund with a short record, and the screen should
    say so.
    """
    value = row.get("roll1y")
    return value is None or float(value) == 0.0


def build(session, catalogue_by_code: dict) -> tuple[list[ScreenedFund], list[ScreenedFund], Coverage]:
    """The whole served universe: ranked funds, new funds, and the coverage line.

    Ranks are computed here over the **unfiltered** universe and carried on the
    row. If the client derived them, "rank 3" would silently become "third of
    whatever is currently showing" the moment anyone applied a filter.
    """
    run = latest_run(session)
    rows = _rows(session, run["id"])

    ranked_rows = [r for r in rows if not _is_new(r)]
    # Recently launched funds never reach `screener_score`, so they have to be
    # collected from the other side. See `_is_new` for why.
    new_rows = [r for r in rows if _is_new(r)] + _new_fund_rows(session, run["id"])

    # Universe rank: score descending, ties broken by the most recent month's
    # return descending. Same tie-break as the reference, and it matters because
    # scores round to four decimals and genuinely collide.
    ranked_rows.sort(key=lambda r: (-(r["score"] or 0.0), -(r["ret1m"] or 0.0)))

    per_category: dict[tuple, int] = {}
    funds: list[ScreenedFund] = []
    for position, row in enumerate(ranked_rows, start=1):
        key = (row["category"], row["sub_category"])
        per_category[key] = per_category.get(key, 0) + 1
        funds.append(_to_fund(row, catalogue_by_code, position, per_category[key]))

    # Sorted by sortino, as the reference does: with no year of record, the best
    # available signal is risk-adjusted return over what history there is.
    new_funds = [
        _to_fund(row, catalogue_by_code, 0, 0, is_new=True)
        for row in sorted(new_rows, key=lambda r: -(r["sortino"] or 0.0))
    ]

    sizes: dict[tuple, int] = {}
    for f in funds:
        sizes[(f.category, f.sub_category)] = sizes.get((f.category, f.sub_category), 0) + 1
    thin = [
        ThinCategory(category=c, sub_category=s, peer_size=n)
        for (c, s), n in sorted(sizes.items())
        if n < MIN_PEERS_TO_RANK
    ]

    unscorable = [
        (r[0], r[1])
        for r in session.execute(
            navstore.text(
                "SELECT code, reason FROM screener_unscorable WHERE run_id = :r "
                "ORDER BY code"
            ),
            {"r": run["id"]},
        ).all()
    ]

    today = date.today()
    coverage = Coverage(
        universe=run["universe_size"],
        scored=len(funds) + len(new_funds),
        shown=len(funds),
        new_funds=len(new_funds),
        categories_total=len(sizes),
        categories_ranked=len(sizes) - len(thin),
        unscorable=unscorable,
        thin_categories=thin,
        as_of=run["as_of"],
        stale_days=max(0, (today - run["as_of"]).days),
    )
    return funds, new_funds, coverage


def _to_fund(
    row: dict, catalogue: dict, rank: int, category_rank: int, is_new: bool = False
) -> ScreenedFund:
    code = row["code"]
    meta = catalogue.get(code)
    # A new fund has no scored row, so its category comes from the catalogue.
    category = row["category"] or _catalogue_category(meta)
    sub_category = row["sub_category"] or _catalogue_sub_category(meta)
    return ScreenedFund(
        scheme_code=code,
        name=getattr(meta, "name", code),
        fund_house=getattr(meta, "fund_house", ""),
        category=category,
        sub_category=sub_category,
        asset_class=ASSET_CLASS_OF.get(category, "Other"),
        rank=rank,
        category_rank=category_rank,
        fund_score=round(float(row["score"] or 0.0), 4),
        grade=row["grade"],
        peer_median=_plain(row["peer_median"]),
        peer_size=row["peer_size"],
        returns_1m=_pct(row["ret1m"]),
        returns_3m=_pct(row["ret3m"]),
        returns_6m=_pct(row["ret6m"]),
        returns_1y=_pct(row["ret1y"]),
        returns_3y=_pct(row["ret3y"]),
        rolling_1m=_rolling(row["roll1m"], "roll1m", row["history_years"]),
        rolling_3m=_rolling(row["roll3m"], "roll3m", row["history_years"]),
        rolling_6m=_rolling(row["roll6m"], "roll6m", row["history_years"]),
        rolling_1y=_rolling(row["roll1y"], "roll1y", row["history_years"]),
        rolling_3y=_rolling(row["roll3y"], "roll3y", row["history_years"]),
        sortino=_plain(row["sortino"]),
        volatility=_pct(row["vol"]),
        max_drawdown=_pct(row["max_dd"]),
        worst_30d=_pct(row["worst_30d"]),
        momentum_signal=_plain(row["momentum"]),
        drawdown_signal=_plain(row["drawdown"]),
        risk_score=_plain(row["risk_score"]),
        risk_tier=row["risk_tier"],
        history_years=_plain(row["history_years"]),
        nav_rows=row["nav_rows"],
        is_new=is_new,
    )


def group_by_category(funds: list[ScreenedFund], per_category: int) -> list[CategoryGroup]:
    """Leaders per (category, sub_category), thin groups excluded.

    Excluded, not truncated: a top-3 of four funds is the category with one
    member left out, and presenting it as a ranking is a claim the data does not
    support. The excluded groups are named in `coverage.thin_categories`.
    """
    buckets: dict[tuple, list[ScreenedFund]] = {}
    for f in funds:
        buckets.setdefault((f.category, f.sub_category), []).append(f)

    groups = []
    for (category, sub_category), members in buckets.items():
        if len(members) < MIN_PEERS_TO_RANK:
            continue
        members.sort(key=lambda f: f.category_rank)
        groups.append(
            CategoryGroup(
                category=category,
                sub_category=sub_category,
                asset_class=ASSET_CLASS_OF.get(category, "Other"),
                peer_size=len(members),
                caveat=CAVEATED_SUB_CATEGORIES.get(sub_category or ""),
                funds=members[:per_category],
            )
        )
    # Equity first, then Hybrid, then the rest. Sorting by asset class name put
    # "Debt - Banking and PSU Fund" at the top of the page, which is a strange
    # thing to lead a fund screen with; alphabetical order is not an opinion
    # about what anyone came here to look at.
    groups.sort(key=lambda g: (ASSET_CLASS_ORDER.get(g.asset_class, 99),
                               g.sub_category or ""))
    return groups


def dominance(funds: list[ScreenedFund]) -> list[Dominance]:
    """Which sub-category is running, per asset class.

    Per class rather than globally: a global top ten over a universe holding
    Overnight, Liquid, Gilt and Arbitrage funds is guaranteed to be whichever
    equity sub-category ran hardest, which is not an observation.
    """
    by_class: dict[str, list[ScreenedFund]] = {}
    for f in funds:
        by_class.setdefault(f.asset_class, []).append(f)

    out = []
    for asset_class, members in by_class.items():
        members.sort(key=lambda f: f.rank)
        top = members[:DOMINANCE_TOP_N]
        if len(top) < DOMINANCE_TOP_N:
            continue
        counts: dict[str, int] = {}
        for f in top:
            if f.sub_category:
                counts[f.sub_category] = counts.get(f.sub_category, 0) + 1
        sizes: dict[str, int] = {}
        for f in members:
            if f.sub_category:
                sizes[f.sub_category] = sizes.get(f.sub_category, 0) + 1
        for sub_category, count in counts.items():
            share = count / len(top)
            population_share = sizes.get(sub_category, 0) / len(members)
            lift = share / population_share if population_share else 0.0
            if (
                count >= DOMINANCE_MIN_COUNT
                and share >= DOMINANCE_MIN_SHARE
                and lift >= DOMINANCE_MIN_LIFT
                and sizes.get(sub_category, 0) >= MIN_PEERS_TO_RANK
            ):
                out.append(
                    Dominance(
                        asset_class=asset_class,
                        sub_category=sub_category,
                        count=count,
                        of=len(top),
                        share=round(share, 4),
                        lift=round(lift, 2),
                    )
                )
    out.sort(key=lambda d: (-d.count, d.asset_class))
    return out


def _catalogue_category(meta) -> str:
    raw = getattr(meta, "category", "") or ""
    return raw.split(" - ", 1)[0] if " - " in raw else raw


def _catalogue_sub_category(meta) -> str | None:
    raw = getattr(meta, "category", "") or ""
    return raw.split(" - ", 1)[1] if " - " in raw else None


# ------------------------------------------------------------------ reasons


def reasons_for_run(session, run_id: int | None = None) -> dict:
    """The "why this fund" bullets for a run, keyed by scheme code.

    Kept separate from `build()` because it is only wanted on the grouped view
    (~195 rows) and on a single expanded row. The flat full-universe response
    ships without them: 1,466 funds' bullets would roughly double a payload that
    is already the reason that endpoint sits on the heavy rate-limit tier.

    Reads the same rows `build()` does and reconstitutes the `ScoredFund` /
    `FundMetrics` pair the claim engine works in. Note those are in PERCENT
    units -- the fraction conversion happens on the way out of `_to_fund`, not
    here, because a bullet reading "+6.2% (3M)" is formatted from the percent.
    """
    from app.services.screener import metrics as metrics_mod
    from app.services.screener import reasons as reasons_mod
    from app.services.screener import universe as universe_mod

    if run_id is None:
        run_id = navstore.latest_run_id(session)
        if run_id is None:
            raise NoCompletedRun(navstore.store_stats(session))

    scored, measured = [], {}
    for row in _rows(session, run_id):
        if _is_new(row):
            continue
        scored.append(
            universe_mod.ScoredFund(
                code=row["code"],
                category=row["category"],
                sub_category=row["sub_category"],
                quality=0.0,
                momentum=float(row["momentum"] or 0.0),
                drawdown=float(row["drawdown"] or 0.0),
                score=float(row["score"] or 0.0),
                in_sample=True,
                grade=row["grade"],
                peer_median=row["peer_median"],
                peer_size=row["peer_size"],
                risk_score=row["risk_score"],
                risk_tier=row["risk_tier"],
            )
        )
        measured[row["code"]] = _metrics_from_row(row)
    return reasons_mod.reasons_for_universe(scored, measured)


def _metrics_from_row(row: dict):
    """A `FundMetrics` rebuilt from a stored run.

    Only the fields the claim engine reads are meaningful; the rest are filled
    with the same zeros `metrics.compute` would produce for an unmeasurable
    series. They are never displayed from here -- `_to_fund` is what the table
    reads -- so a placeholder cannot leak onto the screen.
    """
    from app.services.screener import metrics as metrics_mod

    return metrics_mod.FundMetrics(
        annualized_return=0.0,
        returns_1m=float(row["ret1m"] or 0.0),
        returns_3m=float(row["ret3m"] or 0.0),
        returns_6m=float(row["ret6m"] or 0.0),
        returns_1y=float(row["ret1y"] or 0.0),
        returns_3y=float(row["ret3y"] or 0.0),
        rolling_1m=float(row["roll1m"] or 0.0),
        rolling_3m=float(row["roll3m"] or 0.0),
        rolling_6m=float(row["roll6m"] or 0.0),
        rolling_1y=float(row["roll1y"] or 0.0),
        rolling_3y=float(row["roll3y"] or 0.0),
        volatility=float(row["vol"] or 0.0),
        sharpe=0.0,
        sortino=float(row["sortino"] or 0.0),
        max_drawdown=float(row["max_dd"] or 0.0),
        best_30d=0.0,
        worst_30d=float(row["worst_30d"] or 0.0),
        negative_days_pct=0.0,
        momentum=_plain(row["momentum"]),
        drawdown=_plain(row["drawdown"]),
        history_years=float(row["history_years"] or 0.0),
        nav_rows=int(row["nav_rows"] or 0),
        capped_days=0,
        first_nav_date=None,
        last_nav_date=None,
        nav_fresh=True,
    )
