"""The NAV store's guarantees, including the ones that keep it out of the app DB.

Every test here points the store at a tmp_path, so nothing touches the real
`.navstore/nav.db`.
"""

import os
from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.screener import navstore

AS_OF = date.today()

# Every seeded series ends HERE, derived from AS_OF rather than written down.
#
# It used to be a literal `LAST_NAV` while `AS_OF` followed the wall
# clock. That works until the gap crosses the screener's freshness rule, and
# then a batch of tests fails on a day nobody changed anything — reporting
# `pool_size=0` as though the slot mapping had broken.
LAST_NAV = AS_OF - timedelta(days=1)



@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    yield
    navstore.reset_engine()


def navs(start: date, n: int, first: float = 10.0) -> list[tuple[date, float]]:
    return [(start + timedelta(days=i), first + i * 0.1) for i in range(n)]


# --------------------------------------------------------------- the constraint


def test_a_zero_nav_cannot_be_stored():
    """AMFI serves zero-NAV placeholder rows for dates before a scheme launched.

    Dividing by one produces NaN metrics, and a fund with NaN metrics once
    ranked first on garbage. Filtering in the parser fixes that parser; the
    constraint makes the whole class of bug unreachable from anywhere.
    """
    with pytest.raises(IntegrityError):
        with navstore.session() as s:
            navstore.insert_navs(s, "1", [(date(2024, 1, 1), 0.0)])


def test_a_negative_nav_cannot_be_stored():
    with pytest.raises(IntegrityError):
        with navstore.session() as s:
            navstore.insert_navs(s, "1", [(date(2024, 1, 1), -3.0)])


def test_the_constraint_can_actually_fail():
    """The control. A guard that cannot fire is worse than no guard, because it
    reads as protection. This suite has twice contained a check that could only
    pass."""
    engine = navstore.get_engine()
    with engine.connect() as conn:
        sql = conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE name = 'nav_history'"
        ).scalar()
    assert "nav > 0" in sql, "the CHECK is not in the deployed schema"
    assert "WITHOUT ROWID" in sql, "the layout that costs 2.8x on disk is not applied"


# --------------------------------------------------------------- idempotency


def test_reinserting_the_same_day_is_a_no_op():
    """The backfill is resumable, so a chunk can be replayed. Replaying it must
    cost bandwidth and nothing else."""
    rows = navs(date(2024, 1, 1), 5)
    with navstore.session() as s:
        assert navstore.insert_navs(s, "A", rows) == 5
    with navstore.session() as s:
        assert navstore.insert_navs(s, "A", rows) == 0
        assert len(navstore.nav_window(s, "A")) == 5


def test_a_later_value_for_a_stored_date_does_not_overwrite():
    """Pins the DO NOTHING decision so a change to UPSERT has to change a test.

    A settled NAV should not flap because AMFI served one bad row today. The
    cost -- a genuine restatement is never picked up -- is covered by
    validate_nav_integrity.py and by `backfill --force --only CODE`.
    """
    with navstore.session() as s:
        navstore.insert_navs(s, "A", [(date(2024, 1, 1), 10.0)])
    with navstore.session() as s:
        navstore.insert_navs(s, "A", [(date(2024, 1, 1), 99.0)])
    with navstore.session() as s:
        assert navstore.nav_window(s, "A") == [(date(2024, 1, 1), 10.0)]


# --------------------------------------------------------------- reads


def test_the_window_is_bounded_at_both_ends_and_ordered_oldest_first():
    with navstore.session() as s:
        navstore.insert_navs(s, "A", navs(date(2024, 1, 1), 10))
    with navstore.session() as s:
        got = navstore.nav_window(s, "A", start=date(2024, 1, 3), end=date(2024, 1, 5))
    assert [d for d, _ in got] == [date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)]


