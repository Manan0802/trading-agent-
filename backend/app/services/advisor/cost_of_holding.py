"""What one held fund costs, read from both sources, with the disagreements kept.

Cost is this app's method. §1.1's measurement is the study that pivoted the
product away from picking funds on past returns, so the one number the whole
thing rests on had better not be quietly wrong -- and there are three separate
ways it can be, each of which this module refuses rather than papers over.

**Two sources, and never their average.** AMFI publishes the TER a fund filed;
Groww publishes the TER it sells against. Across the 1,233 buyable funds that
carry both, 71 disagree by more than 0.10pp. Averaging two numbers that disagree
produces a third number that neither source stands behind, and it looks exactly
as confident as agreement does. So a disagreement is SHOWN, and the fund is not
ranked on cost at all while it stands.

**The join is `scheme_code`.** Joining these two sources on the fund NAME --
which is the field a human reaches for -- returns exactly zero matches, because
the two spell every fund differently. It does not error. It returns an empty
table and a cost gate that silently has no second source for anything.

**One source is `n/a`, never `0`.** A fund whose TER we failed to read must not
sort as the cheapest one. That failure once put three unpriced funds in a Large
Cap top five.

**And the ceiling is not a ceiling.** "SEBI's 2.25% cap" leaves no edge in the
data: this repo's own 2,793 AMFI values run smoothly through it to 3.46, with
241 above. SEBI's real limit is slab-based on AUM and scheme type, and that slab
table could not be sourced -- SEBI's document paths returned 404 and both search
budgets were exhausted. So this flags a direct plan as *unusually high* and shows
the number, and claims no breach of anything, which is §14's rule about
contested magnitudes applied to our own threshold.
"""

from dataclasses import dataclass

from app.services.advisor.fund_evidence import expense_ratios

# Two filings of the same fee that differ by less than this are the same fee
# reported on different dates. Above it, something is actually different.
AGREEMENT_TOLERANCE_PP = 0.10

# Both sources publish to two decimal places, and 1.33 - 1.23 is 0.10000000000000009
# in binary floating point. Without this, a gap of exactly the tolerance falls on
# whichever side the representation error happens to land, so the same two
# filings agree or disagree depending on which fund you are looking at.
_FLOAT_SLACK = 1e-9

# Not regulatory limits -- see the module docstring. Thresholds for the word
# "unusually", chosen because a DIRECT plan excludes the distributor commission
# that lifts most of the 8.6% sitting above 2.25%, and because a fund that only
# tracks an index has little it can be spending 1% on.
_UNUSUAL_DIRECT_PP = 2.25
_UNUSUAL_PASSIVE_PP = 1.00

_PASSIVE_WORDS = ("index", "etf", "nifty", "sensex", "bse ", "exchange traded")


def looks_passive(scheme_name: str = "", sub_category: str = "") -> bool:
    """Whether this is an index tracker, on the only signal we currently have.

    ONE signal, and the plan is explicit that this is a one-signal design
    wearing two: Groww's `st_filter` listing carries an `index` boolean, but 0
    of the 39 cached scheme-detail payloads include it, so nothing here can read
    it until slice 2.1 pulls that listing. Until then this is a name test, and a
    name test is why `is_passive` is not used to rank anything -- only to pick
    which threshold the word "unusually" is measured against.
    """
    haystack = f"{scheme_name} {sub_category}".lower()
    return any(word in haystack for word in _PASSIVE_WORDS)


@dataclass(frozen=True)
class CostOfHolding:
    """Both readings of one fund's cost, and what may be done with them."""

    scheme_code: str
    # Percentages, as both sources publish them. None means "we do not know",
    # which the screen renders `n/a`.
    amfi_direct_ter: float | None
    amfi_regular_ter: float | None
    groww_ter: float | None
    # The single figure to show, when there is one honest single figure.
    ter: float | None
    sources: tuple[str, ...]
    # None when only one source carries the fund, so there is nothing to agree.
    agrees: bool | None
    # False when the two sources disagree. Cost is the axis this app ranks on,
    # so a fund whose cost is contested does not compete on it.
    rankable_on_cost: bool
    is_passive: bool
    # Set when the figure is high enough to be worth a second look. Deliberately
    # not a compliance claim.
    flag: str | None
    note: str | None

    @property
    def disagreement_pp(self) -> float | None:
        if self.amfi_direct_ter is None or self.groww_ter is None:
            return None
        return abs(self.amfi_direct_ter - self.groww_ter)


