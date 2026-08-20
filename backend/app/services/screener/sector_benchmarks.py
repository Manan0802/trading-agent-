"""Loading the per-sector medians the four valuation factors compare against.

Built by `scripts/build_sector_benchmarks.py` into `app/data/sector_benchmarks.json`
and read here through an `@lru_cache(maxsize=1)` loader, matching how every other
piece of reference data in this codebase is handled.

**This layer exists partly to close a crash.** Upstream's benchmark record allows
`median_pe` and `median_pb` to be None when a sector's basket comes back too
thin, and `_score_pe` and `_score_pb` divide by them without checking. An
unknown or thin sector is therefore a TypeError at scoring time rather than the
neutral score every other missing input produces -- upstream has simply not hit
it yet. The builder never writes a None, and `resolve()` guarantees a complete
record for every input including sectors it has never heard of, so the division
cannot be reached with a None on either side.

Units are not uniform and this is where a caller gets it wrong:

    median_pe        a ratio      (18.97 means a P/E of 18.97)
    median_pb        a ratio      (2.18)
    median_roe       a PERCENT    (13.35 means 13.35%)
    median_div_yield a PERCENT    (0.94 means 0.94%)

Note the asymmetry inside `_score_roe`: the benchmark arrives as a percent while
the company's own ROE arrives as a decimal fraction from yfinance, and the
function converts the company's before comparing. Do not "fix" one to match the
other without reading that function.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "sector_benchmarks.json"

# The record handed back for a sector we have no basket for. Deliberately the
# same shape as a real one, so no caller needs a None branch.
UNKNOWN_SECTOR = "Unknown"

_REQUIRED = ("median_pe", "median_pb", "median_roe", "median_div_yield")


class SectorBenchmarksUnavailable(Exception):
    """The benchmark file is missing or unusable.

    Raised rather than silently substituting neutral medians: scoring every
    stock against invented numbers would produce a full, plausible-looking
    ranking built on nothing, which is worse than an error a router can turn
    into a 503.
    """


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        payload = json.loads(DATA.read_text())
    except (OSError, ValueError) as exc:
        raise SectorBenchmarksUnavailable(
            f"cannot read {DATA}; run scripts/build_sector_benchmarks.py"
        ) from exc

    sectors = payload.get("sectors") or {}
    if UNKNOWN_SECTOR not in sectors:
        raise SectorBenchmarksUnavailable(
            f"{DATA} has no {UNKNOWN_SECTOR!r} record, so an unmapped stock has "
            "nothing to be scored against"
        )
    for name, row in sectors.items():
        missing = [k for k in _REQUIRED if row.get(k) is None]
        if missing:
            raise SectorBenchmarksUnavailable(
                f"{name} is missing {missing}; the valuation factors divide by "
                "these and would raise rather than score neutrally"
            )
    return payload


def built_on() -> str:
    """The date the medians were computed, for the screen to disclose.

    Sector medians drift with the market. A number built six months ago is not
    wrong, but it is not current either, and a screen that shows "cheap versus
    peers" should say when "peers" was measured.
    """
    return _load().get("built_on", "unknown")


def sectors() -> list[str]:
    return sorted(n for n in _load()["sectors"] if n != UNKNOWN_SECTOR)


def resolve(sector: str | None) -> dict:
    """The medians for a sector, always complete, never None.

    An unrecognised sector gets the Unknown record rather than an error or a
    guess. That is what makes a newly-listed company in a sector we have no
    basket for score neutrally on valuation instead of crashing the run.
    """
    table = _load()["sectors"]
    if sector and sector in table:
        return table[sector]
    return table[UNKNOWN_SECTOR]


def clear_cache() -> None:
    """Drop the cached file. Only tests need this."""
    _load.cache_clear()
