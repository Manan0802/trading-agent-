"""When each committed data file was built, and how confidently we know it.

§14 makes coverage a type: `ScreenerCoverageOut` carries `as_of` and
`stale_days` because "a nightly precompute that quietly goes stale returns 200
with old numbers and nothing catches it". The files under `app/data/` did not
hold to that. Four could date themselves; three could not, and one of those was
`sector_benchmarks.json` -- twelve sectors of median P/E, P/B and ROE, which is
what decides whether a stock reads cheap or dear. A P/E median from three months
ago against today's price is a stale comparison presenting itself as a current
one, and nothing said so.

The date lives beside the files rather than inside them. `fund_catalogue.json`
is `{category: [funds]}`, `stock_universe.json` is a list and
`sector_benchmarks.json` is `{sector: metrics}` -- every reader iterates the
whole structure, so a top-level `as_of` key would arrive as a category, a
sector, or a stock.

Two kinds of date, kept apart on purpose:

    "built"  the builder wrote it and said so. Trustworthy.
    "mtime"  nobody recorded it; this is when the file was last written on
             disk. A floor, not a fact -- a checkout or a copy moves it.
"""

import json
from datetime import date, datetime
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_MANIFEST = _DATA / "built.json"


def record(filename: str, when: date | None = None) -> None:
    """Called by a builder after it writes `filename`."""
    manifest = _read()
    manifest[filename] = {"as_of": (when or date.today()).isoformat(), "how": "built"}
    _MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")


def _read() -> dict:
    try:
        return json.loads(_MANIFEST.read_text())
    except (OSError, ValueError):
        return {}


def as_of(filename: str) -> tuple[date, str] | None:
    """(date, how) for one data file, or None if the file itself is gone.

    Falls back to the file's mtime when no builder recorded it, and says so, so
    a caller can present "built on" and "last written" differently. A screen
    that cannot tell them apart should show neither as a guarantee.
    """
    path = _DATA / filename
    if not path.exists():
        return None
    entry = _read().get(filename)
    if entry:
        try:
            return date.fromisoformat(entry["as_of"]), entry.get("how", "built")
        except (KeyError, ValueError):
            pass
    return datetime.fromtimestamp(path.stat().st_mtime).date(), "mtime"


def stale_days(filename: str, today: date | None = None) -> int | None:
    stamped = as_of(filename)
    if stamped is None:
        return None
    return ((today or date.today()) - stamped[0]).days
