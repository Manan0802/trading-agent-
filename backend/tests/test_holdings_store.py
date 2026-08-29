"""The holdings store, and the backup that is the only thing standing behind it.

`.holdings/` is gitignored, for the usual reason a database is. That means git
is NOT its backup, and a store with no backup is a store one `rm -rf` from
being re-crawled across every AMC.
"""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from app.services.marketdata import holdings_store
from app.services.marketdata.fund_holdings import Holding, SchemePortfolio


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_HOLDINGS_DB", str(tmp_path / "holdings.db"))
    yield tmp_path


def _portfolio(
    name: str, rows: list[tuple[str, str, float]], as_of=date(2026, 7, 31), covered=95.0
):
    return SchemePortfolio(
        scheme_name=name,
        as_of=as_of,
        holdings=[Holding(isin=i, name=n, industry="Financial", weight=w)
                  for i, n, w in rows],
        covered=covered,
    )


_PPFAS = _portfolio(
    "Parag Parikh Flexi Cap Fund",
    [("INE040A01034", "HDFC Bank", 7.55), ("INE002A01018", "Reliance", 5.10)],
)
_HDFC = _portfolio(
    "HDFC Flexi Cap Fund",
    [("INE040A01034", "HDFC Bank", 9.20), ("INE009A01021", "Infosys", 4.40)],
)


