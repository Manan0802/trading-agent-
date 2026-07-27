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


@dataclass
class FundPlan:
    picks: list[FundPick] = field(default_factory=list)
    skipped: list[SkippedClass] = field(default_factory=list)
    # Rupees a year the plan avoids by being direct-only, where both plans of a
    # picked fund are published. None when none of them are.
    annual_commission_avoided: float | None = None


def _split(amount: float, count: int) -> list[float]:
    """Weight the top pick more heavily, and make the parts add back exactly."""
    if count == 1:
        return [amount]
    top = round(amount * _TOP_SHARE)
    return [top, amount - top]


def _rank_asset_class(
    asset_class: str, ranker: Ranker, amount: float, years: int | None
) -> tuple[CategoryRanking | None, str]:
    """The peer group for one asset class, and the label to report it under.

    Gold is not a SEBI category — its funds live inside "Other Scheme - FoF
    Domestic" beside overseas-equity and silver funds — so it is ranked as a
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

    for asset_class, percent in allocation.items():
        if percent <= 0:
            continue

        class_amount = monthly_sip * percent / 100
        if class_amount < MIN_MONTHLY_SIP:
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
    return plan
