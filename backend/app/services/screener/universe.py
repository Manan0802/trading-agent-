"""Scoring a whole universe of funds: score, then grade, then tier -- in that order.

`scoring.py` holds the arithmetic. This holds the orchestration around it, which
is just as much part of the method and just as easy to get subtly wrong:

    1. score   quality over the eligible peer group (in-sample), plus anything
               outside it scored against that same distribution (out-of-sample,
               so a fund we merely display cannot shift the percentiles of the
               funds actually being ranked)
    2. grade   percentile bands inside each peer group, with a minimum gap
    3. tier    a risk composite ranked across the entire universe at once,
               because cross-category comparability is the whole point of it

The order is not cosmetic. Grades are percentiles *of the score*, so scoring has
to finish first; risk tiers need `drawdown_score` and `momentum_score`, which
only exist once step 1 has run.

Everything here is a pure function over plain records. No database, no network,
no clock. That is what makes it exhaustively testable, and it is why the NAV
layer in the next phase can be swapped without touching any of this.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from app.services.screener import scoring

# Categories AMFI's feed still carries that are not investable SEBI categories:
# wound-up fixed-maturity series, pre-2018 labels, and a few outright junk
# strings. Ported verbatim -- a fund in one of these must never be scored, let
# alone ranked.
EXCLUDED_CATEGORIES = frozenset({
    "1", "1098 Days", "1099 Days", "1100 Days", "1194 DAYS",
    "54EB Growth", "Annual Dividend", "Compulsory Reinvestment",
    "Direct", "DIRECT", "Formerly Known as IIFL Mutual Fund",
    "FV Rs 32.161", "Gilt", "Half Yearly Dividend",
    "IDF", "Merger of Capex & Energy Opportunities", "Money Market",
})

# Written values are rounded to four decimals upstream, so anything comparing
# our numbers to theirs has to round the same way or it will chase noise in the
# fifteenth decimal place.
SCORE_DECIMALS = 4

# A peer group of one is not a ranking. Those funds keep their score and are
# returned ungraded rather than being handed a grade the group cannot support.
MIN_PEERS_TO_GRADE = 2

# Guards against a divide-by-zero downstream where the peer median is used as a
# denominator; upstream uses the same fallback.
MIN_PEER_MEDIAN = 0.1

_QUALITY_COLUMNS = ("roll1y", "roll6m", "roll3m", "roll1m", "ret3y", "ret1y", "ret3m", "vol")


def safe_float(value) -> float:
    """None, NaN and unparseable values all become 0.0, as upstream does.

    Worth being explicit about: this means a fund missing `ret3y` is scored as
    though it returned zero over three years, not excluded. That is upstream's
    behaviour and we reproduce it; the eligibility filter is what keeps genuinely
    empty records out, not this.
    """
    if value is None:
        return 0.0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(f) or math.isinf(f):
        return 0.0
    return f


@dataclass(frozen=True)
class FundInputs:
    """One fund's metrics, as the scorer needs them."""
    code: str
    category: str | None
    sub_category: str | None
    roll1y: float | None = None
    roll6m: float | None = None
    roll3m: float | None = None
    roll1m: float | None = None
    ret3y: float | None = None
    ret1y: float | None = None
    ret3m: float | None = None
    vol: float | None = None
    sortino: float | None = None
    # From the fourteen-day window. None means the fund has too little NAV
    # history to be scored at all -- see `momentum_drawdown`.
    momentum: float | None = None
    drawdown: float | None = None
    # Whether the fund published a NAV recently enough to be considered live.
    # Upstream enforces this in SQL; here it is an input so this layer stays
    # free of a clock.
    nav_fresh: bool = True


@dataclass(frozen=True)
class ScoredFund:
    code: str
    category: str | None
    sub_category: str | None
    quality: float
    momentum: float
    drawdown: float
    score: float
    in_sample: bool
    grade: str | None = None
    peer_median: float | None = None
    peer_size: int | None = None
    risk_score: float | None = None
    risk_tier: str | None = None


@dataclass(frozen=True)
class Unscorable:
    code: str
    reason: str


def is_scoreable(fund: FundInputs) -> tuple[bool, str]:
    """Whether a fund may enter the peer distribution, and why not if it may not.

    A reason string rather than a bare False: a screen that silently drops
    funds is indistinguishable from one that lost them, and "1,878 of 1,878"
    is only meaningful if the shortfall can be named.
    """
    if not fund.category:
        return False, "no category"
    if fund.category in EXCLUDED_CATEGORIES:
        return False, f"category '{fund.category}' is not an investable SEBI category"
    if fund.roll1y is None:
        return False, "no 1-year rolling return"
    if safe_float(fund.roll1y) == 0.0:
        return False, "1-year rolling return is zero, so there is no full year of history"
    if not fund.nav_fresh:
        return False, "no NAV published recently, so the fund looks wound up"
    return True, ""


def _quality_frame(funds: list[FundInputs]) -> pd.DataFrame:
    return pd.DataFrame(
        {col: [safe_float(getattr(f, col)) for f in funds] for col in _QUALITY_COLUMNS}
    )


