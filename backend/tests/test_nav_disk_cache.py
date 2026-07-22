import json
import time

import pytest

from app.services.marketdata import mutual_fund


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(mutual_fund, "_DISK_CACHE_DIR", tmp_path)
    mutual_fund.clear_cache()
    yield tmp_path
    mutual_fund.clear_cache()


def _stub(monkeypatch, payload, counter):
    def fake_get(path):
        counter.append(path)
        return payload

    monkeypatch.setattr(mutual_fund, "_get_json", fake_get)


PAYLOAD = {"meta": {"scheme_code": 1}, "data": [{"date": "01-01-2024", "nav": "10.5"}]}


def test_a_second_process_does_not_refetch_what_the_first_already_fetched(
    cache_dir, monkeypatch
):
    """The cache used to live only in memory, so every server restart re-paid
    for the whole universe: a cold category took up to 38 seconds."""
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)

    mutual_fund._get_json_cached("/mf/1")
    assert len(calls) == 1

    # Simulate a restart: memory is empty, the disk cache is not.
    mutual_fund._memory_cache.clear()
    assert mutual_fund._get_json_cached("/mf/1") == PAYLOAD
    assert len(calls) == 1, "refetched despite a warm disk cache"


def test_the_disk_entry_expires_on_the_same_ttl_as_memory(cache_dir, monkeypatch):
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)

    mutual_fund._get_json_cached("/mf/1")
    mutual_fund._memory_cache.clear()

    monkeypatch.setattr(
        time, "time", lambda: time.time.__self__ if False else 1e12  # far future
    )
    mutual_fund._get_json_cached("/mf/1")
    assert len(calls) == 2, "served a stale entry past its TTL"


def test_a_corrupt_cache_file_is_refetched_rather_than_raising(cache_dir, monkeypatch):
    """A half-written file from a killed process must not break the app."""
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)

    mutual_fund._get_json_cached("/mf/1")
    mutual_fund._memory_cache.clear()
    next(cache_dir.iterdir()).write_text("{not json")

    assert mutual_fund._get_json_cached("/mf/1") == PAYLOAD
    assert len(calls) == 2


def test_paths_with_slashes_and_queries_become_safe_filenames(cache_dir, monkeypatch):
    """/mf/search?q=hdfc%20flexi cannot be a filename as-is."""
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)

    mutual_fund._get_json_cached("/mf/search?q=hdfc+flexi&x=1")
    mutual_fund._memory_cache.clear()
    mutual_fund._get_json_cached("/mf/search?q=hdfc+flexi&x=1")
    assert len(calls) == 1


def test_two_different_paths_do_not_collide(cache_dir, monkeypatch):
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)

    mutual_fund._get_json_cached("/mf/1")
    mutual_fund._get_json_cached("/mf/2")
    mutual_fund._memory_cache.clear()
    mutual_fund._get_json_cached("/mf/1")
    mutual_fund._get_json_cached("/mf/2")
    assert len(calls) == 2


def test_clear_cache_empties_disk_too(cache_dir, monkeypatch):
    """Otherwise a test that clears the cache still gets yesterday's data."""
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)

    mutual_fund._get_json_cached("/mf/1")
    mutual_fund.clear_cache()
    mutual_fund._get_json_cached("/mf/1")
    assert len(calls) == 2


def test_an_unwritable_cache_dir_degrades_to_network_rather_than_failing(
    cache_dir, monkeypatch
):
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)
    monkeypatch.setattr(mutual_fund, "_DISK_CACHE_DIR", cache_dir / "nope" / "deeper")
    monkeypatch.setattr(
        mutual_fund.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("ro"))
    )

    assert mutual_fund._get_json_cached("/mf/1") == PAYLOAD


def test_the_cached_payload_round_trips_exactly(cache_dir, monkeypatch):
    calls: list[str] = []
    _stub(monkeypatch, PAYLOAD, calls)

    mutual_fund._get_json_cached("/mf/1")
    mutual_fund._memory_cache.clear()
    assert json.dumps(mutual_fund._get_json_cached("/mf/1"), sort_keys=True) == (
        json.dumps(PAYLOAD, sort_keys=True)
    )
