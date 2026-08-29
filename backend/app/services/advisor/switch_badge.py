"""What switching this fund actually costs, and whether it pays back.

`Costs more than it needs to` is this app's strongest signal -- cost is the one
thing measured to work, 43 of 52 windows. As a badge on its own it is
**incomplete to the point of being misleading**, because switching is not free:
selling realises capital gains and may hit an exit load, and an app that says
"this fund costs 1.0pp more than a peer" and stops has told half a fact.

**The obvious completion is also wrong, and in the expensive direction.** A
first draft charged the whole capital-gains bill against the switch -- ₹9,375 on
a ₹2,00,000 long-term gain -- and concluded "two-year payback". That treats
deferred tax as sunk, and it is not:

  exit load      a TRUE cost. The money leaves and does not come back.
  capital gains  mostly a DEFERRAL. The cost basis resets, so the same gain is
                 not taxed twice -- the tax paid today is tax that was owed on
                 exit anyway. The real cost is only the return forgone on money
                 paid early, across the remaining horizon.
  the exemption  the first ₹1.25 lakh of equity LTCG each year costs nothing at
                 all. Charging it is charging for gain-harvesting the user
                 should be doing regardless.

Charging the gross bill overstates switching, which pushes the badge toward
"leave it" in the one place this app has a measured signal.

**The exemption is annual and shared across every equity gain**, so it cannot be
spent per holding -- ten rows each claiming the full ₹1.25 lakh overstate the
saving ten times over. `exemption_available` is therefore passed IN, allocated
by the caller across the year, and this module never assumes it.

**And it is Section 112A, equity only.** Gold, debt-oriented and international
funds sit under Section 112, which has no such threshold. `equity=False`
switches the exemption off rather than quietly applying an equity rule to a
gold fund.

Every figure here is arithmetic over data already held. Nothing is a prediction.
"""

from dataclasses import dataclass

from app.services.advisor.money import inr
from app.services.llm.grounding import Claim, check_all

# Section 112A, verified current against the Income Tax Department's portal.
LTCG_RATE = 0.125
STCG_RATE = 0.20

# §11.7's column budget. Anything longer is a sentence in a column that has
# room for a verdict.
BADGE_MAX_CHARS = 34


@dataclass(frozen=True)
class SwitchMath:
    """The four numbers, the verdict, and the payload they can be checked against."""

    annual_saving: float
    exit_load: float
    # Paid now instead of at exit. NOT a cost -- the basis resets.
    tax_brought_forward: float
    # What that early payment costs: the return it would have earned.
    tax_carry_per_year: float
    net_annual_benefit: float
    # None when nothing is saved, so there is nothing to pay back.
    breakeven_years: float | None
    horizon_years: float
    pays_back: bool
    badge: str
    detail: str
    source: dict
    claims: tuple[Claim, ...]

    def verify(self):
        """Every printed figure, checked against the payload that produced it.

        This is `grounding.py`'s first non-test caller. The module is 792 lines
        with 50 tests and had none, which made it a guard nothing was behind.
        """
        return check_all(f"{self.badge}\n{self.detail}", list(self.claims), self.source)


def switch_math(
    *,
    balance: float,
    ter_gap_pp: float,
    unrealised_gain: float,
    long_term: bool,
    exit_load: float,
    horizon_years: float,
    assumed_return: float,
    equity: bool = True,
    exemption_available: float = 0.0,
    kind: str = "peer",
) -> SwitchMath:
    """Whether moving this balance to the cheaper option pays back inside the horizon.

    `ter_gap_pp` is in percentage points, the unit both TER sources publish.
    `exemption_available` is the slice of the annual ₹1.25 lakh this holding has
    been allocated -- see the module docstring on why it is not assumed here.
    """
    annual_saving = balance * ter_gap_pp / 100.0

    taxable = max(0.0, unrealised_gain)
    if long_term:
        if equity:
            taxable = max(0.0, taxable - max(0.0, exemption_available))
        tax = taxable * LTCG_RATE
    else:
        tax = taxable * STCG_RATE

    # The deferral costs its return, not its face value.
    tax_carry = tax * assumed_return
    net = annual_saving - tax_carry

    # Only the exit load is money that does not come back, so only it has to be
    # paid back. Dividing by the GROSS bill is the overstatement above.
    if net <= 0:
        breakeven = None
    elif exit_load <= 0:
        breakeven = 0.0
    else:
        breakeven = exit_load / net

    pays_back = breakeven is not None and breakeven <= horizon_years

    saving_text = inr(round(annual_saving))
    if not pays_back:
        badge = "Cheaper option won't pay back"
    elif kind == "plan":
        badge = f"Direct saves {saving_text}/yr"
    else:
        badge = f"{saving_text}/yr cheaper elsewhere"

    source = {
        "annual_saving": round(annual_saving),
        "exit_load": round(exit_load),
        "tax_brought_forward": round(tax),
        "tax_carry_per_year": round(tax_carry),
        "horizon_years": round(horizon_years),
    }
    detail = (
        f"Saves {inr(source['annual_saving'])} a year at today's balance. "
        f"Exit load {inr(source['exit_load'])}, a real cost. "
        f"Tax brought forward {inr(source['tax_brought_forward'])} — not a cost, "
        "the basis resets; what it costs is the return forgone on it, about "
        f"{inr(source['tax_carry_per_year'])} a year. "
        f"Your horizon is {source['horizon_years']} years."
    )
    claims = (
        Claim(str(source["annual_saving"]), "annual_saving"),
        Claim(str(source["exit_load"]), "exit_load"),
        Claim(str(source["tax_brought_forward"]), "tax_brought_forward"),
        Claim(str(source["tax_carry_per_year"]), "tax_carry_per_year"),
        Claim(str(source["horizon_years"]), "horizon_years"),
    )

    return SwitchMath(
        annual_saving=annual_saving,
        exit_load=exit_load,
        tax_brought_forward=tax,
        tax_carry_per_year=tax_carry,
        net_annual_benefit=net,
        breakeven_years=breakeven,
        horizon_years=horizon_years,
        pays_back=pays_back,
        badge=badge,
        detail=detail,
        source=source,
        claims=claims,
    )
