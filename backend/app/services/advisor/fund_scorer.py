"""Ranks funds against their category peers into a 0-100 score.

Each metric is percentile-ranked *within the peer group* before weighting,
because raw metrics are not comparable in their own units — a Sortino of 1.4
and a downside capture of 0.4 cannot simply be averaged. This is the same
shape licensed agencies use, and it makes the score relative to a real
alternative set rather than an arbitrary absolute bar.

Every score carries a breakdown, so a recommendation can always answer
"why this fund".
"""

from dataclasses import dataclass, field

from app.services.advisor.fund_metrics import FundMetrics

# Weights from the researched methodology. Expense ratio (5%) and manager
# tenure / AUM stability (5%) are omitted: no free structured source exists for
# them in India, and guessing would be worse than leaving them out. The
# remaining weights are renormalised to 100%.
METRIC_WEIGHTS: dict[str, float] = {
    "sortino": 0.35,
    "consistency": 0.25,
    "alpha": 0.15,
    "downside_capture": 0.15,
}

# Smaller is better — the fund gave up less when the market fell.
LOWER_IS_BETTER = {"downside_capture"}

# Without these a fund cannot be judged at all, so it is set aside rather than
# scored on partial evidence.
REQUIRED_METRICS = ("cagr_3y", "sortino", "consistency")

NEUTRAL_SCORE = 50.0


@dataclass(frozen=True)
class FundForScoring:
    scheme_code: str
    scheme_name: str
    category: str
    metrics: FundMetrics


@dataclass(frozen=True)
class ScoredFund:
    scheme_code: str
    scheme_name: str
    category: str
    metrics: FundMetrics
    score: float
    breakdown: dict[str, float]


@dataclass(frozen=True)
class UnscorableFund:
    scheme_code: str
    scheme_name: str
    reason: str


@dataclass
class ScoringResult:
    ranked: list[ScoredFund] = field(default_factory=list)
    unscorable: list[UnscorableFund] = field(default_factory=list)


def _missing_required(metrics: FundMetrics) -> list[str]:
    return [m for m in REQUIRED_METRICS if getattr(metrics, m) is None]


def _percentiles(values: list[float], lower_is_better: bool) -> list[float]:
    """Rank values 0-100 within the group, averaging ties."""
    if len(values) == 1:
        return [NEUTRAL_SCORE]

    order = sorted(range(len(values)), key=lambda i: values[i], reverse=lower_is_better)
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        tied = [order[position]]
        while (
            position + len(tied) < len(order)
            and values[order[position + len(tied)]] == values[order[position]]
        ):
            tied.append(order[position + len(tied)])
        shared = sum(range(position, position + len(tied))) / len(tied)
        for index in tied:
            ranks[index] = shared / (len(values) - 1) * 100
        position += len(tied)
    return ranks


def score_peer_group(funds: list[FundForScoring]) -> ScoringResult:
    result = ScoringResult()

    scorable: list[FundForScoring] = []
    for fund in funds:
        missing = _missing_required(fund.metrics)
        if missing:
            result.unscorable.append(
                UnscorableFund(
                    scheme_code=fund.scheme_code,
                    scheme_name=fund.scheme_name,
                    reason=f"Not enough history to judge (missing {', '.join(missing)})",
                )
            )
        else:
            scorable.append(fund)

    if not scorable:
        return result

    # Only metrics every remaining fund has can be ranked fairly.
    usable = {
        name: weight
        for name, weight in METRIC_WEIGHTS.items()
        if all(getattr(f.metrics, name) is not None for f in scorable)
    }
    total_weight = sum(usable.values())

    percentiles: dict[str, list[float]] = {
        name: _percentiles(
            [getattr(f.metrics, name) for f in scorable], name in LOWER_IS_BETTER
        )
        for name in usable
    }

    for i, fund in enumerate(scorable):
        breakdown = {
            name: percentiles[name][i] * weight / total_weight
            for name, weight in usable.items()
        }
        result.ranked.append(
            ScoredFund(
                scheme_code=fund.scheme_code,
                scheme_name=fund.scheme_name,
                category=fund.category,
                metrics=fund.metrics,
                # Clamped so floating-point drift never renders as "100.0000001".
                score=min(100.0, max(0.0, sum(breakdown.values()))),
                breakdown=breakdown,
            )
        )

    result.ranked.sort(key=lambda f: f.score, reverse=True)
    return result