def test_the_four_year_window_is_measured_from_as_of_not_from_the_last_nav():
    """Upstream cuts at `now() - 4y`, not at `max(nav_date) - 4y`.

    A fund that stopped publishing two years ago therefore gets a two-year
    window, not four years of its own history. That is their behaviour and it
    changes every metric, so it is pinned rather than tidied.
    """
    as_of = date(2026, 8, 20)
    with navstore.session() as s:
        navstore.insert_navs(s, "DEAD", navs(date(2020, 1, 1), 400))  # ends 2021-02
    cutoff = date(as_of.year - 4, as_of.month, as_of.day)
    with navstore.session() as s:
        assert navstore.nav_window(s, "DEAD", start=cutoff) == []
        assert len(navstore.nav_window(s, "DEAD")) == 400


def test_the_tail_ignores_the_window_entirely():
    """Momentum reads the last 22 NAVs over the fund's whole history, with no
    four-year cutoff -- upstream's `ORDER BY nav_date DESC LIMIT 22`. For a
    rarely-publishing fund that is a different set of rows from the window's
    tail, which is why there are two queries and not one."""
    with navstore.session() as s:
        navstore.insert_navs(s, "OLD", navs(date(2015, 1, 1), 30))
    with navstore.session() as s:
        tail = navstore.nav_tail(s, "OLD", 22)
    assert len(tail) == 22
    assert tail[0][0] < tail[-1][0], "the tail must come back oldest first"
    assert tail[-1][0] == date(2015, 1, 30)


def test_an_unknown_scheme_reads_as_empty_not_as_an_error():
    with navstore.session() as s:
        assert navstore.nav_window(s, "nope") == []
        assert navstore.nav_tail(s, "nope", 22) == []


# --------------------------------------------------------------- the ledger


def test_the_ledger_is_derived_from_what_is_actually_stored():
    """Not from the caller's count, so it cannot drift from the data it describes."""
    with navstore.session() as s:
        navstore.insert_navs(s, "A", navs(date(2024, 1, 1), 7))
        navstore.record_source(s, "A", backfilled_at="2026-08-20T00:00:00")
    with navstore.session() as s:
        row = s.execute(
            navstore.text("SELECT row_count, first_nav_date, last_nav_date FROM nav_source")
        ).one()
    assert row[0] == 7
    assert str(row[1]) == "2024-01-01"
    assert str(row[2]) == "2024-01-07"


def test_zero_rows_accumulate_across_runs_rather_than_being_overwritten():
    """A fund that is suddenly half zeros is a feed problem. If the counter reset
    on every touch, that signal would never survive to be noticed."""
    with navstore.session() as s:
        navstore.insert_navs(s, "A", navs(date(2024, 1, 1), 2))
        navstore.record_source(s, "A", zero_rows=3)
    with navstore.session() as s:
        navstore.record_source(s, "A", zero_rows=4)
    with navstore.session() as s:
        assert s.execute(navstore.text("SELECT zero_rows FROM nav_source")).scalar() == 7


def test_only_finished_funds_count_as_backfilled():
    with navstore.session() as s:
        navstore.insert_navs(s, "DONE", navs(date(2024, 1, 1), 2))
        navstore.record_source(s, "DONE", backfilled_at="2026-08-20T00:00:00")
        navstore.insert_navs(s, "PART", navs(date(2024, 1, 1), 2))
        navstore.record_source(s, "PART", last_error="timeout")
    with navstore.session() as s:
        assert navstore.backfilled_codes(s) == {"DONE"}
        assert navstore.store_stats(s)["funds"] == 1


def test_the_live_count_is_relative_to_as_of_not_to_the_whole_catalogue():
    """Only about 1,700 of the 4,957 catalogue codes are alive; the rest are
    wound-up series that last published between 2014 and 2022. A canary phrased
    against 4,957 would be red every night."""
    as_of = date(2026, 8, 20)
    with navstore.session() as s:
        navstore.insert_navs(s, "LIVE", [(LAST_NAV, 10.0)])
        navstore.record_source(s, "LIVE")
        navstore.insert_navs(s, "DEAD", [(date(2019, 3, 3), 10.0)])
        navstore.record_source(s, "DEAD")
    with navstore.session() as s:
        assert navstore.live_fund_count(s, as_of) == 1


# --------------------------------------------------------------- the serving gate


def _run(session_, *, completed: bool, as_of=date(2026, 8, 20)) -> int:
    session_.execute(
        navstore.text(
            "INSERT INTO screener_run (as_of, started_at, completed_at) "
            "VALUES (:a, 'x', :c)"
        ),
        {"a": as_of.isoformat(), "c": "done" if completed else None},
    )
    return int(session_.execute(navstore.text("SELECT MAX(id) FROM screener_run")).scalar())


