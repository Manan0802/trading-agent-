"""The AMFI daily feed, and the silence it was allowed to fail into.

The reference implementation read `parts[4]` as the NAV and `parts[5]` as the
date. AMFI went from 6 fields to 8. Against today's file that parser matches 0
of 14,283 rows, logs "Found 0 valid NAV records" and returns successfully -- no
error, no alert, dead for an unknown length of time. Every test here exists
because of that, and `test_the_reference_index_layout_would_now_parse_nothing`
is that incident written down.

Nothing here touches the network, and every test points the NAV store at a
tmp_path.
"""

import os
from datetime import date, datetime

import pytest

from app.services.marketdata import mutual_fund
from app.services.screener import amfi, navstore


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    monkeypatch.setattr(amfi, "_DISK_CACHE_DIR", tmp_path / "cache")
    # The fixture below is twelve data rows, not 14,283. The truncation floor is
    # lowered rather than switched off, so it can still fire on an empty file.
    monkeypatch.setattr(amfi, "_MIN_DATA_ROWS", 3)
    navstore.reset_engine()
    navstore.ensure_schema()
    yield
    navstore.reset_engine()


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "cache"


HEADER = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;"
    "Scheme Name;Plan;Option;Net Asset Value;Date"
)

# Real rows, copied out of the live file on 2026-08-20, plus one synthetic N.A.
# row and two scheme codes AMFI publishes and we do not sell. The blank lines
# are a single space, because that is what AMFI actually serves.
FIXTURE = "\n".join([
    HEADER,
    " ",
    "Open Ended Schemes(Debt Scheme - Banking and PSU Fund)",
    " ",
    "Aditya Birla Sun Life Mutual Fund",
    " ",
    "119550;INF209K01YN0;-;Aditya Birla Sun Life Banking & PSU Debt Fund;"
    "Direct Plan;GROWTH;404.7300;19-Aug-2026",
    "120438;INF846K01CR6;-;Axis Banking & PSU Debt Fund;"
    "Direct Plan;Growth Option;2899.1711;19-Aug-2026",
    " ",
    "Baroda BNP Paribas Mutual Fund",
    " ",
    "152898;INF955L01JF3;-;Baroda BNP Paribas Credit Risk Fund "
    "(scheme has Two segregated portfolios);Direct Plan;Growth Option;0.0000;19-Aug-2026",
    "148333;INF955L01IT6;-;Baroda BNP Paribas Credit Risk Fund "
    "(scheme has Two segregated portfolios);Direct Plan;Growth Option;N.A.;19-Aug-2026",
    "",
    "Open Ended Schemes(Other Scheme - FoF Domestic)",
    " ",
    "SBI Mutual Fund",
    " ",
    "119788;INF200K01RP8;-;SBI GOLD FUND;;;46.4505;19-Aug-2026",
    "125503;INF200K01V08;-;SBI BANKING & PSU FUND;;;3531.3230;19-Aug-2026",
    "146215;INF200KA1YR4;-;SBI Corporate Bond Fund;;;17.0360;19-Aug-2026",
    " ",
    "Sundaram Mutual Fund",
    "134363;INF903J017I5;-;Sundaram Banking & PSU Fund "
    "(Formerly Known as Sundaram Banking & PSU Debt Fund);Direct Plan;GROWTH;11.7065;17-Mar-2017",
    " ",
    "ICICI Prudential Mutual Fund",
    "120625;INF109K01K45;-;ICICI Prudential Interval Fund - Annual Interval Plan - I;;;"
    "18.0131;26-Sep-2017",
    " ",
    "Bandhan Mutual Fund",
    "121279;INF194K015G8;-;Bandhan Banking and PSU Fund;Direct Plan;Growth;27.1238;19-Aug-2026",
    " ",
    "Close Ended Schemes(Debt Scheme - Fixed Term Plan)",
    " ",
    "Some Other Mutual Fund",
    "999999;INF000X01AA1;-;A Scheme AMFI Lists But We Do Not Sell;"
    "Direct Plan;Growth;22.3300;19-Aug-2026",
    "999998;INF000X01BB2;-;Another Scheme We Do Not Sell;;;18.4100;19-Aug-2026",
])

