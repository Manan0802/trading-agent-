"""Ranking funds against their category peers.

Four pillars, and the choice of pillars is the argument:

**Consistency (35%)** — not the average return, but the shape of the whole
distribution of rolling windows: how often the fund made money over a full
holding period, and how bad its worst one was. A fund averaging 19% that never
handed anyone a losing three-year stretch is a different proposition from one
averaging 22% that lost 8.8% annualised over some of them, and a goal-based
investor is not indifferent between the two.

**Return (25%)** — the level, from rolling means rather than a point-to-point
CAGR. Point-to-point is one observation and both of its dates are accidents;
the rolling mean is every answer the fund could have given a real investor.

**Cost (20%)** — the expense ratio. This is the only input here with replicated
predictive power over future returns, it is published by AMFI, and it is the
one thing on this list that is knowable in advance rather than inferred from
the past. It is weighted accordingly.

**Risk (20%)** — volatility and max drawdown.

Deliberately absent: short-horizon momentum. A fourteen-day signal is the wrong
instrument for choosing a fund somebody will hold for fifteen years, and the
evidence that it survives Indian transaction costs does not exist.
"""

from dataclasses import dataclass, field

from app.services.advisor.peer_normalise import hybrid

# Longer horizons get more magnitude weight, because over three years a gap in
# returns is signal; over one year it is substantially noise and only the
# ordering is worth trusting.
_W_RANK_3Y = 0.70
_W_RANK_1Y = 0.80

PILLAR_WEIGHTS: dict[str, float] = {
    "consistency": 0.35,
    "return": 0.25,
    "cost": 0.20,
    "risk": 0.20,
}

# Without a full three-year window there is no distribution to judge, and a
# fund scored on a shorter record would sit in a list it does not belong in.
REQUIRED_WINDOW = "3y"
REQUIRED_WINDOW_YEARS = 3.0

# Full confidence in a consistency claim needs three non-overlapping windows,
# so nine years of history for a three-year window. Below that the claim is
# shrunk toward neutral in proportion to what is missing — toward neutral, not
# toward zero, because a short record is an absence of evidence rather than
# evidence of a bad fund.
_FULL_CONFIDENCE_SPANS = 3.0
_NEUTRAL = 0.5


def evidence_strength(history_years: float | None) -> float:
    """How far a fund's record can be trusted to describe more than one market."""
    if history_years is None:
        return 1.0
    excess = history_years - REQUIRED_WINDOW_YEARS
    if excess <= 0:
        return 0.0
    return min(1.0, excess / (REQUIRED_WINDOW_YEARS * (_FULL_CONFIDENCE_SPANS - 1)))


@dataclass(frozen=True)
class WindowEvidence:
    mean: float
    worst: float
    share_positive: float
    count: int


@dataclass(frozen=True)
class FundEvidence:
    scheme_code: str
    scheme_name: str
    category: str
    windows: dict[str, WindowEvidence]
    volatility: float | None = None
    max_drawdown: float | None = None
    # Direct-plan TER as a fraction (0.008 = 0.80%). None when AMFI's filing
    # does not cover the scheme.
    direct_ter: float | None = None
    regular_ter: float | None = None
    # Span of the NAV history. Rolling windows overlap almost completely on a
    # short record, so a three-year-old fund's windows all describe the same
    # stretch of market and cannot support a claim about how it behaves in a
    # different one.
    history_years: float | None = None


@dataclass(frozen=True)
class ScoredFund:
    scheme_code: str
    scheme_name: str
    category: str
    score: float
    breakdown: dict[str, float]
    # How much independent evidence the consistency claim rests on, 0-1.
    evidence_strength: float
    evidence: FundEvidence


@dataclass(frozen=True)
class UnscorableFund:
    scheme_code: str
    scheme_name: str
    reason: str


@dataclass
class ScoringResult:
    ranked: list[ScoredFund] = field(default_factory=list)
    unscorable: list[UnscorableFund] = field(default_factory=list)