def score_universe(
    eligible: list[FundInputs],
    others: list[FundInputs] | None = None,
) -> tuple[list[ScoredFund], list[Unscorable]]:
    """Quality + final score for every fund that can carry one.

    `eligible` sets the peer distribution and is scored in-sample. `others` are
    scored against that same distribution without joining it, so displaying an
    extra fund never moves anyone else's rank.

    A fund with no momentum/drawdown has too little NAV history to score and is
    returned as unscorable with that reason, never as a zero.
    """
    others = others or []
    scored: list[ScoredFund] = []
    unscorable: list[Unscorable] = []

    if not eligible:
        # Without a reference distribution there is nothing to normalise
        # against; scoring anyone here would invent a scale.
        return [], [Unscorable(f.code, "no eligible peer group to rank against")
                    for f in list(eligible) + list(others)]

    ref = _quality_frame(eligible)
    quality_in = scoring.compute_quality(ref, scoring.hybrid)

    def emit(funds: list[FundInputs], quality: pd.Series, in_sample: bool) -> None:
        for fund, q in zip(funds, quality):
            if fund.momentum is None or fund.drawdown is None:
                unscorable.append(Unscorable(fund.code, "not enough NAV history to score"))
                continue
            value = scoring.final_score(float(q), float(fund.momentum), float(fund.drawdown))
            scored.append(ScoredFund(
                code=fund.code,
                category=fund.category,
                sub_category=fund.sub_category,
                quality=round(float(q), SCORE_DECIMALS),
                momentum=round(float(fund.momentum), SCORE_DECIMALS),
                drawdown=round(float(fund.drawdown), SCORE_DECIMALS),
                score=round(float(value), SCORE_DECIMALS),
                in_sample=in_sample,
            ))

    emit(eligible, quality_in, True)

    if others:
        oos = _quality_frame(others)
        quality_out = scoring.compute_quality(oos, scoring.make_oos_hybrid(ref))
        emit(others, quality_out, False)

    return scored, unscorable


def grade_universe(scored: list[ScoredFund]) -> list[ScoredFund]:
    """Attach a grade and the peer median to every fund, in place of nothing.

    Peer group is `(category, sub_category)` for Debt and Commodity -- where a
    Liquid fund and a Credit Risk fund have no business being compared -- and
    `(category,)` for everything else.

    Groups smaller than two are returned ungraded. A grade is a statement about
    standing among peers, and one fund has no peers.
    """
    # Grouped by position, never by code: scheme codes should be unique, but if
    # two ever collide a code-keyed map would return one record twice and drop
    # the other with no error at all.
    groups: dict[tuple, list[int]] = {}
    for i, fund in enumerate(scored):
        groups.setdefault(scoring.grade_peer_key(fund.category, fund.sub_category), []).append(i)

    out = list(scored)
    for indices in groups.values():
        members = [scored[i] for i in indices]
        if len(members) < MIN_PEERS_TO_GRADE:
            for i, f in zip(indices, members):
                out[i] = replace(f, peer_size=len(members))
            continue
        values = np.array([f.score for f in members], dtype=float)
        median = float(np.median(values)) or MIN_PEER_MEDIAN
        cutoffs = scoring.grade_cutoffs(values)
        for i, f in zip(indices, members):
            out[i] = replace(
                f,
                grade=scoring.grade_from_cutoffs(f.score, *cutoffs),
                peer_median=round(median, SCORE_DECIMALS),
                peer_size=len(members),
            )
    return out


def assign_risk_tiers(
    scored: list[ScoredFund],
    inputs: list[FundInputs],
) -> list[ScoredFund]:
    """Risk composite and tier, ranked across the whole universe at once.

    Not per category, deliberately: the point of this number is that a Large Cap
    fund and a Small Cap fund land in different tiers, which SEBI's riskometer
    cannot express because it marks every equity scheme "Very High".

    Funds missing any of the four inputs keep `risk_tier = None` rather than
    being given a tier the data cannot support.
    """
    by_code = {f.code: f for f in inputs}
    # Positions, not codes -- see grade_universe for why.
    usable = [
        (i, f) for i, f in enumerate(scored)
        if by_code.get(f.code) is not None
        and by_code[f.code].vol is not None
        and by_code[f.code].sortino is not None
    ]
    if not usable:
        return list(scored)

    frame = pd.DataFrame({
        "volatility": [safe_float(by_code[f.code].vol) for _, f in usable],
        "drawdown_score": [f.drawdown for _, f in usable],
        "sortino": [safe_float(by_code[f.code].sortino) for _, f in usable],
        "momentum_score": [f.momentum for _, f in usable],
    })
    values = scoring.risk_score(frame).to_numpy()
    cutoffs = scoring.risk_tier_cutoffs(values)

    out = list(scored)
    for (i, f), v in zip(usable, values):
        out[i] = replace(
            f,
            risk_score=round(float(v), SCORE_DECIMALS),
            risk_tier=scoring.risk_tier_for(float(v), cutoffs),
        )
    return out


def run(
    funds: list[FundInputs],
) -> tuple[list[ScoredFund], list[Unscorable]]:
    """The whole method, end to end: filter, score, grade, tier.

    Returns (scored, unscorable). Every input fund appears in exactly one of the
    two lists -- nothing is silently dropped, which is the only way the coverage
    line on a screen can be trusted.
    """
    eligible: list[FundInputs] = []
    rejected: list[Unscorable] = []
    for fund in funds:
        ok, why = is_scoreable(fund)
        (eligible.append(fund) if ok else rejected.append(Unscorable(fund.code, why)))

    scored, unscorable = score_universe(eligible)
    scored = grade_universe(scored)
    scored = assign_risk_tiers(scored, eligible)
    return scored, rejected + unscorable
