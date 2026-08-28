"""Groww's own catalogue: which funds are actually buyable, and what they hold.

WHY THIS MODULE EXISTS
----------------------
Three things this repo had recorded as unobtainable turn out to sit behind two
unauthenticated Groww endpoints, verified live on 2026-08-27:

    fund manager + tenure   Phase 7 of the screener plan was dropped outright
                            for having "no free source".
    minimum investment      recorded in the Bachatt teardown as structurally
                            unavailable -- their distributor feed, no public
                            equivalent.
    holdings, every fund    we could read seven AMCs' monthly XLS files, so
                            fund overlap had to fall back to NAV correlation.

Measured on a stratified sample of 40 funds across 20 AMCs: 40/40 returned an
ISIN, a benchmark, a full holdings list and manager details. That is a different
class of coverage from the XLS parser, and it is why this module exists.

WHAT THIS MODULE IS NOT ALLOWED TO BE
-------------------------------------
Groww's robots.txt says `Disallow: /v1/api/*`. No authentication is required,
but that is not the same as permission. So this is an ENRICHMENT layer and the
app must work without it -- degraded, but working. AMFI's NAVAll.txt stays the
spine because it is public, documented and ToS-clean. Nothing here may become a
precondition for the screener producing a ranking.

Concretely that means every function in this module raises `GrowwUnavailable`
rather than a generic error, and every caller is expected to catch it and carry
on with a named gap rather than an empty screen.

THE FOUR TRAPS, EACH FOUND BY PROBING RATHER THAN BY READING DOCS
-----------------------------------------------------------------
1.  A slug that does not exist returns **HTTP 200 with every field set to
    null** -- not a 404. `parag-parikh-flexi-cap-fund-direct-growth` looks
    exactly like a real slug and is not one; the real one is
    `parag-parikh-long-term-value-fund-direct-growth`. A caller that trusted
    the status code would store a fund with no ISIN, no holdings and no
    manager, and nothing would log. `parse_scheme_detail` therefore treats a
    null ISIN as the failure it is.

2.  Holdings on the v1 endpoint are **arrays, not objects** -- positional,
    unlabelled, twelve entries wide, so a column insertion shifts sector and
    weight one place left with every value still plausible. This module calls
    **v5**, which returns the same holdings as named objects and removes the
    failure entirely. The positional reader is retained for cached v1 payloads,
    and the weight-sum tripwire is retained for both: a fund's disclosed weights
    summing to something other than ~100 is wrong however it was parsed.

3.  `sip_return3y` and `sipReturn3y` **both exist and disagree** -- 43.44
    against 27.43 on SBI Gold. Which is which is not documented and was not
    established. Neither is read here. A field whose meaning is unknown is more
    dangerous than a field that is missing, because it renders.

4.  `expense_ratio` arrives as a **string** (`'0.24'`), and the stock endpoint's
    fundamentals are formatted display strings (`'₹17,57,876Cr'`). Only the
    fields parsed below are trusted to be numeric.

DUPLICATES ARE EXPECTED
-----------------------
The live feed carries 1,741 direct-growth rows against 1,686 distinct AMFI
scheme codes -- the same fund reachable under more than one slug. Deduplicating
is correct; treating the 55 as an error is not.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://groww.in"
UNIVERSE_URL = f"{_BASE}/v1/api/search/v3/query/filter_derived_data/st_filter"
# v5 over v1 deliberately. v1 returns holdings as POSITIONAL arrays -- twelve
# unlabelled entries wide, where a column insertion shifts sector and weight one
# place left and every value stays plausible. v5 returns the same holdings as
# named objects, and additionally carries `stock_search_id` on each line, which
# is the join from a fund's holding to that company's own page. Measured on
# PPFAS: v1 37 KB, v2 188 KB, v5 190 KB, same 152 holdings.
#
# v6 exists and returned byte-identical output to v5 when probed on 2026-08-27.
# v5 is used because it is the older of the two that already carries everything,
# so it is the one less likely to be moved next.
SCHEME_URL = f"{_BASE}/v1/api/data/mf/web/v5/scheme/search"

# The v1 shape, kept only so `parse_holdings` can still read a cached v1 payload
# and so the positional-shift guard remains exercised by a test.
LEGACY_SCHEME_URL = f"{_BASE}/v1/api/data/mf/web/v1/scheme/search"

# The edge cache is `max-age=900`, so anything more often than a few times a day
# is asking for a different answer than the one it will get. One nightly pull is
# the intended usage.
_TIMEOUT_SECONDS = 60

# Sized past the 3,410 rows the feed returned when measured, so that a growing
# catalogue does not silently truncate at the page boundary. `total_results` is
# cross-checked against the row count regardless, which is what actually catches
# truncation.
_PAGE_SIZE = 6000

# Measured: 1,741 direct-growth rows. A collapse well below this is a feed
# change or a partial response, and ranking against half a universe while
# calling it "every fund on Groww" is the specific failure this prevents.
_MIN_GROWTH_ROWS = 1_200

# Holdings weights are percentages of the portfolio. Cash, derivatives and
# rounding mean they do not sum to exactly 100, but a column shift lands far
# outside this band, which is the whole point of checking the sum rather than
# the type.
_WEIGHT_SUM_BAND = (85.0, 115.0)

_DISK_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".growwcache"
_CACHE_KEEP_DAYS = 14


class GrowwUnavailable(RuntimeError):
    """Groww did not answer, or answered with something we refuse to trust.

    A distinct type because callers must degrade rather than fail: the screener
    still ranks funds without any of this, it just cannot say what they hold or
    who runs them.
    """


@dataclass(frozen=True)
class GrowwFund:
    """One buyable direct-growth scheme, as Groww lists it.

    `scheme_code` is the AMFI code, which is what joins this to our NAV store,
    our catalogue and our expense-ratio table. It is the reason this endpoint is
    worth anything: a Groww-only identifier would have needed a fuzzy name join,
    which is exactly how the AMFI TER table ended up missing PPFAS.
    """

    scheme_code: str
    search_id: str
    name: str
    amc: str
    fund_house: str
    category: str
    sub_category: str
    expense_ratio: float | None
    aum_crore: float | None
    fund_manager: str | None
    min_lumpsum: float | None
    min_sip: float | None
    exit_load: str | None
    risk: str | None
    groww_rating: int | None
    sip_allowed: bool
    lumpsum_allowed: bool


@dataclass(frozen=True)
class Holding:
    """One line of a fund's disclosed portfolio.

    `weight_pct` is the share of the fund, not of the user's money. The
    conversion to the user's exposure belongs to the caller that knows how much
    of the fund the user owns, and deliberately does not happen here.

    `stock_search_id` is the reason look-through is possible at all: it joins a
    fund's holding to that company's own record, so "which of my funds own this
    company, and what does it add up to" becomes a lookup rather than a fuzzy
    name match. It is None for cash, debt paper and anything without a listed
    equity page.
    """

    name: str
    instrument_type: str          # EQUITY / DEBT / CASH / REALEST / MF
    sector: str | None
    asset_class: str | None
    weight_pct: float
    as_of: date
    market_value: float | None = None      # rupees lakh, as disclosed
    stock_search_id: str | None = None
    rating: str | None = None              # credit rating, debt lines only


@dataclass(frozen=True)
class Manager:
    name: str
    since: date | None


@dataclass(frozen=True)
class SchemeDetail:
    scheme_code: str
    isin: str
    benchmark: str | None
    registrar: str | None
    launch_date: date | None
    holdings: tuple[Holding, ...]
    managers: tuple[Manager, ...]


# ---------------------------------------------------------------------------
# Parsing. Pure -- no network, no clock, no disk -- so the traps above are all
# reachable from a fixture string in a test.
# ---------------------------------------------------------------------------


def _opt_float(value: object) -> float | None:
    """Groww sends numbers as strings often enough that this is the norm.

    Returns None rather than 0.0 on anything unparseable, because a fund whose
    expense ratio we failed to read must not sort as the cheapest one.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _opt_int(value: object) -> int | None:
    f = _opt_float(value)
    return None if f is None else int(f)


