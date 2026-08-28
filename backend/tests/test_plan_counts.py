"""The redesign plan states how many items are open and closed. Check it.

Three times a stated count in `docs/phase-1-redesign.md` drifted from the
table it described — twice from grouping the rows with a regex, once from a
headline that stopped being re-totalled while the tables under it grew. A
number in prose that nothing checks is a number that goes wrong quietly, and
this plan's own section 11 says an assertion has to be verifiable.
"""

import re
from pathlib import Path

PLAN = Path(__file__).resolve().parent.parent.parent / "docs" / "phase-1-redesign.md"


def _tables() -> tuple[list[str], list[str]]:
    text = PLAN.read_text()
    a = text.index("### 9.1 Still open")
    b = text.index("### 9.2 Closed")
    end = text.find("\n## 10.", b)
    closed_block = text[b:] if end == -1 else text[b:end]

    def rows(block: str) -> list[str]:
        return [
            line
            for line in block.split("\n")
            if line.startswith("| ") and "|---" not in line and line.strip() != "| | |"
        ]

    return rows(text[a:b]), rows(closed_block)


def test_headline_matches_both_tables():
    open_rows, closed_rows = _tables()
    line = re.search(
        r"\*\*(\d+) things are open\. (\d+) were open and are now closed\.\*\*",
        PLAN.read_text(),
    )
    assert line, "section 9 no longer states its counts"
    assert int(line.group(1)) == len(open_rows)
    assert int(line.group(2)) == len(closed_rows)


def test_every_open_row_carries_one_owner_tag():
    open_rows, _ = _tables()
    allowed = {
        "slice 0", "slice 1", "slice 2", "slice 3", "slice 4",
        "scope", "decide", "Manan", "limit",
    }
    for row in open_rows:
        tag = re.match(r"\| `([^`]+)` ", row)
        assert tag, f"untagged open row: {row[:70]}"
        assert tag.group(1) in allowed, f"unknown tag {tag.group(1)!r}"


def test_stated_group_sizes_match_the_tags():
    """The block of per-group counts is derived, so it must agree with the tags."""
    open_rows, _ = _tables()
    tally: dict[str, int] = {}
    for row in open_rows:
        tag = re.match(r"\| `([^`]+)` ", row).group(1)
        tally[tag] = tally.get(tag, 0) + 1

    text = PLAN.read_text()
    block = text[text.index("### 9.1 Still open") :].split("```")[1]
    stated = {}
    for line in block.strip().split("\n"):
        name, _, count = line.rpartition(" ")
        stated[name.strip()[:9].strip()] = int(count)

    assert set(stated) == set(tally), f"prose groups {set(stated)} != tags {set(tally)}"
    for tag, n in tally.items():
        assert stated[tag] == n, f"{tag}: table has {n}, prose says {stated[tag]}"


def test_the_plans_current_state_test_count_is_the_real_one():
    """Three separate counts in this plan went stale by never being re-totalled.

    §9's headline, §9.1 row 41 and the repo-history block each stated a number
    once and were not updated as the thing they counted grew. The suite size is
    the one that appears in prose twice, so it gets pinned. This test counts
    itself, which is correct: adding a test is exactly when the prose is wrong.
    """
    import subprocess
    import sys

    root = PLAN.parent.parent
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only"],
        cwd=root / "backend",
        capture_output=True,
        text=True,
    ).stdout
    match = re.search(r"(\d+) tests collected", out)
    assert match, f"could not read a collected count from pytest:\n{out[-400:]}"
    real = int(match.group(1))

    text = PLAN.read_text()
    # the two current-state mentions; historical ones ("suite 1,577 -> 1,584")
    # are records of a past run and are deliberately not touched
    current = {int(m.replace(",", "")) for m in re.findall(r"([\d,]+) tests green", text)}
    current |= {int(m.replace(",", "")) for m in re.findall(r"([\d,]+) tests · a 5\.2M-row", text)}
    assert current, "the plan no longer states its suite size"
    assert current == {real}, f"plan says {sorted(current)}, suite collects {real}"


_WORDS = {
    "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}


def _spelled(phrase: str) -> int:
    """"eighty-four" -> 84; "one hundred four" -> 104. Hundreds multiply."""
    total = chunk = 0
    for part in phrase.lower().replace("-", " ").split():
        if part == "hundred":
            chunk = (chunk or 1) * 100
        else:
            chunk += _WORDS[part]
    return total + chunk


def test_the_front_page_pass_count_matches_the_log():
    """The readiness verdict is the first thing a reviewer reads.

    It said "thirty-six review passes" while §18 recorded eighty-four, and it
    is the one number in this document that, when stale, makes the review look
    like it found less than it did. Spelled-out numbers were invisible to every
    other check here, which is why this one reads words rather than digits.
    """
    text = PLAN.read_text()
    logged = {int(n) for n in re.findall(r"^pass (\d+)\s", text, re.M)}
    assert logged, "§18's review log is gone"

    match = re.search(r"\*\*([a-z]+(?:[ -][a-z]+)*) review passes\*\*", text)
    assert match, "the readiness verdict no longer states a pass count"
    assert _spelled(match.group(1)) == len(logged), (
        f"verdict says {match.group(1)} ({_spelled(match.group(1))}), "
        f"§18 logs {len(logged)}"
    )
