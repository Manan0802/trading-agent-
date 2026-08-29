"""Which AMFI category labels are two names for the same SEBI category.

**Derived from evidence, not from judgement.** mfapi serves a different category
string for the SAME scheme code between crawls -- 563 funds changed label between
2026-08-28 and 2026-08-29 -- so a fund seen as `Debt Scheme - Low Duration Fund`
one day and `Income/Debt Oriented Schemes - Ultra Short to Short Term Fund` the
next has told us those are the same bucket. That is a measurement. Reading the
two names and deciding they look similar is not, and it gets things wrong: the
obvious guess for "Ultra Short to Short Term" is SEBI's *Ultra Short Duration*,
and all 23 funds carrying it are actually *Low Duration*.

Why it matters: a variant label is not a wrong ranking, it is ABSENCE. The
rankings route demands an exact SEBI prefix, so a fund wearing the other spelling
is unreachable through category browse and its real peer group is computed
without it.

    PYTHONPATH=. venv/bin/python scripts/build_category_synonyms.py OLD.json NEW.json

Both arguments are `fund_catalogue.json` snapshots. Output: app/data/category_synonyms.json
"""

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import data_built  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "category_synonyms.json"

_SEBI = (
    "Equity Scheme - ",
    "Debt Scheme - ",
    "Hybrid Scheme - ",
    "Other Scheme - ",
    "Solution Oriented Scheme - ",
)

# A synonym is accepted only when the evidence is both plentiful and one-sided.
# A single fund switching label is as likely to be a fund that genuinely changed
# category as it is to be a spelling; five funds all making the same move is not.
_MIN_FUNDS = 5
_MIN_SHARE = 0.80


def _codes(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text())
    return {e["code"]: cat for cat, funds in raw.items() for e in funds}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    before, after = _codes(Path(sys.argv[1])), _codes(Path(sys.argv[2]))

    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for code, old in before.items():
        new = after.get(code)
        if new is None or new == old:
            continue
        if old.startswith(_SEBI) and not new.startswith(_SEBI):
            votes[new][old] += 1
        elif new.startswith(_SEBI) and not old.startswith(_SEBI):
            votes[old][new] += 1

    synonyms, rejected = {}, []
    for variant, counts in votes.items():
        canon, n = counts.most_common(1)[0]
        total = sum(counts.values())
        if n >= _MIN_FUNDS and n / total >= _MIN_SHARE:
            synonyms[variant] = {"canonical": canon, "funds": n, "of": total}
        else:
            rejected.append((variant, dict(counts)))

    OUT.write_text(json.dumps(synonyms, indent=1, sort_keys=True))
    data_built.record("category_synonyms.json")

    print(f"{len(synonyms)} synonyms accepted -> {OUT}")
    for variant, row in sorted(synonyms.items(), key=lambda kv: -kv[1]["funds"])[:12]:
        print(f"  {row['funds']:4d}  {variant}  ->  {row['canonical']}")
    if rejected:
        print(f"\n{len(rejected)} rejected — too few funds or the evidence disagreed:")
        for variant, counts in rejected:
            print(f"  {variant}: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
