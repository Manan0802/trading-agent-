"""The NAV spine: a local, rebuildable history of every fund's published NAV.

This is a *separate database file* from the app's, and that is a deliberate
decision rather than a convenience.

`nextrade.db` is 933 KB. This dataset is around 184 MB -- roughly two hundred
times the entire user database -- and it is public, rederivable from mfapi in
minutes, and rewritten every night. Putting it in the same file would mean every
backup, restore and free-tier disk quota carries it, and that a backfill filling
the disk turns into "the user cannot save a goal". `Procfile` runs
`alembic upgrade head` on every boot, so a `downgrade()` here would be a
multi-minute destructive operation running against live user data.

There is also a correctness argument. Production may be Postgres while dev is
SQLite, and that divergence would land precisely on the most performance-
sensitive code in the system: bulk insert, `ON CONFLICT`, and the query plan for
the per-fund range scan. A dedicated SQLite store is byte-identical in dev and
in production.

What it costs, stated honestly: losing this file is not free the way losing
`.navcache` is. It costs a 5-30 minute rebuild, during which the screener has
nothing to serve. That is handled at the serving edge -- a 503 carrying rebuild
progress -- not wished away.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# Matches the four existing cache-dir env vars (NEXTRADE_CACHE_DIR and friends),
# so deployment has one convention to follow rather than two.
DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / ".navstore" / "nav.db"

# Bumped when the derived screener_* tables change shape. They rebuild from
# nav_history in about fifteen seconds, so dropping and recreating them is
# cheaper than writing a migration. nav_history itself is never touched by this;
# a change to its shape is rare enough to deserve a deliberate one-off script.
SCHEMA_VERSION = 1

# How many nightly runs to keep. Enough to answer "why did this fund drop forty
# places last Tuesday" without the score tables growing without bound.
RUNS_RETAINED = 7


class StoreBase(DeclarativeBase):
    """Deliberately NOT `app.database.Base`.

    These tables must never reach `app/models/__init__.py` or `migrations/env.py`.
    If they did, every test file's `Base.metadata.create_all` would start building
    NAV tables inside the user test database, and Alembic would start generating
    migrations for a cache. `test_navstore.py` asserts the separation.
    """


class NavHistory(StoreBase):
    """One published NAV. The whole point of the phase.

    `WITHOUT ROWID` is worth 2.8x on disk here (869 MB -> 480 MB at 13.6M rows,
    332 MB -> 184 MB at the 5.2M we actually expect), because the primary key
    *is* the row rather than a duplicated index over it.

    There is no secondary index and there must not be one. Every read is
    `WHERE scheme_code = ? AND nav_date >= ? ORDER BY nav_date`, which
    EXPLAIN QUERY PLAN resolves as
    `SEARCH nav_history USING PRIMARY KEY (scheme_code=? AND nav_date>?)`.
    An index on nav_date would add about 35% to the file and serve no query in
    this design -- the daily refresh writes, it does not scan by date.
    """

    __tablename__ = "nav_history"
    # Ignored by Postgres, honoured by SQLite. Autogenerate never emits it,
    # which is one more reason this table is not under Alembic.
    __table_args__ = (
        CheckConstraint("nav > 0", name="ck_nav_history_nav_positive"),
        {"sqlite_with_rowid": False},
    )

    scheme_code: Mapped[str] = mapped_column(String, primary_key=True)
    nav_date: Mapped[date] = mapped_column(Date, primary_key=True)
    # The CHECK is the structural fix for AMFI's zero-NAV placeholder rows, which
    # it serves for dates before a scheme launched. Dividing by one produces NaN
    # metrics, and a fund with NaN metrics once ranked first on garbage. Filtering
    # in the parser fixes the parser; the constraint fixes the class of bug.
    nav: Mapped[float] = mapped_column(Float, nullable=False)


class NavSource(StoreBase):
    """One row per scheme: the backfill resume ledger, and its provenance.

    `backfilled_at` is what makes the backfill resumable. It is written in the
    same transaction as that chunk's nav_history rows, so an interrupt can only
    lose the chunk in flight -- at most a hundred funds redone.
    """

    __tablename__ = "nav_source"

    scheme_code: Mapped[str] = mapped_column(String, primary_key=True)
    first_nav_date: Mapped[date | None] = mapped_column(Date)
    last_nav_date: Mapped[date | None] = mapped_column(Date)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Counted rather than merely dropped: a fund that is suddenly half zeros is
    # a feed problem, and a silent filter would hide it.
    zero_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backfilled_at: Mapped[str | None] = mapped_column(String)
    last_error: Mapped[str | None] = mapped_column(String)


class ScreenerRun(StoreBase):
    """One nightly scoring pass.

    `completed_at IS NULL` means the run either is still going or died. Nothing
    serves from such a run -- see `latest_run_id`. A failed run is recorded
    rather than discarded, so the failure is visible in the data and not only in
    a log nobody reads.
    """

    __tablename__ = "screener_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String)
    universe_size: Mapped[int | None] = mapped_column(Integer)
    scored: Mapped[int | None] = mapped_column(Integer)
    unscorable: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String)


class ScreenerScore(StoreBase):
    """A `ScoredFund`, persisted. Mirrors `universe.ScoredFund` field for field."""

    __tablename__ = "screener_score"
    __table_args__ = ({"sqlite_with_rowid": False},)

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("screener_run.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str | None] = mapped_column(String)
    sub_category: Mapped[str | None] = mapped_column(String)
    quality: Mapped[float | None] = mapped_column(Float)
    momentum: Mapped[float | None] = mapped_column(Float)
    drawdown: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    in_sample: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str | None] = mapped_column(String)
    peer_median: Mapped[float | None] = mapped_column(Float)
    peer_size: Mapped[int | None] = mapped_column(Integer)
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_tier: Mapped[str | None] = mapped_column(String)


class ScreenerUnscorable(StoreBase):
    """A fund the run could not score, and why.

    Persisted rather than dropped because the coverage line on the screen --
    "1,886 of 1,886" -- is only trustworthy if the shortfall can be named per
    fund.
    """

    __tablename__ = "screener_unscorable"
    __table_args__ = ({"sqlite_with_rowid": False},)

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("screener_run.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)


class ScreenerInput(StoreBase):
    """The exact metrics that produced a run's scores.

    About two thousand rows a night. This is the only thing that makes "why did
    this fund drop forty places" answerable next month: without it, a rank change
    is unattributable to either the NAV data or the arithmetic.
    """

    __tablename__ = "screener_input"
    __table_args__ = ({"sqlite_with_rowid": False},)

    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("screener_run.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String, primary_key=True)
    roll1y: Mapped[float | None] = mapped_column(Float)
    roll6m: Mapped[float | None] = mapped_column(Float)
    roll3m: Mapped[float | None] = mapped_column(Float)
    roll1m: Mapped[float | None] = mapped_column(Float)
    ret3y: Mapped[float | None] = mapped_column(Float)
    ret1y: Mapped[float | None] = mapped_column(Float)
    ret3m: Mapped[float | None] = mapped_column(Float)
    vol: Mapped[float | None] = mapped_column(Float)
    sortino: Mapped[float | None] = mapped_column(Float)
    max_dd: Mapped[float | None] = mapped_column(Float)
    worst_30d: Mapped[float | None] = mapped_column(Float)
    history_years: Mapped[float | None] = mapped_column(Float)
    nav_rows: Mapped[int | None] = mapped_column(Integer)
    capped_days: Mapped[int | None] = mapped_column(Integer)
    last_nav_date: Mapped[date | None] = mapped_column(Date)
    nav_fresh: Mapped[int] = mapped_column(Integer, nullable=False)


def db_path() -> Path:
    return Path(os.environ.get("NEXTRADE_NAV_DB", str(DEFAULT_DB_PATH)))


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None
_engine_url: str | None = None


def _set_navstore_pragmas(dbapi_connection, connection_record) -> None:
    """WAL is load-bearing here, not a tuning knob.

    Without it the nightly writer holds an exclusive lock for the length of the
    write and every screener request blocks behind it. With it, readers never
    block on the writer.

    `synchronous=NORMAL` is durable across process crashes when WAL is on, and
    only at risk on power loss. For a store that can be rebuilt from mfapi in
    half an hour that is the right trade, and it is what makes committing once
    per hundred-fund chunk cheap enough to be the resume granularity.

    Deliberately absent: VACUUM. This table only ever grows -- inserts are
    `DO NOTHING`, there are no deletes -- so there is nothing to reclaim, and a
    VACUUM over a 200 MB file would lock it for minutes.

    Registered on our engine instance rather than on the Engine class, so the
    app's own connections are untouched.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def get_engine() -> Engine:
    global _engine, _SessionLocal, _engine_url
    url = f"sqlite:///{db_path().resolve()}"
    if _engine is None or _engine_url != url:
        db_path().parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(_engine, "connect", _set_navstore_pragmas)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        _engine_url = url
    return _engine


