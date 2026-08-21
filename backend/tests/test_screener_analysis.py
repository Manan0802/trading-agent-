"""The fund's own charts, and the ways a chart can lie.

Almost every test here is about a comparison that looks fine and is not: two
lines over different periods, a median of raw NAVs, a smoothed-away crash.
"""

from datetime import date, timedelta

import pytest

from app.services.screener import analysis, navstore


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    yield
    navstore.reset_engine()


AS_OF = date(2026, 8, 20)


def seed(code: str, days: int, start_level: float = 100.0, daily: float = 0.0004,
         end: date = AS_OF) -> None:
    import math
    navs, level = [], start_level
    for i in range(days):
        level *= math.exp(daily)
        navs.append((end - timedelta(days=days - 1 - i), round(level, 4)))
    with navstore.session() as s:
        navstore.insert_navs(s, code, navs)
        navstore.record_source(s, code, backfilled_at="x")


def peers(n: int, days: int = 1200, daily: float = 0.0002) -> list[str]:
    codes = [f"P{i:03d}" for i in range(n)]
    for i, c in enumerate(codes):
        seed(c, days, start_level=50.0 + i * 37.0, daily=daily + i * 0.00001)
    return codes


def analyse(code, peer_codes, range_key="1y"):
    with navstore.session() as s:
        return analysis.analyse(s, code, peer_codes, AS_OF, range_key)


# ------------------------------------------------- both lines, one period


def test_a_young_fund_and_its_peers_are_clipped_to_the_same_window():
    """The bug this exists for, measured on real data before it was fixed.

    A fifteen-month-old silver fund asked for "3 years" drew fifteen months of
    itself against three years of its peers: +128.8% against +156.7%, which
    reads as underperformance. Over the days they actually share it was +100.3%
    against +56.3%. Same axis, same rebase point, or no comparison at all.
    """
    seed("YOUNG", 400, daily=0.0018)          # ~13 months, strong
    codes = peers(12, days=1200, daily=0.0003)

    result = analyse("YOUNG", codes, "3y")
    assert result.clipped_to_fund_history is True
    assert result.nav and result.peer_median
    # Both series begin on the fund's own first day, not three years back.
    assert result.peer_median[0].date >= result.nav[0].date
    assert (result.peer_median[0].date - result.nav[0].date).days <= 7


def test_a_fund_older_than_the_range_is_not_clipped():
    seed("OLD", 1500)
    result = analyse("OLD", peers(12), "1y")
    assert result.clipped_to_fund_history is False


def test_the_clipped_comparison_agrees_with_the_shorter_range():
    """The tell that the fix works: if a fund beats its peers over one year, it
    must still beat them when a three-year range is clipped to that same year.
    Before the fix the sign flipped."""
    seed("YOUNG", 400, daily=0.0018)
    codes = peers(12, days=1200, daily=0.0003)
    one_year = analyse("YOUNG", codes, "1y")
    three_year = analyse("YOUNG", codes, "3y")
    assert one_year.total_return > one_year.peer_total_return
    assert three_year.total_return > three_year.peer_total_return


# ------------------------------------------------- the comparison itself


def test_the_peer_median_is_of_rebased_paths_not_raw_navs():
    """Peers are seeded with unit prices from 50 to 450. A median of raw NAVs
    would be a line about whichever fund launched at the highest price, which is
    a fact about a launch and nothing else."""
    seed("F", 1200)
    result = analyse("F", peers(12), "1y")
    assert result.peer_median
    # Rebased means the first point is 100 by construction.
    assert result.peer_median[0].value == pytest.approx(100.0, abs=0.5)
    assert all(1 < p.value < 1000 for p in result.peer_median)


def test_a_thin_category_gets_no_comparison_line_rather_than_a_fake_one():
    """A median of three funds is three funds wearing the word median."""
    seed("F", 1200)
    result = analyse("F", peers(3), "1y")
    assert result.peer_median == []
    assert result.peers_compared == 0
    assert result.peer_total_return is None


def test_the_fund_is_never_its_own_peer():
    """A fund included in its own peer median drags the comparison toward
    itself, which flatters a strong fund and rescues a weak one.

    Asserting the two returns merely differ is too weak -- with twelve peers,
    adding a thirteenth barely moves the median and the assertion held with the
    exclusion removed. The real test is that the median is identical either way.
    """
    seed("F", 1200, daily=0.003)
    codes = peers(12)
    without = analyse("F", codes, "1y")
    with_itself = analyse("F", codes + ["F"], "1y")
    assert with_itself.peer_total_return == without.peer_total_return
    assert [p.value for p in with_itself.peer_median] == [
        p.value for p in without.peer_median
    ]


def test_dates_only_a_couple_of_peers_published_on_are_excluded():
    """A date one fund published on is not a median of anything, and including
    it makes the line jump.

    Two earlier fixtures were inert and taught this the hard way: the first
    reused a date the peer already had, and `insert_navs` is DO NOTHING so the
    outlier was never stored; the second used a date outside the comparison
    window, so it was filtered before the median ran. The peers here are seeded
    with a gap, and the outlier lands inside the window on a day they skipped.
    """
    import math

    end = AS_OF
    skipped = end - timedelta(days=200)          # inside the window, by design
    codes = [f"G{i:02d}" for i in range(12)]
    with navstore.session() as s:
        for i, code in enumerate(codes):
            navs, level = [], 50.0 + i * 37.0
            for d in range(1200):
                day = end - timedelta(days=1199 - d)
                if day == skipped:
                    continue                      # nobody publishes that day
                level *= math.exp(0.0002)
                navs.append((day, round(level, 4)))
            navstore.insert_navs(s, code, navs)
            navstore.record_source(s, code, backfilled_at="x")
        # One fund alone publishes on the skipped day, at an absurd level.
        navstore.insert_navs(s, codes[0], [(skipped, 9_999.0)])
        assert navstore.nav_window(s, codes[0], start=skipped, end=skipped), (
            "the outlier NAV was not stored; the fixture is inert"
        )

    seed("SPARSE", 1200)
    result = analyse("SPARSE", codes, "max")
    assert result.peer_median, "no comparison line at all; the fixture is wrong"
    assert skipped not in {p.date for p in result.peer_median}, (
        "a date only one fund published on reached the median line"
    )


