"""Turning a goal's asset allocation into named funds and rupee amounts.

"Put 65% in equity" is not something anyone can act on. This resolves it into
"₹8,000 a month into Parag Parikh Flexi Cap Direct Growth", using exactly the
ranking the Research page shows, so a goal and a browse never disagree about
the same fund.

Every pick is a direct plan, which is worth saying out loud once: the same
portfolios bought through a distributor cost more every year, and the plan
totals what that comes to.
"""

from dataclasses import dataclass, field
from typing import Callable

from app.services.advisor.category_ranking import (
    CategoryRanking,
    rank_category,
    rank_codes,
)
from app.services.advisor.fund_universe import ASSET_CLASS_CATEGORY, gold_funds
from app.services.advisor.fund_verdict import Verdict

# Below this a monthly instalment is not worth splitting further: most funds
# will not accept it.
MIN_MONTHLY_SIP = 500.0

# The top pick takes more, but not so much that the basket stops being one.
_TOP_SHARE = 0.6

_DEFAULT_FUNDS_PER_CLASS = 2

Ranker = Callable[..., CategoryRanking]


@dataclass(frozen=True)
class FundPick:
    asset_class: str
    rank: int
    scheme_code: str
    scheme_name: str
    category: str
    monthly_amount: float
    score: float
    direct_ter: float | None
    regular_ter: float | None
    verdict: Verdict


@dataclass(frozen=True)
class SkippedClass:
    asset_class: str
    reason: str


@dataclass(frozen=True)
class Reallocation:
    """A sleeve too small to place, and where its money went instead."""

    asset_class: str
    amount: float
    moved_to: dict[str, float]
    note: str


@dataclass
class FundPlan:
    picks: list[FundPick] = field(default_factory=list)
    skipped: list[SkippedClass] = field(default_factory=list)
    # Rupees a year the plan avoids by being direct-only, where both plans of a
    # picked fund are published. None when none of them are.
    annual_commission_avoided: float | None = None
    # Where the plan had to depart from the target mix to stay placeable.
    reallocations: list[Reallocation] = field(default_factory=list)
    # The mix actually being bought, which is the target only when nothing had
    # to move. Reported because a plan that quietly differs from the allocation
    # it claims to implement is worse than one that says it differs.
    actual_mix: dict[str, float] = field(default_factory=dict)


def _split(amount: float, count: int) -> list[float]:
    """Weight the top pick more heavily, and make the parts add back exactly.

    The weighting is abandoned when it would push the smaller instalment below
    what a fund will accept. It used to be applied unconditionally, so a sleeve
    of ₹1,000 became ₹600 and ₹400 — and the ₹400 SIP was rejected at the
    counter, after the guard above had already checked that an even ₹500 split
    would clear.
    """
    if count == 1:
        return [amount]
    top = round(amount * _TOP_SHARE)
    if amount - top < MIN_MONTHLY_SIP:
        # The even split is known to clear: the caller only reaches count=2
        # once amount / 2 is at or above the minimum.
        smaller = round(amount / 2)
        return [amount - smaller, smaller]
    return [top, amount - top]


def _placeable_allocation(
    allocation: dict[str, float], monthly_sip: float
) -> tuple[dict[str, float], list[Reallocation]]:
    """Drop sleeves too small to invest, and give their money to the rest.

    A goal that puts 10% in gold on a ₹4,000 SIP is asking for a ₹400 monthly
    instalment, which no fund will take. Leaving it out is right; leaving the
    ₹400 uninvested is not, and that is what used to happen — the money simply
    stopped existing between the allocation and the plan.

    Dropping the smallest sleeve raises every other, which can rescue a second
    sleeve that was itself below the line, so this repeats until what remains
    is placeable. The survivors keep their weights relative to each other, so
    a 65/25 equity/debt split stays 65/25 after gold leaves rather than
    drifting toward whichever happened to be larger.
    """
    live = {k: v for k, v in allocation.items() if v > 0}
    moves: list[Reallocation] = []

    while len(live) > 1:
        total = sum(live.values())
        amounts = {k: monthly_sip * v / total for k, v in live.items()}
        too_small = {k: a for k, a in amounts.items() if a < MIN_MONTHLY_SIP}
        if not too_small:
            break

        # Smallest first: it is the one least likely to be rescued by the
        # others growing, and dropping it may lift the rest above the line.
        victim = min(too_small, key=lambda k: amounts[k])
        freed = amounts[victim]
        del live[victim]

        remaining = sum(live.values())
        moved_to = {k: round(freed * v / remaining, 2) for k, v in live.items()}
        moves.append(
            Reallocation(
                asset_class=victim,
                amount=round(freed, 2),
                moved_to=moved_to,
                note=(
                    f"₹{freed:,.0f} a month is below the ₹{MIN_MONTHLY_SIP:,.0f} "
                    f"minimum a fund will accept, so the {victim} sleeve is not "
                    "bought and its money goes to the rest of the plan in "
                    "proportion. Your mix differs from the target because of it."
                ),
            )
        )

    return live, moves


