import atexit
import os
from pathlib import Path

# One database file per pytest process, not one per checkout.
#
# This file previously hard-coded `backend/test_nextrade.db` and deleted it at
# import. Two pytest runs overlapping -- two terminals, or an agent running the
# suite while you do -- therefore delete each other's database mid-flight, and
# the result is dozens of OperationalErrors scattered across files that have
# nothing to do with each other. It cost real time to work out that those
# failures were not real, and it left `test_nextrade 2.db` ... `6.db` lying
# around the repo root.
#
# The PID makes runs independent. Everything else is unchanged: the file is
# still removed before anything imports `app.database`, so each run still starts
# from an empty schema and the tests' disjoint-user-id-band convention still
# does the within-run isolation.
TEST_DB_PATH = Path(__file__).parent.parent / f"test_nextrade.{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()


@atexit.register
def _remove_test_db() -> None:
    """Clean up on the way out, so a run does not leave a file per invocation.

    Best effort: a crashed interpreter skips this, and a leftover file is
    harmless because the next run picks a different name and this one is
    gitignored by `*.db`.
    """
    for path in (TEST_DB_PATH, TEST_DB_PATH.with_suffix(".db-wal"),
                 TEST_DB_PATH.with_suffix(".db-shm")):
        try:
            path.unlink()
        except OSError:
            pass
