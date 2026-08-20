"""The sector medians, and the crash this layer exists to make unreachable.

Upstream's benchmark record allows `median_pe` and `median_pb` to be None when
a sector's basket comes back thin, and `_score_pe` and `_score_pb` divide by
them without checking. An unknown or thin sector is therefore a TypeError at
scoring time rather than the neutral score every other missing input produces.
"""

import json

import pytest

from app.services.screener import sector_benchmarks as sb

KEYS = ("median_pe", "median_pb", "median_roe", "median_div_yield")


@pytest.fixture(autouse=True)
def fresh():
    sb.clear_cache()
    yield
    sb.clear_cache()


def test_the_shipped_file_has_every_median_for_every_sector():
    """A None here is a division by None two layers down."""
    for name in sb.sectors() + [sb.UNKNOWN_SECTOR]:
        row = sb.resolve(name)
        for key in KEYS:
            assert row.get(key) is not None, f"{name}.{key} is missing"
            assert isinstance(row[key], (int, float))


def test_an_unknown_sector_gets_a_complete_record_rather_than_an_error():
    """A newly listed company in a sector we have no basket for must score
    neutrally on valuation, not take the run down."""
    row = sb.resolve("Interdimensional Widgets")
    assert all(row[k] is not None for k in KEYS)
    assert row == sb.resolve(None)
    assert row == sb.resolve("")


def test_the_units_are_what_the_scorer_expects():
    """Not uniform, and this is where a builder gets it wrong. `median_roe` and
    `median_div_yield` are PERCENTS; the company's own ROE reaches `_score_roe`
    as a decimal fraction and is converted there."""
    for name in sb.sectors():
        row = sb.resolve(name)
        assert 3.0 <= row["median_pe"] <= 120.0, f"{name} PE {row['median_pe']}"
        assert 0.2 <= row["median_pb"] <= 40.0, f"{name} PB {row['median_pb']}"
        # A percent, so a plausible sector ROE is a number like 13.35, not 0.1335.
        assert 0.5 <= row["median_roe"] <= 90.0, f"{name} ROE {row['median_roe']}"
        assert 0.0 < row["median_div_yield"] <= 12.0, f"{name} DY {row['median_div_yield']}"


def test_roe_is_a_percent_not_a_fraction():
    """The single most likely unit slip. If someone rebuilds the file emitting
    yfinance's raw decimal, every sector median becomes ~0.14 and every real
    company looks twenty times more profitable than its peers."""
    values = [sb.resolve(n)["median_roe"] for n in sb.sectors()]
    assert max(values) > 1.5, (
        f"every sector ROE is below 1.5 ({values}); these look like decimal "
        "fractions, not percents"
    )


def test_the_medians_are_measured_not_all_fallbacks():
    """The file is allowed to fall back per sector, but a file that is ALL
    fallbacks means the fetch failed and nobody noticed."""
    rows = [sb.resolve(n) for n in sb.sectors()]
    measured = sum(1 for r in rows if r.get("constituents_usable", 0) >= 3)
    assert measured >= len(rows) - 3, (
        f"only {measured} of {len(rows)} sectors have a usable basket"
    )


def test_the_build_date_is_recorded_so_the_screen_can_disclose_it():
    """Sector medians drift with the market. A number built six months ago is
    not wrong, but a screen saying "cheap versus peers" should say when peers
    was measured."""
    assert sb.built_on() != "unknown"
    assert len(sb.built_on()) == 10


def test_a_missing_file_raises_rather_than_inventing_medians(tmp_path, monkeypatch):
    """Scoring every stock against invented numbers produces a full,
    plausible-looking ranking built on nothing. An error a router can turn into
    a 503 is strictly better."""
    monkeypatch.setattr(sb, "DATA", tmp_path / "gone.json")
    sb.clear_cache()
    with pytest.raises(sb.SectorBenchmarksUnavailable, match="build_sector_benchmarks"):
        sb.resolve("Technology")


def test_a_corrupt_file_raises(tmp_path, monkeypatch):
    bad = tmp_path / "b.json"
    bad.write_text("{not json")
    monkeypatch.setattr(sb, "DATA", bad)
    sb.clear_cache()
    with pytest.raises(sb.SectorBenchmarksUnavailable):
        sb.resolve("Technology")


def test_a_file_with_no_unknown_record_raises(tmp_path, monkeypatch):
    """Without it, an unmapped stock has nothing to be scored against and the
    fallback path silently does not exist."""
    partial = tmp_path / "p.json"
    partial.write_text(json.dumps({
        "built_on": "2026-08-21",
        "sectors": {"Technology": {k: 1.0 for k in KEYS}},
    }))
    monkeypatch.setattr(sb, "DATA", partial)
    sb.clear_cache()
    with pytest.raises(sb.SectorBenchmarksUnavailable, match="Unknown"):
        sb.resolve("Technology")


def test_a_sector_with_a_null_median_raises_at_load_not_at_scoring_time(tmp_path, monkeypatch):
    """The whole point of this module. Better to refuse the file than to hand a
    None to a function that divides by it."""
    broken = tmp_path / "n.json"
    broken.write_text(json.dumps({
        "built_on": "2026-08-21",
        "sectors": {
            "Technology": {"median_pe": None, "median_pb": 4.0,
                           "median_roe": 20.0, "median_div_yield": 1.0},
            sb.UNKNOWN_SECTOR: {k: 1.0 for k in KEYS},
        },
    }))
    monkeypatch.setattr(sb, "DATA", broken)
    sb.clear_cache()
    with pytest.raises(sb.SectorBenchmarksUnavailable, match="median_pe"):
        sb.resolve("Technology")


def test_the_file_is_only_read_once():
    """It is reference data on every scored stock's path; re-reading it per
    stock would be 1,900 file opens a run."""
    sb.clear_cache()
    sb.resolve("Technology")
    before = sb._load.cache_info()
    sb.resolve("Energy")
    sb.resolve("Healthcare")
    assert sb._load.cache_info().misses == before.misses