def _rank_asset_class(
    asset_class: str, ranker: Ranker, amount: float, years: int | None
) -> tuple[CategoryRanking | None, str]:
    """The peer group for one asset class, and the label to report it under.

    Gold is not a SEBI category, its funds live inside "Other Scheme - FoF
    Domestic" beside overseas-equity and silver funds, so it is ranked as a
    named subset instead.
    """
    if asset_class == "gold":
        funds = gold_funds()
        if not funds:
            return None, "gold funds"
        return (
            rank_codes("Gold funds", funds, monthly_sip=amount, years=years),
            "Gold funds",
        )

    category = ASSET_CLASS_CATEGORY.get(asset_class)
    if category is None:
        return None, asset_class
    return ranker(category, monthly_sip=amount, years=years), category


def build_fund_plan(
    allocation: dict[str, float],
    monthly_sip: float,
    *,
    funds_per_class: int = _DEFAULT_FUNDS_PER_CLASS,
    years: int | None = None,
    ranker: Ranker = rank_category,
) -> FundPlan:
    """Named funds and rupee amounts for one goal's allocation."""
    plan = FundPlan()
    commission = 0.0
    priced_any = False

    live, plan.reallocations = _placeable_allocation(allocation, monthly_sip)
    for move in plan.reallocations:
        plan.skipped.append(SkippedClass(move.asset_class, move.note))

    live_total = sum(live.values())
    for asset_class, percent in live.items():
        # Re-based on what survived, so the freed money is actually spent
        # rather than quietly falling out of the plan.
        class_amount = monthly_sip * percent / live_total
        if class_amount < MIN_MONTHLY_SIP:
            # Only reachable when a single sleeve holds everything and the whole
            # SIP is under the minimum. Nothing to redistribute to.
            plan.skipped.append(
                SkippedClass(
                    asset_class,
                    f"₹{class_amount:,.0f} a month is below the ₹{MIN_MONTHLY_SIP:,.0f} "
                    "minimum most funds accept, so it is left out rather than "
                    "recommended as an instalment that would be rejected",
                )
            )
            continue

        ranking, label = _rank_asset_class(asset_class, ranker, class_amount, years)
        if ranking is None or not ranking.ranked:
            plan.skipped.append(
                SkippedClass(
                    asset_class,
                    f"No fund in {label} has a long enough record to rank yet",
                )
            )
            continue

        # Narrow the basket rather than recommend instalments too small to place.
        count = min(funds_per_class, len(ranking.ranked))
        while count > 1 and class_amount / count < MIN_MONTHLY_SIP:
            count -= 1

        for ranked, amount in zip(ranking.ranked[:count], _split(class_amount, count)):
            fund = ranked.fund
            plan.picks.append(
                FundPick(
                    asset_class=asset_class,
                    rank=ranked.rank,
                    scheme_code=fund.scheme_code,
                    scheme_name=fund.scheme_name,
                    category=fund.category,
                    monthly_amount=amount,
                    score=fund.score,
                    direct_ter=fund.evidence.direct_ter,
                    regular_ter=fund.evidence.regular_ter,
                    verdict=ranked.verdict,
                )
            )
            direct, regular = fund.evidence.direct_ter, fund.evidence.regular_ter
            if direct is not None and regular is not None and regular > direct:
                priced_any = True
                commission += (regular - direct) * amount * 12

    plan.annual_commission_avoided = round(commission, 2) if priced_any else None

    placed = sum(p.monthly_amount for p in plan.picks)
    plan.actual_mix = (
        {
            asset_class: round(
                sum(
                    p.monthly_amount
                    for p in plan.picks
                    if p.asset_class == asset_class
                )
                / placed
                * 100,
                1,
            )
            for asset_class in dict.fromkeys(p.asset_class for p in plan.picks)
        }
        if placed > 0
        else {}
    )
    return plan
