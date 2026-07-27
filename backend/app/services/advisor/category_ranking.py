"""Ranking one SEBI category, end to end.

Fetches every fund in the category, builds its evidence from NAV history, ranks
the group against itself and attaches the verdict. This is the single entry
point the API uses, so the Research page and a goal's fund plan are always
looking at the same judgement.
"""

from concurrent.futures import ThreadPoolExecutor
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
    catalogue = funds_in_category(category)
    if not catalogue:
        return CategoryRanking(category=category, ranked=[], unscorable=[], priced=0)

    def load(entry):
        try:
            navs = mutual_fund.get_nav_history(entry.code)
        except mutual_fund.MutualFundDataError:
            # One unreachable scheme drops out of its peer group rather than
            # failing the whole category.
            return None
        return build_evidence(entry.code, entry.name, entry.category, navs)

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        # Ordered map, so a tie is broken identically on every request.
        evidence = [e for e in pool.map(load, catalogue) if e is not None]

    result = score_peer_group_v2(evidence)
    total = len(result.ranked)

    ranked = [
        RankedFund(
            rank=i,
            fund=fund,
            verdict=build_verdict(
                fund.evidence, rank=i, peers=total, monthly_sip=monthly_sip, years=years
            ),
        )
        for i, fund in enumerate(result.ranked, start=1)
    ]

    return CategoryRanking(
        category=category,
        ranked=ranked,
        unscorable=result.unscorable,
        priced=sum(1 for f in result.ranked if f.evidence.regular_ter is not None),
    )
