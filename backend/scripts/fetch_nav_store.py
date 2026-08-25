"""Download the nightly NAV store so a fresh container can serve immediately.

    python scripts/fetch_nav_store.py

Run this once at boot, before uvicorn. It fetches the `nav.db.gz` asset that
`.github/workflows/nightly.yml` publishes to the `nav-store` release and unpacks
it to `NEXTRADE_NAV_DB` (default `.navstore/nav.db`).

Why a release asset rather than the repository
----------------------------------------------
The store is rewritten every night. Committing it would add ~24 MB to git
history per day -- roughly 8 GB a year for a file whose old versions are worth
nothing. A release asset is replaced in place and lives outside the object
store, so history stays small and a clone stays fast.

Why fetch at boot rather than mount a disk
------------------------------------------
This is the step that makes a free host viable. Every free tier that offers a
persistent disk wants a credit card; ephemeral disk is free everywhere. The
store is read-only at runtime -- the nightly job that writes it runs on GitHub's
runners, not here -- so losing it on restart costs one download, not a rebuild.
Without this the alternative is re-crawling mfapi for the whole universe, which
takes five to thirty minutes and serves 503 throughout.

Exit codes
----------
0  store is in place (downloaded, or already present and fresh)
1  no store available and none on disk -- refuse to start rather than boot an
   API whose every screener route will 503
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date, timedelta

DEFAULT_REPO = "Manan0802/trading-agent-"
RELEASE_TAG = "nav-store"
ASSET = "nav.db.gz"

# Below this the download is not a store, it is an error page or a truncated
# transfer. The real asset is ~24 MB.
MIN_BYTES = 5_000_000

# A store whose newest NAV is older than this has missed several nightly runs.
# Worth saying out loud: the screen will still serve, but on stale prices.
STALE_AFTER_DAYS = 5


def _dest() -> str:
    return os.environ.get("NEXTRADE_NAV_DB", ".navstore/nav.db")


def _newest_nav(path: str) -> date | None:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        row = con.execute("SELECT max(nav_date) FROM nav_history").fetchone()
        con.close()
        return date.fromisoformat(row[0]) if row and row[0] else None
    except (sqlite3.Error, ValueError, TypeError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=os.environ.get("NEXTRADE_REPO", DEFAULT_REPO))
    ap.add_argument("--dest", default=None)
    ap.add_argument(
        "--force", action="store_true", help="download even if a store is present"
    )
    args = ap.parse_args()

    dest = args.dest or _dest()
    url = (
        f"https://github.com/{args.repo}/releases/download/{RELEASE_TAG}/{ASSET}"
    )

    existing = _newest_nav(dest) if os.path.exists(dest) else None
    if existing and not args.force:
        age = (date.today() - existing).days
        if age <= STALE_AFTER_DAYS:
            print(f"store present, newest NAV {existing} ({age}d old); nothing to do")
            return 0
        print(f"store present but newest NAV is {existing} ({age}d old); refreshing")

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    print(f"downloading {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".gz") as tmp:
                shutil.copyfileobj(response, tmp)
                gz_path = tmp.name
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        if existing:
            print(f"keeping the store already on disk (newest NAV {existing})")
            return 0
        print("no store on disk either; refusing to start", file=sys.stderr)
        return 1

    size = os.path.getsize(gz_path)
    if size < MIN_BYTES:
        os.unlink(gz_path)
        print(f"downloaded only {size:,} bytes; that is not the store", file=sys.stderr)
        return 0 if existing else 1

    # Unpack beside the destination and move into place, so an interrupted
    # decompression can never leave a half-written database where the app will
    # open it and serve a truncated universe behind a 200.
    staged = f"{dest}.incoming"
    with gzip.open(gz_path, "rb") as src, open(staged, "wb") as out:
        shutil.copyfileobj(src, out)
    os.unlink(gz_path)

    newest = _newest_nav(staged)
    if newest is None:
        os.unlink(staged)
        print("downloaded file is not a readable NAV store", file=sys.stderr)
        return 0 if existing else 1

    for leftover in (f"{dest}-wal", f"{dest}-shm"):
        if os.path.exists(leftover):
            os.remove(leftover)
    os.replace(staged, dest)

    age = (date.today() - newest).days
    print(f"store ready: {os.path.getsize(dest)/1e6:.1f} MB, newest NAV {newest}")
    if age > STALE_AFTER_DAYS:
        print(f"::warning::newest NAV is {age} days old; the nightly job may be failing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
