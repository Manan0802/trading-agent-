"""Which plan a holding is really on, and which direct plan replaces it.

Two problems, one cause.

**The name a user types is not evidence.** Plan type was read off whatever they
called the holding, so somebody who typed "HDFC Flexi Cap Fund - Regular Plan"
against scheme code 118955 — which AMFI publishes as the *Direct* plan — was
told they were losing money to a distributor and shown a lever worth over a lakh
to fix it. Nothing was wrong. The code is authoritative and we already fetch its
real name; the typed string is a label.

**"Switch to the direct plan" is not an instruction.** It is the one fund
decision this app has measured and it stopped one step short of being followable,
leaving the user to find the right scheme themselves on a broker's search box —
which is where a plan like this actually dies. The direct twin is found by
stripping the plan and option words from both names and matching the rest.

The matcher refuses rather than guesses. Naming the wrong fund is far worse than
naming none: the reader would move real money into it.
"""

import re
from dataclasses import dataclass

from app.services.advisor.fund_catalogue import CatalogueFund, all_funds
from app.services.marketdata.mutual_fund import MutualFundDataError, get_scheme_meta

# Everything that distinguishes two share classes of one portfolio, rather than
# two portfolios. Stripped from both sides before matching.
_PLAN_WORDS = re.compile(
    r"\b(direct|regular)\b"
    r"|\bplan\b|\boption\b|\bgrowth\b|\bpayout\b|\breinvestment\b"
    r"|\bidcw\b|\bdividend\b|\bmutual\s+fund\b"
    r"|[-–—,()./]",
    re.I,
)

_DIRECT = re.compile(r"\bdirect\b", re.I)
_REGULAR = re.compile(r"\bregular\b", re.I)


def core_name(name: str) -> str:
    """"HDFC Flexi Cap Fund - Growth Option - Regular Plan" -> "HDFC FLEXI CAP FUND"."""
    return " ".join(_PLAN_WORDS.sub(" ", name or "").split()).upper()


@dataclass(frozen=True)
class PlanIdentity:
    """What a holding actually is, and what it could be swapped for."""

    scheme_code: str
    # The name AMFI publishes for this code, not the one the user typed.
    official_name: str | None
    plan: str | None
    # The direct plan of the same portfolio. None when the holding is already
    # direct, or when no confident match exists.
    direct_code: str | None = None
    direct_name: str | None = None
    # Why there is no twin, when there is none to give.
    note: str | None = None


def classify(name: str) -> str | None:
    """Direct, regular, or unknown. Older schemes predate the split entirely."""
    if _DIRECT.search(name or ""):
        return "direct"
    if _REGULAR.search(name or ""):
        return "regular"
    return None


def _catalogue_index() -> dict[str, list[CatalogueFund]]:
    index: dict[str, list[CatalogueFund]] = {}
    for fund in all_funds():
        index.setdefault(core_name(fund.name), []).append(fund)
    return index


def identify(scheme_code: str, typed_name: str = "") -> PlanIdentity:
    """Resolve one holding: what plan it is on, and its direct equivalent."""
    official: str | None = None
    try:
        official = get_scheme_meta(scheme_code).scheme_name
    except (MutualFundDataError, Exception):  # noqa: BLE001
        # The feed being down must not silently reclassify a holding. Falling
        # back to the typed name is a guess, and it is marked as one.
        official = None

    name = official or typed_name
    plan = classify(name)

    if plan != "regular":
        return PlanIdentity(
            scheme_code=scheme_code,
            official_name=official,
            plan=plan,
            note=None
            if plan == "direct"
            else "This scheme's name says neither direct nor regular, so we do "
            "not assume. Check your statement before acting on any cost figure.",
        )

    matches = _catalogue_index().get(core_name(name), [])
    # A regular plan matching more than one direct scheme means the stripped
    # name is not unique enough to act on, which is a refusal, not a coin toss.
    if len(matches) != 1:
        return PlanIdentity(
            scheme_code=scheme_code,
            official_name=official,
            plan="regular",
            note=(
                "We could not identify its direct plan with confidence, so we "
                "are not naming one. Search your broker for the same fund with "
                '"Direct" in the name and check the AMC matches.'
                if not matches
                else f"{len(matches)} direct schemes share this name, so we are "
                "not guessing which is the pair. Check the AMC on your statement."
            ),
        )

    twin = matches[0]
    return PlanIdentity(
        scheme_code=scheme_code,
        official_name=official,
        plan="regular",
        direct_code=twin.code,
        direct_name=twin.name,
    )
