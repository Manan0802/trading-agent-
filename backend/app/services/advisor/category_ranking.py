"""Ranking one SEBI category, end to end.

Fetches every fund in the category, builds its evidence from NAV history, ranks
the group against itself and attaches the verdict. This is the single entry
point the API uses, so the Research page and a goal's fund plan are always
looking at the same judgement.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from dataclasses import dataclass

from app.services.advisor.fund_catalogue import funds_in_category
from app.services.advisor.fund_evidence import build_evidence
from app.services.advisor.fund_score import (
    ScoredFund,
    UnscorableFund,
    score_peer_group_v2,
)
from app.services.advisor.fund_verdict import Verdict, build_verdict
from app.services.marketdata import mutual_fund

# The cost is network latency, not computation, and every response lands in the
# disk cache, so this is paid once a day per fund.
_FETCH_WORKERS = 24

# Past this, a scheme has stopped publishing rather than sat out a holiday. No
# Indian market closure comes close to a month, so this needs no tuning: it
# separates "wound up" from "shut for Diwali", not "fresh" from "slightly late".
_CLOSED_AFTER_DAYS = 30


@dataclass(frozen=True)
class RankedFund:
    rank: int
    fund: ScoredFund
    verdict: Verdict


@dataclass(frozen=True)
class CategoryRanking:
    category: str
    ranked: list[RankedFund]
    unscorable: list[UnscorableFund]
    # Funds whose direct plan we can price against their regular plan.
    priced: int


def rank_codes(
    label: str,
    entries: list,
    *,
    monthly_sip: float | None = None,
    years: int | None = None,
) -> CategoryRanking:
    """Rank an explicit set of funds against each other.

    Needed because not every asset class is a SEBI category. Gold funds sit
    inside "Other Scheme - FoF Domestic" alongside overseas-equity and silver
    funds, so the gold sleeve is a named subset rather than a category.
    """
    if not entries:
        return CategoryRanking(category=label, ranked=[], unscorable=[], priced=0)

    def load(entry):
        # Retried once, and NEVER dropped silently.
        #
        # This was `except MutualFundDataError: return None, None`, which took
        # the fund out of the ranked list AND out of the unscorable list — it
        # simply evaporated. That matters because **the score is peer-relative**:
        # a fund's number is its standing among the peers that happened to load,
        # so one transient fetch failure moves EVERY OTHER fund's score, and
        # nothing on screen said the peer group had shrunk.
        #
        # Measured on a cold server: the goal plan and the research page returned
        # 87.81 and 88.13 for the same fund in the same category, and on the
        # second call — everything cached — they agreed exactly. Two surfaces
        # disagreeing about one number is the thing this app exists not to do.
        navs = None
        for attempt in range(2):
            try:
                navs = mutual_fund.get_nav_history(entry.code)
                break
            except mutual_fund.MutualFundDataError as exc:
                if attempt == 1:
                    return None, UnscorableFund(
                        scheme_code=entry.code,
                        scheme_name=entry.name,
                        reason=(
                            f"its NAV history could not be fetched ({exc}), so it "
                            "is named here rather than vanishing from a ranking "
                            "everyone else's score is measured against"
                        ),
                    )
        if not navs:
            return None, UnscorableFund(
                scheme_code=entry.code,
                scheme_name=entry.name,
                reason="no NAV history was returned for this scheme",
            )

        # A scheme that wound up or matured keeps its whole history in the feed,
        # so it scores like any other fund and can rank above the ones you can
        # actually buy. Multi Cap carried one that last published 2,772 days
        # ago. Nothing about a stale series looks wrong -- the record is real,
        # it just ended -- which is why this has to be an explicit check.
        behind = (date.today() - navs[-1].date).days
        if behind > _CLOSED_AFTER_DAYS:
            return None, UnscorableFund(
                scheme_code=entry.code,
                scheme_name=entry.name,
                reason=(
                    f"no NAV published since {navs[-1].date}, {behind} days ago, "
                    "so this scheme has almost certainly wound up or matured"
                ),
            )
        return build_evidence(entry.code, entry.name, entry.category, navs), None

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        loaded = list(pool.map(load, entries))
    evidence = [e for e, _ in loaded if e is not None]
    closed = [u for _, u in loaded if u is not None]

    result = score_peer_group_v2(evidence)
    total = len(result.ranked)
    return CategoryRanking(
        category=label,
        ranked=[
            RankedFund(
                rank=i,
                fund=fund,
                verdict=build_verdict(
                    fund.evidence, rank=i, peers=total,
                    monthly_sip=monthly_sip, years=years,
                ),
            )
            for i, fund in enumerate(result.ranked, start=1)
        ],
        # Wound-up schemes are listed with the ones that could not be scored,
        # never dropped in silence: "34 funds" that was really 40 is an
        # omission the reader cannot see.
        unscorable=closed + result.unscorable,
        priced=sum(1 for f in result.ranked if f.evidence.regular_ter is not None),
    )


def rank_category(
    category: str,
    *,
    monthly_sip: float | None = None,
    years: int | None = None,
) -> CategoryRanking:
    """Every fund in a category, ranked, with the reasoning attached.

    `monthly_sip` and `years` are only used to price the commission gap in
    rupees over the user's own horizon; the ranking itself does not depend on
    them, so an anonymous Research page and a specific goal see the same order.
    """
    return rank_codes(
        category,
        funds_in_category(category),
        monthly_sip=monthly_sip,
        years=years,
    )
