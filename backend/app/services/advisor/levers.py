"""Which decisions are actually worth money, in rupees, ranked.

Most people spend nearly all their attention on the one decision that turns out
not to matter. We tested it: picking funds on their past record beat the
category median in half of sixty three-year windows, and over 54 windows the
quartile our own score ranked best went on to return less than the quartile it
ranked worst. That is a coin flip.

Meanwhile the things nobody finds interesting are arithmetic. Buying the direct
plan of the identical fund is a published fee difference, measured at 0.64
percentage points a year across 1,385 funds, and the cheapest quartile beat the
dearest in 45 of 52 windows. Choosing the right tax regime is a slab
calculation. Neither is a bet.

So this ranks the levers by what each is worth to this particular user, over
their own horizon, and includes fund selection at zero rather than leaving it
off — because the zero is the finding.
"""

from dataclasses import dataclass

from app.services.advisor.money import inr

# Growth assumed when compounding a cost saving. Only the *difference* between
# two paths is reported, so the exact figure matters far less than it looks:
# a saving of 0.64pp compounds similarly at 10% or 14%.
_ASSUMED_RETURN = 0.12


@dataclass(frozen=True)
class Lever:
    key: str
    title: str
    annual_value: float
    lifetime_value: float
    detail: str
    action: str


def _compounded_saving(value: float, gap: float, years: float) -> float:
    """What a fee saving is worth by the end, not what it sums to along the way.

    The fee comes out of a balance that would otherwise have grown, so the
    honest figure is the gap between two compounded paths.
    """
    if years <= 0 or value <= 0:
        return 0.0
    gross = value * (1 + _ASSUMED_RETURN) ** years
    net = value * (1 + _ASSUMED_RETURN - gap) ** years
    return gross - net


def _sip_future_value(monthly: float, years: float, rate: float) -> float:
    if monthly <= 0 or years <= 0:
        return 0.0
    r = rate / 12
    n = round(years * 12)
    return monthly * (((1 + r) ** n - 1) / r) * (1 + r)


def rank_levers(
    portfolio_value: float,
    annual_income: float,
    monthly_sip: float,
    years_remaining: float,
    regular_plan_cost_gap: float | None,
    tax_saving: float,
    tax_regime_gap: float = 0.0,
    current_regime: str = "new",
) -> list[Lever]:
    """Every lever we can price for this user, biggest first.

    `tax_saving` is what switching regime is worth *from the one they are
    already in*, so it is zero for the majority who are on the new regime by
    default. `tax_regime_gap` is what the two regimes differ by at all, which
    is what separates "you already made this call correctly" from "there is no
    call to make here".
    """
    levers: list[Lever] = []

    if regular_plan_cost_gap and regular_plan_cost_gap > 0:
        gap = regular_plan_cost_gap
        on_holdings = _compounded_saving(portfolio_value, gap, years_remaining)
        on_future = _sip_future_value(
            monthly_sip, years_remaining, _ASSUMED_RETURN
        ) - _sip_future_value(monthly_sip, years_remaining, _ASSUMED_RETURN - gap)
        levers.append(
            Lever(
                key="plan_switch",
                title="Move from regular plans to direct",
                annual_value=round(portfolio_value * gap, 2),
                lifetime_value=round(on_holdings + on_future, 2),
                detail=(
                    f"The direct plan of the same fund owns the identical "
                    f"portfolio and costs {gap * 100:.2f} percentage points a "
                    "year less. Across 52 three-year windows the cheapest "
                    "quarter of funds beat the dearest quarter in 45 of them, "
                    "which makes this the one fund decision that is measured "
                    "rather than hoped for."
                ),
                action=(
                    "Switch each holding to its direct plan, and check the "
                    "capital gain it realises against the saving first: the "
                    "switch is a redemption and a fresh purchase."
                ),
            )
        )

    if tax_saving > 0:
        other = "new" if current_regime == "old" else "old"
        levers.append(
            Lever(
                key="tax_regime",
                title=f"Move to the {other} tax regime",
                annual_value=round(tax_saving, 2),
                # Not compounded: the saving is only invested and growing if the
                # user actually invests it, and assuming they do would be
                # inventing a behaviour.
                lifetime_value=round(tax_saving * max(years_remaining, 0), 2),
                detail=(
                    f"You told us you are on the {current_regime} regime. On your "
                    f"income and the deductions you claim, the {other} one costs "
                    "less. This is a slab calculation, not a forecast."
                ),
                action=(
                    f"Declare the {other} regime with your employer at the start "
                    "of the financial year, and recheck it if your rent or home "
                    "loan changes."
                ),
            )
        )
    elif annual_income > 0 and tax_regime_gap > 0:
        # Shown at zero rather than omitted, for the same reason fund selection
        # is: a lever already pulled is worth knowing about, and without this
        # line the page reads as though nothing about tax was ever checked.
        levers.append(
            Lever(
                key="tax_regime",
                title="Be in the cheaper tax regime",
                annual_value=0.0,
                lifetime_value=0.0,
                detail=(
                    f"Already done. You are on the {current_regime} regime, and on "
                    f"your numbers it costs {inr(tax_regime_gap)} a year less "
                    "than the alternative. Worth nothing more because you are "
                    "already collecting it."
                ),
                action=(
                    "Leave it alone, and recheck after any change to your rent, "
                    "home loan or 80C — a large enough deduction can flip which "
                    "regime wins."
                ),
            )
        )

    levers.append(
        Lever(
            key="fund_selection",
            title="Pick the best-performing fund",
            annual_value=0.0,
            lifetime_value=0.0,
            detail=(
                "Worth nothing measurable. Over sixty three-year windows, picks "
                "made on past record beat their category median in half of them, "
                "and the quartile our own score ranked best went on to return "
                "17.2% against 19.4% for the quartile it ranked worst. Ranking "
                "funds on past returns does not predict which do better, and "
                "this is the most replicated finding in the field."
            ),
            action=(
                "Spend the attention on cost, tax and staying invested instead. "
                "Any cheap fund in the right category does the job."
            ),
        )
    )

    return sorted(levers, key=lambda lever: -lever.lifetime_value)
