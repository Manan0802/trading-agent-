"""The one-off crawl that fills the NAV spine: every catalogue fund, whole history.

4,957 funds, a measured mfapi median latency of 0.29s and a mean payload of
128 KiB, for an expected ~5.2M rows (mean 1,052 rows/fund, median 752 -- the
distribution is strongly bimodal, live funds around 3,300 rows and wound-up ones
around 750). That is roughly a five to thirty minute run, which is long enough
that two things stop being theoretical: memory, and being interrupted.

**Memory.** The repo idiom is
`with ThreadPoolExecutor(max_workers=N) as pool: list(pool.map(fn, items))`,
and applied to all 4,957 codes at once it does two bad things at the same time:
it submits every task immediately, and it materialises every result before the
loop body ever runs. Peak RSS measures at about 585 MB -- an OOM kill an hour
into the run on a small container, after which there is nothing to show for it.

So the idiom is kept, but *inside a chunk of 100*. Peak drops to about 12 MB.
The network is still parallel across eight workers; what is deliberately serial
is the writer. **The DB writer is the single main thread**, which is what SQLite
wants -- one connection, one transaction at a time -- and it removes any
`check_same_thread` question from the design rather than answering it.

**Interruption.** `nav_source.backfilled_at` is the ledger, and it is written in
the *same transaction* as that chunk's nav_history rows. An interrupt can
therefore only lose the chunk in flight: at most a hundred funds redone. Because
`insert_navs` is `DO NOTHING`, re-running a completed backfill costs bandwidth
and nothing else -- and with `--resume` (the default) it does not even cost that.

**Why this does not call `mutual_fund.get_nav_history`.** Two reasons, both
fatal here and neither a criticism of that function:

  1. It goes through a 6-hour TTL disk cache. A cached crawl of 4,957 funds
     would write ~650 MB into `.navcache` -- a duplicate of exactly what we are
     writing into the store, with a shorter shelf life than the run itself.
  2. It *drops* zero-NAV rows silently. Dropping is right; silence is not. A
     fund that is suddenly half zeros is a feed problem, and the count is the
     only place that shows up. So the rows are counted into
     `FetchResult.zero_rows` and persisted through `record_source(zero_rows=n)`.

What is reused: `mutual_fund._get_json` (the retrying HTTP call, uncached),
`_parse_nav_point` (the dd-mm-yyyy parse), and `MutualFundDataError`. The
"drop nav <= 0, sort ascending, raise if nothing usable" behaviour is
reproduced here because it has to be, to count the drops.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterator, Sequence

from sqlalchemy import text

from app.services.marketdata import mutual_fund
from app.services.screener import navstore

# Politeness, matching scripts/build_fund_catalogue.py: this is a free API doing
# us a favour and the crawl is one-off.
_WORKERS = 8
_PAUSE_SECONDS = 0.02

# The bound that turns 585 MB into 12 MB. Also the resume granularity: one
# transaction per chunk, so an interrupt costs at most this many funds.
_CHUNK = 100

# Matching mutual_fund.py's retry shape exactly, so there is one backoff
# behaviour in the codebase rather than two.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0


# ---------------------------------------------------------------- the canary
#
# `build_fund_catalogue.py` refuses to *write* when its canary fails. Inverted
# here on purpose: by the time we can check, hours of crawling are already on
# disk and throwing it away would be the expensive wrong move. So the data
# stays, the run is simply not marked accepted, and the script returns 1.
#
# Values are pinned, not counts. A count survives a reversed sort, a units
# change and a wrong-code mapping; a first-row NAV survives none of them.
# Fetched live on 2026-08-20.


@dataclass(frozen=True)
class Anchor:
    code: str
    name: str
    first_nav_date: date
    first_nav: float
    rows: int


ANCHORS: tuple[Anchor, ...] = (
    Anchor("122639", "Parag Parikh Flexi Cap", date(2013, 5, 28), 9.9992, 3253),
    Anchor("118955", "HDFC Flexi Cap", date(2013, 1, 1), 296.876, 3354),
    Anchor("118814", "Nippon India Corporate Bond", date(2013, 1, 2), 23.8807, 3289),
    Anchor("119788", "SBI Gold", date(2013, 1, 2), 10.7479, 3302),
    Anchor("120716", "UTI Nifty 50 Index", date(2013, 1, 2), 37.404, 3353),
)

# NAVs are published to four decimals. Comparing floats any tighter than the
# source's own precision would fail on nothing but repr noise.
_NAV_DECIMALS = 4
# Every anchor is a live fund with a 2013 start, so anything under this means
# a truncated crawl rather than a short fund.
_ANCHOR_MIN_ROWS = 3000
# An anchor that stopped publishing while the rest of the store went on is a
# wrong-code mapping or a dead feed, not a holiday.
_ANCHOR_STALENESS_DAYS = 5
# Universe-level, full runs only. About 2,482 catalogue codes are wound-up
# series, but they still have history, so 90% coverage is a low bar that only a
# genuinely broken crawl fails.
_MIN_FUND_COVERAGE = 0.90
_MIN_TOTAL_ROWS = 3_500_000


# ---------------------------------------------------------------- fetching


@dataclass(frozen=True)
class FetchResult:
    """What comes back from a worker thread. Never an exception.

    A thread that raises inside `pool.map` re-raises in the main thread at the
    point the result is consumed, which would abandon the other 99 funds in the
    chunk and the transaction they were about to share. So failure is a value.
    """

    code: str
    rows: tuple[tuple[date, float], ...] = ()
    error: str | None = None
    zero_rows: int = 0


def _get_payload(scheme_code: str) -> dict:
    """The single network call. Deliberately not `mutual_fund._get_scheme`.

    `_get_json` is the *uncached* path -- see the module docstring for why the
    6-hour disk cache must not be in the way of a 4,957-fund crawl.
    """
    payload = mutual_fund._get_json(f"/mf/{scheme_code}")
    if not isinstance(payload, dict) or "data" not in payload:
        raise mutual_fund.MutualFundDataError(
            f"Unexpected payload for scheme {scheme_code}"
        )
    return payload


def _fetch_rows(scheme_code: str) -> tuple[tuple[tuple[date, float], ...], int]:
    """Parse one payload into (rows oldest-first, zero-NAV rows counted).

    Same two rules as `get_nav_history` -- drop nav <= 0, sort ascending -- with
    the drop counted instead of silent. Unlike `get_nav_history` this does not
    raise on an empty result: that decision belongs to the caller, because the
    zero count is exactly what a fund whose entire history is zeros needs to
    report, and an exception would throw it away.
    """
    rows: list[tuple[date, float]] = []
    zero_rows = 0
    for row in _get_payload(scheme_code)["data"]:
        point = mutual_fund._parse_nav_point(row)
        if point.nav > 0:
            rows.append((point.date, point.nav))
        else:
            zero_rows += 1
    rows.sort(key=lambda r: r[0])
    return tuple(rows), zero_rows


def _fetch_one(scheme_code: str) -> FetchResult:
    """Fetch with a linear backoff. Returns a sentinel rather than raising, ever."""
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            rows, zero_rows = _fetch_rows(scheme_code)
        except Exception as exc:  # noqa: BLE001 -- a worker must not raise
            last_error = exc
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
            continue
        if not rows:
            # Deliberately not retried: an empty history is an answer, not a
            # failure to get one, and asking three times triples the load on a
            # free API to learn the same thing. The zero count survives with it,
            # because a fund whose whole history is zeros is the feed problem
            # this counter exists for.
            return FetchResult(
                code=scheme_code,
                zero_rows=zero_rows,
                error=_describe(
                    mutual_fund.MutualFundDataError(
                        f"No usable NAV history for scheme {scheme_code}"
                    )
                ),
            )
        return FetchResult(code=scheme_code, rows=rows, zero_rows=zero_rows)
    return FetchResult(code=scheme_code, error=_describe(last_error))


def _describe(exc: Exception | None) -> str:
    return f"{type(exc).__name__}: {exc}"


def error_class(message: str) -> str:
    """The histogram key. One line per failure mode, not one per fund."""
    return message.split(":", 1)[0]


# ---------------------------------------------------------------- writing


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(session_, result: FetchResult) -> int:
    """One fund's rows and its ledger row. Both, or neither -- see `run`.

    A failure is written too, as `last_error` with no `backfilled_at`, so the
    fund stays in `todo` on the next run and the reason survives to the report.
    """
    if result.error is not None:
        navstore.record_source(
            session_,
            result.code,
            zero_rows=result.zero_rows,
            last_error=result.error,
        )
        return 0
    inserted = navstore.insert_navs(session_, result.code, list(result.rows))
    navstore.record_source(
        session_,
        result.code,
        backfilled_at=_now_iso(),
        zero_rows=result.zero_rows,
        last_error=None,
    )
    return inserted


# ---------------------------------------------------------------- planning


@dataclass(frozen=True)
class Plan:
    todo: tuple[str, ...]
    """What will actually be fetched."""
    targeted: tuple[str, ...]
    """What the run covers, including funds `--resume` is skipping."""
    full_run: bool
    """False once `--only` or `--limit` has narrowed the universe.

    The universe-level canary is meaningless on a five-fund run, and a check
    that fails for the wrong reason gets switched off by whoever meets it next.
    """
    already_done: int


def plan_run(
    session_,
    catalogue_codes: Sequence[str],
    *,
    force: bool = False,
    only: Sequence[str] | None = None,
    limit: int | None = None,
) -> Plan:
    targeted = list(only) if only else list(catalogue_codes)
    full_run = only is None and limit is None
    if limit is not None:
        targeted = targeted[:limit]
    if force:
        todo = list(targeted)
    else:
        # The ledger check. This one line is what makes `--resume` the default
        # and a completed re-run a no-op.
        done = navstore.backfilled_codes(session_)
        todo = [c for c in targeted if c not in done]
    return Plan(
        todo=tuple(todo),
        targeted=tuple(targeted),
        full_run=full_run,
        already_done=len(targeted) - len(todo),
    )


# ---------------------------------------------------------------- the crawl


@dataclass(frozen=True)
class RunReport:
    attempted: int
    succeeded: int
    failed: int
    rows_inserted: int
    zero_rows: int
    errors: dict[str, int] = field(default_factory=dict)
    elapsed_seconds: float = 0.0


def _chunks(items: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def run(
    plan: Plan,
    *,
    chunk: int | None = None,
    pause: float | None = None,
    workers: int | None = None,
    progress: bool = True,
) -> RunReport:
    chunk = chunk or _CHUNK
    pause = _PAUSE_SECONDS if pause is None else pause
    workers = workers or _WORKERS

    started = time.monotonic()
    done = rows_inserted = failed = zero_rows = 0
    errors: dict[str, int] = {}
    total = len(plan.todo)

    for batch in _chunks(plan.todo, chunk):
        # The repo idiom, kept -- but bounded to one chunk, so at most `chunk`
        # payloads are alive at once instead of all 4,957.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_fetch_one, batch))

        # ONE transaction per chunk, on the main thread. The rows and the
        # ledger entries that describe them commit together or not at all.
        with navstore.session() as s:
            for result in results:
                rows_inserted += _write(s, result)
                zero_rows += result.zero_rows
                if result.error is not None:
                    failed += 1
                    key = error_class(result.error)
                    errors[key] = errors.get(key, 0) + 1

        done += len(batch)
        if progress:
            elapsed = time.monotonic() - started
            eta = (elapsed / done) * (total - done) if done else 0.0
            print(
                f"  {done}/{total} funds · {rows_inserted:,} rows · "
                f"{failed} failed · {_hms(elapsed)} elapsed · eta {_hms(eta)}",
                flush=True,
            )
        time.sleep(pause)

    return RunReport(
        attempted=total,
        succeeded=total - failed,
        failed=failed,
        rows_inserted=rows_inserted,
        zero_rows=zero_rows,
        errors=errors,
        elapsed_seconds=time.monotonic() - started,
    )


def _hms(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


# ---------------------------------------------------------------- acceptance


@dataclass(frozen=True)
class AnchorCheck:
    anchor: Anchor
    first_nav_date: date | None
    first_nav: float | None
    row_count: int
    last_nav_date: date | None
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class Acceptance:
    anchors: tuple[AnchorCheck, ...]
    universe_failures: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return all(a.ok for a in self.anchors) and not self.universe_failures


def check_anchor(session_, anchor: Anchor, newest: date | None) -> AnchorCheck:
    first = session_.execute(
        text(
            "SELECT nav_date, nav FROM nav_history WHERE scheme_code = :c "
            "ORDER BY nav_date LIMIT 1"
        ),
        {"c": anchor.code},
    ).first()
    row_count = int(
        session_.execute(
            text("SELECT COUNT(*) FROM nav_history WHERE scheme_code = :c"),
            {"c": anchor.code},
        ).scalar()
        or 0
    )
    last = session_.execute(
        text("SELECT MAX(nav_date) FROM nav_history WHERE scheme_code = :c"),
        {"c": anchor.code},
    ).scalar()

    first_date = navstore._as_date(first[0]) if first else None
    first_nav = float(first[1]) if first else None
    last_date = navstore._as_date(last) if last else None

    failures: list[str] = []
    if first is None:
        failures.append("no rows in the store at all")
    else:
        if first_date != anchor.first_nav_date:
            failures.append(
                f"first nav date: expected {anchor.first_nav_date}, found {first_date}"
            )
        if round(first_nav, _NAV_DECIMALS) != round(anchor.first_nav, _NAV_DECIMALS):
            failures.append(
                f"first nav: expected {anchor.first_nav:.4f}, found {first_nav:.4f}"
            )
    if row_count < _ANCHOR_MIN_ROWS:
        failures.append(
            f"row count: expected >= {_ANCHOR_MIN_ROWS}, found {row_count}"
        )
    if newest is not None and last_date is not None:
        lag = (newest - last_date).days
        if lag > _ANCHOR_STALENESS_DAYS:
            failures.append(
                f"last nav date: expected within {_ANCHOR_STALENESS_DAYS} days of "
                f"{newest}, found {last_date} ({lag} days behind)"
            )

    return AnchorCheck(
        anchor=anchor,
        first_nav_date=first_date,
        first_nav=first_nav,
        row_count=row_count,
        last_nav_date=last_date,
        failures=tuple(failures),
    )


def coverage(session_) -> tuple[int, int]:
    """(funds that have at least one stored NAV, total stored NAV rows).

    Read off `nav_source`, whose counts `record_source` derives from
    `nav_history` itself, so this cannot drift from the data and does not cost
    a five-million-row scan.
    """
    row = session_.execute(
        text(
            "SELECT COUNT(*), COALESCE(SUM(row_count), 0) "
            "FROM nav_source WHERE row_count > 0"
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


def accept(session_, plan: Plan) -> Acceptance:
    newest = session_.execute(text("SELECT MAX(nav_date) FROM nav_history")).scalar()
    newest_date = navstore._as_date(newest) if newest else None

    if plan.full_run:
        anchors = ANCHORS
    else:
        # A five-fund run cannot be asked about funds it never touched.
        targeted = set(plan.targeted)
        anchors = tuple(a for a in ANCHORS if a.code in targeted)

    checks = tuple(check_anchor(session_, a, newest_date) for a in anchors)

    universe_failures: list[str] = []
    if plan.full_run:
        funds, rows = coverage(session_)
        floor = _MIN_FUND_COVERAGE * len(plan.targeted)
        if funds < floor:
            universe_failures.append(
                f"funds with rows: expected >= {floor:.0f} "
                f"({_MIN_FUND_COVERAGE:.0%} of {len(plan.targeted)}), found {funds}"
            )
        if rows < _MIN_TOTAL_ROWS:
            universe_failures.append(
                f"total rows: expected >= {_MIN_TOTAL_ROWS:,}, found {rows:,}"
            )

    return Acceptance(anchors=checks, universe_failures=tuple(universe_failures))


# ---------------------------------------------------------------- the report


def smallest_funds(session_, limit: int = 10) -> list[tuple[str, int]]:
    return [
        (r[0], int(r[1]))
        for r in session_.execute(
            text(
                "SELECT scheme_code, row_count FROM nav_source "
                "ORDER BY row_count, scheme_code LIMIT :n"
            ),
            {"n": limit},
        ).all()
    ]


def empty_fund_count(session_) -> int:
    return int(
        session_.execute(
            text("SELECT COUNT(*) FROM nav_source WHERE row_count = 0")
        ).scalar()
        or 0
    )


def render_report(session_, plan: Plan, report: RunReport, acceptance: Acceptance) -> str:
    funds, rows = coverage(session_)
    lines = [
        "",
        f"{report.attempted} funds fetched in {_hms(report.elapsed_seconds)} "
        f"({plan.already_done} skipped as already done)",
        f"{report.rows_inserted:,} rows inserted; the store now holds "
        f"{rows:,} rows across {funds:,} funds",
        f"{report.zero_rows:,} zero-NAV rows counted and dropped",
        f"{empty_fund_count(session_)} funds ended with zero rows",
    ]

    lines.append("")
    if report.errors:
        lines.append(f"{report.failed} failures by class:")
        for name, count in sorted(report.errors.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {count:5d}  {name}")
    else:
        lines.append("no failures")

    lines.append("")
    lines.append("fewest rows:")
    for code, count in smallest_funds(session_):
        lines.append(f"  {code:>8}  {count:6d} rows")

    lines.append("")
    lines.append("integrity anchors (values pinned live on 2026-08-20):")
    if not acceptance.anchors:
        lines.append("  none in this run's scope")
    for check in acceptance.anchors:
        a = check.anchor
        got_date = check.first_nav_date or "-"
        got_nav = f"{check.first_nav:.4f}" if check.first_nav is not None else "-"
        lines.append(
            f"  {'PASS' if check.ok else 'FAIL'}  {a.code}  {a.name:<30} "
            f"first {got_date} @ {got_nav} (expected {a.first_nav_date} @ "
            f"{a.first_nav:.4f}), {check.row_count} rows"
        )
        for failure in check.failures:
            lines.append(f"          {failure}")

    if acceptance.universe_failures:
        lines.append("")
        lines.append("universe-level canary failed:")
        for failure in acceptance.universe_failures:
            lines.append(f"  {failure}")
    elif plan.full_run:
        lines.append("")
        lines.append("universe-level canary passed")
    else:
        lines.append("")
        lines.append("universe-level canary skipped (--only / --limit narrows the run)")

    lines.append("")
    lines.append("ACCEPTED" if acceptance.accepted else "NOT ACCEPTED")
    return "\n".join(lines)
