"""The plan counts this repo's routes three ways, and one count did not add up.

§9.1 read "34 declare a response_model, 12 do not" against 49 routes — 34 + 12
is 46. The substantive claim (which endpoints are untyped) was right; the
arithmetic was not, and it had been read past for many passes because nothing
recomputed it.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
PLAN = BACKEND.parent / "docs" / "phase-1-redesign.md"

_ROUTE = re.compile(
    r"@router\.(?:get|post|put|delete|patch)\(\s*(?:\"[^\"]*\"|'[^']*')([^)]*)\)", re.S
)


def _counts() -> tuple[int, int, int]:
    total = typed = 0
    for path in (BACKEND / "app" / "routers").glob("*.py"):
        for match in _ROUTE.finditer(path.read_text()):
            total += 1
            if "response_model" in match.group(1):
                typed += 1
    return total, typed, total - typed


def test_the_plan_states_the_real_route_counts():
    total, typed, untyped = _counts()
    text = PLAN.read_text()

    stated = re.search(
        r"\*\*(\d+) declare a `response_model`, (\d+) do not\*\*", text
    )
    assert stated, "§9.1 no longer states the typed/untyped split"
    assert (int(stated.group(1)), int(stated.group(2))) == (typed, untyped)
    assert int(stated.group(1)) + int(stated.group(2)) == total, "the split must sum"

    assert re.search(rf"\b{total} (?:routes|endpoints|API endpoints)\b", text), (
        f"the plan no longer states {total} routes"
    )