# The eight codes in FIXTURE that are ours, carry a positive NAV and a readable
# date -- the rows that must reach the store.
PARSED_CODES = {"119550", "120438", "119788", "125503", "146215", "134363",
                "120625", "121279"}

BAD_NAV_ROW = (
    "118989;INF090I01AA1;-;A Fund Whose NAV Field Is Not A Number;"
    "Direct Plan;Growth;n/a-ish;19-Aug-2026"
)
BAD_DATE_ROW = (
    "119062;INF090I01BB2;-;A Fund Whose Date Field Is Not A Date;"
    "Direct Plan;Growth;12.3400;not-a-date"
)


def with_rows(*extra: str) -> str:
    return FIXTURE + "\n" + "\n".join(extra)


def rename_header(old: str, new: str) -> str:
    return FIXTURE.replace(HEADER, HEADER.replace(old, new), 1)


def feed(monkeypatch, text: str) -> list[bool]:
    """Stand in for the download. Returns the list of calls made."""
    calls: list[bool] = []

    def fake_fetch(use_cache: bool = True) -> str:
        calls.append(use_cache)
        return text

    monkeypatch.setattr(amfi, "fetch_navall", fake_fetch)
    return calls


def seed(codes, nav_date: date, nav: float = 10.0) -> None:
    with navstore.session() as s:
        for code in codes:
            navstore.insert_navs(s, code, [(nav_date, nav)])
            navstore.record_source(s, code)


# --------------------------------------------------------------- today's format


def test_todays_real_format_parses():
    """Eight columns, semicolon separated, with section headers and AMC names
    interleaved. Every field of the report is pinned, because the number that
    went unnoticed for months was a count."""
    rows, report = amfi.parse_navall(FIXTURE)

    assert report.data_lines == 12
    assert report.non_data_lines == 23
    assert report.parsed == 8
    assert report.skipped_na == 1
    assert report.skipped_zero == 1
    assert report.skipped_bad_nav == 0
    assert report.skipped_bad_date == 0
    assert report.skipped_unknown_code == 2
    assert report.inserted == 0
    assert report.newest_date == date(2026, 8, 19)
    assert report.matched_catalogue_codes == 8
    assert {r.code for r in rows} == PARSED_CODES


def test_the_files_day_mon_year_date_format_is_parsed():
    """AMFI writes `19-Aug-2026`. Parsed against an explicit month map rather
    than strptime's %b, which is locale-dependent: on a host with a German
    LC_TIME, "Oct" and "Dec" would stop parsing and two months a year would
    vanish without a word."""
    rows, _ = amfi.parse_navall(FIXTURE)
    by_code = {r.code: r for r in rows}
    assert by_code["119550"].nav_date == date(2026, 8, 19)
    assert by_code["134363"].nav_date == date(2017, 3, 17)
    assert by_code["120625"].nav_date == date(2017, 9, 26)


def test_a_malformed_date_is_counted_as_a_bad_date(monkeypatch):
    monkeypatch.setattr(amfi, "_MIN_PARSE_RATE", 0.5)
    _, report = amfi.parse_navall(with_rows(BAD_DATE_ROW))
    assert report.skipped_bad_date == 1
    assert report.data_lines == 13
    assert report.parsed == 8


# --------------------------------------------------------------- layer 1


def test_a_renamed_column_raises():
    """The column we read by name is the one most likely to be renamed, and a
    positional parser would carry on reading the same index regardless."""
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.parse_navall(rename_header("Net Asset Value", "NAV"))
    assert "Net Asset Value" in str(exc.value)
    assert "NAV" in str(exc.value)


def test_an_inserted_column_raises():
    nine = HEADER.replace("Scheme Name", "Scheme Name;AMC Code")
    with pytest.raises(amfi.AmfiFeedError):
        amfi.parse_navall(FIXTURE.replace(HEADER, nine, 1))


def test_a_removed_column_raises():
    seven = HEADER.replace("ISIN Div Reinvestment;", "")
    with pytest.raises(amfi.AmfiFeedError):
        amfi.parse_navall(FIXTURE.replace(HEADER, seven, 1))


