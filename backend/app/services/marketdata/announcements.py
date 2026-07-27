"""Exchange filings for companies the user actually holds.

This is deliberately not a news feed. The evidence on retail investors and
attention runs one way — the more people watch, the more they trade, and
turnover and tax are two of the few things this app has measured as decisive.
A headline stream would work against the advice on every other page.

So the unit is not "news", it is "something changed about a thing you own".
And the filter is the entire product: NSE published a hundred announcements for
Tata Steel in seven months, of which twenty were conference-call notices and
thirteen were copies of newspaper advertisements. A list of a hundred is worse
than no list, because it buries the six that matter.

What is kept is what changes what you own or what it is worth: credit ratings,
auditor and director departures, acquisitions, litigation outcomes, regulatory
action, and capital changes. Everything else is counted and dropped, and the
count is reported rather than hidden.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

_BASE = "https://www.nseindia.com"
# NSE rejects a bare API call; it wants the cookies its own page would set.
_BOOTSTRAP = f"{_BASE}/companies-listing/corporate-filings-announcements"
_API = f"{_BASE}/api/corporate-announcements"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_TIMEOUT = 20
_CACHE_TTL_SECONDS = 6 * 60 * 60  # filings are published, then they stop moving
_DISK_CACHE_DIR = Path(
    os.environ.get(
        "NEXTRADE_NEWS_CACHE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent / ".newscache",
    )
)

_memory: dict[str, tuple[float, Any]] = {}

# Substrings of NSE's category label. Matched as substrings because the
# vocabulary is long, inconsistently punctuated, and grows without notice —
# an exact-match list would silently stop matching the week NSE reworded one.
_MATERIAL = (
    "credit rating",
    "auditor",
    "audit report",
    "resignation",
    "change in directors",
    "key managerial",
    "acquisition",
    "amalgamation",
    "scheme of arrangement",
    "merger",
    "demerger",
    "litigation",
    "dispute",
    "penalt",
    "regulatory",
    "sebi",
    "adjudicat",
    "fraud",
    "default",
    "insolvency",
    "delisting",
    "buyback",
    "bonus",
    "rights issue",
    "stock split",
    "sub-division",
    "dividend",
    "one time settlement",
)

# Kept out even when a phrase above appears inside them. "Copy of newspaper
# publication" is how a dividend notice gets published, and it is the notice we
# already have, printed again.
_NEVER = (
    "copy of newspaper",
    "investor presentation",
    "con. call",
    "conference call",
    "analysts/institutional investor meet",
    "trading window",
    "news verification",
    "certificate under sebi (depositories",
)


class AnnouncementError(Exception):
    """Raised when NSE is unreachable or answers with something unusable."""


@dataclass(frozen=True)
class Announcement:
    symbol: str
    company: str
    category: str
    summary: str
    published: date
    attachment: str | None


def _cache_path(key: str) -> Path:
    return _DISK_CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"


def _read_disk(key: str, now: float) -> Any | None:
    try:
        entry = json.loads(_cache_path(key).read_text())
        if now - entry["fetched_at"] < _CACHE_TTL_SECONDS:
            return entry["payload"]
    except (OSError, ValueError, KeyError):
        return None
    return None


def _write_disk(key: str, payload: Any, now: float) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = _cache_path(key)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": now, "payload": payload}))
        tmp.replace(target)
    except (OSError, TypeError):
        pass


def clear_cache() -> None:
    _memory.clear()
    try:
        for entry in _DISK_CACHE_DIR.glob("*.json"):
            entry.unlink()
    except OSError:
        pass


def _fetch(symbol: str, since: date, until: date) -> list[dict]:
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
        # Load the page first so the session carries the cookies NSE expects.
        # Without it the API answers 401 regardless of headers.
        client.get(_BOOTSTRAP)
        response = client.get(
            _API,
            params={
                "index": "equities",
                "symbol": symbol,
                "from_date": since.strftime("%d-%m-%Y"),
                "to_date": until.strftime("%d-%m-%Y"),
            },
        )
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, list) else []


def _cached_fetch(symbol: str, since: date, until: date) -> list[dict]:
    key = f"{symbol}:{since}:{until}"
    now = time.time()

    hit = _memory.get(key)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    from_disk = _read_disk(key, now)
    if from_disk is not None:
        _memory[key] = (now, from_disk)
        return from_disk

    try:
        rows = _fetch(symbol, since, until)
    except (httpx.HTTPError, ValueError) as exc:
        raise AnnouncementError(f"NSE announcements unavailable for {symbol}: {exc}") from exc

    _memory[key] = (now, rows)
    _write_disk(key, rows, now)
    return rows


def is_material(category: str) -> bool:
    """Whether a filing changes what you own or what it is worth."""
    label = (category or "").lower()
    if any(skip in label for skip in _NEVER):
        return False
    return any(word in label for word in _MATERIAL)


def _parse(row: dict) -> Announcement | None:
    raw = row.get("an_dt") or row.get("exchdisstime") or ""
    try:
        published = datetime.strptime(raw.strip(), "%d-%b-%Y %H:%M:%S").date()
    except ValueError:
        return None
    return Announcement(
        symbol=row.get("symbol") or "",
        company=row.get("sm_name") or row.get("symbol") or "",
        category=row.get("desc") or "",
        summary=(row.get("attchmntText") or "").strip(),
        published=published,
        attachment=row.get("attchmntFile") or None,
    )


def material_announcements(
    symbol: str, *, days: int = 180, today: date | None = None
) -> tuple[list[Announcement], int]:
    """Filings worth reading for one company, and how many were filtered out.

    The dropped count comes back rather than being swallowed: a screen showing
    three items out of a hundred should be able to say so.
    """
    until = today or date.today()
    since = until - timedelta(days=days)
    rows = _cached_fetch(symbol, since, until)

    kept: list[Announcement] = []
    dropped = 0
    for row in rows:
        parsed = _parse(row)
        if parsed is None:
            dropped += 1
            continue
        if not is_material(parsed.category):
            dropped += 1
            continue
        kept.append(parsed)

    kept.sort(key=lambda a: a.published, reverse=True)
    return kept, dropped
