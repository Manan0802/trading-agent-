"""Ranking funds against their category peers, weighted by what actually predicts.

The weights below are not a matter of taste. They were set by testing, and the
test is in docs/does-the-score-work.md.

Ranking by past returns was measured over sixty three-year windows and does not
work: the picks beat their category median in 50% of them, and over 54 windows
the quartile ranked *best* went on to return 17.2% against 19.4% for the
quartile ranked worst. That is a coin flip with the sign slightly wrong, which
is the most replicated finding in the literature and is now confirmed on Indian
data with this code.

Ranking by expense ratio, tested the same way, works: the cheapest quartile
returned 20.0% against 17.8% for the dearest, beating it in 45 of 52 windows.
A 2.2 percentage point spread a year, and unlike a performance record it is a
published fee rather than a bet.

So:

**Cost (55%)** — the expense ratio, and the only pillar here with any measured
predictive power. It leads because the evidence says it should.

**Risk (25%)** and **consistency (20%)** — the shape of the record: how deep
the falls went, how often a full three-year holding made money, how bad the
worst one was. These are kept not as forecasts, which they are not, but because
they decide whether somebody stays invested through a bad year, and staying
invested is a real lever even where selection is not.

**Past return is deliberately not a ranking input at all.** It is the one thing
here that was directly tested and directly failed. It is still reported on every
fund, because it is a true fact about the past that a reader is entitled to,
but it does not move a fund up the list.

Also absent: short-horizon momentum, for the same reason and worse.
"""

from dataclasses import dataclass, field

from app.services.advisor.peer_normalise import hybrid

# Longer horizons get more magnitude weight, because over three years a gap in
# returns is signal; over one year it is substantially noise and only the
# ordering is worth trusting.
_W_RANK_3Y = 0.70

PILLAR_WEIGHTS: dict[str, float] = {
    "cost": 0.55,
    "risk": 0.25,
    "consistency": 0.20,
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

    # Cost is the majority of the score and the only pillar with measured
    # predictive power, so a fund AMFI files no TER for is scored neutral on it
    # rather than having the pillar dropped. Dropping it would rank that fund
    # purely on inputs we know do not predict, and let it climb above funds we
    # can actually measure.
    cost = [
        _NEUTRAL if v is None else v
        for v in hybrid([f.direct_ter for f in funds], 0.60, lower_is_better=True)
    ]

    vol = hybrid([f.volatility for f in funds], 0.70, lower_is_better=True)
    dd = hybrid([f.max_drawdown for f in funds], 0.70)
    risk = [
        None if a is None and b is None else 0.6 * (a or 0.5) + 0.4 * (b or 0.5)
        for a, b in zip(vol, dd)
    ]

    return {"consistency": consistency, "cost": cost, "risk": risk}


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