def test_renaming_a_column_we_never_read_still_raises():
    """The tuple check is the tripwire, not the name lookup. We do not read the
    reinvestment ISIN, so a name-only parser would sail past this -- and AMFI
    reshaping the file is news whichever column it touched."""
    with pytest.raises(amfi.AmfiFeedError):
        amfi.parse_navall(rename_header("ISIN Div Reinvestment", "ISIN Reinvest"))


def test_the_columns_are_found_by_name_not_by_position(monkeypatch):
    """The other half of layer 1. Hardcoded indices are how this broke the first
    time, and the tuple check alone cannot tell them apart from a name lookup --
    both stop a reshaped file. The difference shows the morning after, when
    someone has confirmed AMFI's new shape and updates `_EXPECTED_HEADER`: a
    parser that reads by name is already correct, one that counts is not.
    """
    swapped_header = HEADER.replace("Net Asset Value;Date", "Date;Net Asset Value")
    monkeypatch.setattr(amfi, "_EXPECTED_HEADER", tuple(swapped_header.split(";")))

    swapped = [swapped_header]
    for line in FIXTURE.splitlines()[1:]:
        if line.count(";") == 7:
            parts = line.split(";")
            parts[6], parts[7] = parts[7], parts[6]
            line = ";".join(parts)
        swapped.append(line)

    rows, report = amfi.parse_navall("\n".join(swapped))
    assert report.parsed == 8
    gold = next(r for r in rows if r.code == "119788")
    assert (gold.nav, gold.nav_date) == (46.4505, date(2026, 8, 19))


def test_an_empty_file_raises():
    with pytest.raises(amfi.AmfiFeedError):
        amfi.parse_navall("")


def test_the_reference_index_layout_would_now_parse_nothing():
    """This test IS the incident.

    The reference reads `parts[4]` as NAV and `parts[5]` as date with
    `except ValueError: continue`. With eight fields, parts[4] is the Plan and
    parts[5] is the Option, so every row raises and every row is skipped: 0 of
    14,283 rows, logged as "Found 0 valid NAV records", returned successfully.
    The same bytes, read by name, parse.
    """

    def reference_parser(text: str) -> list[tuple[str, date, float]]:
        out = []
        for line in text.splitlines()[1:]:
            parts = line.split(";")
            if len(parts) < 6:
                continue
            try:
                nav = float(parts[4])
                nav_date = datetime.strptime(parts[5], "%d-%b-%Y").date()
            except ValueError:
                continue
            out.append((parts[0], nav_date, nav))
        return out

    assert reference_parser(FIXTURE) == [], "the reference layout must be dead here"

    rows, report = amfi.parse_navall(FIXTURE)
    assert len(rows) == 8
    assert report.parsed == 8


# --------------------------------------------------------------- layer 2


def test_a_file_of_only_section_headers_raises():
    """A truncated file has no failing rows at all -- it simply has no rows.
    Without the floor that is indistinguishable from a quiet day."""
    truncated = "\n".join([
        HEADER,
        " ",
        "Open Ended Schemes(Debt Scheme - Banking and PSU Fund)",
        " ",
        "Aditya Birla Sun Life Mutual Fund",
    ])
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.parse_navall(truncated)
    assert "truncated" in str(exc.value)


def test_a_file_where_every_row_fails_raises_rather_than_returning_empty():
    """The 0.0% parse rate. The reference had this number and logged it; here it
    is a precondition, which is the entire fix.

    The NAV column is filled with the Plan value, which is exactly what the
    reference's `parts[4]` handed to `float()` on every row of today's file.
    """
    broken = [HEADER]
    for line in FIXTURE.splitlines()[1:]:
        if line.count(";") == 7:
            parts = line.split(";")
            parts[6] = parts[4] or "Direct Plan"
            line = ";".join(parts)
        broken.append(line)

    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.parse_navall("\n".join(broken))
    message = str(exc.value)
    assert "0.0%" in message
    assert "12 data lines" in message
    for code in ("119550", "120438", "152898"):
        assert code in message, "the first three failing lines are not shown"
    assert "121279" not in message, "the message is not capped at three lines"


def test_the_floor_names_the_first_three_failing_lines(monkeypatch):
    """A rate on its own tells you something broke, not what. The three raw
    lines are what turns the alert into a diagnosis."""
    monkeypatch.setattr(amfi, "_MIN_PARSE_RATE", 0.99)
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.parse_navall(with_rows(BAD_NAV_ROW))
    assert "n/a-ish" in str(exc.value)


