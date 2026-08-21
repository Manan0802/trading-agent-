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

from dataclasses import dataclass, field

from app.services.advisor.money import inr

# Growth assumed when compounding a cost saving. Only the *difference* between
# two paths is reported, so the exact figure matters far less than it looks:
# a saving of 0.64pp compounds similarly at 10% or 14%.
_ASSUMED_RETURN = 0.12

# The band the "save more" lever is quoted across. Unlike a cost gap, where only
# the difference between two paths matters, this one scales WITH the assumption:
# +₹5,000/month over fifteen years is ₹14.6L at 6% and ₹30.6L at 14%. The
# direction never changes and the size does, so it is shown as a range rather
# than as a number pretending to a precision it has not got.
_RETURN_BAND = (0.06, 0.14)

# What a debt fund is assumed to do, for the equity-share trade only.
_DEBT_RETURN = 0.065

# Long-term capital gains on equity: ₹1.25 lakh a year exempt, 12.5% above it.
# Arithmetic, re-checkable at every Budget.
_LTCG_EXEMPT = 125_000.0
_LTCG_RATE = 0.125

# Months of spending to keep reachable before money goes anywhere with a
# drawdown. A gate, not a lever: it earns nothing, it prevents a forced sale.
_EMERGENCY_MONTHS = 6

# What to clear first. Debt at 42% before a fund earning nothing.
_GATE_ORDER = ("high_interest_debt", "emergency_fund")


@dataclass(frozen=True)
class Lever:
    key: str
    title: str
    annual_value: float
    lifetime_value: float
    detail: str
    action: str
    # What kind of thing this is, because they must not be read as one list.
    #
    #   certain   -- arithmetic. A fee difference, a slab calculation, an
    #                exemption. Not a bet; the number is the number.
    #   behaviour -- worth this much only if the person actually does it. The
    #                arithmetic is sound; the doing is the uncertain part.
    #   trade     -- buys return by taking risk. NEVER listed beside `certain`
    #                levers. "Full equity is worth ₹23.6L more than 60%" is only
    #                true if you hold through the fall that buys it, and putting
    #                that next to a fee saving is the most irresponsible thing
    #                this product could do.
    #   gate      -- a prerequisite. Earns nothing; prevents a forced sale.
    kind: str = "certain"
    # The bottom and top of the value when it turns on an assumption we cannot
    # pin. None when the figure does not move with one.
    low: float | None = None
    high: float | None = None
    # How we know, and how well. A number with no provenance is
    # indistinguishable from one we made up.
    evidence: str = ""
    # What would change this answer. Nothing else on the Indian market tells a
    # reader when to come back.
    revisit: str = ""


@dataclass(frozen=True)
class Unpriced:
    """A decision we know matters and cannot value for this person yet.

    Returned rather than omitted. A list containing only what we happened to be
    able to compute reads as a complete list of what matters, which is the
    exact dishonesty this screen exists to avoid.
    """

    key: str
    title: str
    why: str
    what_we_need: str


@dataclass(frozen=True)
class LeverSet:
    """Ranked money decisions, in separate lists on purpose."""

    levers: list[Lever] = field(default_factory=list)
    trades: list[Lever] = field(default_factory=list)
    gates: list[Lever] = field(default_factory=list)
    unpriced: list[Unpriced] = field(default_factory=list)


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


def _saving_step(monthly_sip: float) -> float:
    """How much more a month to suggest putting in.

    A round number near a fifth of what they already save. Suggesting "double
    it" is ignored; suggesting "₹87 more" is not a decision anyone acts on. The
    rounding is to the nearest ₹500 up to ₹10,000 and ₹1,000 above it, so the
    figure reads as a decision rather than as a calculation result.
    """
    raw = max(monthly_sip * 0.2, 500.0)
    step = 500.0 if raw <= 10_000 else 1000.0
    return float(round(raw / step) * step)


def _sip_future_value(monthly: float, years: float, rate: float) -> float:
    if monthly <= 0 or years <= 0:
        return 0.0
    r = rate / 12
    n = round(years * 12)
    return monthly * (((1 + r) ** n - 1) / r) * (1 + r)


