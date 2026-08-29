"""Is what the NAV store says actually true, and does the latest run hang together?

The unit tests ask whether the code does what it was written to do. They cannot
ask whether the 5.2 million NAVs already on disk are the numbers AMFI published,
because they run against fixtures. This runs against the real store and the real
feed and asks that instead.

**The one thing only this can catch.** `insert_navs` is `ON CONFLICT DO NOTHING`
— deliberately, so a settled NAV does not flap because AMFI served one bad row
today. The cost of that decision is that a stored date is *never corrected*. If
a fund restates a NAV, or if a chunk of a backfill landed against the wrong
scheme code, nothing in this codebase will ever notice: no error, no log, no
test. Sampling stored-against-source is the only thing that will, which is why
check A exists and why `backfill --force --only CODE` is the repair.

The rest is arithmetic that has to hold no matter what the feed did: a ledger
that is derived cannot drift from the data it describes, a run cannot lose funds
between its own two output tables, and a nightly precompute that quietly stops
running keeps serving 200s with last month's numbers.

    python scripts/validate_nav_integrity.py [--api http://127.0.0.1:8020]
                                             [--sample 25] [--offline]
                                             [--nav-db PATH]

Exit 1 means the store or the run is wrong. mfapi being down is NOT that, and is
counted and printed apart from it — see INCONCLUSIVE below.
"""

import argparse
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _ratelimit import PatientClient  # noqa: E402

FAILURES: list[str] = []
# Something we could not test, kept apart from something that is wrong. mfapi
# rate-limiting us is not evidence that the store is corrupt, and printing it
# under the same heading would send someone rebuilding a database that is fine.
# `isolation.py` learned this when a 429 got recorded as "LEAKED".
INCONCLUSIVE: list[str] = []
CHECKS = 0

# Fixed so a failure is reproducible: the same 25 funds and the same 10 dates
# inside each of them, run after run, until the store changes.
SEED = 20260820

# 20 calendar days already absorbs a Diwali cluster plus a weekend, so a gap
# wider than this is a refresh window that was missed, not a holiday.
MAX_GAP_DAYS = 20

# How many gaps to put back to the source before giving up. Each is one mfapi
# request; a store with hundreds of gaps has a bigger problem than this check.
MAX_GAPS_VERIFIED = 12

# What counts as a fund still publishing, for the gap check. Measured from the
# store's own newest NAV rather than from today on purpose: if the whole store
# were a month stale, "live within 10 days of today" would be nobody, and the
# gap check would silently examine zero funds and pass. Staleness is check C's
# job; this one must keep working while it is true.
LIVE_WITHIN_DAYS = 10

# A nightly precompute that stops running is invisible: every endpoint still
# answers 200, with last week's numbers.
MAX_RUN_STALE_DAYS = 3

# How far the store's last NAV and mfapi's may sit apart before it stops being
# feed latency and starts being one of them having stopped publishing.
MAX_FEED_LAG_DAYS = 7

# Written out rather than imported from `scoring.RISK_TIERS`. An independent
# statement of what is allowed is the whole point; importing the constant would
# make this check agree with the code by construction.
GRADES = {"Very Good", "Good", "Avg", "Bad"}
RISK_TIERS = {"Low", "Low to Moderate", "Moderate", "Moderately High", "High", "Very High"}

# `screener_input` column -> the `FundMetrics` field the pipeline copies it from.
RECOMPUTED_FIELDS = (
    ("roll1y", "rolling_1y"),
    ("roll6m", "rolling_6m"),
    ("roll3m", "rolling_3m"),
    ("roll1m", "rolling_1m"),
    ("ret3y", "returns_3y"),
    ("ret1y", "returns_1y"),
    ("ret3m", "returns_3m"),
    ("vol", "volatility"),
    ("sortino", "sortino"),
    ("max_dd", "max_drawdown"),
    ("worst_30d", "worst_30d"),
    ("history_years", "history_years"),
    ("nav_rows", "nav_rows"),
    ("capped_days", "capped_days"),
)
TOLERANCE = 1e-9


def check(what: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(f"{what}: {detail}")
        print(f"   WRONG  {what}: {detail}")


def untestable(what: str, detail: str) -> None:
    """Counted as attempted, reported apart from something being wrong."""
    global CHECKS
    CHECKS += 1
    INCONCLUSIVE.append(f"{what}: {detail}")
    print(f"   ?      {what}: {detail}")


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 58 - len(title)))