def reset_engine() -> None:
    """Drop the cached engine so a changed NEXTRADE_NAV_DB takes effect.

    Only tests need this; they point the store at a tmp_path per module.
    """
    global _engine, _SessionLocal, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    _engine_url = None


@contextmanager
def session():
    """A session usable from a scheduler job.

    `app.database.get_db()` is a FastAPI generator dependency and must not be
    called from an APScheduler job. Because this store is a separate engine, the
    nightly job never touches `app.database` at all.
    """
    get_engine()
    assert _SessionLocal is not None
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def ensure_schema() -> None:
    """Create anything missing, and rebuild the derived tables if they are stale.

    `create_all` emits IF NOT EXISTS, so this is safe to call on every startup
    and at the top of every job.
    """
    engine = get_engine()
    StoreBase.metadata.create_all(engine)

    with engine.connect() as conn:
        version = conn.exec_driver_sql("PRAGMA user_version").scalar() or 0
        if version == SCHEMA_VERSION:
            return

    derived = [
        ScreenerInput.__table__,
        ScreenerUnscorable.__table__,
        ScreenerScore.__table__,
        ScreenerRun.__table__,
    ]
    StoreBase.metadata.drop_all(engine, tables=derived)
    StoreBase.metadata.create_all(engine, tables=list(reversed(derived)))
    with engine.begin() as conn:
        conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")