# ------------------------------------------------- drawdown


def test_drawdown_is_never_positive_and_starts_at_zero():
    seed("F", 800)
    result = analyse("F", peers(12), "max")
    assert result.drawdown
    assert result.drawdown[0].value == pytest.approx(0.0, abs=1e-6)
    assert all(p.value <= 1e-9 for p in result.drawdown)


def test_a_crash_shows_in_the_drawdown_series():
    """The point of the series rather than the number: "worst fall 24%" is a
    fact about one day, the shape is how long the fund spent underwater."""
    import math
    navs, level = [], 100.0
    for i in range(400):
        level *= math.exp(-0.02 if 200 <= i < 215 else 0.0006)
        navs.append((AS_OF - timedelta(days=399 - i), round(level, 4)))
    with navstore.session() as s:
        navstore.insert_navs(s, "CRASH", navs)
        navstore.record_source(s, "CRASH", backfilled_at="x")
    result = analyse("CRASH", peers(12), "max")
    assert min(p.value for p in result.drawdown) < -20
    underwater = sum(1 for p in result.drawdown if p.value < -1)
    assert underwater > 10, "the recovery period vanished from the series"


# ------------------------------------------------- downsampling


def test_a_long_series_is_thinned_but_keeps_both_ends():
    """The most recent NAV is the one a reader checks against everywhere else on
    the page, so it must survive the thinning."""
    seed("F", 3000)
    with navstore.session() as s:
        raw = navstore.nav_window(s, "F")
    result = analyse("F", peers(12), "max")
    assert len(result.nav) <= analysis.CHART_POINTS
    assert result.nav[-1].date == raw[-1][0]
    assert result.nav[0].date == raw[0][0]


def test_downsampling_samples_rather_than_averages():
    """An average would smooth away the single-day drop a drawdown chart exists
    to show."""
    points = [analysis.Point(date(2020, 1, 1) + timedelta(days=i), float(i))
              for i in range(1000)]
    points[500] = analysis.Point(points[500].date, -999.0)
    thinned = analysis.downsample(points, limit=100)
    assert len(thinned) == 100
    assert all(p.value in {float(i) for i in range(1000)} | {-999.0} for p in thinned)


# ------------------------------------------------- rolling returns


def test_rolling_returns_cover_every_entry_date_not_one():
    """A single "1-year return" is one entry date's luck."""
    seed("F", 1400)
    with navstore.session() as s:
        rolling = analysis.rolling_returns(s, "F", AS_OF)
    assert rolling["windows"] > 500
    assert rolling["worst"] <= rolling["median"] <= rolling["best"]
    assert 0.0 <= rolling["positive_share"] <= 1.0


def test_a_fund_too_short_to_roll_says_zero_windows_rather_than_guessing():
    seed("F", 40)
    with navstore.session() as s:
        rolling = analysis.rolling_returns(s, "F", AS_OF)
    assert rolling["windows"] == 0
    assert rolling["median"] is None


# ------------------------------------------------- edges


def test_a_fund_with_no_navs_returns_empty_series_rather_than_raising():
    result = analyse("NOTHING", peers(12), "1y")
    assert result.nav == [] and result.drawdown == []
    assert result.total_return is None
    assert result.latest_nav is None


def test_an_unknown_range_falls_back_to_the_default():
    seed("F", 800)
    assert analyse("F", peers(12), "nonsense").range_key == analysis.DEFAULT_RANGE


@pytest.mark.parametrize("range_key", list(analysis.RANGES))
def test_every_offered_range_works(range_key):
    seed("F", 2000)
    result = analyse("F", peers(12), range_key)
    assert result.nav
    assert result.nav[0].value == pytest.approx(100.0, abs=1e-6)


def test_a_weekend_at_the_window_start_is_not_a_short_record():
    """The flag fired on almost every fund, and the caption was a lie.

    A window starting on a Saturday has its first NAV on the Monday, so a strict
    `first_nav > window_start` is true nearly always. PPFAS has thirteen years of
    history and its five-year chart was captioned "shorter than the range you
    picked" -- false, and exactly the sentence that stops a reader trusting the
    rest of the page.
    """
    seed("LONG", 3000)                     # eight years, plenty for a 1y window
    result = analyse("LONG", peers(12), "1y")
    assert result.clipped_to_fund_history is False


def test_a_genuinely_young_fund_is_still_flagged():
    seed("YOUNG", 200)
    assert analyse("YOUNG", peers(12), "3y").clipped_to_fund_history is True


def test_the_tolerance_is_about_a_month_not_a_year():
    """Loose enough for a holiday cluster, tight enough that a fund missing half
    the window still says so."""
    assert 7 <= analysis.CLIP_TOLERANCE_DAYS <= 45