def same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) <= TOLERANCE
    return a == b


# ------------------------------------------------------------------ A. source


def against_the_source(session, navstore, mutual_fund, sample_size: int) -> None:
    """Refetch a sample from mfapi and hold the store against it."""
    codes = sorted(navstore.backfilled_codes(session))
    if not codes:
        print("   no fund is marked backfilled — nothing to hold against mfapi yet")
        return

    picked = sorted(random.Random(SEED).sample(codes, min(sample_size, len(codes))))
    print(f"   {len(picked)} of {len(codes)} backfilled funds, refetched from mfapi")
    behind: list[str] = []

    for code in picked:
        try:
            points = mutual_fund.get_nav_history(code)
        except Exception as exc:  # noqa: BLE001 - any failure here is the feed's
            untestable(f"{code} against mfapi", f"{type(exc).__name__}: {exc}")
            continue
        time.sleep(0.05)

        ledger = session.execute(
            navstore.text(
                "SELECT first_nav_date, last_nav_date, row_count "
                "FROM nav_source WHERE scheme_code = :c"
            ),
            {"c": code},
        ).one_or_none()
        if ledger is None or ledger[0] is None or ledger[1] is None:
            check(
                f"{code} is marked backfilled, so the ledger describes it",
                False,
                "no nav_source row" if ledger is None else "marked done with no date range",
            )
            continue
        first, last = date.fromisoformat(str(ledger[0])), date.fromisoformat(str(ledger[1]))

        source = {p.date: p.nav for p in points}
        source_last = max(source)
        stored = dict(navstore.nav_window(session, code))
        # Compare only the period BOTH sides cover. The store has two writers --
        # the backfill reads mfapi per scheme, the nightly refresh reads AMFI's
        # own NAVAll.txt -- and mfapi mirrors AMFI a day late. Measured on
        # 2026-08-20: the store held 2026-08-19 for 1,698 funds and mfapi's
        # newest was 2026-08-18. Calling that a corrupt store would make this
        # harness red every single day for a store doing exactly its job.
        overlap_end = min(last, source_last)
        covered = {d: n for d, n in source.items() if first <= d <= overlap_end}
        ahead = [d for d in stored if d > source_last]

        missing = sorted(set(covered) - set(stored))
        phantom = sorted(d for d in stored if first <= d <= overlap_end and d not in covered)
        check(
            f"{code}: the store holds every NAV mfapi publishes in {first}..{overlap_end}",
            not missing and not phantom,
            f"missing {missing[:3]}" + (f"; not in the feed {phantom[:3]}" if phantom else ""),
        )
        check(
            f"{code}: row_count is mfapi's rows plus the ones only AMFI has yet",
            int(ledger[2]) == len(covered) + len(ahead),
            f"ledger {ledger[2]}, mfapi {len(covered)} + {len(ahead)} newer than mfapi",
        )
        check(
            f"{code}: first NAV date agrees with mfapi",
            min(source) == first,
            f"stored {first}, mfapi {min(source)}",
        )
        # One day apart is the two feeds' latency. A week apart is one of them
        # having stopped, which is worth a red gate whichever one it is.
        check(
            f"{code}: last NAV date is within {MAX_FEED_LAG_DAYS} days of mfapi's",
            abs((source_last - last).days) <= MAX_FEED_LAG_DAYS,
            f"stored {last}, mfapi {source_last}",
        )
        if last != source_last:
            direction = "ahead of" if last > source_last else "behind"
            behind.append(f"{code} {abs((source_last - last).days)}d {direction} mfapi")

        shared = sorted(set(stored) & set(covered))
        per_fund = random.Random(f"{SEED}:{code}")
        for d in sorted(per_fund.sample(shared, min(10, len(shared)))):
            check(
                f"{code}: the NAV stored for {d} is still mfapi's",
                round(stored[d], 4) == round(covered[d], 4),
                f"stored {stored[d]}, mfapi {covered[d]}",
            )

    if behind:
        # Not a failure: which of two feeds published first today is a cadence
        # fact. Check C's stale_days is what owns "nothing published at all".
        print(f"   note: {len(behind)} of the sample sit at a different last date — "
              f"{'; '.join(behind[:5])}")


