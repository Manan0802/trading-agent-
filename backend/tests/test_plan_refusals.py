"""§5's refusals are referenced by number thirteen times, from an ordinary list.

`§5.2`, `§5.6` and the rest point at items in a markdown ordered list. Nothing
ties the reference to the item: insert a tenth refusal at position three and
every reference from `§5.4` on silently means something else, in a section whose
whole job is to say what the app refuses to do and why.

This pins the nine, in order, by their opening words. It is deliberately a
change-detector: the correct response to a failure is to renumber the
references, not to update the list here and move on.
"""

import re
from pathlib import Path

PLAN = Path(__file__).resolve().parent.parent.parent / "docs" / "phase-1-redesign.md"

REFUSALS = [
    'No "sell the underperformer"',
    "No concentration *limit* as a risk trigger",
    "No trailing stops",
    "No price alerts, streaks, confetti, or daily P&L on the home screen",
    "No AUM-bloat threshold",
    "No manager-change action",
    "No behaviour-gap number",
    "No `groww_rating` shown as a rating",
    "The app never places an order",
]


def _items() -> list[str]:
    text = PLAN.read_text()
    start = text.index("## 5. What this app will not do")
    section = text[start : text.index("## 6.", start)]
    return re.findall(r"^\d+\. \*\*(.+?)\.?\*\*", section, re.M)


def test_the_nine_refusals_are_unchanged_and_in_order():
    found = _items()
    assert found == REFUSALS, (
        "§5's list changed. Thirteen references point at these by position — "
        "renumber them before updating this test."
    )


def test_every_bare_section_five_reference_resolves_to_one():
    """A `§5.n` with no PRD prefix must land inside the list."""
    text = PLAN.read_text()
    n = len(_items())
    for m in re.finditer(r"(PRD )?§5\.(\d)", text):
        if m.group(1):
            continue  # "PRD §5.6" is the other document, correctly marked
        assert 1 <= int(m.group(2)) <= n, f"§5.{m.group(2)} has no item ({n} exist)"
