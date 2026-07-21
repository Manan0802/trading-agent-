"""Per-goal inflation, because one rate for every goal under-funds the expensive ones.

The advisor previously inflated every target at 6%, roughly headline CPI. That
is close enough for a car and badly wrong for education and healthcare, which
have compounded far above CPI in India for two decades. Over a fifteen-year
horizon the gap between 6% and 10% nearly doubles the target, so the error does
not show up as a slightly small SIP — it shows up as a goal that misses.
"""

GENERAL_INFLATION = 0.06

# Rates are deliberately round numbers. The underlying series are noisy and
# vary by city and institution, so a spuriously precise 10.4% would imply a
# confidence the data does not support.
_GOAL_INFLATION: dict[str, tuple[float, str]] = {
    "education": (
        0.10,
        "Private school and college fees in India have compounded around "
        "10-12% a year, far above headline CPI. Using CPI here is the single "
        "most common reason an education corpus falls short.",
    ),
    "healthcare": (
        0.13,
        "Medical inflation is the fastest-running number in the household "
        "budget at roughly 13-14%, driven by procedure costs rather than drug "
        "prices. Health cover matters more here than the SIP does.",
    ),
    "home": (
        0.07,
        "Property prices track construction costs and land, which have run "
        "slightly ahead of CPI. Highly city-specific — if you are buying in a "
        "metro, treat this as a floor.",
    ),
    "retirement": (
        0.07,
        "Headline inflation plus a tilt for the fact that healthcare becomes a "
        "large share of spending in later life. A single blended rate is a "
        "simplification; a real plan would inflate medical spending separately.",
    ),
    "car": (
        0.06,
        "Vehicle prices have broadly tracked general inflation.",
    ),
    "wedding": (
        0.08,
        "Venue, catering and gold all run ahead of CPI, and the budget tends "
        "to expand to fit the corpus.",
    ),
    "emergency": (
        0.06,
        "An emergency fund is sized against current monthly expenses, so it "
        "inflates with the general basket.",
    ),
}

_FALLBACK_NOTE = (
    "No goal-specific series applies, so this uses general inflation. If this "
    "goal is really education or healthcare spending under another name, "
    "reclassify it — those inflate much faster."
)


def inflation_for_goal(goal_type: str) -> float:
    entry = _GOAL_INFLATION.get((goal_type or "").strip().lower())
    return entry[0] if entry else GENERAL_INFLATION


def inflation_note(goal_type: str) -> str:
    entry = _GOAL_INFLATION.get((goal_type or "").strip().lower())
    rate, body = entry if entry else (GENERAL_INFLATION, _FALLBACK_NOTE)
    return f"Inflated at {rate:.0%} a year. {body}"
