"""Trim the NAV store to funds you can actually buy, over the history the
scorer actually reads.

    venv/bin/python scripts/trim_nav_store.py --dry-run
    venv/bin/python scripts/trim_nav_store.py --out .navstore/nav.trimmed.db

Why this exists
---------------
The full store is ~189 MB, and most of it is dead weight:

    4,939 schemes with NAV history
    1,777 of them still publishing a NAV        <- the buyable universe
    3,162 wound-up, merged or closed-ended      <- 64% of the funds

    2006-04-02 .. today of daily NAVs, where the scorer reads a 4-year window

Dropping the dead ones gives ~177 MB, and ~41 MB gzipped. That is the
difference between a store that needs a mounted volume and one that ships
alongside the code, which is the whole reason a free host becomes possible.

History is kept in full by default; see `DEFAULT_YEARS` for why cutting it
looks free and is not.

What is deliberately NOT trimmed
--------------------------------
`nav_source` and the four `screener_*` tables are copied verbatim. Together they
are under 5 MB, they are what lets a fresh boot serve a ranking immediately
instead of returning 503 until the first nightly run, and the coverage line is
computed from `screener_unscorable` -- dropping rows there would silently
overstate how much of the universe the screen covers.

Two safety properties
---------------------
1. **Never writes to the source.** Output is a separate file; promoting it is a
   deliberate `mv` you do yourself, after checking the numbers this prints.
2. **Never drops a fund the served run ranked.** Live-ness is read from the
   store's own newest NAV per scheme, and every code scored by the latest
   published run is kept on top of that -- otherwise the store and the run it
   serves disagree, and a ranked fund's detail page opens onto no history.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sqlite3
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.screener.metrics import METRICS_WINDOW_YEARS  # noqa: E402

DEFAULT_SRC = ".navstore/nav.db"

# History is NOT trimmed by default, and that is a deliberate reversal of the
# obvious optimisation. The scorer only reads a 4-year window, so cutting to 5
# looks free -- but `analysis.py` serves the fund detail page from the fund's
# ENTIRE history: the chart offers a "max" range, and `rolling_returns` walks
# every entry date the fund has ever had. Cutting to 5 years turns "max" into a
# silent synonym for "5y" and quietly weakens the one statistic on that page
# that distinguishes a typical result from a lucky window.
#
# Dropping dead funds is what actually pays: 3,162 of 4,939 schemes are wound
# up, which is 64% of the rows for 0% of the value. Measured on the live store:
#
#     4,939 funds, full history   189 MB   (41 MB gzipped)
#     1,777 funds, full history   177 MB   (41 MB gzipped)  <- default
#     1,777 funds, 5y history      98 MB   (23 MB gzipped)  <- --years 5
#
# Gzipped, keeping every year costs nothing over trimming to five, because NAV
# rows compress far better than they shrink. Pass `--years` only if the target
# actually cannot hold the decompressed file.
DEFAULT_YEARS = 0  # 0 means keep every year

# How stale a fund's last NAV may be before it counts as wound up. A working
# fund publishes daily; 90 days spans any plausible feed outage or holiday
# cluster without keeping schemes that quietly stopped reporting.
LIVE_WITHIN_DAYS = 90

COPY_VERBATIM = (
    "nav_source",
    "screener_run",
    "screener_score",
    "screener_unscorable",
    "screener_input",
)


def _parse_amfi_date(value: str) -> date | None:
    """AMFI writes DD-MM-YYYY. Anything else is treated as no date at all."""
    try:
        return datetime.strptime(value.strip(), "%d-%m-%Y").date()
    except (ValueError, AttributeError):
        return None


def live_codes(con: sqlite3.Connection, as_of: date) -> set[str]:
    """Codes whose newest NAV in the store is inside `LIVE_WITHIN_DAYS`.

    Read from the store, not from the catalogue. `CatalogueFund` carries only
    code, name, category and fund_house -- it has no `latest_nav_date` at all,
    so asking it for one returns nothing and silently keeps zero funds alive.
    The store is also the more honest source: it is the thing being trimmed, so
    a fund is live here if and only if the rows we are about to keep say it is.
    """
    cutoff = (as_of - timedelta(days=LIVE_WITHIN_DAYS)).isoformat()
    return {
        str(r[0])
        for r in con.execute(
            "SELECT scheme_code FROM nav_history "
            "GROUP BY scheme_code HAVING max(nav_date) >= ?",
            (cutoff,),
        )
    }


def served_codes(con: sqlite3.Connection) -> set[str]:
    """Every code the latest published run refers to, scored or not."""
    row = con.execute(
        "SELECT id FROM screener_run WHERE completed_at IS NOT NULL "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        row = con.execute("SELECT max(id) FROM screener_run").fetchone()
    run_id = row[0] if row else None
    if run_id is None:
        return set()
    # `screener_score` only, deliberately. Every catalogue fund lands in
    # `screener_input` or `screener_unscorable`, so including those matches the
    # entire universe and the trim becomes a no-op -- measured: 4,939 of 4,939
    # kept. Only funds that actually earned a rank need their history kept.
    return {
        str(r[0])
        for r in con.execute(
            "SELECT code FROM screener_score WHERE run_id=?", (run_id,)
        )
    }


# What the RUNTIME actually reads out of this file. Everything else is build
# scratch and must not be shipped.
#
# An allowlist, not a blocklist, and the difference is the whole point. The trim
# is `con.backup()` -- a whole-file snapshot -- followed by one DELETE against
# nav_history, so any table added later rides along at full size unless somebody
# remembers to name it here. `stock_daily` is coming and is estimated at ~9.3M
# rows; a blocklist ships it the day it lands and nobody finds out until the
# free host runs out of disk. With an allowlist a new table is excluded by
# default, and adding it to the published copy is a deliberate line of code.
_SERVED_TABLES = frozenset(
    {
        "nav_history",
        "nav_source",
        "screener_run",
        "screener_score",
        "screener_input",
        "screener_unscorable",
    }
)


def _drop_unserved_tables(dst: sqlite3.Connection) -> list[str]:
    """Remove every table the served app does not read. Returns what went."""
    present = {
        row[0]
        for row in dst.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    }
    dropped = sorted(present - _SERVED_TABLES)
    for name in dropped:
        dst.execute(f'DROP TABLE IF EXISTS "{name}"')
    if dropped:
        dst.commit()
    return dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=None, help="default: <src>.trimmed")
    ap.add_argument("--years", type=int, default=DEFAULT_YEARS)
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--gzip", action="store_true", help="also write <out>.gz")
    args = ap.parse_args()

    src = args.src
    if not os.path.exists(src):
        print(f"no store at {src}", file=sys.stderr)
        return 1
    out = args.out or f"{src}.trimmed"

    as_of = date.today()
    cutoff = (
        date(as_of.year - args.years, as_of.month, as_of.day).isoformat()
        if args.years
        else "0000-00-00"  # sorts below every real date, so nothing is cut
    )

    con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    before_rows = con.execute("SELECT count(*) FROM nav_history").fetchone()[0]
    before_codes = con.execute(
        "SELECT count(DISTINCT scheme_code) FROM nav_history"
    ).fetchone()[0]

    keep = live_codes(con, as_of) | served_codes(con)
    have = {r[0] for r in con.execute("SELECT DISTINCT scheme_code FROM nav_history")}
    keep &= {str(c) for c in have}

    print(f"source        : {src}  ({os.path.getsize(src)/1e6:.1f} MB)")
    print(f"schemes        : {before_codes:,} -> {len(keep):,}")
    print(f"history        : {'all years kept' if not args.years else f'cut before {cutoff}'}  (scorer window {METRICS_WINDOW_YEARS}y)")
    if args.dry_run:
        n = con.execute(
            "SELECT count(*) FROM nav_history WHERE nav_date >= ?", (cutoff,)
        ).fetchone()[0]
        print(f"rows           : {before_rows:,} -> at most {n:,} (dry run, nothing written)")
        return 0

    for path in (out, f"{out}-wal", f"{out}-shm"):
        if os.path.exists(path):
            os.remove(path)

    # SQLite's backup API, NOT shutil.copyfile.
    #
    # The store runs in WAL mode, so the newest writes sit in `nav.db-wal` and
    # not in `nav.db` at all -- 10 MB of it here. A file copy takes the main
    # database and silently leaves that behind: measured, the copy's newest NAV
    # was 2026-08-24 against the source's 2026-08-25, one whole day of NAVs gone
    # with no error anywhere, which then moved `roll1y` for 121 funds. The
    # backup API reads through the WAL and produces a consistent snapshot.
    #
    # Copying rather than re-declaring the schema also means indexes, types and
    # any column added later arrive on their own instead of being dropped here.
    dst = sqlite3.connect(out)
    con.backup(dst)
    dst.execute("PRAGMA journal_mode=DELETE")
    dropped = _drop_unserved_tables(dst)
    if dropped:
        print(f"dropped        : {', '.join(dropped)}  (not served at runtime)")
    placeholders = ",".join("?" * len(keep))
    dst.execute(
        f"DELETE FROM nav_history WHERE nav_date < ? OR scheme_code NOT IN ({placeholders})",
        [cutoff, *sorted(keep)],
    )
    dst.commit()
    after_rows = dst.execute("SELECT count(*) FROM nav_history").fetchone()[0]
    after_codes = dst.execute(
        "SELECT count(DISTINCT scheme_code) FROM nav_history"
    ).fetchone()[0]
    dst.execute("VACUUM")
    dst.close()

    size = os.path.getsize(out)
    print(f"rows           : {before_rows:,} -> {after_rows:,}")
    print(f"schemes kept   : {after_codes:,}")
    print(f"output        : {out}  ({size/1e6:.1f} MB, was {os.path.getsize(src)/1e6:.1f} MB)")

    if args.gzip:
        with open(out, "rb") as fh, gzip.open(f"{out}.gz", "wb", compresslevel=6) as gz:
            shutil.copyfileobj(fh, gz)
        print(f"gzipped       : {out}.gz  ({os.path.getsize(f'{out}.gz')/1e6:.1f} MB)")

    print("\nNothing was promoted. To use it:")
    print(f"  mv {out} {src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