def _pillar_inputs(funds: list[FundEvidence]) -> dict[str, list[float | None]]:
    """Each pillar as a peer-normalised 0-1 series, or None where unknowable."""
    w3 = [f.windows.get("3y") for f in funds]
    w1 = [f.windows.get("1y") for f in funds]

    # Consistency: how often it worked, and how bad it got when it did not.
    share = hybrid([w.share_positive if w else None for w in w3], _W_RANK_3Y)
    worst = hybrid([w.worst if w else None for w in w3], _W_RANK_3Y)
    consistency = []
    for fund, a, b in zip(funds, share, worst):
        if a is None or b is None:
            consistency.append(None)
            continue
        raw = 0.55 * a + 0.45 * b
        strength = evidence_strength(fund.history_years)
        consistency.append(_NEUTRAL + (raw - _NEUTRAL) * strength)

    # Return: three-year rolling mean leads, one-year supports.
    mean3 = hybrid([w.mean if w else None for w in w3], _W_RANK_3Y)
    mean1 = hybrid([w.mean if w else None for w in w1], _W_RANK_1Y)
    returns = [
        a if b is None else (0.7 * a + 0.3 * b) if a is not None else None
        for a, b in zip(mean3, mean1)
    ]

    cost = hybrid([f.direct_ter for f in funds], 0.60, lower_is_better=True)

    vol = hybrid([f.volatility for f in funds], 0.70, lower_is_better=True)
    dd = hybrid([f.max_drawdown for f in funds], 0.70)
    risk = [
        None if a is None and b is None else 0.6 * (a or 0.5) + 0.4 * (b or 0.5)
        for a, b in zip(vol, dd)
    ]

    return {"consistency": consistency, "return": returns, "cost": cost, "risk": risk}


def score_peer_group_v2(funds: list[FundEvidence]) -> ScoringResult:
    """Rank funds against each other. A peer group of one is not a ranking."""
    result = ScoringResult()
    if not funds:
        return result

    eligible, set_aside = [], []
    for fund in funds:
        if REQUIRED_WINDOW in fund.windows:
            eligible.append(fund)
        else:
            set_aside.append(fund)

    for fund in set_aside:
        result.unscorable.append(
            UnscorableFund(
                scheme_code=fund.scheme_code,
                scheme_name=fund.scheme_name,
                reason=(
                    f"Needs a full {REQUIRED_WINDOW} of history before it can be "
                    "ranked against funds that have one"
                ),
            )
        )

    if len(eligible) < 2:
        for fund in eligible:
            result.unscorable.append(
                UnscorableFund(
                    scheme_code=fund.scheme_code,
                    scheme_name=fund.scheme_name,
                    reason="No peers in this category to rank it against",
                )
            )
        return result

    pillars = _pillar_inputs(eligible)

    scored: list[ScoredFund] = []
    for i, fund in enumerate(eligible):
        breakdown = {
            name: values[i] for name, values in pillars.items() if values[i] is not None
        }
        # Missing pillars are dropped and the rest reweighted rather than
        # scored zero: a gap in our data is not evidence against the fund.
        total_weight = sum(PILLAR_WEIGHTS[name] for name in breakdown)
        if total_weight <= 0:
            result.unscorable.append(
                UnscorableFund(
                    scheme_code=fund.scheme_code,
                    scheme_name=fund.scheme_name,
                    reason="No usable metrics",
                )
            )
            continue
        weighted = sum(PILLAR_WEIGHTS[n] * v for n, v in breakdown.items())
        scored.append(
            ScoredFund(
                scheme_code=fund.scheme_code,
                scheme_name=fund.scheme_name,
                category=fund.category,
                score=round(weighted / total_weight * 100, 2),
                breakdown={n: round(v, 4) for n, v in breakdown.items()},
                evidence_strength=round(evidence_strength(fund.history_years), 4),
                evidence=fund,
            )
        )

    # Scheme code breaks ties so two identical funds never swap places between
    # requests.
    result.ranked = sorted(scored, key=lambda f: (-f.score, f.scheme_code))
    return result
