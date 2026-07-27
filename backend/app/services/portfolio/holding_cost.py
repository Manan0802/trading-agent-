"""What a user's regular-plan holdings are costing them.

A regular plan and a direct plan of the same fund own the identical portfolio.
The only difference is that the regular plan's NAV has a distributor commission
deducted from it every day. AMFI publishes both plans' expense ratios, so this
is a measured fee difference rather than an estimate — and across the funds we
can price, the median gap is 0.64 percentage points a year.

That number sounds small and is not. It comes out of a balance that would
otherwise have compounded, so the cost of paying it compounds too.

Nothing here tells anyone to switch without saying what switching costs: moving
from regular to direct is a redemption and a fresh purchase, which realises
capital gains.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

PlanType = Literal["direct", "regular"]

_DIRECT = re.compile(r"\bdirect\b", re.I)
_REGULAR = re.compile(r"\bregular\b", re.I)


def classify_plan(name: str) -> PlanType | None:
    """Which plan a scheme name describes, or None when it does not say.

    Older schemes predate the direct/regular split and carry neither word.
    Guessing would put a warning on a fund that may not deserve one.
    """
    if _DIRECT.search(name or ""):
        return "direct"
    if _REGULAR.search(name or ""):
        return "regular"
    return None


@dataclass(frozen=True)
class FlaggedHolding:
    name: str
    value: float
    ter_gap: float
    annual_cost: float


@dataclass
class CostReview:
    annual_cost: float = 0.0
    lifetime_cost: float = 0.0
    flagged: list[FlaggedHolding] = field(default_factory=list)
    # Regular-plan holdings AMFI does not publish a TER for. Reported rather
    # than assigned an average, which would be inventing the number that the
    # whole point of this is to measure.
    unpriced: list[str] = field(default_factory=list)
    summary: str = ""


def _compounded_cost(
    value: float, gap: float, years: float, assumed_return: float
) -> float:
    """What the fee costs by the end, not what it adds up to along the way.

    The fee is charged on a balance that would otherwise have grown, so the
    honest figure is the difference between two compounded paths.
    """
    if years <= 0:
        return 0.0
    gross = value * (1 + assumed_return) ** years
    net = value * (1 + assumed_return - gap) ** years
    return gross - net


def cost_review(
    holdings: list[dict],
    years_remaining: float,
    assumed_return: float = 0.12,
) -> CostReview:
    """Price the regular-plan holdings in a portfolio.

    Each holding is `{name, value, ter_gap}` where `ter_gap` is the published
    regular-minus-direct expense ratio as a fraction, or None if AMFI does not
    file one for that scheme.
    """
    review = CostReview()

    for holding in holdings:
        name = holding.get("name", "")
        if classify_plan(name) != "regular":
            continue

        gap = holding.get("ter_gap")
        if not gap or gap <= 0:
            review.unpriced.append(name)
            continue

        value = float(holding.get("value") or 0)
        annual = value * gap
        review.annual_cost += annual
        review.lifetime_cost += _compounded_cost(
            value, gap, years_remaining, assumed_return
        )
        review.flagged.append(
            FlaggedHolding(
                name=name, value=value, ter_gap=gap, annual_cost=round(annual, 2)
            )
        )

    review.annual_cost = round(review.annual_cost, 2)
    review.lifetime_cost = round(review.lifetime_cost, 2)
    review.summary = _summarise(review, years_remaining)
    return review


def _summarise(review: CostReview, years: float) -> str:
    if not review.flagged and not review.unpriced:
        return (
            "Every fund here is a direct plan, so none of your return is going "
            "to a distributor."
        )

    if not review.flagged:
        names = ", ".join(review.unpriced)
        return (
            f"{names} looks like a regular plan, but AMFI does not publish a "
            "direct-plan expense ratio for it, so the cost cannot be measured "
            "rather than guessed."
        )

    count = len(review.flagged)
    subject = "1 fund here is a regular plan" if count == 1 else f"{count} funds here are regular plans"
    lifetime = (
        f" Over {years:.0f} more years that compounds to about "
        f"₹{review.lifetime_cost:,.0f}."
        if years > 0
        else ""
    )
    return (
        f"{subject}, costing about "
        f"₹{review.annual_cost:,.0f} a year in distributor commission for the "
        f"identical portfolio.{lifetime} Switching to the direct plan of the "
        "same fund is a redemption and a fresh purchase, so it realises capital "
        "gains — worth checking against the saving before you move."
    )