# ---------------------------------------------------------------- reads


def nav_window(
    session_,
    scheme_code: str,
    start: date | None = None,
    end: date | None = None,
) -> list[tuple[date, float]]:
    """One fund's NAVs in a date range, oldest first.

    Served entirely by the primary key -- `EXPLAIN QUERY PLAN` gives
    `SEARCH nav_history USING PRIMARY KEY (scheme_code=? AND nav_date>?)`.
    Reading a four-year window for all 4,957 funds this way takes about 2.3
    seconds against a 13.6M-row table, which is why the nightly metrics pass is
    not worth parallelising.
    """
    sql = "SELECT nav_date, nav FROM nav_history WHERE scheme_code = :code"
    params: dict[str, object] = {"code": scheme_code}
    if start is not None:
        sql += " AND nav_date >= :start"
        params["start"] = start.isoformat()
    if end is not None:
        sql += " AND nav_date <= :end"
        params["end"] = end.isoformat()
    sql += " ORDER BY nav_date"
    rows = session_.execute(text(sql), params).all()
    return [(_as_date(r[0]), float(r[1])) for r in rows]


def nav_tail(session_, scheme_code: str, limit: int) -> list[tuple[date, float]]:
    """The last N NAVs over the fund's *entire* history, oldest first.

    Momentum needs this rather than a slice of the four-year window: upstream's
    `compute_momentum_drawdown` runs `ORDER BY nav_date DESC LIMIT 22` with no
    cutoff at all. For a fund with 22 NAVs inside the window the two are
    identical; for a rarely-publishing one they are not, and issuing the second
    query is cheaper than the argument about whether it matters.
    """
    rows = session_.execute(
        text(
            "SELECT nav_date, nav FROM nav_history WHERE scheme_code = :code "
            "ORDER BY nav_date DESC LIMIT :n"
        ),
        {"code": scheme_code, "n": limit},
    ).all()
    return [(_as_date(r[0]), float(r[1])) for r in reversed(rows)]


def latest_run_id(session_) -> int | None:
    """The newest run that actually finished.

    The `completed_at IS NOT NULL` clause is the belt to the transaction's
    braces. The write is a single transaction, so a half-finished run should be
    impossible -- but a future refactor might split it, and an empty screener
    rendering zero rows behind a 200 is exactly the silent failure this codebase
    keeps writing tests against.
    """
    return session_.execute(
        text("SELECT MAX(id) FROM screener_run WHERE completed_at IS NOT NULL")
    ).scalar()


def backfilled_codes(session_) -> set[str]:
    """Schemes the backfill has already finished, for `--resume`."""
    rows = session_.execute(
        text("SELECT scheme_code FROM nav_source WHERE backfilled_at IS NOT NULL")
    ).all()
    return {r[0] for r in rows}


def store_stats(session_) -> dict[str, object]:
    """Enough to render "rebuilding: 1,240 of 4,957 funds" in a 503."""
    row = session_.execute(
        text(
            "SELECT COUNT(*), COALESCE(SUM(row_count), 0), MAX(last_nav_date) "
            "FROM nav_source WHERE backfilled_at IS NOT NULL"
        )
    ).one()
    return {
        "funds": int(row[0] or 0),
        "rows": int(row[1] or 0),
        "newest_nav_date": _as_date(row[2]) if row[2] else None,
    }


def newest_nav_date(session_) -> date | None:
    value = session_.execute(text("SELECT MAX(last_nav_date) FROM nav_source")).scalar()
    return _as_date(value) if value else None