# -------------------------------------------------------------- B. invariants


def invariants(session, navstore, today: date, mutual_fund=None, offline: bool = True) -> None:
    """Everything that has to hold with the network unplugged."""
    text = navstore.text

    # The CHECK makes this impossible -- which is exactly why it is worth
    # asserting. It proves the constraint is deployed in *this* file; a schema
    # rebuilt by hand, or restored from a dump that dropped it, would not say so.
    zero = int(session.execute(text("SELECT COUNT(*) FROM nav_history WHERE nav <= 0")).scalar())
    check("no stored NAV is zero or negative", zero == 0, f"{zero} rows")

    # Tomorrow is legitimate for exactly two kinds of fund, and for nobody else.
    #
    # SEBI requires LIQUID and OVERNIGHT schemes to declare a NAV for every
    # CALENDAR day, including weekends and holidays, because they accrue
    # interest on those days. AMFI publishes the next day's figure on the
    # previous evening, so an overnight fund carrying tomorrow's date this
    # afternoon is the feed working correctly.
    #
    # This check used to reject all of it. Measured on 2026-08-29: 15 rows dated
    # 2026-08-30, and every single one a Liquid or Overnight fund. Flagging
    # correct data is not a harmless false alarm — it is how a real corruption
    # gets skipped past as "that one again".
    #
    # Still bounded: ONE day, and only those two categories. A month ahead, or
    # an equity fund tomorrow, is a broken feed either way.
    from app.services.advisor.fund_catalogue import all_funds

    daily_accrual = {
        f.code
        for f in all_funds()
        if "liquid fund" in f.category.lower() or "overnight fund" in f.category.lower()
    }
    tomorrow = today + timedelta(days=1)
    rows = session.execute(
        text("SELECT scheme_code, nav_date FROM nav_history WHERE nav_date > :t ORDER BY nav_date DESC"),
        {"t": today.isoformat()},
    ).all()
    future = [
        r
        for r in rows
        if not (str(r[0]) in daily_accrual and str(r[1])[:10] <= tomorrow.isoformat())
    ]
    allowed = len(rows) - len(future)
    check(
        "no NAV is dated further ahead than a liquid fund's next calendar day",
        not future,
        f"{len(future)} rows, worst {future[0][0]} on {future[0][1]}" if future else "",
    )
    if allowed:
        print(f"     ({allowed} liquid/overnight rows dated tomorrow, which is correct)")

    # The ledger is derived from nav_history by `record_source`, so it cannot
    # disagree with it unless something wrote one without the other.
    drift = session.execute(
        text(
            "SELECT s.scheme_code, s.row_count, COALESCE(h.c, 0) FROM nav_source s "
            "LEFT JOIN (SELECT scheme_code, COUNT(*) c FROM nav_history GROUP BY scheme_code) h "
            "  ON h.scheme_code = s.scheme_code "
            "WHERE s.row_count <> COALESCE(h.c, 0)"
        )
    ).all()
    for code, claimed, actual in drift[:10]:
        print(f"   WRONG  {code}: ledger says {claimed} rows, nav_history holds {actual}")
    check(
        "every nav_source.row_count equals the rows it describes",
        not drift,
        f"{len(drift)} schemes drifted",
    )

    newest = navstore.newest_nav_date(session)
    cutoff = (newest - timedelta(days=LIVE_WITHIN_DAYS)) if newest else today
    live = int(
        session.execute(
            text("SELECT COUNT(*) FROM nav_source WHERE last_nav_date >= :c"),
            {"c": cutoff.isoformat()},
        ).scalar()
        or 0
    )
    gaps = session.execute(
        text(
            "WITH pairs AS ("
            "  SELECT scheme_code, nav_date,"
            "         LAG(nav_date) OVER (PARTITION BY scheme_code ORDER BY nav_date) prev"
            "  FROM nav_history WHERE scheme_code IN"
            "    (SELECT scheme_code FROM nav_source WHERE last_nav_date >= :c)"
            ") "
            "SELECT scheme_code, prev, nav_date,"
            "       CAST(julianday(nav_date) - julianday(prev) AS INTEGER) gap "
            "FROM pairs WHERE prev IS NOT NULL "
            "  AND julianday(nav_date) - julianday(prev) > :g "
            "ORDER BY gap DESC"
        ),
        {"c": cutoff.isoformat(), "g": MAX_GAP_DAYS},
    ).all()
    print(f"   {live} funds published within {LIVE_WITHIN_DAYS} days of {newest}, gaps checked")

    # A gap is only OUR problem if the source has rows we do not. Measured on the
    # real store, all three gaps found were in mfapi too -- ICICI Prudential
    # Aggressive Hybrid Active FOF genuinely published nothing between May 2013
    # and May 2015, and we hold all 2,805 rows mfapi has for it. Failing on that
    # would make this check permanently red, which is how a gate stops being read.
    #
    # So each gap is put back to the source, capped, and only a gap the source
    # can fill counts as wrong. Under --offline every gap is reported as a note,
    # because we cannot tell the two apart without asking.
    ours, theirs = [], []
    for code, prev, nav_date, gap in gaps[:MAX_GAPS_VERIFIED]:
        if offline:
            theirs.append((code, prev, nav_date, gap, "not checked (offline)"))
            continue
        try:
            source = {p.date.isoformat() for p in mutual_fund.get_nav_history(code)}
        except Exception as exc:                      # noqa: BLE001
            theirs.append((code, prev, nav_date, gap, f"could not check: {exc}"))
            continue
        missing = sum(
            1 for d in source if str(prev) < d < str(nav_date)
        )
        (ours if missing else theirs).append(
            (code, prev, nav_date, gap, f"{missing} rows the source has and we do not")
            if missing
            else (code, prev, nav_date, gap, "the source has the same gap")
        )

    for code, prev, nav_date, gap, why in ours:
        print(f"   WRONG  {code}: {gap} days with no NAV, {prev} -> {nav_date} ({why})")
    for code, prev, nav_date, gap, why in theirs[:5]:
        print(f"   NOTE   {code}: {gap} days with no NAV, {prev} -> {nav_date} ({why})")
    if len(gaps) > MAX_GAPS_VERIFIED:
        print(f"   NOTE   {len(gaps) - MAX_GAPS_VERIFIED} further gaps not put back to the source")

    check(
        f"no live fund is missing NAVs the source still has (gaps over {MAX_GAP_DAYS} days)",
        not ours,
        f"{len(ours)} gap(s) the source could fill",
    )

    hollow = session.execute(
        text("SELECT scheme_code FROM nav_source WHERE backfilled_at IS NOT NULL AND row_count <= 0")
    ).all()
    check(
        "every fund marked backfilled actually has rows",
        not hollow,
        f"{len(hollow)} marked done with nothing stored, e.g. {[h[0] for h in hollow[:5]]}",
    )