def test_a_file_that_matches_none_of_our_schemes_raises():
    """Reachable at a 100% read rate: AMFI could serve a file we understand
    perfectly that contains not one scheme we sell."""
    foreign = FIXTURE
    for code in PARSED_CODES:
        foreign = foreign.replace(f"{code};", f"9{code[1:]}9;")
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.parse_navall(foreign)
    assert "0 of our schemes" in str(exc.value)


# --------------------------------------------------------------- layer 3


def test_zero_nav_rows_are_counted_and_dropped():
    """AMFI serves zero-NAV placeholders for dates before a scheme launched --
    243 of them in today's file. Dividing by one produces NaN metrics, and a
    fund with NaN metrics once ranked first on garbage."""
    rows, report = amfi.parse_navall(FIXTURE)
    assert report.skipped_zero == 1
    assert "152898" not in {r.code for r in rows}


def test_na_rows_are_counted_and_dropped():
    rows, report = amfi.parse_navall(FIXTURE)
    assert report.skipped_na == 1
    assert "148333" not in {r.code for r in rows}


def test_an_empty_nav_field_counts_as_a_bad_nav_not_as_na(monkeypatch):
    """Deliberate. Plan and Option are empty on 6,284 rows, so a column shift
    that lands the NAV read on one of them produces empty strings. Counting
    those as "not available" would hide the shift from the parse rate; counting
    them as unreadable is what makes the floor fire."""
    monkeypatch.setattr(amfi, "_MIN_PARSE_RATE", 0.5)
    empty_nav = (
        "118989;INF090I01AA1;-;A Fund With No NAV At All;Direct Plan;Growth;;19-Aug-2026"
    )
    _, report = amfi.parse_navall(with_rows(empty_nav))
    assert report.skipped_bad_nav == 1
    assert report.skipped_na == 1, "the real N.A. row must still be an N.A. row"


def test_empty_plan_and_option_do_not_prevent_parsing():
    """SBI Gold's real shape: `119788;INF200K01RP8;-;SBI GOLD FUND;;;46.4505;
    19-Aug-2026`. 873 catalogue codes carry ('', '') for Plan and Option, so a
    join that filtered on either would drop them all."""
    rows, _ = amfi.parse_navall(FIXTURE)
    gold = next(r for r in rows if r.code == "119788")
    assert gold.nav == 46.4505
    assert gold.nav_date == date(2026, 8, 19)


def test_codes_outside_our_catalogue_are_counted_but_not_inserted(monkeypatch):
    """AMFI publishes 14,283 rows; we sell about 2,475 of them. The other nine
    thousand are somebody else's schemes -- not an error, and not ours to
    store."""
    feed(monkeypatch, FIXTURE)
    report = amfi.refresh(as_of=date(2026, 8, 20))
    assert report.skipped_unknown_code == 2
    with navstore.session() as s:
        assert navstore.nav_window(s, "999999") == []
        assert navstore.nav_window(s, "999998") == []
        assert len(navstore.nav_window(s, "119788")) == 1


def test_every_skip_is_counted(monkeypatch):
    """The structural test. A bare `except: continue` with no counter beside it
    is the actual defect; the wrong index was only how it surfaced."""
    monkeypatch.setattr(amfi, "_MIN_PARSE_RATE", 0.5)
    _, report = amfi.parse_navall(with_rows(BAD_NAV_ROW, BAD_DATE_ROW))
    assert (
        report.parsed
        + report.skipped_na
        + report.skipped_zero
        + report.skipped_bad_nav
        + report.skipped_bad_date
        + report.skipped_unknown_code
    ) == report.data_lines
    assert report.skipped_bad_nav == 1
    assert report.skipped_bad_date == 1


def test_non_data_lines_are_never_counted_as_failures():
    """Section headers, bare AMC names and blanks outnumber nothing here but run
    to 3,581 in the real file. Counting them as failures would put the parse
    rate at 80% on a perfectly healthy day."""
    _, report = amfi.parse_navall(FIXTURE)
    assert report.non_data_lines == 23
    assert report.data_lines + report.non_data_lines == len(FIXTURE.splitlines()) - 1