def live_fund_count(session_, as_of: date, within_days: int = 10) -> int:
    """Funds that published a NAV recently. The denominator for the daily canary.

    Phrased against yesterday's live set rather than against the full 4,957,
    because only about 1,700 of those codes are alive: 2,482 are wound-up FMPs
    and capital-protection series that last published between 2014 and 2022.
    A canary against 4,957 would be red every single night.
    """
    cutoff = date.fromordinal(as_of.toordinal() - within_days)
    return int(
        session_.execute(
            text("SELECT COUNT(*) FROM nav_source WHERE last_nav_date >= :cutoff"),
            {"cutoff": cutoff.isoformat()},
        ).scalar()
        or 0
    )


# ---------------------------------------------------------------- writes


def insert_navs(session_, scheme_code: str, rows: list[tuple[date, float]]) -> int:
    """Insert NAVs, ignoring any date already stored. Returns rows inserted.

    `DO NOTHING` rather than an upsert is a decision, not an oversight: a settled
    NAV should not flap because AMFI served one bad row today. It does mean a
    genuine restatement is never picked up, which is why
    `scripts/validate_nav_integrity.py` samples stored-vs-mfapi and reports
    mismatches, and why `backfill --force --only CODE` exists.

    Rows with a non-positive NAV are the caller's job to filter and *count*; the
    CHECK constraint here is the backstop, and a CHECK violation is not a
    conflict, so it would raise rather than being swallowed by DO NOTHING.
    """
    if not rows:
        return 0
    before = session_.execute(
        text("SELECT COUNT(*) FROM nav_history WHERE scheme_code = :c"),
        {"c": scheme_code},
    ).scalar()
    session_.execute(
        text(
            "INSERT INTO nav_history (scheme_code, nav_date, nav) "
            "VALUES (:c, :d, :n) ON CONFLICT (scheme_code, nav_date) DO NOTHING"
        ),
        [{"c": scheme_code, "d": d.isoformat(), "n": n} for d, n in rows],
    )
    after = session_.execute(
        text("SELECT COUNT(*) FROM nav_history WHERE scheme_code = :c"),
        {"c": scheme_code},
    ).scalar()
    return int(after) - int(before)


def record_source(
    session_,
    scheme_code: str,
    *,
    backfilled_at: str | None = None,
    zero_rows: int = 0,
    last_error: str | None = None,
) -> None:
    """Refresh a scheme's ledger row from what is actually stored.

    Derived from nav_history rather than from the caller's count, so the ledger
    cannot drift from the data it describes.
    """
    agg = session_.execute(
        text(
            "SELECT COUNT(*), MIN(nav_date), MAX(nav_date) "
            "FROM nav_history WHERE scheme_code = :c"
        ),
        {"c": scheme_code},
    ).one()
    session_.execute(
        text(
            "INSERT INTO nav_source "
            "(scheme_code, first_nav_date, last_nav_date, row_count, zero_rows,"
            " backfilled_at, last_error) "
            "VALUES (:c, :f, :l, :n, :z, :b, :e) "
            "ON CONFLICT (scheme_code) DO UPDATE SET "
            "  first_nav_date = excluded.first_nav_date,"
            "  last_nav_date  = excluded.last_nav_date,"
            "  row_count      = excluded.row_count,"
            "  zero_rows      = nav_source.zero_rows + excluded.zero_rows,"
            "  backfilled_at  = COALESCE(excluded.backfilled_at, nav_source.backfilled_at),"
            "  last_error     = excluded.last_error"
        ),
        {
            "c": scheme_code,
            "f": agg[1],
            "l": agg[2],
            "n": int(agg[0] or 0),
            "z": zero_rows,
            "b": backfilled_at,
            "e": last_error,
        },
    )


def prune_runs(session_, keep: int = RUNS_RETAINED) -> int:
    """Drop all but the newest `keep` runs. Returns how many went.

    SQLite does not enforce the ON DELETE CASCADE unless foreign keys are
    switched on per connection, so the child rows go explicitly.
    """
    ids = [
        r[0]
        for r in session_.execute(
            text("SELECT id FROM screener_run ORDER BY id DESC LIMIT -1 OFFSET :k"),
            {"k": keep},
        ).all()
    ]
    if not ids:
        return 0
    marks = ",".join(str(int(i)) for i in ids)
    for table in ("screener_input", "screener_unscorable", "screener_score", "screener_run"):
        column = "id" if table == "screener_run" else "run_id"
        session_.execute(text(f"DELETE FROM {table} WHERE {column} IN ({marks})"))
    return len(ids)


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