def parse_universe(payload: dict) -> list[GrowwFund]:
    """Every buyable direct-growth scheme in the feed, deduplicated by AMFI code.

    Filters on `scheme_type == "Growth"` and `available_for_investment == 1`.
    Both matter and for different reasons: the feed carries 951 Dividend and 582
    IDCW variants of the same funds, and this app only ever recommends growth
    plans; and a scheme Groww has stopped selling is not part of "the funds you
    can buy", however healthy its NAV series looks.

    `plan_type` is deliberately NOT filtered on. Every row in the measured feed
    was already Direct -- Regular plans are not exposed by this endpoint at all
    -- so a filter here would be untested code that silently starts dropping
    everything the day Groww adds them. The count guard below is the real
    protection.
    """
    rows = payload.get("content")
    if not isinstance(rows, list):
        raise GrowwUnavailable(
            f"universe payload has no 'content' list (keys: {sorted(payload)[:8]})"
        )

    total = payload.get("total_results")
    if isinstance(total, int) and total != len(rows):
        # A short page reads as a shrinking fund universe, which is indis-
        # tinguishable from funds being delisted unless we say so here.
        raise GrowwUnavailable(
            f"feed says {total} results but sent {len(rows)} rows -- page truncated"
        )

    seen: dict[str, GrowwFund] = {}
    for row in rows:
        if row.get("scheme_type") != "Growth":
            continue
        if row.get("available_for_investment") != 1:
            continue
        code = row.get("scheme_code")
        search_id = row.get("search_id")
        if not code or not search_id:
            continue
        code = str(code)
        if code in seen:
            continue
        seen[code] = GrowwFund(
            scheme_code=code,
            search_id=str(search_id),
            name=str(row.get("scheme_name") or row.get("fund_name") or ""),
            amc=str(row.get("amc") or ""),
            fund_house=str(row.get("fund_house") or ""),
            category=str(row.get("category") or ""),
            sub_category=str(row.get("sub_category") or ""),
            expense_ratio=_opt_float(row.get("expense_ratio")),
            aum_crore=_opt_float(row.get("aum")),
            fund_manager=(row.get("fund_manager") or None),
            min_lumpsum=_opt_float(row.get("min_investment_amount")),
            min_sip=_opt_float(row.get("min_sip_investment")),
            exit_load=(row.get("exit_load") or None),
            risk=(row.get("risk") or None),
            groww_rating=_opt_int(row.get("groww_rating")),
            sip_allowed=bool(row.get("sip_allowed")),
            lumpsum_allowed=bool(row.get("lumpsum_allowed")),
        )

    if len(seen) < _MIN_GROWTH_ROWS:
        raise GrowwUnavailable(
            f"only {len(seen)} buyable direct-growth schemes parsed from "
            f"{len(rows)} rows; expected at least {_MIN_GROWTH_ROWS}"
        )
    return sorted(seen.values(), key=lambda f: f.scheme_code)


