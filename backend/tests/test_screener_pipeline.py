"""The nightly run, and every way it is supposed to refuse.

A screener that serves an empty or half-built universe behind a 200 is worse
than one that serves an error, because nobody finds out. Most of this file is
therefore about writing *nothing* -- the canaries, the transaction boundary, and
the rule that a failed run is recorded rather than discarded.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.advisor import fund_catalogue
from app.services.screener import amfi, inputs as inputs_mod, navstore, pipeline, universe

AS_OF = date(2026, 8, 20)


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    # No test in this file is allowed near the network.
    monkeypatch.setattr(amfi, "refresh", lambda as_of=None: _feed_report())
    monkeypatch.setattr(amfi, "gap_fill", lambda as_of=None, limit=0: {"inserted": 0})
    yield
    navstore.reset_engine()


def _feed_report(inserted: int = 0):
    return amfi.FeedReport(
        data_lines=0, non_data_lines=0, parsed=0, skipped_na=0, skipped_zero=0,
        skipped_bad_nav=0, skipped_bad_date=0, skipped_unknown_code=0,
        inserted=inserted, newest_date=AS_OF, matched_catalogue_codes=0,
    )


def eligible_codes(n: int) -> list[str]:
    out = []
    for f in fund_catalogue.all_funds():
        category, sub = inputs_mod.split_category(f.category)
        if inputs_mod.is_eligible(category)[0] and sub:
            out.append(f.code)
            if len(out) == n:
                return out
    raise AssertionError("not enough eligible funds")


def seed(codes, rows: int = 800) -> None:
    """Eight hundred days, not three hundred.

    Under 365 calendar days `rolling_1y` has no complete window and comes back
    0.0, at which point `universe.is_scoreable` correctly refuses the fund for
    having "no full year of history". A 300-day fixture therefore produces a run
    with zero scored funds and looks like a pipeline bug. It is not one -- it is
    the gate doing its job, and the fixture has to clear it.
    """
    with navstore.session() as s:
        for i, code in enumerate(codes):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.05 + i)
                 for d in range(rows)],
            )
            navstore.record_source(s, code, backfilled_at="x")


def run(**kw):
    return pipeline.run_nightly(as_of=AS_OF, refresh_feed=False, **kw)


# ------------------------------------------------------------- the happy path


def test_a_good_run_is_accepted_and_becomes_the_one_that_serves():
    seed(eligible_codes(12))
    report = run()
    assert report.accepted and report.scored == 12
    with navstore.session() as s:
        assert navstore.latest_run_id(s) == report.run_id


def test_every_offered_fund_is_accounted_for_in_the_written_run():
    """The coverage line reads off these three numbers. If they do not add up,
    the screen is claiming a completeness it does not have."""
    seed(eligible_codes(10))
    report = run()
    with navstore.session() as s:
        scored = s.execute(navstore.text(
            "SELECT COUNT(*) FROM screener_score WHERE run_id = :r"), {"r": report.run_id}).scalar()
        unscorable = s.execute(navstore.text(
            "SELECT COUNT(*) FROM screener_unscorable WHERE run_id = :r"), {"r": report.run_id}).scalar()
        size = s.execute(navstore.text(
            "SELECT universe_size FROM screener_run WHERE id = :r"), {"r": report.run_id}).scalar()
    assert scored + unscorable == size == report.universe_size


def test_the_inputs_that_produced_each_score_are_kept():
    """Without this, "why did this fund drop forty places" is unanswerable next
    month: a rank change cannot be attributed to the NAV data or to the
    arithmetic."""
    codes = eligible_codes(6)
    seed(codes)
    report = run()
    with navstore.session() as s:
        row = s.execute(
            navstore.text(
                "SELECT roll1y, vol, nav_rows, nav_fresh FROM screener_input "
                "WHERE run_id = :r AND code = :c"
            ),
            {"r": report.run_id, "c": codes[0]},
        ).one()
    assert row[2] > 0 and row[3] == 1 and row[0] is not None and row[1] is not None


def test_only_the_last_seven_runs_are_kept():
    seed(eligible_codes(3))
    ids = [run().run_id for _ in range(9)]
    with navstore.session() as s:
        left = [r[0] for r in s.execute(navstore.text("SELECT id FROM screener_run")).all()]
        orphans = s.execute(navstore.text(
            "SELECT COUNT(*) FROM screener_score WHERE run_id NOT IN "
            "(SELECT id FROM screener_run)")).scalar()
    assert sorted(left) == sorted(ids[-7:])
    assert orphans == 0


# ------------------------------------------------------------- the canaries


def test_a_collapsed_universe_refuses_to_write(monkeypatch):
    """The failure this exists for: an empty store or a catalogue that failed to
    load produces twelve funds instead of 1,886, and the screen looks fine."""
    codes = eligible_codes(40)
    seed(codes)
    first = run()
    assert first.accepted and first.universe_size >= 40

    # Tonight the universe comes back tiny. Bound to the real function captured
    # before patching, so the stub cannot recurse into itself.
    real_build = inputs_mod.build_inputs

    # **kwargs so this stub survives a signature change on the real function --
    # it grew an `open_ended` argument and this test broke on the keyword rather
    # than on anything it was written to check.
    def only_two(session, as_of, codes=None, **kwargs):
        built = real_build(session, as_of, codes=codes, **kwargs)
        return inputs_mod.BuildResult(built.inputs[:2], [], built.metrics)

    monkeypatch.setattr(inputs_mod, "build_inputs", only_two)
    with pytest.raises(pipeline.PipelineRefused, match="universe collapsed"):
        run()

    with navstore.session() as s:
        assert navstore.latest_run_id(s) == first.run_id, "the good run stopped serving"
        assert s.execute(navstore.text("SELECT COUNT(*) FROM screener_run")).scalar() == 1, (
            "the refused run left a row behind"
        )


def test_the_collapse_canary_can_actually_fail():
    """The control. This suite has twice contained a check that could only pass,
    so every canary gets one."""
    assert pipeline.MIN_UNIVERSE_FRACTION > 0
    seed(eligible_codes(20))
    assert run().accepted
    with navstore.session() as s:
        previous = pipeline._last_accepted_size(s)
    assert previous and previous > 0, "nothing to compare against, so the canary is inert"


def test_a_first_ever_run_is_not_judged_against_a_universe_that_does_not_exist():
    seed(eligible_codes(3))
    assert run().accepted, "the very first run has no predecessor and must not trip the floor"


@pytest.mark.parametrize(
    "field,bad,expected",
    [
        ("score", 1.5, "outside"),
        ("score", float("nan"), "score is"),
        ("grade", "Excellent", "not one of"),
        ("risk_tier", "Spicy", "not a SEBI tier"),
    ],
)
def test_a_malformed_score_refuses_to_write(field, bad, expected):
    """A NaN score sorts first in some paths and last in others, and `safe_float`
    turns it into 0.0 downstream -- a silent last place with no explanation."""
    good = universe.ScoredFund(
        code="X", category="Equity Scheme", sub_category="Flexi Cap Fund",
        quality=0.5, momentum=0.1, drawdown=0.1, score=0.5, in_sample=True,
        grade="Good", risk_tier="Moderate",
    )
    from dataclasses import replace
    problems = pipeline.check_scored([replace(good, **{field: bad})], offered=1)
    assert problems and expected in problems[0]


def test_a_duplicate_scheme_code_refuses_to_write():
    """`grade_universe` groups by position precisely because codes can collide.
    Two rows with one code would also give React two children with one key."""
    f = universe.ScoredFund(
        code="DUP", category="Equity Scheme", sub_category=None, quality=0.5,
        momentum=0.1, drawdown=0.1, score=0.5, in_sample=True,
    )
    assert "scored more than once" in pipeline.check_scored([f, f], offered=2)[0]


def test_a_clean_universe_produces_no_complaints():
    f = universe.ScoredFund(
        code="A", category="Equity Scheme", sub_category=None, quality=0.5,
        momentum=0.1, drawdown=0.1, score=0.5, in_sample=True,
        grade="Avg", risk_tier="Moderate",
    )
    assert pipeline.check_scored([f], offered=1) == []


# ------------------------------------------------------- nothing half-written


def test_a_crash_mid_write_leaves_the_previous_run_serving(monkeypatch):
    """The single transaction is the mechanism; `completed_at IS NOT NULL` in the
    serving query is the belt. Both, because a refactor could split the write."""
    seed(eligible_codes(8))
    good = run()

    def boom(*a, **k):
        raise RuntimeError("disk went away")

    monkeypatch.setattr(navstore, "prune_runs", boom)
    with pytest.raises(RuntimeError):
        run()

    with navstore.session() as s:
        assert navstore.latest_run_id(s) == good.run_id
        rows = s.execute(navstore.text("SELECT COUNT(*) FROM screener_run")).scalar()
    assert rows == 1, "a rolled-back run left a row behind"


def test_a_second_process_refuses_to_race_a_run_already_in_flight():
    """`max_instances=1` is per process. `--workers N` or a second instance means
    N concurrent nightly runs against one store."""
    seed(eligible_codes(3))
    with navstore.session() as s:
        s.execute(
            navstore.text(
                "INSERT INTO screener_run (as_of, started_at) VALUES (:a, :s)"
            ),
            {"a": AS_OF.isoformat(), "s": datetime.now(timezone.utc).isoformat()},
        )
    with pytest.raises(pipeline.PipelineRefused, match="refusing to race"):
        run()


def test_a_run_abandoned_hours_ago_does_not_block_tonight():
    """The other half. A crashed process must not wedge the job forever."""
    seed(eligible_codes(3))
    stale = datetime.now(timezone.utc) - timedelta(hours=pipeline.STALE_RUN_HOURS + 1)
    with navstore.session() as s:
        s.execute(
            navstore.text("INSERT INTO screener_run (as_of, started_at) VALUES (:a, :s)"),
            {"a": AS_OF.isoformat(), "s": stale.isoformat()},
        )
    assert run().accepted


# ------------------------------------------------------------- the feed


def test_a_dead_feed_is_a_warning_not_a_failed_run(monkeypatch):
    """Today's NAVs did not arrive. The ten-day freshness gate is the correct
    automatic response, and a one-day-stale screener beats no screener. Only a
    *format* change is worth an alert, and that is what AmfiFeedError already is
    to a human reading the note."""
    seed(eligible_codes(5))

    def dead(as_of=None):
        raise amfi.AmfiFeedError("AMFI request failed")

    monkeypatch.setattr(amfi, "refresh", dead)
    report = pipeline.run_nightly(as_of=AS_OF, refresh_feed=True)
    assert report.accepted
    assert report.feed_error and "AMFI request failed" in report.note


def test_a_failing_gap_fill_does_not_stop_the_run(monkeypatch):
    seed(eligible_codes(5))

    def boom(as_of=None, limit=0):
        raise RuntimeError("mfapi is down")

    monkeypatch.setattr(amfi, "gap_fill", boom)
    report = pipeline.run_nightly(as_of=AS_OF, refresh_feed=True)
    assert report.accepted and "mfapi is down" in report.note


# ------------------------------------------------------------- the job wrapper


def test_the_job_never_raises_and_records_why(monkeypatch):
    """A job that raises inside APScheduler logs a traceback and vanishes. The
    failure has to be visible in the data, queryable tomorrow."""
    def refuse(*a, **k):
        raise pipeline.PipelineRefused("universe collapsed: 2 against 1886")

    monkeypatch.setattr(pipeline, "run_nightly", refuse)
    pipeline.nightly_job()  # must not raise

    with navstore.session() as s:
        note = s.execute(navstore.text(
            "SELECT note FROM screener_run ORDER BY id DESC LIMIT 1")).scalar()
        assert navstore.latest_run_id(s) is None, "a failed run must never serve"
    assert "universe collapsed" in note


def test_the_job_survives_an_unexpected_crash(monkeypatch):
    def boom(*a, **k):
        raise ZeroDivisionError("something nobody predicted")

    monkeypatch.setattr(pipeline, "run_nightly", boom)
    pipeline.nightly_job()

    with navstore.session() as s:
        note = s.execute(navstore.text(
            "SELECT note FROM screener_run ORDER BY id DESC LIMIT 1")).scalar()
    assert "crashed" in note and "nobody predicted" in note


def test_a_failure_that_cannot_be_recorded_still_does_not_raise(monkeypatch):
    """Recording a failure must not itself cause one."""
    monkeypatch.setattr(pipeline, "run_nightly", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(navstore, "session", lambda: (_ for _ in ()).throw(OSError("no disk")))
    pipeline.nightly_job()


def test_a_fund_with_under_a_year_of_history_is_named_not_scored():
    """Found by a fixture that was too short, and worth pinning.

    Below 365 calendar days `rolling_1y` has no complete window and comes back
    0.0. `roll1y` is 50% of the consistency pillar and consistency is 45% of
    quality, so scoring such a fund would rank it with a fifth of its score
    silently set to "flat". `universe.is_scoreable` refuses it instead, and says
    why.

    The failure mode this prevents is subtle: a newly launched fund would not
    error, it would simply appear mid-table on a number nobody supplied.
    """
    codes = eligible_codes(6)
    seed(codes[:3], rows=800)        # over a year
    seed(codes[3:], rows=200)        # under a year
    report = run()

    assert report.scored == 3
    with navstore.session() as s:
        reasons = dict(
            s.execute(
                navstore.text(
                    "SELECT code, reason FROM screener_unscorable WHERE run_id = :r"
                ),
                {"r": report.run_id},
            ).all()
        )
    for code in codes[3:]:
        assert "no full year of history" in reasons[code], reasons.get(code)


def test_a_wound_up_fund_is_named_not_scored():
    """Ten days without a NAV and the fund is treated as gone. Note traa's own
    `category_ranking` uses thirty for the same judgement, so the same fund can
    be rankable on one screen and wound up on the other -- a stated divergence,
    recorded in metrics.NAV_FRESH_DAYS."""
    codes = eligible_codes(4)
    seed(codes[:2], rows=800)
    with navstore.session() as s:
        for i, code in enumerate(codes[2:]):
            navstore.insert_navs(
                s, code,
                [(date(2026, 6, 1) - timedelta(days=d), 100.0 + d * 0.05 + i)
                 for d in range(800)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    report = run()
    assert report.scored == 2
    with navstore.session() as s:
        reasons = dict(s.execute(
            navstore.text("SELECT code, reason FROM screener_unscorable WHERE run_id = :r"),
            {"r": report.run_id}).all())
    for code in codes[2:]:
        assert "wound up" in reasons[code]


def test_the_post_scoring_check_is_actually_wired_into_the_run(monkeypatch):
    """Found by a sabotage that walked straight through.

    Every `check_scored` case was tested by calling `check_scored` directly, so
    replacing its call site with `problems = []` left the whole suite green. The
    checks were correct and unreachable, which is the worst of both: a malformed
    run would have been written and served, and a test file full of green ticks
    would have said the guard was in place.
    """
    seed(eligible_codes(5))
    real_run = universe.run

    def poison(funds):
        scored, rejected = real_run(funds)
        from dataclasses import replace
        return [replace(scored[0], grade="Excellent")] + scored[1:], rejected

    monkeypatch.setattr(universe, "run", poison)
    with pytest.raises(pipeline.PipelineRefused, match="malformed"):
        run()

    with navstore.session() as s:
        assert navstore.latest_run_id(s) is None, "a malformed run was written and served"


def test_a_lost_fund_refuses_to_write(monkeypatch):
    """The other half of the accounting: not malformed values, but a fund that
    went into the scorer and came out of neither list. That is what makes the
    coverage line "1,886 of 1,886" a claim rather than a decoration."""
    seed(eligible_codes(6))
    real_run = universe.run

    def lose_one(funds):
        scored, rejected = real_run(funds)
        return scored[1:], rejected           # one fund silently evaporates

    monkeypatch.setattr(universe, "run", lose_one)
    with pytest.raises(pipeline.PipelineRefused, match="lost or duplicated"):
        run()


# ------------------------------------------------------------- the scheduler


def test_both_nightly_jobs_are_registered_and_ordered():
    """The split is deliberate and easy to undo by accident.

    AMFI's file only ever carries each scheme's LATEST NAV, so a missed capture
    is recoverable only through mfapi's one-day-lagged mirror -- while scoring
    can be re-run any time from NAVs already stored. Merging them into one job
    means a scorer bug costs a day of NAV history that cannot be recovered.
    """
    from app.jobs import scheduler as sched

    sched.start_scheduler()
    try:
        jobs = {j.id: j for j in sched.scheduler.get_jobs()}
        assert "nav_refresh" in jobs and "screener_score" in jobs

        capture = jobs["nav_refresh"].trigger
        score = jobs["screener_score"].trigger
        hour = lambda t: int(str(next(f for f in t.fields if f.name == "hour")))  # noqa: E731
        minute = lambda t: int(str(next(f for f in t.fields if f.name == "minute")))  # noqa: E731

        # AMFI publishes around 23:00 IST; capture after that, score after capture.
        assert (hour(capture), minute(capture)) == (23, 45)
        assert (hour(score), minute(score)) == (0, 15)
        assert str(sched.scheduler.timezone) == "Asia/Kolkata"
        for job in (jobs["nav_refresh"], jobs["screener_score"]):
            assert job.max_instances == 1
    finally:
        sched.scheduler.remove_all_jobs()
        if sched.scheduler.running:
            sched.scheduler.shutdown(wait=False)


def test_the_instance_switch_can_turn_the_nightly_job_off(monkeypatch):
    """`max_instances=1` is per process. Two web workers means two nightly runs
    against one store; the pipeline's in-flight guard is the inner defence and
    this switch is the outer one."""
    from app.jobs import scheduler as sched

    monkeypatch.setattr(sched, "SCREENER_JOB_ENABLED", False)
    sched.scheduler.remove_all_jobs()
    sched.start_scheduler()
    try:
        ids = {j.id for j in sched.scheduler.get_jobs()}
        assert "screener_score" not in ids and "nav_refresh" not in ids
    finally:
        sched.scheduler.remove_all_jobs()
        if sched.scheduler.running:
            sched.scheduler.shutdown(wait=False)


def test_the_nav_refresh_job_never_raises(monkeypatch):
    from app.jobs import scheduler as sched

    monkeypatch.setattr(amfi, "refresh", lambda: (_ for _ in ()).throw(RuntimeError("AMFI down")))
    sched.nav_refresh_job()  # must not raise


# --------------------------------------------------- the startup warning


def test_an_empty_nav_store_says_so_at_boot_and_names_the_command():
    """Deliberately a warning, not an automatic backfill.

    Auto-crawling would hit mfapi for 4,957 funds on every container restart --
    three minutes of startup and real load on a free API, repeated for a problem
    that exists once. The screener already answers 503 with the rebuild progress
    in the message; this makes the logs explain it to the one person who can fix
    it.
    """
    import logging

    from app.main import _warn_if_the_nav_store_is_empty

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    log = logging.getLogger("nextrade.startup")
    handler = Capture()
    log.addHandler(handler)
    try:
        _warn_if_the_nav_store_is_empty()
    finally:
        log.removeHandler(handler)

    assert records, "an empty store booted silently"
    assert "backfill_nav_history.py" in records[0], records[0]


def test_a_healthy_store_boots_silently():
    import logging

    from app.main import _warn_if_the_nav_store_is_empty

    seed(eligible_codes(4))
    run()

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    log = logging.getLogger("nextrade.startup")
    handler = Capture()
    log.addHandler(handler)
    try:
        _warn_if_the_nav_store_is_empty()
    finally:
        log.removeHandler(handler)

    assert records == [], f"a healthy store warned anyway: {records}"


def test_a_store_with_navs_but_no_run_says_the_other_thing():
    """Different problem, different instruction: the data is there, nothing has
    scored it yet."""
    import logging

    from app.main import _warn_if_the_nav_store_is_empty

    seed(eligible_codes(4))          # NAVs, but no pipeline run

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    log = logging.getLogger("nextrade.startup")
    handler = Capture()
    log.addHandler(handler)
    try:
        _warn_if_the_nav_store_is_empty()
    finally:
        log.removeHandler(handler)

    assert records and "nothing has been scored yet" in records[0]


def test_the_startup_check_never_blocks_boot(monkeypatch):
    """A cache problem must not stop the app from starting."""
    from app.main import _warn_if_the_nav_store_is_empty

    monkeypatch.setattr(
        navstore, "ensure_schema", lambda: (_ for _ in ()).throw(OSError("disk gone"))
    )
    _warn_if_the_nav_store_is_empty()  # must not raise
