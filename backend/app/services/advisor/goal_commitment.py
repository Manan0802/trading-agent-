"""What every goal together demands each month, against what there is to give.

A goal planner will happily compute a ₹15,000 SIP three times over and present
three tidy plans. Nobody adds them up. The user leaves with ₹45,000 a month of
commitments and ₹38,000 of surplus, and finds out which goal was fiction about
fourteen months later, by missing an instalment.

So the arithmetic here is deliberately the boring kind, and the output is the
sentence the three tidy plans never say: this does not fit, and something has to
move.

What it does not do is choose what moves. Cutting a retirement target and
delaying a house are not comparable in a way a formula can settle, and pretending
otherwise would be the same overreach as a score that claims to pick funds.
"""

from app.services.advisor.money import inr
from dataclasses import dataclass

# Kept aside before anything is called surplus. Not a savings rate: an emergency
# fund is what stops a bad month turning into a redemption, and a plan that
# spends every spare rupee on SIPs is the plan most likely to be broken.
_BUFFER_SHARE = 0.10


@dataclass(frozen=True)
class GoalDemand:
    goal_id: str
    goal_name: str
    monthly_sip: float
    years: float


@dataclass(frozen=True)
class Commitment:
    total_monthly: float
    goals: list[GoalDemand]
    # None when we do not know the income or the expenses. A shortfall figure
    # invented from a missing number is worse than no figure.
    affordable_monthly: float | None
    shortfall: float | None
    verdict: str


def _affordable(monthly_income: float, monthly_expenses: float) -> float:
    return max(0.0, (monthly_income - monthly_expenses) * (1 - _BUFFER_SHARE))


def assess_commitment(
    goals: list[GoalDemand],
    *,
    annual_income: float | None,
    monthly_expenses: float | None,
) -> Commitment:
    """Sum the goals, compare against the surplus, and say plainly which it is."""
    total = round(sum(g.monthly_sip for g in goals), 2)
    ordered = sorted(goals, key=lambda g: -g.monthly_sip)

    if not goals:
        return Commitment(
            total_monthly=0.0,
            goals=[],
            affordable_monthly=None,
            shortfall=None,
            verdict=(
                "No goals yet. A goal is what turns a number in an account into "
                "a decision you can check yourself against."
            ),
        )

    if not annual_income or annual_income <= 0 or monthly_expenses is None:
        return Commitment(
            total_monthly=total,
            goals=ordered,
            affordable_monthly=None,
            shortfall=None,
            verdict=(
                f"These goals ask for {inr(total)} a month between them. Whether "
                "that is affordable is not something we can say without your "
                "income and monthly expenses — add them on the You page and this "
                "line becomes a real answer rather than a total."
            ),
        )

    affordable = _affordable(annual_income / 12, monthly_expenses)
    shortfall = round(max(0.0, total - affordable), 2)

    if shortfall <= 0:
        headroom = affordable - total
        verdict = (
            f"These goals ask for {inr(total)} a month and you have about "
            f"{inr(affordable)} to give, so they fit with {inr(headroom)} to "
            "spare. That figure already holds back a tenth of your surplus: a "
            "plan that spends every spare rupee is the plan a single bad month "
            "breaks."
        )
    else:
        biggest = ordered[0]
        verdict = (
            f"These goals ask for {inr(total)} a month and you have about "
            f"{inr(affordable)} to give. You are {inr(shortfall)} short, which "
            "means at least one target or date has to move — the plans are not "
            "wrong individually, they are only unaffordable together. "
            f"{biggest.goal_name} is the largest at {inr(biggest.monthly_sip)}, "
            "and pushing a date out is usually cheaper than cutting a target, "
            "because the extra years compound."
        )

    return Commitment(
        total_monthly=total,
        goals=ordered,
        affordable_monthly=round(affordable, 2),
        shortfall=shortfall,
        verdict=verdict,
    )
