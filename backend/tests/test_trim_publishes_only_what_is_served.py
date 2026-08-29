"""What the nightly publishes, and the table that has not landed yet.

`trim_nav_store.py` is `con.backup()` -- a whole-file snapshot -- followed by one
DELETE against nav_history. So every OTHER table in the store rides into the
published asset at full size. Today that is harmless. `stock_daily` is estimated
at ~9.3M rows and does not exist yet, which is exactly when this is cheap to fix
and exactly when nobody thinks to.

The guard is an allowlist. A blocklist ships a new table the day it lands.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND / "scripts" / "trim_nav_store.py"


def _store(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE nav_history (scheme_code TEXT, nav_date TEXT, nav REAL);
        CREATE TABLE nav_source (scheme_code TEXT PRIMARY KEY, last_error TEXT);
        CREATE TABLE screener_run (id INTEGER PRIMARY KEY, completed_at TEXT);
        CREATE TABLE screener_score (run_id INTEGER, code TEXT);
        CREATE TABLE screener_input (run_id INTEGER, code TEXT);
        CREATE TABLE screener_unscorable (run_id INTEGER, code TEXT);
        -- The one this test exists for.
        CREATE TABLE stock_daily (symbol TEXT, d TEXT, close REAL);
        CREATE TABLE corporate_actions (symbol TEXT, d TEXT, kind TEXT);
        """
    )
    con.executemany(
        "INSERT INTO nav_history VALUES (?, ?, ?)",
        [("122639", "2026-08-25", 90.0), ("122639", "2026-08-26", 91.0)],
    )
    con.execute("INSERT INTO nav_source VALUES ('122639', NULL)")
    con.execute("INSERT INTO screener_run VALUES (1, '2026-08-29T00:00:00')")
    con.execute("INSERT INTO screener_score VALUES (1, '122639')")
    con.executemany(
        "INSERT INTO stock_daily VALUES (?, ?, ?)",
        [("RELIANCE", f"2026-08-{d:02d}", 1400.0) for d in range(1, 26)],
    )
    con.execute("INSERT INTO corporate_actions VALUES ('RELIANCE','2026-08-01','split')")
    con.commit()
    con.close()


def _tables(path: Path) -> set[str]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }
    finally:
        con.close()


def test_the_published_copy_carries_only_the_tables_the_app_serves(tmp_path):
    src = tmp_path / "nav.db"
    out = tmp_path / "published.db"
    _store(src)
    assert {"stock_daily", "corporate_actions"} <= _tables(src)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--src", str(src), "--out", str(out), "--years", "0"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    published = _tables(out)
    assert "stock_daily" not in published, (
        "~9.3M rows of daily stock prices shipped to a free host that fetches "
        "this file at boot"
    )
    assert "corporate_actions" not in published
    assert "nav_history" in published, "the whole point of the file is still there"
    assert "nav_source" in published


def test_a_table_nobody_has_thought_of_is_excluded_by_default(tmp_path):
    """The allowlist's reason for being.

    A blocklist only excludes what someone remembered to name, so the next
    build-scratch table ships silently at whatever size it happens to be.
    """
    src = tmp_path / "nav.db"
    out = tmp_path / "published.db"
    _store(src)
    con = sqlite3.connect(src)
    con.execute("CREATE TABLE some_future_scratch_table (a TEXT)")
    con.commit()
    con.close()

    subprocess.run(
        [sys.executable, str(SCRIPT), "--src", str(src), "--out", str(out), "--years", "0"],
        cwd=BACKEND,
        check=True,
        capture_output=True,
    )
    assert "some_future_scratch_table" not in _tables(out)


def test_the_nav_rows_still_survive_the_trim(tmp_path):
    src = tmp_path / "nav.db"
    out = tmp_path / "published.db"
    _store(src)
    subprocess.run(
        [sys.executable, str(SCRIPT), "--src", str(src), "--out", str(out), "--years", "0"],
        cwd=BACKEND,
        check=True,
        capture_output=True,
    )
    con = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    try:
        assert con.execute("SELECT count(*) FROM nav_history").fetchone()[0] == 2
    finally:
        con.close()