# ---------------------------------------------------------------- C. the run


def latest_run(session, navstore, today: date):
    """Does the newest completed run agree with itself? Returns (run_id, as_of)."""
    run_id = navstore.latest_run_id(session)
    if run_id is None:
        print("   no completed screener run yet — the nightly pipeline has never")
        print("   published, so there is nothing here to be wrong. Not a failure.")
        return None, None

    text = navstore.text
    as_of_raw, universe_size, scored, unscorable = session.execute(
        text("SELECT as_of, universe_size, scored, unscorable FROM screener_run WHERE id = :i"),
        {"i": run_id},
    ).one()
    as_of = date.fromisoformat(str(as_of_raw)[:10])
    stale_days = (today - as_of).days
    print(f"   run {run_id}, as_of {as_of}, stale_days {stale_days}")

    check(
        "the run accounts for every fund it started with",
        (scored or 0) + (unscorable or 0) == (universe_size or 0),
        f"{scored} scored + {unscorable} unscorable != {universe_size} in the universe",
    )
    rows_scored = int(
        session.execute(
            text("SELECT COUNT(*) FROM screener_score WHERE run_id = :i"), {"i": run_id}
        ).scalar()
    )
    rows_unscorable = int(
        session.execute(
            text("SELECT COUNT(*) FROM screener_unscorable WHERE run_id = :i"), {"i": run_id}
        ).scalar()
    )
    check(
        "and wrote as many rows as it says it did",
        rows_scored == (scored or 0) and rows_unscorable == (unscorable or 0),
        f"claims {scored}/{unscorable}, holds {rows_scored}/{rows_unscorable}",
    )

    grades = {
        r[0]
        for r in session.execute(
            text("SELECT DISTINCT grade FROM screener_score WHERE run_id = :i"), {"i": run_id}
        ).all()
    }
    check(
        "every grade is one the UI knows how to render",
        grades <= GRADES | {None},
        f"unknown: {sorted(g for g in grades - GRADES if g is not None)}",
    )
    tiers = {
        r[0]
        for r in session.execute(
            text("SELECT DISTINCT risk_tier FROM screener_score WHERE run_id = :i"), {"i": run_id}
        ).all()
    }
    check(
        "every risk tier is one of the six",
        tiers <= RISK_TIERS | {None},
        f"unknown: {sorted(t for t in tiers - RISK_TIERS if t is not None)}",
    )

    # SQLite has no NaN -- a NaN bound as a parameter lands as NULL -- so the
    # NULL test is also the NaN test. `score != score` is kept for the day this
    # store is not SQLite.
    unscored = session.execute(
        text(
            "SELECT code FROM screener_score WHERE run_id = :i AND in_sample = 1 "
            "AND (score IS NULL OR score != score)"
        ),
        {"i": run_id},
    ).all()
    check(
        "no in-sample fund is missing its score",
        not unscored,
        f"{len(unscored)} of them, e.g. {[u[0] for u in unscored[:5]]}",
    )

    out_of_range = session.execute(
        text(
            "SELECT code, score FROM screener_score WHERE run_id = :i "
            "AND score IS NOT NULL AND (score < -0.01 OR score > 1.01)"
        ),
        {"i": run_id},
    ).all()
    check(
        "every score is inside 0..1",
        not out_of_range,
        f"{len(out_of_range)} outside, e.g. {[(c, s) for c, s in out_of_range[:5]]}",
    )

    both = session.execute(
        text(
            "SELECT s.code FROM screener_score s JOIN screener_unscorable u "
            "  ON u.run_id = s.run_id AND u.code = s.code WHERE s.run_id = :i"
        ),
        {"i": run_id},
    ).all()
    check(
        "no fund is both scored and unscorable",
        not both,
        f"{len(both)} in both tables, e.g. {[b[0] for b in both[:5]]}",
    )

    check(
        f"the newest run is no more than {MAX_RUN_STALE_DAYS} days old",
        stale_days <= MAX_RUN_STALE_DAYS,
        f"stale_days {stale_days} — every endpoint is still serving {as_of}'s numbers",
    )
    return run_id, as_of


