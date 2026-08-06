"""Promoter shareholding, quarter by quarter, from Screener.in.

Governance rather than valuation is India's dominant equity risk, and a
promoter changing their own stake is the cheapest read on it that exists. The
figure is filed quarterly with the exchanges; Screener publishes it in a table
we can parse.

Best-effort throughout. A company we cannot resolve returns an empty history,
which the scorer treats as "no promoter signal" rather than as a bad signal , 
many of India's largest listed companies genuinely have no promoter at all.
"""

import re
import time
from typing import Any

import httpx

_BASE = "https://www.screener.in"
_TIMEOUT = 15.0
_CACHE_TTL_SECONDS = 24 * 60 * 60  # filed quarterly; a day is generous

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
}

_cache: dict[str, tuple[float, Any]] = {}

# The label sits inside a button with a tooltip span, not directly in the cell,
# so the row is found by the label and then read forward to the row's end.
_LABEL = re.compile(r"Promoters?\s*(?:&nbsp;|\s)*<span", re.I)
_ROW_END = re.compile(r"</tr>", re.I)
_CELL = re.compile(r"<td[^>]*>\s*(-?[0-9]+(?:\.[0-9]+)?)\s*%\s*</td>", re.I)


def _parse(html: str) -> list[float]:
    # The shareholding section holds a quarterly table and a yearly one; the
    # quarterly comes first, which is the one we want.
    section = html.split('id="shareholding"', 1)
    if len(section) < 2:
        return []
    body = section[1]

    label = _LABEL.search(body)
    if not label:
        # The section exists but carries no promoter row, which is how a
        # genuinely promoter-less company renders.
        return []

    end = _ROW_END.search(body, label.end())
    row = body[label.end() : end.start() if end else label.end() + 2000]
    values = [float(v) for v in _CELL.findall(row)]
    # Up to four; a recently listed company simply has fewer, and the caller
    # must say how many it actually got rather than assume four.
    return values[-4:]


def promoter_history(symbol: str) -> list[float]:
    """Promoter stake over the last four filed quarters, oldest first."""
    key = symbol.upper().removesuffix(".NS")
    now = time.time()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    history: list[float] = []
    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=_TIMEOUT) as client:
        # Consolidated first: it is the right view for a group, and Screener
        # falls back to standalone for companies without subsidiaries.
        for path in (f"/company/{key}/consolidated/", f"/company/{key}/"):
            try:
                response = client.get(f"{_BASE}{path}")
            except httpx.HTTPError:
                continue
            if response.status_code != 200:
                continue
            history = _parse(response.text)
            if history:
                break

    _cache[key] = (now, history)
    return history


def clear_cache() -> None:
    _cache.clear()
