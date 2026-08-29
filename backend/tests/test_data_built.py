"""Every committed data file can say how old it is, and how it knows.

Three of seven could not. `sector_benchmarks.json` was the one that mattered:
twelve sectors of median P/E, P/B and ROE, which is what decides whether a stock
reads cheap or dear, with no date on it at all. `sector_benchmarks.built_from()`
already applies the right discipline in one dimension — it returns the peer
count so the screen can say what "cheap versus peers" is counted against — and
the same sentence is true of *when*.
"""

import json
from datetime import date
from pathlib import Path

from app.services import data_built

DATA = Path(__file__).resolve().parent.parent / "app" / "data"


def test_every_committed_data_file_is_dated():
    files = sorted(p.name for p in DATA.glob("*.json") if p.name != "built.json")
    assert files, "app/data has no committed json"
    for name in files:
        stamped = data_built.as_of(name)
        assert stamped is not None, f"{name} has no date and no file"
        when, how = stamped
        assert isinstance(when, date)
        assert how, f"{name} does not say how its date was arrived at"


def test_a_date_nobody_recorded_says_so():
    """An mtime is a floor, not a fact — a checkout moves it.

    A screen that cannot tell "the builder wrote this on the 20th" from "this
    file was last touched on the 20th" should not present either as a
    guarantee, so the difference is carried rather than smoothed away.
    """
    manifest = json.loads((DATA / "built.json").read_text())
    kinds = {name: entry.get("how", "") for name, entry in manifest.items()}
    assert kinds, "built.json is empty"
    for name, how in kinds.items():
        assert how.startswith(("built", "mtime", "inferred")), (
            f"{name}: '{how}' is not one of built / mtime / inferred"
        )


def test_every_builder_records_what_it_wrote():
    """A file dated once and never again is the defect this replaces."""
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    unwired = [
        p.name
        for p in sorted(scripts.glob("build_*.py"))
        if "OUT.write_text" in p.read_text() or "_OUT.write_text" in p.read_text()
        if "data_built.record(" not in p.read_text()
    ]
    assert not unwired, f"these builders write a data file and do not date it: {unwired}"