# ------------------------------------------------------------- D. recompute


def recompute(session, navstore, metrics, run_id: int, as_of: date, sample: int = 5) -> None:
    """Recompute a few funds from the store and hold the run's own inputs to it.

    A difference here means the pipeline wrote a number the metrics engine does
    not produce from the same NAVs — which no unit test can see, because both
    sides of it pass their own tests.
    """
    codes = sorted(
        r[0]
        for r in session.execute(
            navstore.text("SELECT code FROM screener_input WHERE run_id = :i"), {"i": run_id}
        ).all()
    )
    if not codes:
        print("   the run stored no inputs — nothing to recompute against")
        return

    picked = sorted(random.Random(SEED).sample(codes, min(sample, len(codes))))
    print(f"   {len(picked)} of {len(codes)} funds recomputed at as_of {as_of}")
    columns = [c for c, _ in RECOMPUTED_FIELDS] + ["last_nav_date", "nav_fresh"]

    for code in picked:
        stored = session.execute(
            navstore.text(
                f"SELECT {', '.join(columns)} FROM screener_input WHERE run_id = :i AND code = :c"
            ),
            {"i": run_id, "c": code},
        ).one()
        row = dict(zip(columns, stored))

        window = navstore.nav_window(session, code, start=metrics.window_start(as_of))
        tail = navstore.nav_tail(session, code, metrics.MOMENTUM_NAV_ROWS)
        live = metrics.compute(window, as_of, momentum_navs=tail)

        differ = [
            f"{column} stored {row[column]} vs computed {getattr(live, field)}"
            for column, field in RECOMPUTED_FIELDS
            if not same(row[column], getattr(live, field))
        ]
        stored_last = date.fromisoformat(str(row["last_nav_date"])[:10]) if row["last_nav_date"] else None
        if stored_last != live.last_nav_date:
            differ.append(f"last_nav_date stored {stored_last} vs computed {live.last_nav_date}")
        if bool(row["nav_fresh"]) != live.nav_fresh:
            differ.append(f"nav_fresh stored {row['nav_fresh']} vs computed {live.nav_fresh}")

        check(
            f"{code}: the run's stored metrics are what metrics.compute() produces",
            not differ,
            "; ".join(differ[:4]),
        )


