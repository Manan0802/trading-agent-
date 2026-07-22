"""Turns an asset allocation into named funds and rupee amounts.

"Put 65% in equity" is not actionable. This resolves that into "invest
₹8,000/month in Parag Parikh Flexi Cap Direct Growth", with the reasoning
attached so the pick can be questioned.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from app.services.advisor.fund_metrics import FundMetrics
from app.services.advisor.fund_scorer import (
    FundForScoring,
    ScoredFund,
    ScoringResult,
    score_peer_group,
)
from app.services.advisor.fund_catalogue import codes_for_category
from app.services.advisor.fund_universe import (
    BENCHMARK_BY_ASSET_CLASS,
    UNIVERSE,
    benchmark_for_category,
)

# Below this a monthly SIP is not worth splitting further — most funds set a
# ₹500 or ₹1,000 minimum instalment.
MIN_MONTHLY_SIP = 500.0

# The top pick gets a larger share, but not so much that the basket stops
# being a basket.
_TOP_FUND_SHARE = 0.6

Scorer = Callable[[str], ScoringResult]


@dataclass(frozen=True)
class FundRecommendation:
    asset_class: str
    scheme_code: str
    scheme_name: str
    category: str
    monthly_amount: float
    score: float
    rationale: str
    metrics: FundMetrics


@dataclass(frozen=True)
class SkippedAssetClass:
    asset_class: str
    reason: str


@dataclass
class RecommendationResult:
    recommendations: list[FundRecommendation] = field(default_factory=list)
    skipped: list[SkippedAssetClass] = field(default_factory=list)


def _rationale(fund: ScoredFund, rank: int, peers: int) -> str:
    """One telegraphic sentence per fact, so the readout scans without a legend.

    Each part is a full sentence rather than a clause: joining fragments with
    ". " produced sentences that began "beat its benchmark" and "gave up".
    """
    m = fund.metrics
    parts = [f"Ranked {rank} of {peers} {fund.category.split(' - ')[-1]} funds"]

    if m.cagr_3y is not None:
        parts.append(f"Returned {m.cagr_3y:.1%} a year over 3 years")
    if m.sortino is not None:
        parts.append(f"Sortino {m.sortino:.2f}")
    if m.consistency is not None:
        parts.append(
            f"Beat its benchmark in {m.consistency:.0%} of rolling 3-year windows"
        )
    if m.downside_capture is not None:
        if m.downside_capture < 0:
            # A negative capture means the fund rose while the market fell, so
            # any phrasing built around a percentage of the fall is nonsense.
            parts.append("Rose, on average, when the market fell")
        else:
            # Below 1.00 is the good case, and "gave up 40% of market falls"
            # read as a loss rather than as the protection it describes.
            qualifier = "only " if m.downside_capture < 1 else ""
            parts.append(
                f"Fell {qualifier}{m.downside_capture:.0%} as much as the market "
                "in its down periods"
            )
    if m.alpha is not None:
        parts.append(f"Alpha {m.alpha:+.1%} a year")
    return ". ".join(parts) + "."


def _split(amount: float, count: int) -> list[float]:
    """Weight the top pick more heavily, and make the parts add back exactly."""
    if count == 1:
        return [amount]
    top = round(amount * _TOP_FUND_SHARE)
    return [top, amount - top]


# The universe went from 16 hand-picked codes to a few hundred, and each fund
# needs its own NAV history. Fetched one at a time that took 49 seconds for a
# single category: the cost is entirely network latency, not computation, so
# the fetches overlap. Bounded because the free feed does not deserve a burst
# of hundreds of concurrent requests.
_FETCH_WORKERS = 8


def score_codes(codes: list[str], benchmark_code: str | None) -> ScoringResult:
    """Fetch NAV history for each code and rank them against one another."""
    from app.services.advisor import fund_metrics
    from app.services.marketdata import mutual_fund

    benchmark = (
        mutual_fund.get_nav_history(benchmark_code) if benchmark_code else None
    )

    def load(code: str) -> FundForScoring | None:
        try:
            meta = mutual_fund.get_scheme_meta(code)
            navs = mutual_fund.get_nav_history(code)
        except mutual_fund.MutualFundDataError:
            # One unreachable scheme should not take down a whole category.
            # It drops out of the peer group, which score_peer_group already
            # handles, rather than failing the request.
            return None
        return FundForScoring(
            scheme_code=code,
            scheme_name=meta.scheme_name,
            category=meta.scheme_category,
            metrics=fund_metrics.compute_metrics(navs, benchmark),
        )

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        # Ordered map, so the peer group is built in a stable order and two
        # identical requests cannot rank tied funds differently.
        funds = [f for f in pool.map(load, codes) if f is not None]

    return score_peer_group(funds)


def load_scored_universe(asset_class: str) -> ScoringResult:
    """The peer group behind a goal's allocation for one asset class."""
    return score_codes(
        UNIVERSE[asset_class], BENCHMARK_BY_ASSET_CLASS.get(asset_class)
    )


def score_category(category: str) -> ScoringResult:
    """Every fund in a SEBI category, ranked against its own peers.

    Separate from load_scored_universe because Research browses all ninety
    categories while a goal allocates to only three.
    """
    benchmark_code, _ = benchmark_for_category(category)
    return score_codes(codes_for_category(category), benchmark_code)


def recommend_for_allocation(
    allocation: dict[str, int],
    monthly_sip: float,
    funds_per_class: int = 2,
    scorer: Scorer = load_scored_universe,
    return_skipped: bool = False,
):
    result = RecommendationResult()

    for asset_class, percent in allocation.items():
        if percent <= 0:
            continue

        class_amount = monthly_sip * percent / 100
        if class_amount < MIN_MONTHLY_SIP:
            result.skipped.append(
                SkippedAssetClass(
                    asset_class=asset_class,
                    reason=(
                        f"₹{class_amount:,.0f}/month is below the ₹{MIN_MONTHLY_SIP:,.0f} "
                        "minimum most funds accept"
                    ),
                )
            )
            continue

        ranked = scorer(asset_class).ranked
        if not ranked:
            result.skipped.append(
                SkippedAssetClass(
                    asset_class=asset_class,
                    reason="No fund in this category has enough history to judge",
                )
            )
            continue

        # Narrow the basket rather than recommend instalments too small to place.
        count = min(funds_per_class, len(ranked))
        while count > 1 and class_amount / count < MIN_MONTHLY_SIP:
            count -= 1

        for fund, amount in zip(ranked[:count], _split(class_amount, count)):
            result.recommendations.append(
                FundRecommendation(
                    asset_class=asset_class,
                    scheme_code=fund.scheme_code,
                    scheme_name=fund.scheme_name,
                    category=fund.category,
                    monthly_amount=amount,
                    score=fund.score,
                    rationale=_rationale(
                        fund, ranked.index(fund) + 1, len(ranked)
                    ),
                    metrics=fund.metrics,
                )
            )

    return result if return_skipped else result.recommendations