def test_an_unfinished_run_is_never_served():
    """An empty screener rendering zero rows behind a 200 is the silent failure
    this codebase keeps writing tests against."""
    with navstore.session() as s:
        _run(s, completed=False)
    with navstore.session() as s:
        assert navstore.latest_run_id(s) is None


def test_a_crash_mid_write_leaves_the_previous_run_serving():
    with navstore.session() as s:
        good = _run(s, completed=True)
    with navstore.session() as s:
        _run(s, completed=False)
    with navstore.session() as s:
        assert navstore.latest_run_id(s) == good


def test_pruning_keeps_the_newest_runs_and_takes_their_children_with_them():
    with navstore.session() as s:
        ids = [_run(s, completed=True) for _ in range(10)]
        for i in ids:
            s.execute(
                navstore.text(
                    "INSERT INTO screener_score (run_id, code, in_sample) VALUES (:r, 'A', 1)"
                ),
                {"r": i},
            )
    with navstore.session() as s:
        assert navstore.prune_runs(s, keep=7) == 3
    with navstore.session() as s:
        left = [r[0] for r in s.execute(navstore.text("SELECT id FROM screener_run")).all()]
        assert sorted(left) == sorted(ids[3:])
        orphans = s.execute(
            navstore.text(
                "SELECT COUNT(*) FROM screener_score WHERE run_id NOT IN "
                "(SELECT id FROM screener_run)"
            )
        ).scalar()
        assert orphans == 0, "child rows outlived their run"


# --------------------------------------------------------------- the separation


def test_the_nav_tables_are_not_in_the_app_metadata():
    """This is what keeps the two databases from merging by accident.

    If these models ever reach `app/models/__init__.py`, every test file's
    `Base.metadata.create_all` starts building NAV tables inside the user test
    database, and Alembic starts autogenerating migrations for a cache.
    """
    from app.database import Base

    for name in (
        "nav_history",
        "nav_source",
        "screener_run",
        "screener_score",
        "screener_unscorable",
        "screener_input",
    ):
        assert name not in Base.metadata.tables, f"{name} leaked into the app database"


def test_the_store_has_its_own_declarative_base():
    from app.database import Base

    assert navstore.StoreBase is not Base
    assert navstore.NavHistory.__table__.metadata is navstore.StoreBase.metadata


def test_the_store_path_follows_the_env_var():
    assert navstore.db_path().name == "nav.db"
    assert str(navstore.db_path()) == os.environ["NEXTRADE_NAV_DB"]


def test_there_is_no_index_on_nav_date():
    """Documented non-action. An index on nav_date would add about 35% to the
    file and serve no query in this design -- the daily refresh writes, it does
    not scan by date. This test is where someone adding one has to argue."""
    engine = navstore.get_engine()
    with engine.connect() as conn:
        idx = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='nav_history'"
        ).all()
    assert idx == [], f"unexpected index on nav_history: {idx}"


def test_the_range_query_is_served_by_the_primary_key():
    """If this ever stops being a PK search, the nightly read goes from 2.3
    seconds to a full scan of five million rows."""
    engine = navstore.get_engine()
    with engine.connect() as conn:
        plan = " ".join(
            str(r[3])
            for r in conn.exec_driver_sql(
                "EXPLAIN QUERY PLAN SELECT nav_date, nav FROM nav_history "
                "WHERE scheme_code = 'A' AND nav_date >= '2020-01-01' ORDER BY nav_date"
            ).all()
        )
    assert "USING PRIMARY KEY" in plan, plan
    assert "SCAN" not in plan, plan


def test_wal_is_on_because_the_nightly_writer_must_not_block_readers():
    engine = navstore.get_engine()
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"


def test_a_changed_env_var_actually_repoints_the_store(tmp_path, monkeypatch):
    """The engine is cached, so a stale cache would silently keep writing to the
    old file -- which in a test run means writing into the real store."""
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "other.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    assert str(navstore.get_engine().url).endswith("other.db")