class TestTheStoreAnswersTheQuestionTheProductAsks:
    def test_a_portfolio_round_trips(self):
        assert holdings_store.save(_PPFAS) == 2
        back = holdings_store.load("Parag Parikh Flexi Cap Fund")
        assert back is not None
        assert back.as_of == date(2026, 7, 31)
        assert {h.isin: h.weight for h in back.holdings} == {
            "INE040A01034": 7.55,
            "INE002A01018": 5.10,
        }

    def test_the_look_through_runs_stock_first(self):
        """Which of my funds own the same company — one seek, not six workbooks."""
        holdings_store.save(_PPFAS)
        holdings_store.save(_HDFC)
        owners = holdings_store.funds_holding("INE040A01034")
        assert dict(owners) == {
            "HDFC Flexi Cap Fund": 9.20,
            "Parag Parikh Flexi Cap Fund": 7.55,
        }
        assert owners[0][1] > owners[1][1], "heaviest weight first"

    def test_a_fund_we_never_stored_is_absent_not_empty(self):
        holdings_store.save(_PPFAS)
        assert holdings_store.load("Some Fund We Do Not Cover") is None
        assert holdings_store.stored_as_of("Some Fund We Do Not Cover") is None
        assert holdings_store.funds_holding("INE999999999") == []

    def test_a_new_disclosure_replaces_the_old_one(self):
        """A stock the fund SOLD has to disappear.

        Merging would leave it there forever, and the look-through would keep
        reporting exposure to a company the user no longer owns.
        """
        holdings_store.save(_PPFAS)
        sold = _portfolio(
            "Parag Parikh Flexi Cap Fund",
            [("INE040A01034", "HDFC Bank", 8.00)],
            as_of=date(2026, 8, 31),
        )
        holdings_store.save(sold)
        back = holdings_store.load("Parag Parikh Flexi Cap Fund")
        assert [h.isin for h in back.holdings] == ["INE040A01034"]
        assert holdings_store.funds_holding("INE002A01018") == []
        assert back.as_of == date(2026, 8, 31)

    def test_the_equity_covered_fraction_survives_the_round_trip(self):
        """A debt fund's file accounts for very little equity, and that IS the
        answer. Losing it loads the fund back looking like an equity fund that
        happens to hold almost nothing."""
        holdings_store.save(_portfolio("A Debt Fund", [("INE040A01034", "X", 2.0)],
                                       covered=2.0))
        assert holdings_store.load("A Debt Fund").covered == 2.0

    def test_the_isin_index_exists(self):
        """Without it, one stock's weight is a full scan of every fund's rows."""
        holdings_store.save(_PPFAS)
        with holdings_store.connect() as con:
            names = {
                r[0]
                for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
        assert "holding_by_isin" in names


class TestTheBackupIsTheOnlyThingBehindTheStore:
    def test_delete_the_store_restore_from_the_dump_get_the_same_store(self, tmp_path):
        """Slice 2.3's acceptance, run rather than asserted."""
        holdings_store.save(_PPFAS)
        holdings_store.save(_HDFC)
        before = holdings_store.counts()
        owners_before = holdings_store.funds_holding("INE040A01034")

        dump = holdings_store.dump_to(tmp_path / "dumps" / "holdings.sql.gz")
        assert dump.exists() and dump.stat().st_size > 0

        holdings_store.db_path().unlink()
        assert holdings_store.counts() == (0, 0), "the store really was destroyed"

        holdings_store.restore_from(dump)
        assert holdings_store.counts() == before
        assert holdings_store.funds_holding("INE040A01034") == owners_before
        restored = holdings_store.load("Parag Parikh Flexi Cap Fund")
        assert {h.isin: h.weight for h in restored.holdings} == {
            "INE040A01034": 7.55,
            "INE002A01018": 5.10,
        }

    def test_restoring_does_not_merge_onto_what_is_already_there(self, tmp_path):
        """Otherwise a restore silently blends two months of disclosures."""
        holdings_store.save(_PPFAS)
        dump = holdings_store.dump_to(tmp_path / "one.sql.gz")
        holdings_store.save(_HDFC)
        assert holdings_store.counts()[0] == 2

        holdings_store.restore_from(dump)
        assert holdings_store.counts()[0] == 1
        assert holdings_store.load("HDFC Flexi Cap Fund") is None

    def test_the_dump_is_plain_sql_so_it_survives_a_sqlite_upgrade(self, tmp_path):
        import gzip

        holdings_store.save(_PPFAS)
        dump = holdings_store.dump_to(tmp_path / "d.sql.gz")
        text = gzip.open(dump, "rt", encoding="utf-8").read()
        assert "CREATE TABLE" in text and "INSERT INTO" in text
        assert "INE040A01034" in text


def test_a_holding_with_no_isin_is_dropped_rather_than_keyed_on_blank():
    """Cash, receivables and TREPS rows carry no ISIN.

    Storing them under an empty key would make every fund appear to share one
    enormous position with every other fund.
    """
    messy = _portfolio(
        "Some Fund",
        [("INE040A01034", "HDFC Bank", 7.55), ("", "TREPS / Cash", 3.10)],
    )
    assert holdings_store.save(messy) == 1
    assert holdings_store.funds_holding("") == []


def test_an_old_schema_is_replaced_rather_than_failing_on_the_first_write(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` leaves an old table exactly where it is.

    Adding the `covered` column produced `OperationalError: table portfolio has
    no column named covered` — on the first WRITE, from inside a request, long
    after start-up. This store is a cache of public monthly filings, so the
    right answer is to rebuild it, not to migrate it.
    """
    path = holdings_store.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE portfolio (scheme_key TEXT PRIMARY KEY, scheme_name TEXT, "
        "as_of TEXT); PRAGMA user_version = 1;"
    )
    con.commit()
    con.close()

    assert holdings_store.save(_PPFAS) == 2, "the stale store must not block a write"
    assert holdings_store.load("Parag Parikh Flexi Cap Fund").covered == 95.0


def test_a_file_that_is_not_a_database_is_replaced_too(tmp_path):
    path = holdings_store.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a database at all")
    assert holdings_store.save(_PPFAS) == 2


def test_a_restored_store_is_not_wiped_by_the_next_read(tmp_path):
    """`iterdump` emits no PRAGMA user_version.

    So a restored store read back as version 0 and the staleness rule deleted
    it — a backup that erased itself the first time it was used, while looking
    like it had worked.
    """
    holdings_store.save(_PPFAS)
    dump = holdings_store.dump_to(tmp_path / "d.sql.gz")
    holdings_store.db_path().unlink()
    holdings_store.restore_from(dump)

    assert holdings_store.counts()[0] == 1
    assert holdings_store.counts()[0] == 1, "and still there on the second read"
    assert holdings_store.load("Parag Parikh Flexi Cap Fund") is not None
