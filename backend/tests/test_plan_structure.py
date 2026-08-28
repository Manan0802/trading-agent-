"""Two defects this document produced twice, now gated instead of noticed.

Heading order: pass 87 found four headings out of numeric order and moved them.
Pass 129 reintroduced one, inserting §2.5 before §2.4 — the pass that knew about
the defect committed it. Nothing was watching.

Row length: the cost-data finding reached 7,702 characters inside one table
cell, because six consecutive passes appended to it rather than promoting it.
A renderer will not break that cell, so it stops being readable long before
anyone notices it is long.
"""

import re
from pathlib import Path

PLAN = Path(__file__).resolve().parent.parent.parent / "docs" / "phase-1-redesign.md"

# Above this, a finding belongs in its own subsection with the row pointing at
# it. Set from the distribution on pass 130: median 880, and the two rows above
# 2,500 were both findings large enough to have earned a section.
MAX_ROW_CHARS = 3000


def _sort_key(number: str) -> tuple[int, int, str]:
    parts = number.split(".")
    major = int(parts[0])
    if len(parts) == 1:
        return (major, -999, "")
    match = re.match(r"(-?\d+)([a-z]?)$", parts[1])
    if not match:
        return (major, -998, parts[1])
    return (major, int(match.group(1)), match.group(2) or "")


def test_every_heading_is_in_numeric_order():
    numbers = re.findall(
        r"^#{2,4}\s+(\d+(?:\.\d+[a-z]?|\.-\d+)?)\.?\s", PLAN.read_text(), re.M
    )
    out_of_order = [
        (numbers[i - 1], numbers[i])
        for i in range(1, len(numbers))
        if _sort_key(numbers[i]) < _sort_key(numbers[i - 1])
    ]
    assert not out_of_order, f"headings out of order: {out_of_order}"


def test_no_open_row_has_grown_past_reading():
    text = PLAN.read_text()
    start = text.index("### 9.1 Still open")
    rows = [
        line
        for line in text[start : text.index("### 9.2 Closed")].split("\n")
        if line.startswith("| `")
    ]
    assert rows, "§9.1 has no tagged rows"
    too_long = [
        (len(r), re.match(r"\| `[^`]+` (?:🔴|🟡|🟢|✅|⚠️)?\s*\*\*(.*?)\*\*", r))
        for r in rows
        if len(r) > MAX_ROW_CHARS
    ]
    assert not too_long, (
        "these rows are too long to read in a table cell — promote each to its "
        "own subsection and leave a pointer: "
        + "; ".join(f"{n} chars: {m.group(1)[:50] if m else '?'}" for n, m in too_long)
    )


_CONTRASTS = (
    r"`([^`]{2,60})`,?\s+not\s+`([^`]{2,60})`",
    r"`([^`]{2,60})`\s+rather than\s+`([^`]{2,60})`",
    r"\*\"([^\"]{3,60})\"\*,?\s+not\s+\*\"([^\"]{3,60})\"\*",
)


def test_no_contrast_pair_has_collapsed_into_itself():
    """"Write X, not Y" is broken the moment X and Y are the same string.

    Pass 145 path-qualified every file:line citation with one substitution, and
    it rewrote the counter-example too — the sentence briefly read "write
    app/schemas/portfolio.py:262, not app/schemas/portfolio.py:262". A bulk edit
    cannot tell a form being recommended from the same form being warned about,
    so the document has to be able to.
    """
    text = PLAN.read_text()
    collapsed = []
    for pattern in _CONTRASTS:
        for match in re.finditer(pattern, text):
            left, right = match.group(1).strip(), match.group(2).strip()
            if left == right:
                collapsed.append(match.group(0)[:80])
    assert not collapsed, (
        "these say 'X, not X' — a find-and-replace ate one side: "
        + "; ".join(collapsed)
    )