# ------------------------------------------------------------- E. cross-view


def cross_view(client, session, navstore, run_id: int | None) -> None:
    """The research page and the screener must know about the same funds.

    They are two different engines and they are MEANT to disagree, so this
    compares sets and never order. See the note printed below.
    """
    if run_id is None:
        print("   no completed run, so the screener has no view to compare. Skipped.")
        return

    print("   NOTE: these two are EXPECTED to disagree on ORDER and must not be")
    print("   'fixed' to match. /research/fund-rankings ranks on the ported")
    print("   record-based score weighted by the direct-vs-regular cost gap; the")
    print("   screener ranks on the nightly quality/momentum/drawdown blend.")
    print("   Only the SET of scheme codes is compared: a set mismatch means one")
    print("   of them is losing funds, which is a bug in whichever is smaller.")

    email = f"navintegrity{id(client)}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "nav-integrity-pw", "name": "N", "phone": "+919000006666"},
    )
    login = client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "nav-integrity-pw"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if login.status_code != 200:
        untestable("the research page against the screener", f"could not log in, HTTP {login.status_code}")
        return
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # The screener's own endpoint is Phase 4 and does not exist yet, so its view
    # is read from the store the endpoint will serve from. Asked of the OpenAPI
    # schema rather than by guessing a URL, so this starts saying something the
    # day the route lands under whatever name it lands under.
    schema = client.get("/openapi.json")
    served = [p for p in schema.json().get("paths", {}) if "screener" in p] if schema.status_code == 200 else []
    if not served:
        print("   the screener has no HTTP endpoint yet (Phase 4), so its side of")
        print("   this comparison is read from the store the endpoint will serve.")

    # Every fund the run knows about, scored or not, grouped by the category the
    # research page uses. The catalogue does the grouping because
    # `screener_unscorable` stores only a code and a reason -- so a fund the run
    # dropped would otherwise vanish from its own side of this comparison, which
    # is precisely the loss being looked for.
    from app.services.advisor import fund_catalogue

    label_of = {f.code: f.category for f in fund_catalogue.all_funds()}
    screener: dict[str, set[str]] = {}
    for (code,) in session.execute(
        navstore.text(
            "SELECT code FROM screener_score WHERE run_id = :i "
            "UNION SELECT code FROM screener_unscorable WHERE run_id = :i"
        ),
        {"i": run_id},
    ).all():
        label = label_of.get(code)
        if label:
            screener.setdefault(label, set()).add(code)
    if not screener:
        print("   the run scored nothing with a SEBI category. Skipped.")
        return

    listed = client.get("/api/v1/research/fund-categories", headers=auth)
    if listed.status_code != 200:
        untestable(
            "the research page against the screener",
            f"/research/fund-categories answered HTTP {listed.status_code}",
        )
        return
    shared = sorted(set(listed.json()) & set(screener))
    if not shared:
        print("   no category is browsable on both sides. Skipped.")
        return

    # Two, smallest first: the ranking endpoint prices every fund in a category
    # and a 37-category sweep is a different kind of harness.
    for category in sorted(shared, key=lambda c: len(screener[c]))[:2]:
        ranking = client.get(
            f"/api/v1/research/fund-rankings/{category}", headers=auth, timeout=180
        )
        if ranking.status_code == 404:
            print(f"   {category}: the research page does not rank it (404). Skipped.")
            continue
        if ranking.status_code != 200:
            untestable(f"{category} on the research page", f"HTTP {ranking.status_code}")
            continue
        body = ranking.json()
        page = {f["scheme_code"] for f in body["ranked"]} | {
            f["scheme_code"] for f in body["unscorable"]
        }
        mine = screener[category]
        check(
            f"{category}: the research page and the screener see the same funds",
            page == mine,
            f"research has {len(page)}, screener has {len(mine)}; "
            f"only on research {sorted(page - mine)[:4]}, "
            f"only in screener {sorted(mine - page)[:4]}",
        )


