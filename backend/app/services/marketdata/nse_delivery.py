"""Delivery percentage for every NSE equity, from the daily bhavcopy.

## Why this file exists

Delivery volume is 9 of the 100 points in the ported stock score, and until now
it has been the *same 9 points for every company on every run*. The scorer's
only documented source is NSE's `quote-equity?section=trade_info`, which returns
**403** to us and to the vendor we ported from. `_score_delivery(None)` awards
its neutral half, so 4.5 points went to everything, forever, and
`_check_price_delivery_correlation` behind it was unreachable code.

The 403 turned out to be a red herring: delivery was never gated on that
endpoint. `nsearchives.nseindia.com` publishes the full securities bhavcopy as a
plain CSV with `DELIV_QTY` and `DELIV_PER` columns — no cookies, no browser, no
Akamai. Verified 2026-08-21 against 20-Aug-2026: HTTP 200, 393 KB, 2,630
EQ-series names, 746 of traa's 751 matched (99.3%), values spread 3.6% to 100%
with a median of 56.9%. A real factor, not another constant.

## What it does not tell you

This is **one day's** delivery, which is what the ported scorer asks for — it
takes `delivery_pct` as a scalar. One day is noisy: a single block deal moves a
mid-cap's figure by twenty points. The score inherits that noise, and the screen
says so rather than implying the number is a considered measure of conviction.

Averaging a fortnight would be steadier, but it would no longer be the quantity
the ported formula was built on, and parity with that formula is the point of
the port. Left as one day, stated as one day.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

_log = logging.getLogger(__name__)

_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv"

# The archive answers a bare GET, but only with a browser-shaped agent; without
# one it returns 403, which is the same wall that made everyone believe the data
# was gone.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/csv,*/*",
}

# The file exists for trading days only. A Monday morning has to reach back past
# the weekend, and a long festival weekend past three or four days. Six is
# enough for every Indian market holiday cluster; beyond that, something is
# wrong that a wider search would only hide.
_MAX_LOOKBACK_DAYS = 6

_TIMEOUT_SECONDS = 20

# One trading day's file, ~390 KB of CSV reduced to ~2,600 floats. Cached for
# the day because it never changes once published.
_CACHE_TTL_SECONDS = 12 * 60 * 60

_DISK_CACHE_DIR = Path(
    os.environ.get(
        "NEXTRADE_STOCK_CACHE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent / ".stockcache",
    )
)

# Series to keep. EQ is ordinary equity; BE is the trade-to-trade segment where
# delivery is 100% by construction and so carries no information about
# conviction, which is what this factor is trying to measure.
_KEEP_SERIES = ("EQ",)

_memory: dict[str, tuple[float, dict[str, float], str]] = {}


class DeliveryUnavailable(Exception):
    """Raised when no bhavcopy could be read inside the lookback window."""


def _cache_path(key: str) -> Path:
    return _DISK_CACHE_DIR / f"delivery-{key}.json"


def _read_disk(key: str, now: float) -> tuple[dict[str, float], str] | None:
    try:
        entry = json.loads(_cache_path(key).read_text())
        if now - entry["fetched_at"] < _CACHE_TTL_SECONDS:
            return entry["payload"], entry["trade_date"]
    except (OSError, ValueError, KeyError):
        # Missing is the common case; truncated is what a killed process
        # leaves. Both mean fetch it again.
        return None
    return None


def _write_disk(key: str, payload: dict[str, float], trade_date: str, now: float) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _cache_path(key).with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"fetched_at": now, "trade_date": trade_date, "payload": payload})
        )
        tmp.replace(_cache_path(key))
    except OSError:
        # A cache we cannot write is a slow app, not a broken one.
        pass


def _parse(text: str) -> dict[str, float]:
    """Symbol to delivery percentage, from the bhavcopy CSV.

    The header carries a space after every comma (`SYMBOL, SERIES, ...`), so
    both keys and values are stripped. Rows whose `DELIV_PER` is `-` are real
    and mean the exchange published no delivery figure for that scrip that day;
    they are dropped rather than read as zero, because zero delivery and no
    reported delivery are different facts and one of them would score the
    company at the bottom of the factor.
    """
    out: dict[str, float] = {}
    for raw in csv.DictReader(io.StringIO(text)):
        row = {
            (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
            for k, v in raw.items()
            if k is not None
        }
        if row.get("SERIES") not in _KEEP_SERIES:
            continue
        symbol, pct = row.get("SYMBOL"), row.get("DELIV_PER")
        if not symbol or not pct or pct == "-":
            continue
        try:
            value = float(pct)
        except ValueError:
            continue
        # The exchange occasionally prints a rounding artefact above 100.
        if 0.0 <= value <= 100.5:
            out[symbol] = min(value, 100.0)
    return out


def _fetch_one(day: date) -> str | None:
    url = _URL.format(ddmmyyyy=day.strftime("%d%m%Y"))
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        _log.info("delivery bhavcopy %s: %s", day, exc)
        return None
    if response.status_code != 200 or len(response.content) < 10_000:
        # A holiday returns a short error page with a 200 on some days, so size
        # is checked as well as status.
        return None
    return response.text


def latest(as_of: date | None = None) -> tuple[dict[str, float], date]:
    """Delivery percentage by symbol for the most recent published trading day.

    Returns the mapping and the date it belongs to — the date is not decoration.
    A score built on Friday's delivery and shown on Tuesday is a different claim
    from one built this morning, and the screen has to be able to say which.

    Raises `DeliveryUnavailable` if nothing published inside the lookback
    window, so a caller can fall back to the neutral score deliberately rather
    than by accident.
    """
    today = as_of or date.today()
    key = today.isoformat()
    now = time.time()

    cached = _memory.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1], date.fromisoformat(cached[2])

    on_disk = _read_disk(key, now)
    if on_disk is not None:
        payload, trade_date = on_disk
        _memory[key] = (now, payload, trade_date)
        return payload, date.fromisoformat(trade_date)

    for back in range(_MAX_LOOKBACK_DAYS + 1):
        day = today - timedelta(days=back)
        text = _fetch_one(day)
        if text is None:
            continue
        parsed = _parse(text)
        if len(parsed) < 500:
            # The NSE lists well over a thousand EQ scrips. Far fewer means the
            # format moved or the file is a stub, and scoring on it would be
            # worse than scoring neutral.
            _log.warning("delivery bhavcopy %s parsed only %d rows; ignoring", day, len(parsed))
            continue
        _memory[key] = (now, parsed, day.isoformat())
        _write_disk(key, parsed, day.isoformat(), now)
        return parsed, day

    raise DeliveryUnavailable(
        f"no NSE bhavcopy published in the {_MAX_LOOKBACK_DAYS} days to {today}"
    )


def clear_cache() -> None:
    _memory.clear()
    try:
        for entry in _DISK_CACHE_DIR.glob("delivery-*.json"):
            entry.unlink()
    except OSError:
        pass
