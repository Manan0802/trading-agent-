"""Today's NAVs, straight from AMFI, parsed so that a broken parse cannot look
like a quiet day.

THE INCIDENT THIS MODULE EXISTS TO PREVENT
------------------------------------------
The reference implementation we are porting from reads `parts[4]` as the NAV and
`parts[5]` as the date, with `except ValueError: continue` around the pair. AMFI
changed NAVAll.txt from 6 fields to 8. Against today's file that parser matches
**0 of 14,283 rows**, logs "Found 0 valid NAV records", and returns
successfully. No error, no alert, no non-zero exit. It has been dead for an
unknown length of time, and nothing in that code path could ever have said so.

Every design choice below follows from that one sentence. The wrong index was
only how it surfaced; the defect is a parser that treats "I understood nothing"
as a successful outcome.

    Layer 1  Columns are resolved by header NAME, and the header tuple itself is
             compared to `_EXPECTED_HEADER` on the first line, before a single
             row is read. An inserted, removed or renamed column stops the run
             there. The tuple check is the tripwire; the name lookup is the
             resilience.

    Layer 2  A parse-rate floor. The reference already had the number -- "0
             valid NAV records" -- and merely logged it. Making that number a
             precondition instead of a log line is the entire fix.

    Layer 3  Every skipped row lands in a named counter, and the counters are
             checked to sum to the number of data lines. A bare
             `except: continue` with no counter is the actual defect.

What is deliberately NOT a failure: section headers, AMC-name lines and blanks
(counted as `non_data_lines`), zero NAVs, `N.A.` NAVs, and scheme codes outside
our 4,957-code catalogue. AMFI publishes about 14,283 rows and we sell about
2,475 of them; the other ~11,800 are somebody else's schemes, not an error.

`parse_navall` is pure -- no network, no database, no clock -- which is what
makes the whole thing exhaustively testable from a fixture string.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import httpx

from app.services.advisor import fund_catalogue
from app.services.marketdata import mutual_fund
from app.services.screener import navstore

NAVALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
_TIMEOUT_SECONDS = 60

# The exact header AMFI served on 2026-08-20, probed live. Compared as a tuple
# rather than scanned for the columns we happen to want: a column we do not read
# today appearing, vanishing or being renamed is still AMFI changing the file
# under us, and we would rather hear about it on a Tuesday than discover it
# months later in a metric.
_EXPECTED_HEADER = (
    "Scheme Code",
    "ISIN Div Payout/ ISIN Growth",
    "ISIN Div Reinvestment",
    "Scheme Name",
    "Plan",
    "Option",
    "Net Asset Value",
    "Date",
)

# The file writes dates as `19-Aug-2026`. Parsed against an explicit map rather
# than `strptime("%d-%b-%Y")`, because %b is locale-dependent: on a host with
# LC_TIME set to German, "Oct" and "Dec" stop parsing and the run silently loses
# two months of rows a year. This module is not allowed to have failure modes
# that quiet.
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# AMFI serves this literal string where a scheme has no NAV for the day. It is
# missing data, not a broken row. An *empty* NAV field is deliberately NOT in
# here: it falls through to float() and is counted as a bad NAV, so that a
# column shift landing the NAV read on the frequently-empty Plan column shows up
# in the parse rate instead of hiding in this counter.
_NOT_AVAILABLE = frozenset({"N.A.", "N.A", "NA", "N/A"})

_MIN_DATA_ROWS = 10_000  # today's file has 14,283
_MIN_PARSE_RATE = 0.98

# How long a fetched feed stays on disk. Long enough that a parse failure can
# still be diagnosed from the actual bytes days later; short enough that the
# directory does not reach half a gigabyte in a year.
_CACHE_KEEP_DAYS = 30
_FAILING_LINES_SHOWN = 3

# Store-level canaries. All relative, so they survive the universe growing.
_MIN_COVERAGE = 0.90
_STALE_DAYS = 5

# Gap filler. AMFI omits about 198 of our SEBI-prefixed codes entirely, and any
# row the parser rejects is a second source of drift.
_GAP_DAYS = 5
_MAX_GAP_FILL = 300

# Same convention as the four existing cache dirs, so deployment has one env var
# to set and not two.
_DISK_CACHE_DIR = Path(
    os.environ.get(
        "NEXTRADE_CACHE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent / ".navcache",
    )
)


class AmfiFeedError(Exception):
    """Raised when AMFI's file is unreachable, reshaped, truncated or unreadable.

    Every raise in this module is a run that must not be allowed to end in a
    zero and a shrug.
    """


_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NavRow:
    code: str
    nav_date: date
    nav: float


@dataclass(frozen=True)
class FeedReport:
    """What the run actually did, with every dropped row named.

    `parsed` counts rows that became a `NavRow`: a known scheme code, a positive
    NAV and a readable date. The five `skipped_*` counters partition everything
    else, and `parsed + the five == data_lines` is checked in the code below.
    """

    data_lines: int
    non_data_lines: int
    parsed: int
    skipped_na: int
    skipped_zero: int
    skipped_bad_nav: int
    skipped_bad_date: int
    skipped_unknown_code: int
    inserted: int
    newest_date: date | None
    matched_catalogue_codes: int
    # Zero-NAV rows per scheme, on top of the global `skipped_zero`. The global
    # number says the feed had 243 zeros, which it has had for years. This one
    # can say *which* fund, which is what `nav_source.zero_rows` accumulates and
    # what makes "this fund went half zeros" a thing anyone finds out about.
    zero_by_code: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------- the catalogue


@lru_cache(maxsize=1)
def _catalogue_codes() -> frozenset[str]:
    """The 4,957 scheme codes we actually sell.

    AMFI publishes roughly three times that many. Inserting the rest would put
    schemes we cannot transact into the store that feeds the screener.
    """
    return frozenset(f.code for f in fund_catalogue.all_funds())


# ---------------------------------------------------------------- the cache


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return _DISK_CACHE_DIR / f"{digest}.json"


def _read_disk(key: str) -> str | None:
    try:
        entry = json.loads(_cache_path(key).read_text())
        payload = entry["payload"]
    except (OSError, ValueError, KeyError):
        # A missing file is the common case; a truncated one is what a killed
        # process leaves behind. Both mean "fetch it again".
        return None
    # No TTL comparison, unlike mutual_fund's cache: the key *is* the fetch date,
    # so a stale entry is unreachable rather than merely expired.
    return payload if isinstance(payload, str) else None


def _prune_disk(now: float, keep_days: int = _CACHE_KEEP_DAYS) -> int:
    """Delete cached feeds older than `keep_days`. Returns how many went.

    Date-keying is what lets a failed day's bytes still be sitting there to be
    diagnosed instead of re-provoked out of AMFI. Keeping *every* day forever is
    a different thing: the file is ~1.5 MB, so an unpruned cache is about 550 MB
    a year sitting in the same directory as the NAV caches, on a box where the
    NAV store already wants 184 MB.

    Deliberately best-effort. A cache that cannot be pruned is a disk-space
    problem; a nightly job that dies because it could not delete a file is an
    outage. Failures are logged and swallowed.
    """
    cutoff = now - keep_days * 86400
    removed = 0
    try:
        entries = list(_DISK_CACHE_DIR.glob("*.json"))
    except OSError:
        return 0
    for entry in entries:
        try:
            # mtime, not the envelope's `fetched_at`: reading every file to
            # decide whether to delete it defeats the point, and a truncated
            # file has no readable envelope at all -- yet is exactly the kind
            # that should age out.
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        _log.info("pruned %d cached feed(s) older than %d days", removed, keep_days)
    return removed


def _write_disk(key: str, payload: str, now: float) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = _cache_path(key)
        # Written beside the target and moved into place, so a process killed
        # mid-write never leaves a half-file that looks valid.
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": now, "payload": payload}))
        tmp.replace(target)
    except OSError:
        pass


def _get_text(url: str) -> str:
    try:
        response = httpx.get(url, timeout=_TIMEOUT_SECONDS, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AmfiFeedError(f"AMFI request failed for {url}: {exc}") from exc
    return response.text


def fetch_navall(use_cache: bool = True) -> str:
    """The raw NAVAll.txt, cached on disk under today's date.

    Keyed by fetch date rather than by a TTL for two reasons: a same-day rerun
    costs nothing, and a file that failed to parse is still sitting there
    afterwards to be looked at, rather than having to be re-provoked out of
    AMFI to be diagnosed.
    """
    key = f"navall:{date.today().isoformat()}"
    if use_cache:
        cached = _read_disk(key)
        if cached is not None:
            return cached
    text = _get_text(NAVALL_URL)
    now = time.time()
    _write_disk(key, text, now)
    # Pruned on write rather than on a schedule: this is the only path that adds
    # to the directory, so it is the only one that needs to take it away, and it
    # runs exactly once a night.
    _prune_disk(now)
    return text


# ---------------------------------------------------------------- the parser


def _parse_amfi_date(raw: str) -> date:
    day, month, year = raw.split("-")
    return date(int(year), _MONTHS[month[:3].title()], int(day))


def parse_navall(text: str) -> tuple[list[NavRow], FeedReport]:
    """Parse the feed. Pure: no network, no database, no clock.

    Raises `AmfiFeedError` rather than returning an empty list whenever the file
    is not the file we know how to read.
    """
    lines = text.splitlines()
    if not lines:
        raise AmfiFeedError("AMFI returned an empty file")

    # --- Layer 1: the header, before a single row is parsed.
    header = tuple(part.strip() for part in lines[0].split(";"))
    if header != _EXPECTED_HEADER:
        raise AmfiFeedError(
            "AMFI changed the NAVAll header. "
            f"expected {_EXPECTED_HEADER}, got {header}"
        )
    idx = {name: i for i, name in enumerate(header)}
    code_at = idx["Scheme Code"]
    nav_at = idx["Net Asset Value"]
    date_at = idx["Date"]

    known = _catalogue_codes()
    separators = len(header) - 1

    rows: list[NavRow] = []
    matched: set[str] = set()
    failing: list[str] = []
    data_lines = non_data_lines = 0
    skipped_na = skipped_zero = skipped_bad_nav = skipped_bad_date = 0
    zero_by_code: Counter[str] = Counter()
    skipped_unknown_code = 0

    for line in lines[1:]:
        # A data line is one with the header's field count. Section headers
        # ("Open Ended Schemes(...)"), bare AMC names and blanks are none of our
        # business and are counted apart -- never as a failure.
        if line.count(";") != separators:
            non_data_lines += 1
            continue
        data_lines += 1
        parts = line.split(";")
        code = parts[code_at].strip()
        raw_nav = parts[nav_at].strip()
        raw_date = parts[date_at].strip()

        # --- Layer 3: exactly one counter is incremented per data line, and the
        # order below is the precedence when a row is wrong in two ways at once.
        if raw_nav.upper() in _NOT_AVAILABLE:
            skipped_na += 1
            continue
        try:
            nav = float(raw_nav)
        except ValueError:
            skipped_bad_nav += 1
            if len(failing) < _FAILING_LINES_SHOWN:
                failing.append(line)
            continue
        if nav <= 0:
            # AMFI serves zero-NAV placeholders for dates before a scheme
            # launched. navstore's CHECK would reject them anyway; counting them
            # here is what makes "this fund went half zeros" visible.
            #
            # Counted per fund as well as globally: the global number tells you
            # the feed had 243 zeros, which is normal and has been for years.
            # The per-fund number is the one that can say *which* fund, and it
            # is the signal `nav_source.zero_rows` was built to accumulate.
            skipped_zero += 1
            zero_by_code[code] += 1
            continue
        try:
            nav_date = _parse_amfi_date(raw_date)
        except (ValueError, KeyError):
            skipped_bad_date += 1
            if len(failing) < _FAILING_LINES_SHOWN:
                failing.append(line)
            continue
        if code not in known:
            # Parsed fine, simply not a scheme we sell. Not an error.
            skipped_unknown_code += 1
            continue

        rows.append(NavRow(code=code, nav_date=nav_date, nav=nav))
        matched.add(code)

    accounted = (
        len(rows)
        + skipped_na
        + skipped_zero
        + skipped_bad_nav
        + skipped_bad_date
        + skipped_unknown_code
    )
    # Written as a raise rather than an `assert` on purpose: `python -O` strips
    # asserts, and this is the invariant that stops a future `except: continue`
    # from being added without a counter beside it.
    if accounted != data_lines:
        raise AmfiFeedError(
            f"{data_lines - accounted} data lines went uncounted "
            f"({accounted} accounted for out of {data_lines}); "
            "a skip path exists with no counter"
        )

    # --- Layer 2: the floors. Truncation first, because the rate needs a
    # non-zero denominator.
    if data_lines < _MIN_DATA_ROWS:
        raise AmfiFeedError(
            f"AMFI file is truncated: {data_lines} data lines, "
            f"expected at least {_MIN_DATA_ROWS}"
        )

    # The rate measures comprehension -- lines whose fields we could actually
    # read -- so a row dropped on purpose (zero, N.A., a scheme we do not sell)
    # does not count against it. Only rows we failed to understand do. The
    # reference's shifted index turns every row into a bad NAV, which is a 0.0%
    # rate: exactly the "Found 0 valid NAV records" it used to log and ignore.
    unreadable = skipped_bad_nav + skipped_bad_date
    parse_rate = (data_lines - unreadable) / data_lines
    if parse_rate < _MIN_PARSE_RATE:
        raise AmfiFeedError(
            f"AMFI parse rate {parse_rate:.1%} over {data_lines} data lines "
            f"({unreadable} unreadable), below the {_MIN_PARSE_RATE:.0%} floor. "
            f"First failures: {failing[:_FAILING_LINES_SHOWN]}"
        )
    if not rows:
        # The reference's exact end state, now a hard stop. Reachable even at a
        # 100% read rate -- for instance if AMFI served every scheme as N.A.
        raise AmfiFeedError(
            f"AMFI file read cleanly but matched 0 of our schemes across "
            f"{data_lines} data lines"
        )

    report = FeedReport(
        data_lines=data_lines,
        non_data_lines=non_data_lines,
        parsed=len(rows),
        skipped_na=skipped_na,
        skipped_zero=skipped_zero,
        skipped_bad_nav=skipped_bad_nav,
        skipped_bad_date=skipped_bad_date,
        skipped_unknown_code=skipped_unknown_code,
        inserted=0,
        newest_date=max(r.nav_date for r in rows),
        matched_catalogue_codes=len(matched),
        zero_by_code=dict(zero_by_code),
    )
    return rows, report


# ---------------------------------------------------------------- the daily run


def refresh(as_of: date | None = None) -> FeedReport:
    """Fetch, parse, check the store-level canaries, insert. Returns the report.

    The canaries are all phrased relative to what the store already holds, so
    none of them has to be re-tuned when the universe grows.
    """
    as_of = as_of or date.today()
    navstore.ensure_schema()

    rows, report = parse_navall(fetch_navall())

    with navstore.session() as s:
        previous_newest = navstore.newest_nav_date(s)
        live = navstore.live_fund_count(s, as_of)

    # On a first ever run the store is empty, so `live` is 0 and
    # `previous_newest` is None. 0.90 * 0 == 0 would pass vacuously, but the
    # skip is explicit: with no prior state there is nothing to compare against,
    # and a canary that is merely vacuous reads as a canary that fired.
    first_run = previous_newest is None
    if not first_run and report.matched_catalogue_codes < _MIN_COVERAGE * live:
        raise AmfiFeedError(
            f"AMFI matched {report.matched_catalogue_codes} of our schemes, "
            f"below {_MIN_COVERAGE:.0%} of the {live} that were live on {as_of}"
        )

    newest = report.newest_date
    if not first_run and newest < previous_newest:
        raise AmfiFeedError(
            f"feed went backwards: AMFI's newest date is {newest}, "
            f"the store already holds {previous_newest}"
        )
    if newest < as_of - timedelta(days=_STALE_DAYS):
        raise AmfiFeedError(
            f"stale mirror: AMFI's newest date is {newest}, "
            f"more than {_STALE_DAYS} days before {as_of}"
        )

    by_code: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for row in rows:
        by_code[row.code].append((row.nav_date, row.nav))

    # A fund can be all zeros on a given day, in which case it has no rows to
    # insert but still has a zero count worth recording -- so the ledger loop
    # covers the union, not just the funds that produced data.
    touched = set(by_code) | set(report.zero_by_code)
    inserted = 0
    with navstore.session() as s:
        for code in touched:
            navs = by_code.get(code, [])
            if navs:
                inserted += navstore.insert_navs(s, code, navs)
            navstore.record_source(s, code, zero_rows=report.zero_by_code.get(code, 0))

    if inserted == 0:
        if newest != previous_newest:
            raise AmfiFeedError(
                f"new date, no rows: AMFI published {newest} but nothing was "
                "inserted, so the store did not move"
            )
        # A market holiday. AMFI reserves the previous day's file, we insert
        # nothing, and that is the correct outcome rather than a failure.
        _log.info("no new NAV date from AMFI (%s), nothing to insert", newest)

    return replace(report, inserted=inserted)


# ---------------------------------------------------------------- the gap filler


def gap_fill(as_of: date | None = None, limit: int = _MAX_GAP_FILL) -> dict:
    """Top up funds AMFI's daily file left behind, from mfapi's full history.

    Two things land here: the ~198 SEBI-prefixed codes AMFI omits from NAVAll
    entirely, and anything the parser rejected. Candidates are taken newest-
    stale-first, so the funds most likely to be genuinely alive are filled
    before the wound-up 2014 series that will never move again.

    `limit` is the whole point of the cap: without it one bad night -- AMFI
    serving a short file -- turns into 4,957 mfapi requests in a loop.

    Never raises. A fund that fails is counted, its error recorded against its
    ledger row, and the run carries on.
    """
    as_of = as_of or date.today()
    navstore.ensure_schema()

    with navstore.session() as s:
        newest = navstore.newest_nav_date(s)
        if newest is None:
            return {
                "candidates": 0,
                "attempted": 0,
                "filled": 0,
                "failed": 0,
                "inserted": 0,
                "capped": False,
            }
        cutoff = newest - timedelta(days=_GAP_DAYS)
        behind = [
            r[0]
            for r in s.execute(
                navstore.text(
                    "SELECT scheme_code FROM nav_source "
                    "WHERE last_nav_date IS NULL OR last_nav_date < :cutoff "
                    "ORDER BY last_nav_date DESC"
                ),
                {"cutoff": cutoff.isoformat()},
            ).all()
        ]

    candidates = len(behind)
    targets = behind[:limit]
    filled = failed = inserted = 0
    for code in targets:
        try:
            history = mutual_fund.get_nav_history(code)
        except Exception as exc:  # noqa: BLE001 -- one bad fund is not a bad night
            failed += 1
            with navstore.session() as s:
                navstore.record_source(s, code, last_error=str(exc))
            continue
        with navstore.session() as s:
            inserted += navstore.insert_navs(
                s, code, [(p.date, p.nav) for p in history]
            )
            navstore.record_source(s, code)
        filled += 1

    return {
        "candidates": candidates,
        "attempted": len(targets),
        "filled": filled,
        "failed": failed,
        "inserted": inserted,
        "capped": candidates > len(targets),
    }
