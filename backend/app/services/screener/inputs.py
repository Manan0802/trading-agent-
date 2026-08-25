"""Deciding which funds enter the ranking, and assembling what the scorer needs.

This is traa's equivalent of upstream's `optimizer_include` column: the gate
between "a code in the catalogue" and "a fund on the screen". `universe.py` is
not touched by any of it -- that module keeps deciding who among the funds
*offered* to it is scoreable, and its `EXCLUDED_CATEGORIES` stays a verbatim
port. This module decides what gets offered.

Two things happen here and both change who competes with whom.

**The category is split.** `fund_catalogue.json` stores one string,
`"Equity Scheme - Flexi Cap Fund"`. Upstream stores two columns, and
`scoring.grade_peer_key()` groups by `category` alone for everything except Debt
and Commodity, which use `(category, sub_category)`. Feed the joined string and
you get 39 peer groups; split it and you get 5, which is what upstream actually
grades on. This is not cosmetic -- it is the difference between a Flexi Cap fund
being graded against 62 flexi caps and against 586 equity funds, and upstream
does the latter.

**Eligibility is an allowlist, not a blocklist.** Measured against the live feed
on 2026-08-20: 785 funds still publishing NAVs carry a category label that is
not a SEBI scheme type -- `Income` (110), `Growth` (21), `ELSS` (16),
`Index Funds` (9) and so on, all pre-2018 vocabulary the feed never cleaned up.
The ported `EXCLUDED_CATEGORIES` catches 600 of those and **misses 185**. An
`Income` peer group of 110 funds is large enough to look like a real ranking and
hand out grades, which is exactly the failure that must not happen quietly.

A blocklist also cannot be finished. The catalogue contains `1100 Days`,
`1100 days` and `1100 DAYS` as three separate labels; the ported set has one of
the three. Allowing five known-good strings is a decision that stays correct
when the feed invents a sixth junk label tomorrow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from app.services.advisor import fund_catalogue
from app.services.screener import metrics as metrics_mod
from app.services.screener import navstore, universe

# The five scheme types SEBI's 2017 categorisation circular defines. Everything
# else in the feed is either pre-2018 vocabulary or outright noise.
SEBI_SCHEME_TYPES = frozenset({
    "Equity Scheme",
    "Debt Scheme",
    "Hybrid Scheme",
    "Other Scheme",
    "Solution Oriented Scheme",
})

# Pre-2018 spellings of the five types above, as they still appear in AMFI's
# feed. Only mechanical renames belong here -- a plural, or SEBI's own earlier
# name for the same class of scheme. Nothing that requires deciding which peer
# group a fund joins: that is what the sub-category beside it already states.
#
# `Index Funds` and `Overseas Fund of Funds` map to Other Scheme because that is
# where SEBI's 2017 circular puts index funds, ETFs and overseas FoFs.
#
# This is a rescue path, not an eligibility widening. A fund matched here must
# still appear in AMFI's open-ended feed, so a closed-ended scheme carrying a
# legacy label stays out exactly as before -- measured: 90 of the 128 live funds
# with a legacy label are closed-ended, and all 90 remain excluded.
LEGACY_SCHEME_TYPES = {
    "Equity Schemes": "Equity Scheme",
    "Hybrid Schemes": "Hybrid Scheme",
    "Debt Schemes": "Debt Scheme",
    "Income/Debt Oriented Schemes": "Debt Scheme",
    "Index Funds": "Other Scheme",
    "Overseas Fund of Funds": "Other Scheme",
}

CATEGORY_SEPARATOR = " - "

# How many NAVs the momentum window needs: 14 scoring days after a 7-day
# warm-up. Read over the fund's ENTIRE history, not the four-year window, because
# that is what upstream's `ORDER BY nav_date DESC LIMIT 22` does. Below it,
# `momentum_drawdown` returns None and `score_universe` reports the fund
# unscorable rather than scoring it on a hole -- momentum and drawdown together
# are 27% of the final number.
MIN_NAV_ROWS = metrics_mod.MOMENTUM_NAV_ROWS


@dataclass(frozen=True)
class BuildResult:
    """What the pipeline needs, with the shortfall named fund by fund."""

    inputs: list[universe.FundInputs]
    unscorable: list[universe.Unscorable]
    metrics: dict[str, metrics_mod.FundMetrics]

    @property
    def considered(self) -> int:
        return len(self.inputs) + len(self.unscorable)


def split_category(raw: str | None) -> tuple[str | None, str | None]:
    """`"Equity Scheme - Flexi Cap Fund"` -> `("Equity Scheme", "Flexi Cap Fund")`.

    Split once, on the first separator only. Verified against all 90 distinct
    catalogue categories: none contains two occurrences, so `split` and
    `rsplit` agree today -- but splitting once is what stays correct if a
    sub-category ever contains a hyphenated phrase.

    A label with no separator has no sub-category. It is returned as the
    category so the caller can name it in a rejection reason; it will not pass
    `is_eligible` unless it happens to be a bare SEBI scheme type.
    """
    if not raw:
        return None, None
    head, sep, tail = raw.partition(CATEGORY_SEPARATOR)
    head = head.strip()
    if not sep:
        return (head or None), None
    return (head or None), (tail.strip() or None)


def is_eligible(category: str | None) -> tuple[bool, str]:
    """Whether a scheme type may enter the ranking, and why not if it may not.

    The reason string is the whole point. A screen that silently drops funds is
    indistinguishable from one that lost them, and "1,886 of 1,886" only means
    something if the shortfall can be named per fund.
    """
    if not category:
        return False, "no category in the catalogue"
    if category not in SEBI_SCHEME_TYPES:
        return False, (
            f"category {category!r} is a pre-2018 label, not a current SEBI scheme type"
        )
    return True, ""


@lru_cache(maxsize=1)
def _sebi_sub_categories() -> dict[str, tuple[str, str]]:
    """Every SEBI sub-category traa already knows, keyed by its lowercase name.

    Derived from the funds that ARE correctly labelled, so it cannot drift from
    the catalogue: if AMFI renames a category, this follows.
    """
    known: dict[str, tuple[str, str]] = {}
    for fund in fund_catalogue.all_funds():
        category, sub_category = split_category(fund.category)
        if is_eligible(category)[0] and sub_category:
            known[sub_category.lower()] = (category, sub_category)
    return known


def category_from_name(name: str) -> tuple[str, str] | None:
    """A fund's real category, read off its own name -- or None if unclear.

    Only used to rescue a fund whose AMFI label is pre-2018 vocabulary. The rule
    is deliberately strict: exactly one known SEBI sub-category phrase must
    appear in the name. "Mahindra Manulife Flexi Cap Fund" resolves; "Mahindra
    Manulife Consumption Fund" does not, because SEBI has no Consumption
    category and guessing it is Sectoral/Thematic is a judgement this module has
    no business making.

    Strictness is the point. A wrong category does not error -- it silently
    ranks a fund against the wrong peers, which is worse than leaving it out.
    """
    lowered = name.lower()
    matches = {
        value for phrase, value in _sebi_sub_categories().items() if phrase in lowered
    }
    return next(iter(matches)) if len(matches) == 1 else None


def build_inputs(
    session,
    as_of: date,
    codes: list[str] | None = None,
    open_ended: frozenset[str] | None = None,
) -> BuildResult:
    """Read the store, compute metrics, and hand the scorer its inputs.

    Every catalogue code lands in exactly one of `inputs` or `unscorable`.
    Nothing is dropped, because the coverage line depends on it.

    Two queries per eligible fund, not one. The four-year window feeds every
    trailing and rolling number; the 22-row tail feeds momentum, over the fund's
    *entire* history with no window cutoff, because that is what upstream's
    `ORDER BY nav_date DESC LIMIT 22` does. For a fund with 22 NAVs inside the
    window the two are identical; for a quarterly-reporting one they are not.
    Measured at well under a second for the whole universe.
    """
    catalogue = fund_catalogue.all_funds()
    if codes is not None:
        wanted = set(codes)
        catalogue = [f for f in catalogue if f.code in wanted]

    window_start = metrics_mod.window_start(as_of)

    inputs: list[universe.FundInputs] = []
    unscorable: list[universe.Unscorable] = []
    computed: dict[str, metrics_mod.FundMetrics] = {}

    for fund in catalogue:
        category, sub_category = split_category(fund.category)
        ok, why = is_eligible(category)

        if not ok:
            # Second chance, for a fund whose label is stale rather than wrong.
            #
            # 3,071 catalogue funds carry pre-2018 vocabulary. Most are genuinely
            # closed -- capital-protection and fixed-maturity series nobody can
            # buy -- but 72 of them are open-ended and real, including every fund
            # of one whole AMC. Dropping those on a label is losing funds, not
            # filtering them.
            #
            # Two conditions, both required. AMFI's open-ended feed has to list
            # the scheme, which is a fact rather than an inference; and the
            # fund's own name has to contain exactly one SEBI sub-category, so
            # the peer group it joins is stated by the fund itself.
            rescued = None
            if open_ended is not None and fund.code in open_ended:
                # The label may be stale only in its *spelling* of the scheme
                # type, with the sub-category beside it already correct --
                # "Equity Schemes - Thematic Fund" is the plural of a SEBI type
                # followed by a real SEBI sub-category. Reading the type off the
                # fund's own category string is stronger evidence than inferring
                # it from the name, so this is tried first. Measured on the live
                # feed: 38 open-ended funds are lost to spelling alone, among
                # them Mirae Asset Great Consumer, Kotak Savings and every
                # `Index Funds` scheme.
                alias = LEGACY_SCHEME_TYPES.get(category)
                if alias is not None and sub_category:
                    rescued = (alias, sub_category)
                else:
                    rescued = category_from_name(fund.name)
            if rescued is None:
                unscorable.append(
                    universe.Unscorable(
                        fund.code,
                        why
                        if open_ended is None or fund.code in open_ended
                        else f"{why}, and it is a closed-ended scheme",
                    )
                )
                continue
            category, sub_category = rescued

        window = navstore.nav_window(session, fund.code, start=window_start)
        if not window:
            unscorable.append(
                universe.Unscorable(
                    fund.code,
                    f"no NAV published since {window_start.isoformat()}",
                )
            )
            continue
        # Deliberately no minimum-rows gate here. An earlier version required 22
        # NAVs *inside the window*, which was an invention -- upstream has no
        # such rule -- and it was self-defeating: the window is a suffix of the
        # history, so once it holds 22 rows its tail IS the history's tail, and
        # the separate momentum query below could never differ from `window[-22:]`.
        # A sabotage that replaced one with the other could not be detected,
        # which is how the redundancy surfaced.
        #
        # The existing gates already name every case, and they are upstream's:
        # too few returns to measure -> momentum is None -> `score_universe`
        # rejects it; under a year of history -> roll1y is 0.0 -> `is_scoreable`
        # rejects it; no recent NAV -> `nav_fresh` is False -> likewise.
        tail = navstore.nav_tail(session, fund.code, MIN_NAV_ROWS)
        m = metrics_mod.compute(window, as_of, momentum_navs=tail)
        computed[fund.code] = m
        inputs.append(
            universe.FundInputs(
                code=fund.code,
                category=category,
                sub_category=sub_category,
                roll1y=m.rolling_1y,
                roll6m=m.rolling_6m,
                roll3m=m.rolling_3m,
                roll1m=m.rolling_1m,
                ret3y=m.returns_3y,
                ret1y=m.returns_1y,
                ret3m=m.returns_3m,
                vol=m.volatility,
                sortino=m.sortino,
                momentum=m.momentum,
                drawdown=m.drawdown,
                nav_fresh=m.nav_fresh,
            )
        )

    return BuildResult(inputs=inputs, unscorable=unscorable, metrics=computed)