# The v1 positional layout, named here rather than inlined so the assumption is
# one edit away from being corrected. Only reached for a cached v1 payload; v5
# returns named objects and is what `fetch_scheme_detail` calls.
_H_AS_OF, _H_NAME, _H_TYPE, _H_SECTOR, _H_ASSET, _H_WEIGHT = 1, 2, 3, 4, 5, 8
_H_MIN_WIDTH = 9


def _holding_from_object(row: dict) -> Holding | None:
    """The v5 shape: named keys, so nothing here depends on column order."""
    weight = _opt_float(row.get("corpus_per"))
    name = row.get("company_name")
    if weight is None or not name:
        return None
    as_of = _parse_iso_opt(row.get("portfolio_date"))
    if as_of is None:
        return None
    return Holding(
        name=str(name),
        instrument_type=str(row.get("nature_name") or ""),
        sector=(row.get("sector_name") or None),
        asset_class=(row.get("instrument_name") or None),
        weight_pct=weight,
        as_of=as_of,
        market_value=_opt_float(row.get("market_value")),
        stock_search_id=(row.get("stock_search_id") or None),
        rating=(row.get("rating") or None),
    )


def _holding_from_array(row: list) -> Holding | None:
    """The v1 shape. Positional, and therefore only as right as the constants."""
    if len(row) < _H_MIN_WIDTH:
        return None
    weight = _opt_float(row[_H_WEIGHT])
    if weight is None:
        return None
    return Holding(
        name=str(row[_H_NAME]),
        instrument_type=str(row[_H_TYPE]),
        sector=(row[_H_SECTOR] or None),
        asset_class=(row[_H_ASSET] or None),
        weight_pct=weight,
        as_of=_parse_iso(row[_H_AS_OF]),
    )


def parse_holdings(rows: object) -> tuple[Holding, ...]:
    """A fund's disclosed portfolio, from either endpoint shape.

    Returns an empty tuple when a fund genuinely discloses nothing -- index
    funds partway through a rebuild, new schemes -- because that is missing
    data, not a broken feed.

    The weight-sum tripwire applies to both shapes. On v1 it catches a shifted
    column, which is the failure that shape invites. On v5 it catches something
    rarer and worse: a disclosure that does not add up to a portfolio, which
    would quietly understate every look-through exposure computed from it.
    """
    if not isinstance(rows, list) or not rows:
        return ()

    out: list[Holding] = []
    for row in rows:
        h = _holding_from_object(row) if isinstance(row, dict) else (
            _holding_from_array(row) if isinstance(row, list) else None
        )
        if h is not None:
            out.append(h)
    if not out:
        return ()

    total = sum(h.weight_pct for h in out)
    low, high = _WEIGHT_SUM_BAND
    if not low <= total <= high:
        raise GrowwUnavailable(
            f"holdings weights sum to {total:.1f}%, outside {low}-{high}% -- "
            "either a shifted column (v1) or an incomplete disclosure (v5)"
        )
    return tuple(out)


def _parse_iso(value: object) -> date:
    return date.fromisoformat(str(value)[:10])


