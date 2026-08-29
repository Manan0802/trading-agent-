"""Every fund's disclosed portfolio, kept where it can be queried across funds.

`fund_holdings.py` answers "what does this one fund hold" by downloading an
AMC's monthly spreadsheet. That is the right shape for one fund and the wrong
shape for the question the product actually asks, which runs the other way:
**which of my funds own the same company, and how much of my money is in it.**
Answering that from a per-AMC file cache means parsing six workbooks to learn
one stock's weight, on every request.

So the parsed portfolios land in a small SQLite store, keyed by ISIN, and the
look-through becomes one query.

**The store is a cache of public filings, and it is disposable.** SEBI requires
every AMC to publish these monthly and they stay downloadable, so nothing here
is irrecoverable -- but rebuilding it means re-downloading and re-parsing every
workbook, which is slow enough that a container restart should not trigger it.
`.holdings/` is gitignored for the usual reason a database is, which means git
is NOT its backup; `dump_to()` writes the plain-SQL backup that is.

**Coverage is 29% and the store says so rather than implying otherwise.**
Seven AMCs have had a real file downloaded and parsed, covering 482 of the
1,659 buyable funds. A fund whose AMC is not among them is ABSENT, not zero --
`stored_as_of` returns None and the surface reports "holdings n/a". An overlap
of 0% between two funds because one of them has no data is the same number as
two funds that genuinely share nothing, and they must not look alike.
"""

import gzip
import os
import sqlite3
from datetime import date
from pathlib import Path

from app.services.marketdata.fund_holdings import Holding, SchemePortfolio, _match_key

