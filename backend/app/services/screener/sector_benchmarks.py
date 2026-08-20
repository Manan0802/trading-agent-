"""Adapting traa's sector medians to what the ported stock scorer expects.

There is one sector table in this codebase and this is not it. It is
`app/data/sector_benchmarks.json`, built by `scripts/build_sector_benchmarks.py`
from traa's own NSE universe -- 961 constituents across 12 sectors, against the
reference implementation's hand-picked 80-ticker basket -- and read by
`advisor/stock_analysis.sector_benchmarks()`. This module is a thin adapter over
that, and deliberately not a second source.

**The units differ and that is the whole reason this file exists.** traa stores
ROE and dividend yield as decimal fractions; the ported scorer's `_score_roe`
and `_score_div_yield` compare against percents. Feeding 0.15 where 15.0 is
expected makes every real company look a hundred times more profitable than its
sector, and nothing downstream would error.

    traa's file            the ported scorer wants
    ---------------------  ------------------------
    pe             22.2    median_pe          22.2   (unchanged)
    pb              3.7    median_pb           3.7   (unchanged)
    roe          0.1463    median_roe        14.63   (x100)
    dividend_yield 0.0091  median_div_yield   0.91   (x100)

**It also closes a crash.** Upstream's benchmark record allows `median_pe` and
`median_pb` to be None when a sector's sample is thin, and `_score_pe` and
`_score_pb` divide by them without checking -- so an unknown or thin sector is a
TypeError at scoring time rather than the neutral score every other missing
input produces. `resolve()` always returns a complete record: traa's table
carries an `_ALL` row computed across every stock it knows, which is a far
better default than a hardcoded guess, and any remaining gap falls back to it
field by field.
"""

from __future__ import annotations

from functools import lru_cache

from app.services.advisor.stock_analysis import sector_benchmarks as _traa_table

# traa's table calls the all-stocks row this. It is the honest default for a
# sector we have no sample for: the median of everything we actually score.
ALL_STOCKS = "_ALL"

_REQUIRED = ("median_pe", "median_pb", "median_roe", "median_div_yield")

# Only reached if traa's table has no `_ALL` row at all. Round numbers because
# they are judgement, not measurement, and `resolve` records when one is used.
_LAST_RESORT = {
    "median_pe": 22.0,
    "median_pb": 3.0,
    "median_roe": 15.0,
    "median_div_yield": 1.2,
}


class SectorBenchmarksUnavailable(Exception):
    """The sector table is missing or unusable.

    Raised rather than substituting neutral medians everywhere: scoring every
    stock against invented numbers produces a full, plausible-looking ranking
    built on nothing, which is worse than an error a router turns into a 503.
    """


def _adapt(row: dict) -> dict:
    """One of traa's rows in the units the ported factors compare against."""
    out = {}
    for ours, theirs, scale in (
        ("median_pe", "pe", 1.0),
        ("median_pb", "pb", 1.0),
        ("median_roe", "roe", 100.0),
        ("median_div_yield", "dividend_yield", 100.0),
    ):
        value = row.get(theirs)
        out[ours] = None if value is None else round(float(value) * scale, 4)
    out["constituents"] = row.get("n", 0)
    return out


@lru_cache(maxsize=1)
def _table() -> dict[str, dict]:
    raw = _traa_table()
    if not raw:
        raise SectorBenchmarksUnavailable(
            "app/data/sector_benchmarks.json is missing or unreadable; "
            "run scripts/build_sector_benchmarks.py"
        )
    return {name: _adapt(row) for name, row in raw.items()}


def built_from() -> int:
    """How many stocks the medians were computed over, for the screen to say.

    "Cheap versus peers" means nothing without knowing how many peers.
    """
    table = _table()
    return table.get(ALL_STOCKS, {}).get("constituents", 0)


def sectors() -> list[str]:
    return sorted(n for n in _table() if n != ALL_STOCKS)


def resolve(sector: str | None) -> dict:
    """A complete record for any sector, real or not. Never None, never partial.

    Missing fields are filled from the all-stocks row rather than dropped,
    because a partial record reaches a function that divides by it.
    """
    table = _table()
    default = table.get(ALL_STOCKS, {})
    row = dict(table.get(sector or "", default) or default)
    for key in _REQUIRED:
        if row.get(key) is None:
            row[key] = default.get(key) if default.get(key) is not None else _LAST_RESORT[key]
    return row


def clear_cache() -> None:
    """Drop the cached table. Only tests need this."""
    _table.cache_clear()
    _traa_table.cache_clear()
