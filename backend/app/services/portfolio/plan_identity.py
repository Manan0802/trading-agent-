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
from functools import lru_cache

from app.services.advisor import plan_pairs
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


@lru_cache(maxsize=1)
def _house_tokens() -> frozenset[str]:
    """First words of every fund house in the catalogue: AXIS, ADITYA, SBI...

    Derived rather than listed, so a new AMC arrives with the catalogue instead
    of with a code change.
    """
    return frozenset(
        fund.fund_house.split()[0].upper()
        for fund in all_funds()
        if fund.fund_house and fund.fund_house.split()
    )


def _house_of(name: str) -> str | None:
    """The fund house a name claims, if it names a recognisable one."""
    words = core_name(name).split()
    return words[0] if words and words[0] in _house_tokens() else None


def misnamed_as(scheme_code: str, typed_name: str) -> str | None:
    """The authoritative name, when the label on a holding is a different fund.

    The scheme code drives every number in this app; the name is only a label
    someone typed. When they disagree, nothing is broken and nothing errors --
    the analysis is simply about a fund other than the one named, which is the
    worst kind of wrong number because it looks entirely right.

    Real case, found in our own demo data: "ICICI Prudential Corporate Bond
    Fund" carried code 119533, which AMFI publishes as "Aditya Birla Sun Life
    Corporate Bond Fund". Every figure was correct, and correct about Aditya
    Birla.

    The test is a disagreement about the **fund house**, not about the string.
    Comparing names directly cries wolf on every shorthand -- "PPFAS" is not a
    claim about a different fund from "Parag Parikh Flexi Cap Fund", it is the
    same fund typed lazily, and warning about it trains people to ignore the
    warning. Nor does sharing words discriminate: the real case above shares
    "Corporate Bond Fund" with the fund it is not.

    So both sides must name a house the catalogue recognises, and those houses
    must differ. Anything less certain stays silent.

    Returns None when they agree, when either side names no known house, when
    the feed is down (an outage is not evidence of a mismatch), or for anything
    that is not a mutual fund.
    """
    if not typed_name:
        return None
    try:
        official = get_scheme_meta(scheme_code).scheme_name
    except (MutualFundDataError, Exception):  # noqa: BLE001
        return None
    if not official:
        return None
    if core_name(official) == core_name(typed_name):
        return None

    typed_house, official_house = _house_of(typed_name), _house_of(official)
    if typed_house is None or official_house is None:
        return None
    return official if typed_house != official_house else None


def identify(scheme_code: str, typed_name: str = "") -> PlanIdentity:
    """Resolve one holding: what plan it is on, and its direct equivalent.

    The precomputed pairing is tried first. It is built from AMFI's own scheme
    list at catalogue-build time by joining both plans of a fund on the same
    normalised name `build_expense_ratios.py` uses, and it covers 3,762 of the
    4,136 regular growth plans AMFI lists.

    Two reasons it goes first. It is a LOCAL lookup, and the path below opens
    with `get_scheme_meta`, a network call per holding just to learn the plan
    type -- on a five-fund portfolio that is five round trips before any number
    appears. And it is built once, from the full list, rather than resolved per
    holding against a catalogue that holds only direct plans.

    When it does not know the code, everything below runs exactly as before,
    including the refusal when a stripped name matches more than one scheme.
    """
    twin = plan_pairs.direct_twin(scheme_code)
    if twin is not None:
        catalogue_names = {f.code: f.name for f in all_funds()}
        direct_name = catalogue_names.get(twin)
        if direct_name:
            return PlanIdentity(
                scheme_code=scheme_code,
                official_name=typed_name or None,
                plan="regular",
                direct_code=twin,
                direct_name=direct_name,
            )
        # Paired, but the direct side is not in the recommendation universe --
        # a fund we would not suggest buying. Say what it is; do not name a
        # scheme we cannot show.
        return PlanIdentity(
            scheme_code=scheme_code,
            # NOT the typed name. This field means "what AMFI publishes for
            # this code", and the whole reason this module exists is that the
            # typed string is a label, not evidence -- code 118955 is AMFI's
            # DIRECT plan and someone had typed "Regular Plan" against it. The
            # fast path skips the network and so cannot know the official name;
            # None says so, and callers already fall back to the typed name for
            # display. The wrong-fund guard is `misnamed_as`, which does its own
            # lookup and is unaffected.
            official_name=None,
            plan="regular",
            note=(
                "This is a regular plan. Its direct version is not in the "
                "browsable universe, so we are not naming one to switch to."
            ),
        )

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