_DEFAULT = Path(__file__).resolve().parent.parent.parent / ".holdings" / "holdings.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio (
    scheme_key  TEXT PRIMARY KEY,
    scheme_name TEXT NOT NULL,
    as_of       TEXT NOT NULL,
    -- Equity weight the AMC's file actually accounts for. Well short of 100 is
    -- information, not a parse failure: it means cash, debt or derivatives. A
    -- store that dropped it would load a debt fund back looking like an equity
    -- fund that happens to hold very little.
    covered     REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS holding (
    scheme_key TEXT NOT NULL,
    isin       TEXT NOT NULL,
    name       TEXT NOT NULL,
    industry   TEXT,
    weight     REAL NOT NULL,
    PRIMARY KEY (scheme_key, isin)
);
-- The look-through runs stock-first: given an ISIN, which funds hold it. Without
-- this index that is a full scan of every holding of every fund, per stock.
CREATE INDEX IF NOT EXISTS holding_by_isin ON holding (isin);
"""


def db_path() -> Path:
    return Path(os.environ.get("NEXTRADE_HOLDINGS_DB", _DEFAULT))


# Bumped whenever the shape below changes. `CREATE TABLE IF NOT EXISTS` leaves an
# old table exactly where it is, so without this a schema change surfaces as
# `OperationalError: table portfolio has no column named covered` on the first
# WRITE in production -- long after start-up, from inside a request. Rebuilding
# is the right answer rather than a migration because this store is a cache of
# public monthly filings: nothing in it is irrecoverable, and a wrong-shaped
# cache is worth less than the download that replaces it.
_SCHEMA_VERSION = 2


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and _version_of(path) != _SCHEMA_VERSION:
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(_SCHEMA)
    con.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
    return con


def _version_of(path: Path) -> int:
    con = sqlite3.connect(path)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError:
        return -1  # not a database we wrote; replacing it is the safe move
    finally:
        con.close()


def save(portfolio: SchemePortfolio) -> int:
    """Store one fund's portfolio, replacing whatever was there. Returns rows written.

    Replacing rather than merging: a monthly disclosure is the whole portfolio
    as of that date, so a stock the fund sold must DISAPPEAR. Merging would
    leave it there forever, and a look-through would keep reporting exposure to
    a company the user no longer owns.
    """
    key = _match_key(portfolio.scheme_name)
    with connect() as con:
        con.execute("DELETE FROM holding WHERE scheme_key = ?", (key,))
        con.execute(
            "INSERT OR REPLACE INTO portfolio "
            "(scheme_key, scheme_name, as_of, covered) VALUES (?, ?, ?, ?)",
            (key, portfolio.scheme_name, portfolio.as_of.isoformat(),
             float(portfolio.covered)),
        )
        con.executemany(
            "INSERT OR REPLACE INTO holding "
            "(scheme_key, isin, name, industry, weight) VALUES (?, ?, ?, ?, ?)",
            [
                (key, h.isin, h.name, h.industry, h.weight)
                for h in portfolio.holdings
                if h.isin
            ],
        )
    return sum(1 for h in portfolio.holdings if h.isin)


def load(scheme_name: str) -> SchemePortfolio | None:
    """The stored portfolio, or None. None means absent, never empty."""
    key = _match_key(scheme_name)
    with connect() as con:
        row = con.execute(
            "SELECT scheme_name, as_of, covered FROM portfolio WHERE scheme_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        rows = con.execute(
            "SELECT isin, name, industry, weight FROM holding WHERE scheme_key = ? "
            "ORDER BY weight DESC",
            (key,),
        ).fetchall()
    return SchemePortfolio(
        scheme_name=row[0],
        as_of=date.fromisoformat(row[1]),
        holdings=[Holding(isin=r[0], name=r[1], industry=r[2], weight=r[3]) for r in rows],
        covered=row[2],
    )


def funds_holding(isin: str) -> list[tuple[str, float]]:
    """(scheme name, weight) for every stored fund that holds this ISIN.

    The query the store exists for. One index seek instead of six workbooks.
    """
    with connect() as con:
        return [
            (r[0], r[1])
            for r in con.execute(
                "SELECT p.scheme_name, h.weight FROM holding h "
                "JOIN portfolio p ON p.scheme_key = h.scheme_key "
                "WHERE h.isin = ? ORDER BY h.weight DESC",
                (isin,),
            )
        ]


def stored_as_of(scheme_name: str) -> date | None:
    """When this fund's stored portfolio is from, or None if we hold none.

    None is the honest answer for the 71% of buyable funds whose AMC has no
    verified source. A caller that turns it into 0% overlap is reporting "these
    funds share nothing" when the truth is "we did not look".
    """
    with connect() as con:
        row = con.execute(
            "SELECT as_of FROM portfolio WHERE scheme_key = ?",
            (_match_key(scheme_name),),
        ).fetchone()
    return date.fromisoformat(row[0]) if row else None


def counts() -> tuple[int, int]:
    """(funds stored, holding rows stored)."""
    with connect() as con:
        funds = con.execute("SELECT count(*) FROM portfolio").fetchone()[0]
        rows = con.execute("SELECT count(*) FROM holding").fetchone()[0]
    return funds, rows


def dump_to(path: Path) -> Path:
    """A gzipped plain-SQL backup. Git is not this database's backup; this is.

    Plain SQL rather than a copy of the file, because a text dump survives a
    SQLite version change and diffs sensibly, and gzip because the same rows
    repeat an ISIN a few hundred times.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con, gzip.open(path, "wt", encoding="utf-8") as out:
        for line in con.iterdump():
            out.write(f"{line}\n")
    return path


def restore_from(path: Path) -> None:
    """Rebuild the store from a dump, replacing whatever is there.

    The store is dropped first. Restoring on top of existing rows would silently
    merge two months of disclosures, which is the same defect `save` avoids.
    """
    target = db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    with gzip.open(path, "rt", encoding="utf-8") as src:
        con = sqlite3.connect(target)
        try:
            con.executescript(src.read())
            # `iterdump` does not emit PRAGMA user_version, so a restored store
            # reads back as version 0 and `connect()` -- correctly, by its own
            # rule -- deletes it as stale. A backup that erases itself the first
            # time it is read is worse than no backup, because it looks like it
            # worked. Stamped here, at the moment the shape is known good.
            con.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            con.commit()
        finally:
            con.close()
