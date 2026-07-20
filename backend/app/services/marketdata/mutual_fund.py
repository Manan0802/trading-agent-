"""Indian mutual fund data, sourced from mfapi.in (which mirrors AMFI).

mfapi.in is free and unauthenticated but asks for fair usage, so every scheme
lookup goes through a TTL cache — NAVs only change once a day, and the fund
scorer will otherwise re-fetch the same schemes repeatedly.
"""

import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

BASE_URL = "https://api.mfapi.in"
_TIMEOUT_SECONDS = 20
_CACHE_TTL_SECONDS = 6 * 60 * 60  # NAVs publish once daily, ~11 PM IST

_cache: dict[str, tuple[float, Any]] = {}


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
    _cache.clear()


def _get_json(path: str) -> Any:
    try:
        response = httpx.get(f"{BASE_URL}{path}", timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise MutualFundDataError(f"mfapi.in request failed for {path}: {exc}") from exc


def _get_json_cached(path: str) -> Any:
    now = time.time()
    hit = _cache.get(path)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    payload = _get_json(path)
    _cache[path] = (now, payload)
    return payload


def _parse_nav_point(row: dict) -> NavPoint:
    return NavPoint(
        date=datetime.strptime(row["date"], "%d-%m-%Y").date(),
        nav=float(row["nav"]),
    )


def search_schemes(query: str) -> list[SchemeSearchResult]:
    payload = _get_json_cached(f"/mf/search?q={query}")
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
    """Full NAV history, oldest first (mfapi.in serves it newest first)."""
    rows = _get_scheme(scheme_code)["data"]
    if not rows:
        raise MutualFundDataError(f"No NAV history for scheme {scheme_code}")
    return sorted((_parse_nav_point(row) for row in rows), key=lambda p: p.date)


def get_latest_nav(scheme_code: str) -> NavPoint:
    return get_nav_history(scheme_code)[-1]