# --------------------------------------------------------------- store canaries


def test_the_first_ever_run_does_not_trip_the_coverage_canary(monkeypatch):
    """On an empty store `live_fund_count` is 0 and there is no previous newest
    date. The canary is skipped explicitly rather than passing vacuously, and
    nothing here may crash on the None."""
    feed(monkeypatch, FIXTURE)
    report = amfi.refresh(as_of=date(2026, 8, 20))
    assert report.inserted == 8
    with navstore.session() as s:
        assert navstore.newest_nav_date(s) == date(2026, 8, 19)


def test_a_collapse_in_coverage_raises(monkeypatch):
    """The control: the canary has to be able to fire. Twenty funds were live
    yesterday, AMFI matched eight of them today."""
    seed([f"1{i:05d}" for i in range(500, 520)], date(2026, 8, 19))
    feed(monkeypatch, FIXTURE)
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.refresh(as_of=date(2026, 8, 20))
    assert "below 90%" in str(exc.value)


def test_a_holiday_is_not_a_failure(monkeypatch):
    """AMFI reserves the previous day's file on a market holiday. Zero rows
    inserted against an unchanged newest date is the correct outcome, and
    turning it into an alert is how nightly alerts get muted."""
    feed(monkeypatch, FIXTURE)
    amfi.refresh(as_of=date(2026, 8, 20))

    feed(monkeypatch, FIXTURE)
    report = amfi.refresh(as_of=date(2026, 8, 20))
    assert report.inserted == 0
    assert report.newest_date == date(2026, 8, 19)


def test_a_new_date_that_inserts_nothing_raises(monkeypatch):
    """The other half of the holiday rule. AMFI moved and the store did not, so
    the write path is broken however healthy the parse looked."""
    feed(monkeypatch, FIXTURE)
    amfi.refresh(as_of=date(2026, 8, 20))
    monkeypatch.setattr(navstore, "insert_navs", lambda *a, **k: 0)
    monkeypatch.setattr(navstore, "newest_nav_date", lambda *a, **k: date(2026, 8, 18))
    feed(monkeypatch, FIXTURE)
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.refresh(as_of=date(2026, 8, 20))
    assert "new date, no rows" in str(exc.value)


def test_a_feed_that_goes_backwards_raises(monkeypatch):
    """A mirror serving last week's file would otherwise insert nothing and
    look exactly like a holiday."""
    seed(["119550"], date(2026, 8, 25))
    feed(monkeypatch, FIXTURE)
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.refresh(as_of=date(2026, 8, 20))
    assert "backwards" in str(exc.value)


def test_a_stale_mirror_raises(monkeypatch):
    feed(monkeypatch, FIXTURE)
    with pytest.raises(amfi.AmfiFeedError) as exc:
        amfi.refresh(as_of=date(2026, 9, 1))
    assert "stale mirror" in str(exc.value)


# --------------------------------------------------------------- the cache


def net(monkeypatch, text: str) -> list[str]:
    """Stand in for httpx. Raises for any URL but AMFI's, so a mistyped call
    fails the test rather than quietly returning the fixture."""
    calls: list[str] = []

    def fake_get_text(url: str) -> str:
        if url != amfi.NAVALL_URL:
            raise AssertionError(f"unexpected fetch: {url}")
        calls.append(url)
        return text

    monkeypatch.setattr(amfi, "_get_text", fake_get_text)
    return calls


def test_a_same_day_rerun_does_not_refetch(monkeypatch):
    """The file is 1.7 MB and AMFI is a government portal. A rerun after a
    failed parse should also be able to look at the same bytes that failed,
    rather than having to provoke them out of AMFI again."""
    calls = net(monkeypatch, FIXTURE)
    assert amfi.fetch_navall() == FIXTURE
    assert amfi.fetch_navall() == FIXTURE
    assert len(calls) == 1


def test_the_cache_can_be_bypassed(monkeypatch):
    calls = net(monkeypatch, FIXTURE)
    amfi.fetch_navall()
    amfi.fetch_navall(use_cache=False)
    assert len(calls) == 2


