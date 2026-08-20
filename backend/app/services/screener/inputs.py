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


def build_inputs(
    session,
    as_of: date,
    codes: list[str] | None = None,
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
            unscorable.append(universe.Unscorable(fund.code, why))
            continue

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