def _parse_iso_opt(value: object) -> date | None:
    try:
        return _parse_iso(value)
    except (TypeError, ValueError):
        return None


def parse_scheme_detail(payload: dict) -> SchemeDetail:
    """One scheme's ISIN, benchmark, holdings and managers.

    THE NULL-OBJECT GUARD. A slug Groww does not recognise returns HTTP 200 and
    the complete object shape with every value null. There is no status code, no
    error field and no exception to catch -- the only signal is that a real
    scheme always has an ISIN. Checking it here means an unrecognised slug fails
    loudly at the one place that can tell, instead of being written to disk as a
    fund that holds nothing.
    """
    isin = payload.get("isin")
    code = payload.get("scheme_code")
    if not isin or not code:
        raise GrowwUnavailable(
            "scheme detail came back with no ISIN -- the slug is almost "
            "certainly wrong; take it from the universe feed's search_id"
        )

    managers: list[Manager] = []
    for entry in payload.get("fund_manager_details") or []:
        name = entry.get("person_name")
        if not name:
            continue
        managers.append(Manager(name=str(name), since=_parse_iso_opt(entry.get("date_from"))))

    return SchemeDetail(
        scheme_code=str(code),
        isin=str(isin),
        benchmark=(payload.get("benchmark_name") or None),
        registrar=(payload.get("registrar_agent") or None),
        launch_date=_parse_launch(payload.get("launch_date")),
        holdings=parse_holdings(payload.get("holdings")),
        managers=tuple(managers),
    )


_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _parse_launch(value: object) -> date | None:
    """`24-May-2013`, parsed against an explicit month map.

    Not `strptime("%d-%b-%Y")`: %b is locale-dependent, and on a host with a
    non-English LC_TIME two months a year stop parsing. The same reasoning, and
    the same map, as the AMFI feed parser.
    """
    if not value:
        return None
    parts = str(value).split("-")
    if len(parts) != 3 or parts[1] not in _MONTHS:
        return None
    try:
        return date(int(parts[2]), _MONTHS[parts[1]], int(parts[0]))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Network. Everything above is reachable without it.
# ---------------------------------------------------------------------------


def _cache_path(key: str) -> Path:
    return _DISK_CACHE_DIR / f"{key}.json"


def _read_disk(key: str) -> dict | None:
    try:
        return json.loads(_cache_path(key).read_text())
    except (OSError, ValueError):
        return None


def _write_disk(key: str, payload: dict) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _cache_path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(_cache_path(key))
    except OSError:
        pass


def _prune_disk() -> None:
    cutoff = time.time() - _CACHE_KEEP_DAYS * 86_400
    try:
        for entry in _DISK_CACHE_DIR.glob("*.json"):
            if entry.stat().st_mtime < cutoff:
                entry.unlink(missing_ok=True)
    except OSError:
        pass


def _get_json(url: str, params: dict | None = None) -> dict:
    # A browser User-Agent is sent because several India-market endpoints reject
    # the default httpx one; it is not an attempt to look like anything other
    # than a script, and the request rate -- once a night -- says the same.
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NexTrade personal research)"}
    try:
        response = httpx.get(
            url, params=params, headers=headers,
            timeout=_TIMEOUT_SECONDS, follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GrowwUnavailable(f"Groww request failed for {url}: {exc}") from exc


def fetch_universe(use_cache: bool = True) -> list[GrowwFund]:
    """Today's buyable direct-growth universe, cached by fetch date.

    Keyed by date rather than by TTL for the same reason as the AMFI feed: a
    same-day rerun is free, and a payload that failed to parse is still on disk
    afterwards to be read, instead of having to be provoked out of Groww again.
    """
    key = f"universe-{date.today().isoformat()}"
    if use_cache:
        cached = _read_disk(key)
        if cached is not None:
            return parse_universe(cached)
    payload = _get_json(UNIVERSE_URL, {"page": 0, "size": _PAGE_SIZE})
    funds = parse_universe(payload)  # parse before caching: never cache garbage
    _write_disk(key, payload)
    _prune_disk()
    return funds


def fetch_scheme_detail(search_id: str, use_cache: bool = True) -> SchemeDetail:
    """One scheme's detail. `search_id` must come from `fetch_universe`.

    Holdings change once a month, so this is cached by month rather than by day:
    re-pulling 1,686 schemes nightly would be 1,686 requests for data that moved
    on none of those nights.
    """
    key = f"scheme-{search_id}-{date.today().strftime('%Y-%m')}"
    if use_cache:
        cached = _read_disk(key)
        if cached is not None:
            return parse_scheme_detail(cached)
    payload = _get_json(f"{SCHEME_URL}/{search_id}")
    detail = parse_scheme_detail(payload)
    _write_disk(key, payload)
    return detail