def read(
    scheme_code: str,
    *,
    groww_ter: float | None = None,
    scheme_name: str = "",
    sub_category: str = "",
) -> CostOfHolding:
    """Both sources for one fund, joined on `scheme_code`.

    `groww_ter` is passed in rather than fetched. This module stays pure so that
    every branch below is reachable from a fixture, and so a Groww outage cannot
    turn a cost reading into a request.
    """
    filed = expense_ratios().get(str(scheme_code)) or {}
    amfi_direct = _percent(filed.get("direct_ter"))
    amfi_regular = _percent(filed.get("regular_ter"))
    groww = _percent(groww_ter)

    sources = tuple(
        name
        for name, value in (("amfi", amfi_direct), ("groww", groww))
        if value is not None
    )
    passive = looks_passive(scheme_name, sub_category)

    if not sources:
        return CostOfHolding(
            scheme_code=str(scheme_code),
            amfi_direct_ter=None,
            amfi_regular_ter=amfi_regular,
            groww_ter=None,
            ter=None,
            sources=(),
            agrees=None,
            # Missing cost is NEUTRAL, not disqualifying -- §14. The fund still
            # ranks, on everything except the axis we cannot read for it.
            rankable_on_cost=False,
            is_passive=passive,
            flag=None,
            note="We could not read this fund's expense ratio from either source.",
        )

    if len(sources) == 1:
        only = amfi_direct if amfi_direct is not None else groww
        return CostOfHolding(
            scheme_code=str(scheme_code),
            amfi_direct_ter=amfi_direct,
            amfi_regular_ter=amfi_regular,
            groww_ter=groww,
            ter=only,
            sources=sources,
            agrees=None,
            rankable_on_cost=True,
            is_passive=passive,
            flag=_unusual(only, passive),
            note=f"Only {sources[0].upper()} publishes a TER for this fund.",
        )

    gap = abs(amfi_direct - groww)
    if gap > AGREEMENT_TOLERANCE_PP + _FLOAT_SLACK:
        return CostOfHolding(
            scheme_code=str(scheme_code),
            amfi_direct_ter=amfi_direct,
            amfi_regular_ter=amfi_regular,
            groww_ter=groww,
            # Deliberately no single figure. The two are shown side by side.
            ter=None,
            sources=sources,
            agrees=False,
            rankable_on_cost=False,
            is_passive=passive,
            flag=None,
            note=(
                f"AMFI files {amfi_direct:.2f}% and Groww shows {groww:.2f}% "
                f"— a gap of {gap:.2f}pp. We are not averaging them, and we are "
                "not ranking this fund on cost until they agree."
            ),
        )

    # They agree. AMFI's is the figure of record: it is the filing, and it is
    # the one the committed table is keyed on and the backtest was run against.
    return CostOfHolding(
        scheme_code=str(scheme_code),
        amfi_direct_ter=amfi_direct,
        amfi_regular_ter=amfi_regular,
        groww_ter=groww,
        ter=amfi_direct,
        sources=sources,
        agrees=True,
        rankable_on_cost=True,
        is_passive=passive,
        flag=_unusual(amfi_direct, passive),
        note=None,
    )


def _percent(value: object) -> float | None:
    """A TER as a percentage, or None. Never 0.0 for something unreadable."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # A published TER of exactly zero is a read failure wearing a number: a fund
    # that charges nothing does not exist, and this value would sort first on
    # the one axis this app ranks by.
    return number if number > 0 else None


def _unusual(ter: float | None, passive: bool) -> str | None:
    """Worth a second look. NOT a claim that a limit was breached."""
    if ter is None:
        return None
    if passive and ter > _UNUSUAL_PASSIVE_PP:
        return f"{ter:.2f}% is unusually high for a fund that tracks an index."
    if not passive and ter > _UNUSUAL_DIRECT_PP:
        return (
            f"{ter:.2f}% is unusually high for a direct plan, which carries no "
            "distributor commission."
        )
    return None