def test_a_corrupt_cache_file_is_treated_as_a_miss(monkeypatch, cache_dir):
    """A half-written file from a killed process must read as "fetch it again",
    not as a crash in a nightly job nobody is watching."""
    calls = net(monkeypatch, FIXTURE)
    amfi.fetch_navall()
    next(cache_dir.iterdir()).write_text("{not json")
    assert amfi.fetch_navall() == FIXTURE
    assert len(calls) == 2


def test_the_cache_is_written_atomically(monkeypatch, cache_dir):
    """Written beside the target and moved into place, so a kill mid-write
    leaves no half-file that reads as valid."""
    net(monkeypatch, FIXTURE)
    amfi.fetch_navall()
    assert [p.suffix for p in cache_dir.iterdir()] == [".json"]


# --------------------------------------------------------------- the gap filler


def history(monkeypatch, failing: set[str] | None = None) -> list[str]:
    """Stand in for mfapi. Raises for the codes named in `failing`."""
    calls: list[str] = []
    failing = failing or set()

    def fake_history(code: str):
        calls.append(code)
        if code in failing:
            raise mutual_fund.MutualFundDataError(f"no usable NAV history for {code}")
        return [mutual_fund.NavPoint(date=date(2026, 8, 19), nav=12.5)]

    monkeypatch.setattr(mutual_fund, "get_nav_history", fake_history)
    return calls


def test_the_gap_filler_is_capped(monkeypatch):
    """Without the cap, one short file from AMFI turns into 4,957 mfapi
    requests in a loop -- a bad night becoming a bad night for mfapi too."""
    seed(["119550"], date(2026, 8, 19))
    seed([f"2{i:05d}" for i in range(500)], date(2026, 6, 1))
    calls = history(monkeypatch)

    result = amfi.gap_fill(as_of=date(2026, 8, 20), limit=300)

    assert result["candidates"] == 500
    assert result["attempted"] == 300
    assert len(calls) == 300
    assert result["capped"] is True


def test_a_failing_fund_does_not_abort_the_gap_fill(monkeypatch):
    """One dead scheme code must cost one scheme code, not the whole run."""
    seed(["119550"], date(2026, 8, 19))
    seed(["220001", "220002", "220003"], date(2026, 6, 1))
    calls = history(monkeypatch, failing={"220002"})

    result = amfi.gap_fill(as_of=date(2026, 8, 20))

    assert len(calls) == 3
    assert result["filled"] == 2
    assert result["failed"] == 1
    with navstore.session() as s:
        assert len(navstore.nav_window(s, "220001")) == 2
        error = s.execute(
            navstore.text("SELECT last_error FROM nav_source WHERE scheme_code='220002'")
        ).scalar()
    assert "220002" in error


def test_the_gap_filler_only_touches_funds_that_are_actually_behind(monkeypatch):
    seed(["119550", "120438"], date(2026, 8, 19))
    seed(["220001"], date(2026, 6, 1))
    calls = history(monkeypatch)

    result = amfi.gap_fill(as_of=date(2026, 8, 20))

    assert calls == ["220001"]
    assert result["capped"] is False


def test_the_gap_filler_on_an_empty_store_does_nothing(monkeypatch):
    calls = history(monkeypatch)
    assert amfi.gap_fill(as_of=date(2026, 8, 20))["candidates"] == 0
    assert calls == []

# --------------------------------------------------------- the cache is bounded


def _age(path, days: float, now: float) -> None:
    stamp = now - days * 86400
    os.utime(path, (stamp, stamp))


def test_a_cached_feed_older_than_the_keep_window_is_pruned(tmp_path, monkeypatch):
    """The cache had no eviction at all.

    Date-keying is what lets a failed day's bytes still be on disk to diagnose
    instead of re-provoked out of AMFI. Keeping every day forever is a different
    thing: at ~1.5 MB a fetch, that is about 550 MB a year, in the same
    directory as the NAV caches, on a box where the NAV store already wants
    184 MB.
    """
    import time as _time

    monkeypatch.setattr(amfi, "_DISK_CACHE_DIR", tmp_path)
    now = _time.time()
    old, fresh = tmp_path / "old.json", tmp_path / "fresh.json"
    for f in (old, fresh):
        f.write_text('{"fetched_at": 0, "payload": "x"}')
    _age(old, 40, now)
    _age(fresh, 2, now)

    assert amfi._prune_disk(now) == 1
    assert not old.exists()
    assert fresh.exists(), "a two-day-old feed is still worth having for diagnosis"


