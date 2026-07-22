"""Indian mutual fund data, sourced from mfapi.in (which mirrors AMFI).

mfapi.in is free and unauthenticated but asks for fair usage, so every scheme
lookup goes through a TTL cache — NAVs only change once a day, and the fund
scorer will otherwise re-fetch the same schemes repeatedly.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

BASE_URL = "https://api.mfapi.in"
_TIMEOUT_SECONDS = 20
_CACHE_TTL_SECONDS = 6 * 60 * 60  # NAVs publish once daily, ~11 PM IST
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0

_memory_cache: dict[str, tuple[float, Any]] = {}

# Also cached on disk, because the universe grew from sixteen scheme codes to
# several thousand and an in-memory cache is empty again after every restart.
# That made a cold category take up to 38 seconds, which reads as "the page is
# broken" rather than "the page is loading".
_DISK_CACHE_DIR = Path(
    os.environ.get(
        "NEXTRADE_CACHE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent / ".navcache",
    )
)


class MutualFundDataError(Exception):
    """Raised when mfapi.in is unreachable or returns unusable data."""


@dataclass(frozen=True)
class SchemeSearchResult:
    scheme_code: str
    scheme_name: str


@dataclass(frozen=True)
class SchemeMeta:
    scheme_code: str
    scheme_name: str
    fund_house: str
    scheme_type: str
    scheme_category: str
    isin: str | None

    @property
    def is_direct_growth(self) -> bool:
        """Direct-Growth is the only variant we ever recommend.

        Regular plans carry a distributor commission inside the NAV (~1%/yr)
        for an otherwise identical portfolio.
        """
        name = self.scheme_name.lower()
        return "direct" in name and "growth" in name


@dataclass(frozen=True)
class NavPoint:
    date: date
    nav: float


def clear_cache() -> None:
    _memory_cache.clear()
    try:
        for entry in _DISK_CACHE_DIR.glob("*.json"):
            entry.unlink()
    except OSError:
        # Nothing here is authoritative, so a cache we cannot clear is a
        # nuisance rather than a failure.
        pass


def _cache_path(path: str) -> Path:
    """A filename per request path.

    Hashed because the path contains slashes and query strings, and a scheme
    code alone would collide between /mf/{code} and its search results.
    """
    digest = hashlib.sha256(path.encode()).hexdigest()[:32]
    return _DISK_CACHE_DIR / f"{digest}.json"


def _read_disk(path: str, now: float) -> Any | None:
    try:
        entry = json.loads(_cache_path(path).read_text())
        if now - entry["fetched_at"] < _CACHE_TTL_SECONDS:
            return entry["payload"]
    except (OSError, ValueError, KeyError):
        # A missing file is the common case; a truncated one is what a killed
        # process leaves behind. Both mean "fetch it again".
        return None
    return None


def _write_disk(path: str, payload: Any, now: float) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = _cache_path(path)
        # Written beside the target and moved into place, so a process killed
        # mid-write never leaves a half-file that looks valid.
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": now, "payload": payload}))
        tmp.replace(target)
    except OSError:
        pass


def _get_json(path: str) -> Any:
    """Fetch with a short retry — mfapi.in intermittently drops connections."""
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = httpx.get(f"{BASE_URL}{path}", timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise MutualFundDataError(
        f"mfapi.in request failed for {path}: {last_error}"
    ) from last_error


def _get_json_cached(path: str) -> Any:
    now = time.time()

    hit = _memory_cache.get(path)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    from_disk = _read_disk(path, now)
    if from_disk is not None:
        _memory_cache[path] = (now, from_disk)
        return from_disk

    payload = _get_json(path)
    _memory_cache[path] = (now, payload)
    _write_disk(path, payload, now)
    return payload


def _parse_nav_point(row: dict) -> NavPoint:
    return NavPoint(
        date=datetime.strptime(row["date"], "%d-%m-%Y").date(),
        nav=float(row["nav"]),
    )


def search_schemes(query: str) -> list[SchemeSearchResult]:
    # Encoded, because fund names legitimately contain "&" and spaces.
    payload = _get_json_cached(f"/mf/search?q={quote_plus(query)}")
    return [
        SchemeSearchResult(
            scheme_code=str(row["schemeCode"]),
            scheme_name=row["schemeName"],
        )
        for row in payload
    ]


def _get_scheme(scheme_code: str) -> dict:
    payload = _get_json_cached(f"/mf/{scheme_code}")
    if not isinstance(payload, dict) or "meta" not in payload:
        raise MutualFundDataError(f"Unexpected payload for scheme {scheme_code}")
    return payload


def get_scheme_meta(scheme_code: str) -> SchemeMeta:
    meta = _get_scheme(scheme_code)["meta"]
    return SchemeMeta(
        scheme_code=str(meta["scheme_code"]),
        scheme_name=meta["scheme_name"],
        fund_house=meta.get("fund_house", ""),
        scheme_type=meta.get("scheme_type", ""),
        scheme_category=meta.get("scheme_category", ""),
        isin=meta.get("isin_growth"),
    )


def get_nav_history(scheme_code: str) -> list[NavPoint]:
    """Full NAV history, oldest first (mfapi.in serves it newest first).

    Rows with a non-positive NAV are dropped: AMFI's feed carries zero-NAV
    placeholder rows for dates before a scheme actually launched, and dividing
    by those produces infinities that silently corrupt every downstream metric.
    """
    rows = _get_scheme(scheme_code)["data"]
    points = [p for p in (_parse_nav_point(row) for row in rows) if p.nav > 0]
    if not points:
        raise MutualFundDataError(f"No usable NAV history for scheme {scheme_code}")
    return sorted(points, key=lambda p: p.date)


def get_latest_nav(scheme_code: str) -> NavPoint:
    return get_nav_history(scheme_code)[-1]


def nav_on_or_before(navs: list[NavPoint], target: date) -> NavPoint | None:
    """The NAV in force on a date — NAVs are not published on holidays.

    Returns None if the series starts after the date, which means the fund did
    not exist yet and the caller must not pretend otherwise.
    """
    candidates = [p for p in navs if p.date <= target]
    return candidates[-1] if candidates else None
