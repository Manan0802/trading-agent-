"""Every fund the app offers must have the history it is judged on.

74 of the 1,659 buyable funds had no NAV row in this repo, and the backfill --
which walks the catalogue -- could reach none of them, because none was in the
catalogue. Among them: HDFC Nifty 50 Index Fund, HDFC BSE Sensex Index Fund,
SBI Arbitrage Fund and the entire Dividend Yield sub-category.

The figure §12 records as "101" was never reproducible, because checking it
needs the buyable universe and that file did not exist. Against the catalogue
the answer is 18; against the buyable universe it was 74.

Skipped rather than failed when the store is absent: it is a 5.3M-row artefact
fetched at boot from a release asset, not something a clone carries.
"""

import os
import sqlite3
from pathlib import Path

import pytest

from app.services.advisor import buyable

_STORE = Path(os.environ.get("NEXTRADE_NAV_DB", ".navstore/nav.db"))


@pytest.fixture(scope="module")
def codes_with_history() -> frozenset[str]:
    store = _STORE if _STORE.is_absolute() else Path(__file__).parent.parent / _STORE
    if not store.exists():
        pytest.skip(f"no NAV store at {store}")
    con = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    try:
        return frozenset(
            r[0] for r in con.execute("SELECT DISTINCT scheme_code FROM nav_history")
        )
    finally:
        con.close()


def test_every_buyable_fund_has_nav_history(codes_with_history):
    missing = sorted(buyable.buyable_codes() - codes_with_history)
    assert not missing, (
        f"{len(missing)} buyable funds have no NAV history, so they cannot be "
        f"scored, ranked or charted while still being offered: {missing[:12]}"
    )


def test_the_index_funds_that_were_missing_are_present(codes_with_history):
    """Named, because a count going green hides which funds came back."""
    for code, name in [
        ("119063", "HDFC Nifty 50 Index Fund"),
        ("119065", "HDFC BSE Sensex Index Fund"),
        ("119287", "Tata BSE Sensex Index Fund"),
        ("118527", "Franklin India Dividend Yield Fund"),
        ("149919", "Motilal Oswal BSE Low Volatility Index Fund"),
    ]:
        assert code in codes_with_history, f"{name} ({code}) still has no history"