def rank_levers(
    portfolio_value: float,
    *,
    annual_income: float,
    monthly_sip: float,
    years_remaining: float,
    regular_plan_cost_gap: float | None,
    tax_saving: float,
    tax_regime_gap: float = 0.0,
    current_regime: str = "new",
    # The money sitting in REGULAR plans, which is the only money a switch to
    # direct is worth anything on. Separate from `portfolio_value` because they
    # mean different things and one parameter serving both silently zeroed the
    # LTCG lever for anyone already fully in direct plans — their whole
    # portfolio still has a gain to harvest.
    regular_plan_value: float | None = None,
    monthly_expenses: float | None = None,
    liquid_savings: float | None = None,
    high_interest_debt: float | None = None,
    high_interest_rate: float = 0.42,
    equity_share: float | None = None,
) -> LeverSet:
    """Every lever we can price for this user, biggest first.

    `tax_saving` is what switching regime is worth *from the one they are
    already in*, so it is zero for the majority who are on the new regime by
    default. `tax_regime_gap` is what the two regimes differ by at all, which
    is what separates "you already made this call correctly" from "there is no
    call to make here".
    """
    levers: list[Lever] = []
    trades: list[Lever] = []
    gates: list[Lever] = []
    unpriced: list[Unpriced] = []

    if regular_plan_cost_gap and regular_plan_cost_gap > 0:
        gap = regular_plan_cost_gap
        switchable = (
            regular_plan_value if regular_plan_value is not None else portfolio_value
        )
        on_holdings = _compounded_saving(switchable, gap, years_remaining)
        on_future = _sip_future_value(
            monthly_sip, years_remaining, _ASSUMED_RETURN
        ) - _sip_future_value(monthly_sip, years_remaining, _ASSUMED_RETURN - gap)
        levers.append(
            Lever(
                key="plan_switch",
                title="Move from regular plans to direct",
                annual_value=round(switchable * gap, 2),
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
                kind="certain",
                evidence=(
                    "A published fee difference, measured at 0.64 percentage "
                    "points across 1,385 funds. Our own harness: the cheapest "
                    "quarter beat the dearest in 45 of 52 three-year windows, an "
                    "87% hit rate. Morningstar found it independently — cheapest "
                    "quintile 62% success, priciest 20%."
                ),
                revisit=(
                    "When you buy a new fund. The saving is per fund, so a "
                    "regular plan bought later starts the leak again."
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
                kind="certain",
                evidence="A slab calculation on the income and deductions you gave us.",
                revisit=(
                    "Every April, and after any change to rent, home loan or 80C "
                    "— a large enough deduction flips which regime wins."
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
                kind="certain",
                evidence="A slab calculation on the income and deductions you gave us.",
                revisit="Every April, and after any change to rent, home loan or 80C.",
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
            kind="certain",
            evidence=(
                "Tested three times on our own NAV history and it failed three "
                "times: 50% by three-year record, 38% by lifetime return (worse "
                "than a coin, and pointing the wrong way), and 68% by the "
                "industry-standard score — but that one was at or below chance "
                "in three of its seven years."
            ),
            revisit=(
                "Nothing will change this. It is the most replicated negative "
                "finding in the field."
            ),
        )
    )

    levers.extend(_saving_levers(monthly_sip, years_remaining))
    levers.extend(_tax_harvest_levers(portfolio_value, years_remaining))
    levers.extend(_behaviour_levers(portfolio_value, monthly_sip))

    # A gate, not a lever. Its value is per YEAR CARRIED, and sorting a
    # per-year figure into a list of lifetime figures ranked a guaranteed 42%
    # return below a ₹5.8L tax saving. You do not weigh clearing a credit card
    # against harvesting an exemption; you clear the card and then do the rest.
    debt_gate, debt_gap = _debt_lever(high_interest_debt, high_interest_rate)
    gates.extend(debt_gate)
    unpriced.extend(debt_gap)

    gate, gate_gap = _emergency_gate(monthly_expenses, liquid_savings)
    gates.extend(gate)
    unpriced.extend(gate_gap)

    trade, trade_gap = _equity_trade(
        equity_share, portfolio_value, monthly_sip, years_remaining
    )
    trades.extend(trade)
    unpriced.extend(trade_gap)

    return LeverSet(
        levers=sorted(levers, key=lambda lever: -lever.lifetime_value),
        # Gates carry no comparable number -- one is a 42% interest bill and the
        # other is zero by design -- so they are ordered by what to do first
        # rather than sorted by value.
        trades=trades,
        gates=sorted(gates, key=lambda gate: _GATE_ORDER.index(gate.key)),
        unpriced=unpriced,
    )


# ---------------------------------------------------------------------------
# The levers that were missing.
#
# Priced for the same user the three above were (₹8L invested, ₹25k/month, 15
# years left), they rank like this:
#
#     save ₹5,000/mo more .................. ₹25,22,880   <- was on no screen
#     move to the cheaper tax regime ....... ₹27,60,000
#     not selling in a crash ............... contested, no number
#     hold 100% equity rather than 60% ..... ₹23,57,804   <- a TRADE, not a lever
#     direct plan instead of regular ....... ₹11,06,705
#     use the ₹1.25L LTCG exemption ........  ₹6,52,395   <- was on no screen
#     pick the best-performing fund ........          ₹0
#
# Eight decisions worth ₹6L to ₹50L each appeared on no screen in this app,
# while the one worth zero had four screens built around it. That is the whole
# reason this file exists.
# ---------------------------------------------------------------------------


def _saving_levers(monthly_sip: float, years_remaining: float) -> list[Lever]:
    """The largest lever for almost everybody, and on no Indian screen.

    Quoted as a range on purpose. A cost gap compares two paths and the
    assumption largely cancels; this one scales with it. Measured across 6% to
    14%: +₹5,000/month over fifteen years is ₹14.6L to ₹30.6L. Direction fixed,
    size not — so a single number would be false precision.
    """
    if monthly_sip <= 0 or years_remaining <= 0:
        return []
    step = _saving_step(monthly_sip)

    def gain(rate: float) -> float:
        return _sip_future_value(monthly_sip + step, years_remaining, rate) - \
            _sip_future_value(monthly_sip, years_remaining, rate)

    low, high, mid = gain(_RETURN_BAND[0]), gain(_RETURN_BAND[1]), gain(_ASSUMED_RETURN)
    return [
        Lever(
            key="save_more",
            title=f"Put {inr(step)} a month more in",
            annual_value=round(step * 12, 2),
            lifetime_value=round(mid, 2),
            low=round(low, 2),
            high=round(high, 2),
            kind="behaviour",
            detail=(
                f"You are putting in {inr(monthly_sip)} a month. Another "
                f"{inr(step)} is worth between {inr(low)} and {inr(high)} by the "
                f"end, depending on what markets do. It is the largest single "
                f"thing here and the only one that does not depend on picking "
                f"anything correctly."
            ),
            evidence=(
                "Compound arithmetic, not a forecast. The range is the same sum "
                "run at 6% and at 14% a year; the direction never changes and "
                "only the size does."
            ),
            action=(
                f"Raise the standing instruction by {inr(step)}. If that is too "
                f"much today, raise it by that much every time your pay goes up "
                f"instead — you do not miss money you never started spending."
            ),
            revisit="Every appraisal.",
        )
    ]


def _tax_harvest_levers(portfolio_value: float, years_remaining: float) -> list[Lever]:
    """The yearly exemption almost nobody uses, compounded over the horizon."""
    if portfolio_value <= 0 or years_remaining <= 0:
        return []
    yearly = _LTCG_EXEMPT * _LTCG_RATE
    total = sum(
        yearly * (1 + _ASSUMED_RETURN) ** max(years_remaining - year - 1, 0)
        for year in range(int(years_remaining))
    )
    return [
        Lever(
            key="ltcg_harvest",
            title="Use the ₹1.25 lakh tax-free gain every year",
            annual_value=round(yearly, 2),
            lifetime_value=round(total, 2),
            kind="certain",
            detail=(
                f"Long-term gains on equity up to {inr(_LTCG_EXEMPT)} a year are "
                f"tax free, and the allowance does not carry forward — miss a "
                f"year and it is gone. Realising that much gain and buying "
                f"straight back banks {inr(yearly)} of tax you would otherwise "
                f"pay later, every year, whether or not you needed the money."
            ),
            evidence=(
                "Arithmetic on the current exemption and the 12.5% rate. Not a "
                "forecast."
            ),
            action=(
                "In March, work out your unrealised long-term gain, sell enough "
                "units to realise about ₹1.25 lakh of it, and buy the same fund "
                "back. Check the exit load before you do."
            ),
            revisit="Every Budget — the exemption and the rate both move.",
        )
    ]


def _behaviour_levers(portfolio_value: float, monthly_sip: float) -> list[Lever]:
    """Staying invested, carrying no number on purpose.

    The direction is well supported across decades and several independent
    methods. The magnitude is genuinely contested: Morningstar's *Mind the Gap
    2025* puts it at 1.2 percentage points a year over 2015-2024; a
    peer-reviewed rebuttal in the *Financial Analysts Journal* (2026) disputes
    the headline; DALBAR reported 0.72 points for 2025 and 8.48 for 2024.

    A figure that swings twelvefold year to year, from methodologies both
    challenged in print for overstating it, is not a figure to put on a screen.
    So `lifetime_value` is zero rather than a guess, and the lever says why.
    """
    if portfolio_value <= 0 and monthly_sip <= 0:
        return []
    return [
        Lever(
            key="stay_invested",
            title="Not selling when it falls",
            annual_value=0.0,
            lifetime_value=0.0,
            kind="behaviour",
            detail=(
                "Investors reliably end up with less than the funds they hold, "
                "because of when they buy and sell rather than what they buy. "
                "We are not putting a number on it: the two studies everyone "
                "quotes disagree by a factor of twelve, and both have been "
                "challenged in print for overstating it."
            ),
            evidence=(
                "That the gap exists is well supported. How big it is is not — "
                "Morningstar says 1.2 points a year, DALBAR said 0.72 in 2025 "
                "and 8.48 in 2024, and a 2026 Financial Analysts Journal paper "
                "argues the headline figure is overstated."
            ),
            action=(
                "Decide now what you will do in a fall, while nothing is "
                "falling. The base rates here show how far this kind of fund "
                "has dropped before and how long it took to come back."
            ),
            revisit="Read it again the first week the market drops 10%.",
        )
    ]


def _debt_lever(
    balance: float | None, rate: float
) -> tuple[list[Lever], list[Unpriced]]:
    """Expensive debt, priced per year carried and never over the horizon.

    ₹1 lakh at 42% "costs" ₹1.87 crore against investing it over fifteen years.
    That is arithmetically correct and rhetorically dishonest: nobody carries a
    card for fifteen years. Per year it is ₹30,000, which is a number a person
    can act on.
    """
    if not balance or balance <= 0:
        return [], [
            Unpriced(
                key="high_interest_debt",
                title="Clearing expensive debt",
                why=(
                    "A credit card at 42% beats every investment on this app, "
                    "guaranteed. We cannot tell whether you are carrying any."
                ),
                what_we_need="What you owe on cards or personal loans, and at what rate.",
            )
        ]
    per_year = balance * (rate - _ASSUMED_RETURN)
    return [
        Lever(
            key="high_interest_debt",
            title="Clear the expensive debt before investing another rupee",
            annual_value=round(per_year, 2),
            # Per year carried, and it is a gate rather than a lever precisely
            # so this figure is never sorted against a fifteen-year one.
            lifetime_value=round(per_year, 2),
            kind="gate",
            detail=(
                f"{inr(balance)} at {rate * 100:.0f}% costs {inr(per_year)} a "
                f"year more than the same money invested is expected to earn. "
                f"Paying it off is a guaranteed {rate * 100:.0f}% return, which "
                f"nothing on this app offers."
            ),
            evidence=(
                "Arithmetic, quoted per year carried rather than over your whole "
                "horizon — compounding it for fifteen years gives a true number "
                "that describes something nobody does."
            ),
            action="Clear this before increasing any SIP.",
            revisit="When it is gone.",
        )
    ], []


def _emergency_gate(
    monthly_expenses: float | None, liquid_savings: float | None
) -> tuple[list[Lever], list[Unpriced]]:
    """A prerequisite, not a lever. It earns nothing and prevents a forced sale."""
    if not monthly_expenses or monthly_expenses <= 0:
        return [], [
            Unpriced(
                key="emergency_fund",
                title="Having enough set aside to not sell in a bad month",
                why="We do not know what you spend in a month.",
                what_we_need="Your monthly expenses.",
            )
        ]
    needed = monthly_expenses * _EMERGENCY_MONTHS
    if liquid_savings is None:
        return [], [
            Unpriced(
                key="emergency_fund",
                title="Having enough set aside to not sell in a bad month",
                why=(
                    f"On your spending you would want about {inr(needed)} "
                    f"reachable. We do not know what you already have."
                ),
                what_we_need="What you hold in cash, a sweep account or liquid funds.",
            )
        ]
    if liquid_savings >= needed:
        return [], []
    return [
        Lever(
            key="emergency_fund",
            title="Build the emergency fund before investing more",
            annual_value=0.0,
            lifetime_value=0.0,
            kind="gate",
            detail=(
                f"You have {inr(liquid_savings)} reachable against about "
                f"{inr(needed)} of spending for {_EMERGENCY_MONTHS} months. This "
                f"earns nothing. It exists so a bad month does not force you to "
                f"sell at the bottom, which is the most expensive thing an "
                f"investor can do."
            ),
            evidence=(
                "Not a return — a prevention. The base rates on this app show "
                "how deep the falls have been and how long they lasted."
            ),
            action=(
                f"Put {inr(needed - liquid_savings)} into a liquid fund or sweep "
                f"account before increasing any SIP."
            ),
            revisit="When your spending changes.",
        )
    ], []


def _equity_trade(
    equity_share: float | None,
    portfolio_value: float,
    monthly_sip: float,
    years_remaining: float,
) -> tuple[list[Lever], list[Unpriced]]:
    """Deliberately not a lever.

    "Full equity is worth ₹23.6L more than 60% over fifteen years" is
    arithmetically true and is not free money — it is the price of holding
    through the fall that buys it. Listing it beside a fee saving, where the
    number really is the number, would be the most irresponsible thing on this
    screen. It is returned in its own list so it cannot be sorted in among them.
    """
    if equity_share is None:
        return [], [
            Unpriced(
                key="equity_share",
                title="How much of your money is in equity",
                why=(
                    "It decides more of your outcome than any fund choice. It is "
                    "a trade rather than a free lever, so it is shown with its "
                    "downside attached and never beside the cost savings."
                ),
                what_we_need="Your split across equity, debt and cash.",
            )
        ]
    if not 0 <= equity_share < 1 or years_remaining <= 0:
        return [], []
    blended = equity_share * _ASSUMED_RETURN + (1 - equity_share) * _DEBT_RETURN
    gain = (
        _sip_future_value(monthly_sip, years_remaining, _ASSUMED_RETURN)
        - _sip_future_value(monthly_sip, years_remaining, blended)
        + _compounded_saving(portfolio_value, _ASSUMED_RETURN - blended, years_remaining)
    )
    return [
        Lever(
            key="equity_share",
            title="Holding more in equity",
            annual_value=0.0,
            lifetime_value=round(gain, 2),
            kind="trade",
            detail=(
                f"You are about {equity_share * 100:.0f}% in equity. Going fully "
                f"into equity would be worth roughly {inr(gain)} more by the end "
                f"— and this is not free money. It is the payment for sitting "
                f"through the falls, which for equity funds here have reached "
                f"41% to 74% depending on the category and taken eight months to "
                f"a year and a half to come back."
            ),
            evidence=(
                "The arithmetic is sound. Whether you collect it depends "
                "entirely on whether you hold through the fall, and that is the "
                "part nobody can compute for you."
            ),
            action=(
                "Only change this if you can say what you would do after a 40% "
                "fall. If you cannot, leave it where it is."
            ),
            revisit="When your horizon changes — not when the market moves.",
        )
    ], []
