"""The nightly run: refresh the NAVs, score the universe, publish the result.

Everything here is arranged around one failure mode. A screener that serves an
empty or half-built universe behind a 200 is worse than one that serves an
error, because nobody finds out. So:

* the write is a **single transaction**, and `completed_at` is set inside it;
* the serving query additionally requires `completed_at IS NOT NULL`, because a
  future refactor might split the write and the belt should outlive the braces;
* a **pre-flight** refuses to write at all if the universe has collapsed;
* a **post-scoring** check refuses to write if the numbers are malformed;
* and a failed run is *recorded* as a row with a note rather than discarded, so
  the failure is visible in the data and not only in a log nobody reads.

A stale feed is deliberately not fatal. `amfi.refresh()` failing means today's
NAVs did not arrive; the ten-day freshness gate in the metrics layer is the
correct automatic response to that, and a one-day-stale screener beats no
screener. Only a *format* failure is worth an alert, and that is what
`AmfiFeedError` already is.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.services.screener import amfi, inputs as inputs_mod, navstore, scoring, universe

_log = logging.getLogger(__name__)

# If tonight's candidate list is below this fraction of the last accepted run's,
# something upstream broke -- an empty store, a catalogue that failed to load, a
# feed that returned half a universe. Writing that run would replace a good
# ranking with a truncated one, and the screen would look fine.
MIN_UNIVERSE_FRACTION = 0.85

# How far behind AMFI a gap-filled fund may be before we chase it, and how many
# we chase in one night. The cap is what stops a bad night becoming 4,957
# requests to a free API.
GAP_FILL_LIMIT = 300

# A run still marked in-flight after this long is a corpse, not a colleague.
# Used to stop a second process piling in behind a crashed one.
STALE_RUN_HOURS = 2

VALID_GRADES = frozenset({"Very Good", "Good", "Avg", "Bad"})
VALID_TIERS = frozenset(scoring.RISK_TIERS)

SCORE_FLOOR, SCORE_CEILING = -0.01, 1.01


class PipelineRefused(Exception):
    """A canary tripped. Nothing was written, and the previous run still serves."""


@dataclass
class RunReport:
    as_of: date
    run_id: int | None = None
    accepted: bool = False
    universe_size: int = 0
    scored: int = 0
    unscorable: int = 0
    inserted_navs: int = 0
    gap_filled: int = 0
    note: str | None = None
    feed_error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        head = "ACCEPTED" if self.accepted else "REFUSED"
        return (
            f"{head} run {self.run_id} for {self.as_of}: "
            f"{self.scored} scored, {self.unscorable} unscorable, "
            f"{self.inserted_navs} NAVs inserted, {self.gap_filled} gap-filled"
            + (f" | {self.note}" if self.note else "")
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _last_accepted_size(session) -> int | None:
    return session.execute(
        navstore.text(
            "SELECT universe_size FROM screener_run "
            "WHERE completed_at IS NOT NULL AND universe_size IS NOT NULL "
            "ORDER BY id DESC LIMIT 1"
        )
    ).scalar()


def _a_run_is_already_in_flight(session) -> bool:
    """Guard against two processes running the job at once.

    `max_instances=1` is per *process*. One uvicorn today, but `--workers N` or a
    second instance means N concurrent nightly runs, and they would race on the
    same store. A row started recently and never completed means someone else is
    doing this right now.
    """
    started = session.execute(
        navstore.text(
            "SELECT started_at FROM screener_run "
            "WHERE completed_at IS NULL ORDER BY id DESC LIMIT 1"
        )
    ).scalar()
    if not started:
        return False
    try:
        began = datetime.fromisoformat(str(started))
    except ValueError:
        return False
    if began.tzinfo is None:
        began = began.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - began).total_seconds() / 3600
    return age_hours < STALE_RUN_HOURS


def check_scored(scored: list[universe.ScoredFund], offered: int) -> list[str]:
    """Everything that must be true of a run before it is allowed to serve.

    Returns the problems. Empty means the run is sane.
    """
    problems: list[str] = []
    codes = [f.code for f in scored]
    if len(set(codes)) != len(codes):
        problems.append("a scheme code was scored more than once")

    for f in scored:
        if f.score is None or f.score != f.score:  # NaN is not equal to itself
            problems.append(f"{f.code}: score is {f.score!r}")
        elif not (SCORE_FLOOR <= f.score <= SCORE_CEILING):
            problems.append(f"{f.code}: score {f.score} outside [{SCORE_FLOOR}, {SCORE_CEILING}]")
        if f.grade is not None and f.grade not in VALID_GRADES:
            problems.append(f"{f.code}: grade {f.grade!r} is not one of {sorted(VALID_GRADES)}")
        if f.risk_tier is not None and f.risk_tier not in VALID_TIERS:
            problems.append(f"{f.code}: risk tier {f.risk_tier!r} is not a SEBI tier")
    if len(scored) > offered:
        problems.append(f"{len(scored)} scored from only {offered} offered")
    return problems[:20]


def _write_run(session, report: RunReport, scored, unscorable, metrics) -> int:
    """One transaction. The rows and the acceptance stamp land together.

    The caller holds the session, so a raise anywhere in here rolls the whole
    thing back and the previous run keeps serving.
    """
    session.execute(
        navstore.text(
            "INSERT INTO screener_run "
            "(as_of, started_at, universe_size, scored, unscorable, note) "
            "VALUES (:a, :s, :u, :sc, :un, :n)"
        ),
        {
            "a": report.as_of.isoformat(), "s": _now(),
            "u": report.universe_size, "sc": len(scored),
            "un": len(unscorable), "n": report.note,
        },
    )
    run_id = int(session.execute(navstore.text("SELECT MAX(id) FROM screener_run")).scalar())

    if scored:
        session.execute(
            navstore.text(
                "INSERT INTO screener_score (run_id, code, category, sub_category, quality,"
                " momentum, drawdown, score, in_sample, grade, peer_median, peer_size,"
                " risk_score, risk_tier) VALUES (:r,:c,:cat,:sub,:q,:m,:d,:s,:i,:g,:pm,:ps,:rs,:rt)"
            ),
            [
                {
                    "r": run_id, "c": f.code, "cat": f.category, "sub": f.sub_category,
                    "q": f.quality, "m": f.momentum, "d": f.drawdown, "s": f.score,
                    "i": 1 if f.in_sample else 0, "g": f.grade, "pm": f.peer_median,
                    "ps": f.peer_size, "rs": f.risk_score, "rt": f.risk_tier,
                }
                for f in scored
            ],
        )
    if unscorable:
        session.execute(
            navstore.text(
                "INSERT INTO screener_unscorable (run_id, code, reason) VALUES (:r,:c,:why)"
            ),
            [{"r": run_id, "c": u.code, "why": u.reason} for u in unscorable],
        )
    if metrics:
        session.execute(
            navstore.text(
                "INSERT INTO screener_input (run_id, code, roll1y, roll6m, roll3m, roll1m,"
                " ret3y, ret1y, ret3m, vol, sortino, max_dd, worst_30d, history_years,"
                " nav_rows, capped_days, last_nav_date, nav_fresh)"
                " VALUES (:r,:c,:r1y,:r6m,:r3m,:r1m,:t3y,:t1y,:t3m,:v,:so,:dd,:w30,:hy,"
                ":nr,:cd,:lnd,:nf)"
            ),
            [
                {
                    "r": run_id, "c": code,
                    "r1y": m.rolling_1y, "r6m": m.rolling_6m,
                    "r3m": m.rolling_3m, "r1m": m.rolling_1m,
                    "t3y": m.returns_3y, "t1y": m.returns_1y, "t3m": m.returns_3m,
                    "v": m.volatility, "so": m.sortino,
                    "dd": m.max_drawdown, "w30": m.worst_30d,
                    "hy": m.history_years, "nr": m.nav_rows, "cd": m.capped_days,
                    "lnd": m.last_nav_date.isoformat() if m.last_nav_date else None,
                    "nf": 1 if m.nav_fresh else 0,
                }
                for code, m in metrics.items()
            ],
        )

    # Inside the same transaction as the rows above. This is what makes a
    # half-finished run structurally impossible rather than merely unlikely.
    session.execute(
        navstore.text("UPDATE screener_run SET completed_at = :t WHERE id = :i"),
        {"t": _now(), "i": run_id},
    )
    navstore.prune_runs(session)
    return run_id


def run_nightly(
    as_of: date | None = None,
    *,
    refresh_feed: bool = True,
    gap_fill_limit: int = GAP_FILL_LIMIT,
) -> RunReport:
    """Refresh, score, and publish. Raises `PipelineRefused` if a canary trips."""
    as_of = as_of or date.today()
    report = RunReport(as_of=as_of)
    navstore.ensure_schema()

    if refresh_feed:
        try:
            feed = amfi.refresh(as_of=as_of)
            report.inserted_navs = feed.inserted
        except amfi.AmfiFeedError as exc:
            # Not fatal. Today's NAVs did not arrive; the ten-day freshness gate
            # is the right automatic response and yesterday's data still scores.
            report.feed_error = str(exc)
            report.warnings.append(f"feed: {exc}")
            _log.warning("AMFI refresh failed, scoring on existing NAVs: %s", exc)
        try:
            report.gap_filled = amfi.gap_fill(as_of=as_of, limit=gap_fill_limit).get("inserted", 0)
        except Exception as exc:  # gap filling is best effort by construction
            report.warnings.append(f"gap fill: {exc}")
            _log.warning("gap fill failed: %s", exc)

    with navstore.session() as session:
        if _a_run_is_already_in_flight(session):
            raise PipelineRefused(
                "another run started less than "
                f"{STALE_RUN_HOURS}h ago and has not finished; refusing to race it"
            )

        built = inputs_mod.build_inputs(session, as_of)
        report.universe_size = built.considered

        previous = _last_accepted_size(session)
        if previous and built.considered < MIN_UNIVERSE_FRACTION * previous:
            raise PipelineRefused(
                f"universe collapsed: {built.considered} funds tonight against "
                f"{previous} in the last accepted run "
                f"(floor is {MIN_UNIVERSE_FRACTION:.0%}). Nothing written."
            )

        scored, rejected = universe.run(built.inputs)
        unscorable = built.unscorable + rejected

        problems = check_scored(scored, offered=len(built.inputs))
        if problems:
            raise PipelineRefused(
                "the scored universe is malformed, nothing written:\n  "
                + "\n  ".join(problems)
            )

        seen = {f.code for f in scored} | {u.code for u in unscorable}
        if len(seen) != built.considered:
            raise PipelineRefused(
                f"{built.considered} funds went in but {len(seen)} distinct codes came out; "
                "a fund was lost or duplicated"
            )

        report.note = "; ".join(report.warnings) or None
        report.run_id = _write_run(
            session, report, scored, unscorable,
            {c: m for c, m in built.metrics.items() if c in {f.code for f in scored}},
        )
        report.scored = len(scored)
        report.unscorable = len(unscorable)
        report.accepted = True

    return report


def nightly_job() -> None:
    """The scheduler entry point. Never raises.

    A job that raises inside APScheduler logs a traceback and vanishes. A run
    that failed needs to be visible in the *data*, so a refusal is recorded as a
    run row with `completed_at` NULL and the reason in `note` -- which is
    therefore never served, and is queryable tomorrow.
    """
    try:
        report = run_nightly()
        _log.info("%s", report.summary())
    except PipelineRefused as exc:
        _log.error("nightly screener refused: %s", exc)
        _record_failure(str(exc))
    except Exception as exc:  # noqa: BLE001 -- a scheduler job must not propagate
        _log.exception("nightly screener crashed")
        _record_failure(f"crashed: {exc}")


def _record_failure(note: str) -> None:
    try:
        navstore.ensure_schema()
        with navstore.session() as session:
            session.execute(
                navstore.text(
                    "INSERT INTO screener_run (as_of, started_at, note) VALUES (:a, :s, :n)"
                ),
                {"a": date.today().isoformat(), "s": _now(), "n": note[:2000]},
            )
    except Exception:  # noqa: BLE001 -- recording a failure must not cause one
        _log.exception("could not even record the failure")
