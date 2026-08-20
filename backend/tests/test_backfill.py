"""What the NAV backfill has to survive: interruption, a bad feed, and its own canary.

Every test here points the store at a tmp_path, and nothing here touches the
network -- `backfill._get_payload` is replaced by a fake that *raises* for a
code it does not know, so the failure path is reachable rather than stubbed
away into permanent green.
"""

import re
import threading
from datetime import date, timedelta
from unittest.mock import Mock

import pytest

from app.services.marketdata import mutual_fund
from app.services.screener import backfill, navstore


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    # The real backoff is 1s then 2s, matching mutual_fund.py. Three funds
    # failing would cost nine seconds of a test suite that runs in twelve.
    monkeypatch.setattr(backfill, "_RETRY_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(backfill, "_PAUSE_SECONDS", 0.0)
    yield
    navstore.reset_engine()


# --------------------------------------------------------------- the fake feed


def navs(start: date, n: int, first: float = 10.0) -> list[tuple[date, float]]:
    return [(start + timedelta(days=i), first + i * 0.1) for i in range(n)]


def payload(rows: list[tuple[date, float]]) -> dict:
    """mfapi's actual shape: newest first, dd-mm-yyyy, NAVs as strings.

    Served newest-first on purpose -- if the module stopped sorting, the store
    would still hold the same rows and only a value-pinned check would notice.
    """
    return {
        "meta": {"scheme_code": 1},
        "data": [
            {"date": d.strftime("%d-%m-%Y"), "nav": f"{n:.4f}"}
            for d, n in reversed(rows)
        ],
    }


class FakeApi:
    """Stands in for mfapi. Raises for a code it does not know.

    A fake that returns something plausible for every input makes the error path
    unreachable, and an error path no test can reach is an error path nobody has
    ever run.
    """

    def __init__(self, histories: dict[str, list[tuple[date, float]]]):
        self.histories = histories
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def __call__(self, code: str) -> dict:
        with self._lock:
            self.calls.append(code)
        if code not in self.histories:
            raise mutual_fund.MutualFundDataError(f"unknown scheme {code}")
        return payload(self.histories[code])

    def reset(self) -> None:
        self.calls.clear()


def install(monkeypatch, api: FakeApi) -> FakeApi:
    monkeypatch.setattr(backfill, "_get_payload", api)
    return api


def crawl(codes, **kwargs):
    """plan + run, the two halves the script glues together."""
    with navstore.session() as s:
        plan = backfill.plan_run(s, list(codes), **kwargs)
    return plan, backfill.run(plan, progress=False)


def done_codes() -> set[str]:
    with navstore.session() as s:
        return navstore.backfilled_codes(s)


def row_count(code: str) -> int:
    with navstore.session() as s:
        return len(navstore.nav_window(s, code))


# --------------------------------------------------------------- resumability


def test_an_interrupted_backfill_resumes_where_it_stopped():
    """The whole point of the ledger. `nav_source.backfilled_at` commits in the
    same transaction as that chunk's rows, so a run that dies is not a run that
    has to start over -- and starting over is a 4,957-fund crawl."""
    codes = [str(i) for i in range(1, 51)]
    histories = {c: navs(date(2024, 1, 1), 5) for c in codes if c != "30"}

    api = FakeApi(histories)
    with pytest.MonkeyPatch.context() as mp:
        install(mp, api)
        with navstore.session() as s:
            plan = backfill.plan_run(s, codes)
        backfill.run(plan, chunk=10, progress=False)

    assert "30" not in done_codes()
    assert len(done_codes()) == 49

    histories["30"] = navs(date(2024, 1, 1), 5)
    api.reset()
    with pytest.MonkeyPatch.context() as mp:
        install(mp, api)
        with navstore.session() as s:
            plan = backfill.plan_run(s, codes)
        assert plan.todo == ("30",)
        backfill.run(plan, chunk=10, progress=False)

    assert set(api.calls) == {"30"}, "the resumed run refetched funds already done"
    assert len(done_codes()) == 50
    assert all(row_count(c) == 5 for c in codes)


def test_a_completed_backfill_rerun_is_a_no_op(monkeypatch):
    """Re-running a finished backfill must cost bandwidth and nothing else --
    DO NOTHING handles the rows, the ledger handles the skip. Here it does not
    even cost bandwidth."""
    codes = [str(i) for i in range(10)]
    api = install(monkeypatch, FakeApi({c: navs(date(2024, 1, 1), 4) for c in codes}))
    crawl(codes)
    assert len(api.calls) == 10

    api.reset()
    plan, report = crawl(codes)
    assert plan.todo == ()
    assert api.calls == []
    assert report.attempted == 0
    assert plan.already_done == 10


def test_an_interrupt_loses_at_most_the_chunk_in_flight(monkeypatch):
    """Not in the brief, but it is the claim the design actually makes.

    A KeyboardInterrupt is a BaseException, so it goes straight past
    `_fetch_one`'s `except Exception` and out of `pool.map`. Chunks already
    committed survive; the one being fetched does not; nothing in between.
    """
    codes = [str(i) for i in range(1, 31)]
    histories = {c: navs(date(2024, 1, 1), 4) for c in codes}

    def interrupting(code: str) -> dict:
        if code == "25":
            raise KeyboardInterrupt
        return payload(histories[code])

    monkeypatch.setattr(backfill, "_get_payload", interrupting)
    with navstore.session() as s:
        plan = backfill.plan_run(s, codes)
    with pytest.raises(KeyboardInterrupt):
        backfill.run(plan, chunk=10, progress=False)

    assert done_codes() == {str(i) for i in range(1, 21)}, (
        "an interrupt must lose exactly the chunk in flight, not more and not less"
    )


def test_force_refetches_a_fund_already_marked_done(monkeypatch):
    """`--force --only CODE` is the documented escape hatch for a restatement
    the DO NOTHING insert would otherwise never pick up."""
    api = install(monkeypatch, FakeApi({"A": navs(date(2024, 1, 1), 4)}))
    crawl(["A"])
    api.reset()

    plan, _ = crawl(["A"], force=True)
    assert plan.todo == ("A",)
    assert api.calls == ["A"]
    assert "A" in done_codes()


# --------------------------------------------------------------- failure is a value


def test_a_fetch_failure_returns_a_sentinel_rather_than_raising(monkeypatch):
    """A worker that raises re-raises in the main thread when `pool.map`'s result
    is consumed, which abandons the other 99 funds in the chunk and the
    transaction they were about to share. So failure is a value."""
    codes = [str(i) for i in range(100)]
    histories = {c: navs(date(2024, 1, 1), 3) for c in codes if c != "42"}
    install(monkeypatch, FakeApi(histories))

    _, report = crawl(codes)

    assert report.failed == 1
    assert report.succeeded == 99
    assert len(done_codes()) == 99
    assert "42" not in done_codes()
    assert all(row_count(c) == 3 for c in codes if c != "42")


def test_the_retry_gives_up_after_three_attempts(monkeypatch):
    """Three attempts, matching mutual_fund.py's shape exactly. A fourth would
    be a second retry policy in one codebase, which is how they drift."""
    boom = mutual_fund.MutualFundDataError("connection reset")
    fetch = Mock(side_effect=[boom, boom, boom])
    monkeypatch.setattr(backfill, "_get_payload", fetch)

    result = backfill._fetch_one("A")

    assert fetch.call_count == 3
    assert result.rows == ()
    assert result.error is not None
    assert "connection reset" in result.error


def test_a_transient_failure_then_success_is_not_recorded_as_an_error(monkeypatch):
    """mfapi intermittently drops connections. If a recovered drop still landed
    in the error histogram, the report would read as a broken feed on a run that
    got everything it asked for."""
    boom = mutual_fund.MutualFundDataError("connection reset")
    fetch = Mock(side_effect=[boom, boom, payload(navs(date(2024, 1, 1), 6))])
    monkeypatch.setattr(backfill, "_get_payload", fetch)

    result = backfill._fetch_one("A")

    assert fetch.call_count == 3
    assert result.error is None
    assert len(result.rows) == 6


def test_a_fund_with_no_usable_history_is_recorded_as_an_error_not_as_done(monkeypatch):
    """Marking it done would retire it from every future run, so a fund whose
    feed is broken today would stay missing forever."""
    install(monkeypatch, FakeApi({"A": [], "B": navs(date(2024, 1, 1), 3)}))

    crawl(["A", "B"])

    assert done_codes() == {"B"}
    with navstore.session() as s:
        error = s.execute(
            navstore.text("SELECT last_error FROM nav_source WHERE scheme_code = 'A'")
        ).scalar()
    assert error is not None and "No usable NAV history" in error


# --------------------------------------------------------------- the zero rows


def test_zero_nav_rows_are_counted_not_silently_dropped(monkeypatch):
    """`get_nav_history` drops them and says nothing, which is why this module
    does not call it. A fund that is suddenly half zeros is a feed problem, and
    the count is the only place that shows up."""
    history = navs(date(2024, 1, 1), 10)
    history[2] = (history[2][0], 0.0)
    history[5] = (history[5][0], 0.0)
    history[6] = (history[6][0], -1.0)
    install(monkeypatch, FakeApi({"A": history}))

    crawl(["A"])

    assert row_count("A") == 7
    with navstore.session() as s:
        assert s.execute(
            navstore.text("SELECT zero_rows FROM nav_source WHERE scheme_code = 'A'")
        ).scalar() == 3


def test_a_fund_that_is_all_zeros_still_reports_its_zero_count(monkeypatch):
    """Not in the brief. It is the exact case the counter exists for, and the
    obvious implementation -- raise on an empty result -- throws the count away
    on the one fund where it matters most."""
    install(monkeypatch, FakeApi({"A": [(date(2024, 1, i + 1), 0.0) for i in range(9)]}))

    crawl(["A"])

    assert "A" not in done_codes()
    with navstore.session() as s:
        zeros, error = s.execute(
            navstore.text(
                "SELECT zero_rows, last_error FROM nav_source WHERE scheme_code = 'A'"
            )
        ).one()
    assert zeros == 9
    assert error is not None


# --------------------------------------------------------------- the transaction


def test_the_ledger_is_written_in_the_same_transaction_as_the_rows(monkeypatch):
    """If they were two transactions, a crash between them would leave rows with
    no ledger entry -- and `--resume` would refetch a fund that is already
    complete, forever, without ever noticing."""
    install(monkeypatch, FakeApi({"A": navs(date(2024, 1, 1), 5)}))

    def crash(*args, **kwargs):
        raise RuntimeError("killed between the rows and the ledger")

    monkeypatch.setattr(navstore, "record_source", crash)

    with navstore.session() as s:
        plan = backfill.plan_run(s, ["A"])
    with pytest.raises(RuntimeError):
        backfill.run(plan, progress=False)

    with navstore.session() as s:
        assert s.execute(navstore.text("SELECT COUNT(*) FROM nav_history")).scalar() == 0
        assert s.execute(navstore.text("SELECT COUNT(*) FROM nav_source")).scalar() == 0


# --------------------------------------------------------------- the bounded loop


def test_the_chunked_loop_never_holds_more_than_one_chunk_of_results(monkeypatch):
    """`list(pool.map(fn, all_4957))` submits every task immediately AND
    materialises every result before the loop body runs -- about 585 MB peak,
    which is an OOM kill an hour into the run on a small container.

    Counted rather than measured: a memory probe is flaky, a fetch-ahead counter
    is not.
    """
    codes = [str(i) for i in range(250)]
    api = FakeApi({c: navs(date(2024, 1, 1), 3) for c in codes})
    lock = threading.Lock()
    state = {"fetched": 0, "written": 0, "peak": 0}

    def counting_fetch(code: str) -> dict:
        with lock:
            state["fetched"] += 1
            state["peak"] = max(state["peak"], state["fetched"] - state["written"])
        return api(code)

    real_write = backfill._write

    def counting_write(session_, result):
        state["written"] += 1
        return real_write(session_, result)

    monkeypatch.setattr(backfill, "_get_payload", counting_fetch)
    monkeypatch.setattr(backfill, "_write", counting_write)

    with navstore.session() as s:
        plan = backfill.plan_run(s, codes)
    backfill.run(plan, chunk=25, progress=False)

    assert state["fetched"] == 250
    assert state["peak"] <= 25, (
        f"the fetcher ran {state['peak']} funds ahead of the writer; "
        "the pool is not chunked"
    )


def test_the_crawl_does_not_fill_the_six_hour_disk_cache(monkeypatch):
    """A cached crawl of 4,957 funds writes ~650 MB into `.navcache` -- a
    duplicate of exactly what is going into the store, with a shorter shelf life
    than the run itself. This is why `_get_json` is called and not
    `_get_json_cached`."""
    written: list[str] = []
    monkeypatch.setattr(
        mutual_fund, "_write_disk", lambda *a, **k: written.append(a[0])
    )
    monkeypatch.setattr(
        mutual_fund,
        "_get_json_cached",
        Mock(side_effect=AssertionError("the backfill went through the TTL cache")),
    )
    monkeypatch.setattr(
        mutual_fund, "_get_json", lambda path: payload(navs(date(2024, 1, 1), 4))
    )

    crawl(["A"])

    assert row_count("A") == 4
    assert written == []


def test_the_progress_line_reports_funds_rows_failures_and_an_eta(monkeypatch, capsys):
    install(monkeypatch, FakeApi({"A": navs(date(2024, 1, 1), 3)}))
    with navstore.session() as s:
        plan = backfill.plan_run(s, ["A", "B"])
    backfill.run(plan, chunk=2)

    line = capsys.readouterr().out.strip()
    assert re.fullmatch(
        r"2/2 funds · 3 rows · 1 failed · \d\d:\d\d:\d\d elapsed · eta \d\d:\d\d:\d\d",
        line,
    ), line


# --------------------------------------------------------------- the canary
#
# Values are pinned, not counts. Every test below exists because a count-based
# canary would have passed the corruption it is looking at.


def anchor_history(
    anchor: backfill.Anchor, rows: int = 3300, last: date = date(2026, 8, 19)
) -> list[tuple[date, float]]:
    """A plausible history whose first row is the hand-verified one."""
    series = [
        (last - timedelta(days=rows - 1 - i), 100.0 + i * 0.01) for i in range(rows)
    ]
    series[0] = (anchor.first_nav_date, anchor.first_nav)
    return series


def catalogue_of(n: int = 4957) -> list[str]:
    """The anchors plus enough filler to make the universe thresholds real."""
    codes = [a.code for a in backfill.ANCHORS]
    return codes + [f"9{i:06d}" for i in range(n - len(codes))]


def seed_anchors(histories: dict[str, list[tuple[date, float]]] | None = None) -> None:
    histories = histories or {a.code: anchor_history(a) for a in backfill.ANCHORS}
    with navstore.session() as s:
        for code, rows in histories.items():
            navstore.insert_navs(s, code, rows)
            navstore.record_source(s, code, backfilled_at="2026-08-20T00:00:00")


def seed_ledger(codes: list[str], rows_each: int) -> None:
    """Synthesise nav_source for funds whose rows we are not going to insert.

    `coverage()` reads nav_source, whose counts `record_source` derives from
    nav_history -- so writing the ledger directly is the only way to exercise
    the real 3.5M-row threshold in a test that finishes in a second.
    """
    anchors = {a.code for a in backfill.ANCHORS}
    with navstore.session() as s:
        s.execute(
            navstore.text(
                "INSERT INTO nav_source (scheme_code, first_nav_date, last_nav_date,"
                " row_count, zero_rows, backfilled_at) "
                "VALUES (:c, '2013-01-01', '2026-08-19', :n, 0, '2026-08-20T00:00:00')"
            ),
            [{"c": c, "n": rows_each} for c in codes if c not in anchors],
        )


def full_plan(catalogue: list[str]) -> backfill.Plan:
    with navstore.session() as s:
        return backfill.plan_run(s, catalogue)


def accept(plan: backfill.Plan) -> backfill.Acceptance:
    with navstore.session() as s:
        return backfill.accept(s, plan)


def test_the_canary_can_actually_fail():
    """The control. This suite has twice contained a check that could only pass.

    Same store, one UPDATE apart: green, then red. A canary that cannot go red
    is worse than no canary, because it reads as protection.
    """
    catalogue = catalogue_of()
    seed_anchors()
    seed_ledger(catalogue, rows_each=1052)
    plan = full_plan(catalogue)

    assert accept(plan).accepted, "the healthy store must pass, or nothing below means anything"

    with navstore.session() as s:
        s.execute(
            navstore.text(
                "UPDATE nav_history SET nav = 99.0 "
                "WHERE scheme_code = '122639' AND nav_date = '2013-05-28'"
            )
        )
    result = accept(plan)
    assert not result.accepted
    failures = [f for c in result.anchors for f in c.failures]
    assert any("expected 9.9992, found 99.0000" in f for f in failures), failures


def test_the_canary_refuses_to_accept_a_partial_crawl():
    """The inversion from build_fund_catalogue.py: the data stays, the run is
    simply not accepted. Throwing away hours of crawling is the expensive wrong
    move; pretending a third of a store is a store is the dangerous one."""
    catalogue = catalogue_of()
    seed_anchors({a.code: anchor_history(a, rows=400) for a in backfill.ANCHORS})
    seed_ledger(catalogue[:1200], rows_each=900)
    plan = full_plan(catalogue)

    result = accept(plan)

    assert not result.accepted
    assert all(
        any("row count" in f for f in c.failures) for c in result.anchors
    ), "a truncated anchor must be named"
    assert len(result.universe_failures) == 2, result.universe_failures
    assert any("funds with rows" in f for f in result.universe_failures)
    assert any("total rows" in f for f in result.universe_failures)


def test_the_canary_catches_a_reversed_sort():
    """This is *why* values are pinned rather than counts.

    mfapi serves newest-first. A sort that goes the wrong way attaches every NAV
    to the wrong date: the dates are unchanged, the row count is unchanged, and
    only the first row's *value* has moved. A count-based canary passes this.
    """
    catalogue = catalogue_of()
    good = {a.code: anchor_history(a) for a in backfill.ANCHORS}
    reversed_one = dict(good)
    victim = backfill.ANCHORS[0]
    dates = [d for d, _ in good[victim.code]]
    values = [n for _, n in reversed(good[victim.code])]
    reversed_one[victim.code] = list(zip(dates, values))

    seed_anchors(reversed_one)
    seed_ledger(catalogue, rows_each=1052)
    plan = full_plan(catalogue)

    result = accept(plan)
    check = next(c for c in result.anchors if c.anchor.code == victim.code)

    assert check.row_count == 3300, "the row count survived the corruption untouched"
    assert not result.accepted
    assert any("first nav:" in f for f in check.failures), check.failures


def test_the_canary_catches_a_wrong_code_mapping():
    """A crawl that maps 118955's history onto 122639 has the right number of
    rows for both funds and the wrong data in both. Only pinned values see it."""
    catalogue = catalogue_of()
    histories = {a.code: anchor_history(a) for a in backfill.ANCHORS}
    histories["122639"] = anchor_history(backfill.ANCHORS[1])  # HDFC's data, PPFAS's code

    seed_anchors(histories)
    seed_ledger(catalogue, rows_each=1052)
    plan = full_plan(catalogue)

    result = accept(plan)
    check = next(c for c in result.anchors if c.anchor.code == "122639")

    assert check.row_count == 3300
    assert not result.accepted
    assert any("first nav date:" in f for f in check.failures), check.failures
    assert any("first nav:" in f for f in check.failures), check.failures


def test_the_canary_catches_a_stale_anchor():
    """Not in the brief. A fund that stopped publishing while the rest of the
    store went on is a dead feed or a wrong code, not a holiday."""
    catalogue = catalogue_of()
    histories = {a.code: anchor_history(a) for a in backfill.ANCHORS}
    histories["119788"] = anchor_history(backfill.ANCHORS[3], last=date(2026, 7, 1))

    seed_anchors(histories)
    seed_ledger(catalogue, rows_each=1052)

    result = accept(full_plan(catalogue))
    check = next(c for c in result.anchors if c.anchor.code == "119788")

    assert not result.accepted
    assert any("last nav date" in f for f in check.failures), check.failures


def test_only_and_limit_skip_the_universe_level_canary():
    """A five-fund run must not fail for having five funds. A check that fails
    for the wrong reason is a check the next person switches off."""
    catalogue = catalogue_of()
    seed_anchors()

    full = full_plan(catalogue)
    assert not accept(full).accepted, "a five-fund store is not a full backfill"
    assert accept(full).universe_failures

    with navstore.session() as s:
        only = backfill.plan_run(s, catalogue, only=[a.code for a in backfill.ANCHORS])
        limited = backfill.plan_run(s, catalogue, limit=5)

    assert accept(only).universe_failures == ()
    assert accept(only).accepted
    assert accept(limited).universe_failures == ()
    assert accept(limited).accepted


def test_a_narrowed_run_is_not_judged_on_anchors_it_never_touched():
    """`--only 118814` must not fail because the other four anchors are absent
    from a store it was never asked to fill."""
    seed_anchors({"118814": anchor_history(backfill.ANCHORS[2])})
    with navstore.session() as s:
        plan = backfill.plan_run(s, catalogue_of(), only=["118814"])

    result = accept(plan)
    assert [c.anchor.code for c in result.anchors] == ["118814"]
    assert result.accepted


def test_the_report_names_the_anchor_that_failed_and_what_was_expected():
    """On failure the script prints which anchor and what was expected versus
    found, because "canary failed" sends the next person back to the code."""
    catalogue = catalogue_of()
    histories = {a.code: anchor_history(a) for a in backfill.ANCHORS}
    histories["120716"] = anchor_history(backfill.ANCHORS[4], rows=100)
    seed_anchors(histories)
    seed_ledger(catalogue, rows_each=1052)
    plan = full_plan(catalogue)

    with navstore.session() as s:
        acceptance = backfill.accept(s, plan)
        text_out = backfill.render_report(
            s, plan, backfill.RunReport(0, 0, 0, 0, 0), acceptance
        )

    assert "FAIL  120716  UTI Nifty 50 Index" in text_out
    assert "row count: expected >= 3000, found 100" in text_out
    assert "NOT ACCEPTED" in text_out
    assert text_out.count("PASS") == 4