def test_pruning_decides_on_mtime_so_a_corrupt_file_can_still_age_out(tmp_path, monkeypatch):
    """A truncated cache file has no readable envelope -- and is exactly the kind
    that should age out. Reading every file to decide whether to delete it would
    also defeat the point of pruning."""
    import time as _time

    monkeypatch.setattr(amfi, "_DISK_CACHE_DIR", tmp_path)
    now = _time.time()
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json at all")
    _age(corrupt, 90, now)
    assert amfi._prune_disk(now) == 1
    assert not corrupt.exists()


def test_a_cache_that_cannot_be_pruned_does_not_kill_the_run(tmp_path, monkeypatch):
    """A cache that cannot be pruned is a disk-space problem. A nightly job that
    dies because it could not delete a file is an outage."""
    monkeypatch.setattr(amfi, "_DISK_CACHE_DIR", tmp_path / "does-not-exist")
    assert amfi._prune_disk(0.0) == 0


def test_fetching_prunes_because_it_is_the_only_path_that_adds(tmp_path, monkeypatch):
    """Pruning on write rather than on a schedule: this is the only code path
    that grows the directory, so it is the only one that has to shrink it, and
    it runs exactly once a night."""
    import time as _time

    monkeypatch.setattr(amfi, "_DISK_CACHE_DIR", tmp_path)
    monkeypatch.setattr(amfi, "_get_text", lambda url: FIXTURE)
    stale = tmp_path / "ancient.json"
    stale.write_text('{"fetched_at": 0, "payload": "x"}')
    _age(stale, 400, _time.time())

    amfi.fetch_navall(use_cache=False)
    assert not stale.exists(), "a fetch left a year-old feed on disk"


# ------------------------------------------------- zeros are named per fund


def test_zero_rows_are_attributed_to_the_fund_that_produced_them():
    """The global count says the feed had 243 zeros -- which it has had for
    years, so on its own it is not a signal. The per-fund count is the one that
    can say *which* fund went half zeros, and `nav_source.zero_rows` exists to
    accumulate exactly that. It was being left dark."""
    text = with_rows(
        "118955;INF0;INF1;A Fund;Direct;Growth;0.0;19-Aug-2026",
        "118955;INF0;INF1;A Fund;Direct;Growth;0;18-Aug-2026",
    )
    _, report = amfi.parse_navall(text)
    assert report.zero_by_code.get("118955") == 2
    assert sum(report.zero_by_code.values()) == report.skipped_zero


def test_the_per_fund_zero_counts_always_add_up_to_the_global_one():
    """If they ever diverge, one of the two is lying about the same feed."""
    _, report = amfi.parse_navall(FIXTURE)
    assert sum(report.zero_by_code.values()) == report.skipped_zero


def test_a_fund_whose_only_row_is_a_zero_still_reaches_the_ledger(monkeypatch):
    """It produces no rows to insert, so a ledger loop over the funds that
    produced data skips it entirely -- and that is precisely the fund whose zero
    count someone needs to see. A fund going all-zeros is the feed problem the
    per-fund counter exists for, and it is the one case where the obvious loop
    is silent.

    The first version of this test was written against helpers that did not
    exist, so it never ran, and the sabotage that removes the union walked
    straight through. That is what a sabotage pass is for.
    """
    # 118955 appears only as a zero; the rest of the fixture supplies real rows
    # so the coverage canaries are satisfied and refresh reaches the ledger.
    text = with_rows("118955;INF0;INF1;A Fund;Direct;Growth;0.0;19-Aug-2026")
    feed(monkeypatch, text)
    report = amfi.refresh(as_of=date(2026, 8, 20))

    assert "118955" not in {r.code for r in amfi.parse_navall(text)[0]}, (
        "fixture is wrong: 118955 must produce no insertable rows"
    )
    assert report.zero_by_code.get("118955") == 1

    with navstore.session() as s:
        stored = s.execute(
            navstore.text("SELECT zero_rows FROM nav_source WHERE scheme_code = '118955'")
        ).scalar()
    assert stored == 1, "the all-zero fund's count never reached the ledger"