# ------------------------------------------------------------------- driver


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # 8000 and 8010 are other projects on this machine. A wrong default does not
    # error -- it runs the whole harness against a different app and passes.
    parser.add_argument("--api", default="http://127.0.0.1:8020")
    parser.add_argument("--sample", type=int, default=25, help="funds to refetch from mfapi")
    parser.add_argument("--offline", action="store_true", help="skip everything needing a network")
    parser.add_argument("--nav-db", help="validate this store instead of NEXTRADE_NAV_DB's")
    args = parser.parse_args()

    if args.nav_db:
        os.environ["NEXTRADE_NAV_DB"] = str(Path(args.nav_db).expanduser().resolve())
    # After the env var, because navstore resolves its path on first use.
    from app.services.marketdata import mutual_fund
    from app.services.screener import metrics, navstore

    today = date.today()
    print(f"store: {navstore.db_path()}")
    if not navstore.db_path().exists():
        # Checked before opening a session, because `get_engine()` would create
        # the file. A validator that brings the thing it validates into
        # existence is a validator nobody should trust.
        print("\nnothing to validate yet — run the backfill first:")
        print("    venv/bin/python scripts/backfill_nav_history.py")
        return 0

    with navstore.session() as session:
        # Deliberately not `ensure_schema()`: it drops and rebuilds the derived
        # tables when SCHEMA_VERSION moves, and a validator that can delete the
        # thing it is validating is worse than no validator.
        tables = {
            r[0]
            for r in session.execute(
                navstore.text("SELECT name FROM sqlite_master WHERE type = 'table'")
            ).all()
        }
        rows = (
            session.execute(navstore.text("SELECT 1 FROM nav_history LIMIT 1")).scalar()
            if "nav_history" in tables
            else None
        )
        if not rows:
            print("\nnothing to validate yet — run the backfill first:")
            print("    venv/bin/python scripts/backfill_nav_history.py")
            return 0

        section("A. the store against mfapi")
        if args.offline:
            print("   --offline: skipped")
        else:
            against_the_source(session, navstore, mutual_fund, args.sample)

        section("B. invariants that need no network")
        invariants(session, navstore, today, mutual_fund, args.offline)

        section("C. the latest completed run")
        run_id, as_of = (None, None)
        if "screener_run" in tables:
            run_id, as_of = latest_run(session, navstore, today)
        else:
            print("   this store has no screener tables yet. Not a failure.")

        section("D. the run's metrics, recomputed")
        if run_id is None:
            print("   no completed run to recompute. Skipped.")
        else:
            recompute(session, navstore, metrics, run_id, as_of)

        section("E. the research page against the screener")
        if args.offline:
            print("   --offline: skipped")
        else:
            # Patient, because this runs inside ./check.sh behind three other
            # harnesses that have usually spent the minute's anonymous budget.
            client = PatientClient(base_url=args.api.rstrip("/"), timeout=180)
            try:
                reachable = client.get("/docs").status_code == 200
            except Exception as exc:  # noqa: BLE001 - no server is the normal case
                reachable = False
                print(f"   {type(exc).__name__}: {exc}")
            if not reachable:
                print(f"   no API on {args.api} — skipped. Start one, or pass --api.")
            else:
                cross_view(client, session, navstore, run_id)

    print(f"\n{CHECKS} integrity checks run")
    if FAILURES:
        print(f"\n{len(FAILURES)} WRONG:\n")
        for i, failure in enumerate(FAILURES, 1):
            print(f"  {i}. {failure}")
        if INCONCLUSIVE:
            print(f"\nand {len(INCONCLUSIVE)} could not be tested at all.")
        return 1
    if INCONCLUSIVE:
        # Exit 0 on purpose: mfapi being down is not the store being corrupt,
        # and reddening the gate for someone else's outage teaches people to
        # ignore it. The count rides on the success line so it cannot be missed
        # by `check.sh`, which reads only the last few lines.
        print(f"\n{len(INCONCLUSIVE)} COULD NOT BE TESTED (the source was unreachable, not wrong):\n")
        for item in INCONCLUSIVE:
            print(f"  {item}")
        print(f"\nthe store agrees with itself ({len(INCONCLUSIVE)} checks could not run)")
        return 0
    print("the stored NAVs are still true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
