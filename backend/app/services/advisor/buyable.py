"""Which funds can actually be bought, and which of them only track an index.

A correct ranking of funds you cannot purchase is useless advice, and that is
what the screener produced: it ranked the whole 4,957-fund catalogue. This is
the filter that makes the output actionable -- 1,689 funds, measured live.

**`is_passive` is a read, not a guess.** It comes from the `index` boolean in
Groww's `st_filter` listing, and only from there: the per-scheme detail endpoint
does not carry the field at all (0 of 39 cached payloads), so before this file
existed the split was a name test -- "does the name contain Index or ETF" --
wearing the confidence of a real signal. On the pull that built this file,
**every one of the 1,689 buyable funds carries the flag.**

`passive_known` is kept alongside it so a fund Groww did not classify reads as
*unknown* rather than being silently filed as active. Nothing here falls back to
the name test: a fund whose classification we do not have is one this app should
not be splitting peer groups on.

Absence is a degraded state, not an error. With this file missing the screener
still ranks -- §2.1's rule is that Groww is an enrichment layer the app degrades
without, and AMFI stays the spine -- it simply cannot narrow to what is buyable,
and the surface has to say so rather than imply the whole catalogue is for sale.
"""

import json
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "groww_buyable.json"


@lru_cache(maxsize=1)
def _table() -> dict[str, dict]:
    try:
        return json.loads(_FILE.read_text())
    except (OSError, ValueError):
        return {}


def is_buyable(scheme_code: str) -> bool:
    return str(scheme_code) in _table()


def buyable_codes() -> frozenset[str]:
    return frozenset(_table())


def is_passive(scheme_code: str) -> bool | None:
    """True, False, or None when Groww did not classify this fund.

    None is a real answer and callers must handle it. Collapsing it to False
    files an unclassified index fund among active funds, where its 0.20% TER
    makes every genuine active fund look expensive.
    """
    row = _table().get(str(scheme_code))
    if row is None or not row.get("passive_known"):
        return None
    return bool(row.get("is_passive"))


def sub_category(scheme_code: str) -> str | None:
    row = _table().get(str(scheme_code))
    return (row or {}).get("sub_category") or None


def known() -> bool:
    """Whether the universe is loaded at all, so a surface can say when it is not."""
    return bool(_table())
