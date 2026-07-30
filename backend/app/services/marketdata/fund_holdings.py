"""What a fund actually holds, from the AMC's own monthly disclosure.

There is no holdings API. mfapi has no such endpoint and Kuvera returns an empty
list, which is why `advisor/fund_overlap.py` measures correlation instead. But
"no API" is not "no data": SEBI requires every AMC to publish a monthly portfolio
spreadsheet, and those files are downloadable and machine-readable. This module
reads them.

Only AMCs whose URL pattern has actually been fetched and parsed appear in
`_AMCS`. Guessing a URL template produces 404s in production and a support
question here, so an unverified AMC is absent rather than optimistic.

Three things in these files bite, and all three are handled by looking at the
data rather than by trusting a per-AMC constant:

* The header row moves. It is found by locating the row containing "ISIN".
* Sheet layout differs -- PPFAS ships one sheet per scheme, SBI one workbook of
  many. Both are handled by reading every sheet and identifying it by the scheme
  name printed above its table.
* The "% to NAV" column is a fraction at some AMCs and a percentage at others.
  Hardcoding that per AMC is a 100x error waiting for a file-format change, so
  the scale is inferred from the column's own total and the sheet is refused if
  it matches neither shape.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import httpx

from app.services.portfolio.plan_identity import core_name

_TIMEOUT = 45
# A month-old portfolio does not change. The TTL exists to pick up a corrected
# re-upload, not because the data moves.
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_DISK_CACHE_DIR = Path(
    os.environ.get(
        "NEXTRADE_HOLDINGS_CACHE_DIR",
        Path(__file__).resolve().parent.parent.parent.parent / ".holdingscache",
    )
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

_ISIN = re.compile(r"^IN[A-Z0-9]{10}$")
_ORDINALS = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"}


class HoldingsUnavailable(Exception):
    """The AMC is not covered, or its file could not be read this month."""


@dataclass(frozen=True)
class Holding:
    isin: str
    name: str
    industry: str | None
    # Always a percentage of net assets, 0-100, whatever the file used.
    weight: float


@dataclass(frozen=True)
class SchemePortfolio:
    scheme_name: str
    as_of: date
    holdings: list[Holding]
    # Equity weight the file accounts for. Well short of 100 means cash, debt or
    # derivatives, which is information rather than a parse failure.
    covered: float


def _ordinal(day: int) -> str:
    return f"{day}{_ORDINALS.get(day, 'th')}"


def _ppfas_url(as_of: date) -> list[str]:
    stem = (
        f"PPFAS_Monthly_Portfolio_Report_{as_of.strftime('%B')}_"
        f"{as_of.day:02d}_{as_of.year}"
    )
    base = f"https://amc.ppfas.com/downloads/portfolio-disclosure/{as_of.year}/{stem}"
    # The extension flips between months with no pattern worth modelling.
    return [f"{base}.xls", f"{base}.xlsx"]


def _sbi_url(as_of: date) -> list[str]:
    stem = (
        "all-schemes-monthly-portfolio---as-on-"
        f"{_ordinal(as_of.day)}-{as_of.strftime('%B').lower()}-{as_of.year}"
    )
    return [f"https://www.sbimf.com/docs/default-source/scheme-portfolios/{stem}.xlsx"]


def _nippon_url(as_of: date) -> list[str]:
    base = "https://mf.nipponindiaim.com/InvestorServices/FactsheetsDocuments"
    # The month is abbreviated in some files and spelled out in others -- June
    # 2026 is "Jun", April 2026 is "April" -- with no rule behind it. Both are
    # offered rather than modelled, because the pattern is a habit, not a spec.
    return [
        f"{base}/NIMF-MONTHLY-PORTFOLIO-{as_of.day:02d}-{month}-{as_of:%y}.xls"
        for month in (as_of.strftime("%b"), as_of.strftime("%B"))
    ]


def _axis_url(as_of: date) -> list[str]:
    stem = f"Monthly Portfolio-{as_of.day:02d} {as_of.month:02d} {as_of:%y}"
    # 301s to transact.axismf.com; httpx is told to follow redirects.
    return [
        "https://www.axismf.com/cms/sites/default/files/Statutory/"
        + stem.replace(" ", "%20")
        + ".xlsx"
    ]


def _kotak_url(as_of: date) -> list[str]:
    base = "https://vatseelabs-s3.kotakmf.com/FAD/Portfolios"
    name = f"ConsolidatedSEBIPortfolio{as_of:%B}{as_of.year}.xlsx"
    # The folder label carries "SEBI" some months and not others, while the
    # file inside keeps its name either way. Both folders are offered rather
    # than predicted. Kotak's own disclosure page is behind a bot manager, but
    # the CDN the page links to is not, which is the only reason this works.
    return [
        f"{base}/Consolidated{token}-Portfolio-as-on-{as_of:%B}-{as_of.day},-{as_of.year}/{name}"
        for token in ("-SEBI", "")
    ]


def _icici_url(as_of: date) -> list[str]:
    base = (
        "https://www.icicipruamc.com/blob/downloads/Files/"
        "Monthly%20Portfolio%20Disclosures"
    )
    stem = f"Monthly-Portfolio-Disclosure-{as_of:%B}-{as_of.year}.zip"
    # The folder is abbreviated in some months and spelled out in others
    # (Mar, Apr, but June). The filename always spells the month out.
    return [
        f"{base}/{as_of.year}/{folder}/{stem}"
        for folder in (as_of.strftime("%b"), as_of.strftime("%B"))
    ]


# Keyed by the AMC token that appears at the start of scheme names. Only
# entries below have had a real file downloaded and parsed. An AMC whose URL
# was guessed but never fetched belongs nowhere near this dict.
_AMCS: dict[str, tuple[str, object]] = {
    "PARAG PARIKH": ("PPFAS Mutual Fund", _ppfas_url),
    "SBI": ("SBI Mutual Fund", _sbi_url),
    "NIPPON INDIA": ("Nippon India Mutual Fund", _nippon_url),
    "AXIS": ("Axis Mutual Fund", _axis_url),
    "KOTAK": ("Kotak Mahindra Mutual Fund", _kotak_url),
    "ICICI PRUDENTIAL": ("ICICI Prudential Mutual Fund", _icici_url),
}

# AMCs whose file is reachable but whose URL needs the scheme name, not just a
# date, so they cannot be served by a builder of this shape:
#   HDFC   one file per scheme, hosted under the *publication* month, and the
#          only one that needs a browser User-Agent.
#   UTI    an API call resolves an internal two-letter code first (017 -> "MR"),
#          and the code is not derivable from anything else.
#   Mirae  one file per scheme keyed on a lowercase internal code ("mafcf").
#   ABSL   one combined zip, but the filename changed in all six consecutive
#          months checked, so it needs the page scraped, not a template.
# All four are verified reachable and recorded; none is guessed at here.


def covered_amcs() -> dict[str, str]:
    """AMC token -> display name, for saying out loud what is and is not covered."""
    return {token: label for token, (label, _) in _AMCS.items()}


def _amc_for(scheme_name: str) -> str | None:
    upper = core_name(scheme_name)
    for token in _AMCS:
        if upper.startswith(token):
            return token
    return None


def _match_key(name: str) -> str:
    """A scheme key that survives the AMC and AMFI spelling the same fund apart.

    AMFI files "SBI Small Cap Fund"; SBI's own workbook says "SBI SmallCap
    Fund". Same for Midcap and Flexicap, and "&" against "and". Dropping every
    non-alphanumeric character collapses all of those at once, which beats a
    list of known variants (it goes stale) and beats fuzzy matching (it can
    confidently return the wrong fund).

    Collisions are still possible in principle, so `_parse_workbook` checks for
    them and discards both sides rather than picking one.
    """
    return re.sub(r"[^A-Z0-9]", "", core_name(name).replace("&", "AND"))


def _cache_path(key: str) -> Path:
    return _DISK_CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"


def _read_disk(key: str, now: float):
    try:
        entry = json.loads(_cache_path(key).read_text())
        if now - entry["fetched_at"] < _CACHE_TTL_SECONDS:
            return entry["payload"]
    except (OSError, ValueError, KeyError):
        return None
    return None


def _write_disk(key: str, payload, now: float) -> None:
    try:
        _DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = _cache_path(key)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": now, "payload": payload}))
        tmp.replace(target)
    except (OSError, TypeError):
        pass


def clear_cache() -> None:
    if _DISK_CACHE_DIR.exists():
        for entry in _DISK_CACHE_DIR.glob("*.json"):
            entry.unlink(missing_ok=True)


def _download(urls: list[str]) -> bytes:
    last = ""
    for url in urls:
        try:
            response = httpx.get(
                url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network
            last = str(exc)
            continue
        if response.status_code == 200 and response.content:
            return response.content
        last = f"HTTP {response.status_code}"
    raise HoldingsUnavailable(f"could not download the disclosure ({last})")


def _open_workbook(blob: bytes):
    """Read the workbook whatever the extension claimed.

    Some AMCs name an XLSX file `.xls`. Trying both engines is cheaper than
    trusting the name, and the failure mode of trusting it is an exception at
    request time rather than at review time.
    """
    import pandas as pd

    errors = []
    for engine in ("openpyxl", "xlrd"):
        try:
            return pd.ExcelFile(BytesIO(blob), engine=engine)
        except Exception as exc:  # noqa: BLE001 - engines raise many types
            errors.append(f"{engine}: {exc}")
    raise HoldingsUnavailable("unreadable workbook (" + "; ".join(errors) + ")")


def _norm(value) -> str:
    """Upper-case with all whitespace collapsed.

    Header cells in these files carry embedded newlines from the AMC's own
    formatting -- the weight column is literally "% to Net\\n Assets" and the
    value column "Market/Fair Value\\n (Rs. in Lakhs)". Matching on the raw
    string finds neither, which is how the first version of this parser read
    every sheet and returned nothing.
    """
    return " ".join(str(value).upper().split())


def _header_row(frame) -> int | None:
    """Index of the row holding the column names, found via the ISIN cell.

    Matched as a prefix, not for equality: the column is "ISIN" at most AMCs but
    "ISIN Code" at Kotak, and an equality test silently found no header at all
    there, which reads downstream as "this workbook has no portfolios in it".
    """
    for index in range(min(len(frame), 30)):
        cells = [_norm(value) for value in frame.iloc[index].tolist()]
        if any(cell.startswith("ISIN") for cell in cells):
            return index
    return None


def _column(cells: list[str], *wanted: str) -> int | None:
    for index, cell in enumerate(cells):
        for token in wanted:
            if token in cell:
                return index
    return None


def _normalise_weights(raw: list[float]) -> list[float] | None:
    """Put the weight column on a 0-100 scale, or refuse.

    A holdings column should total roughly one whole portfolio. If it totals
    near 1 the file used fractions; near 100, percentages. Anything else is a
    column we have misread, and returning it would silently scale every overlap
    number by 100.
    """
    total = sum(raw)
    if 0.5 <= total <= 1.5:
        return [value * 100.0 for value in raw]
    if 50.0 <= total <= 150.0:
        return list(raw)
    return None


def _scheme_name(frame, header: int) -> str | None:
    """The scheme this sheet belongs to, printed above its table, never in it.

    Two layouts. SBI labels it -- a "SCHEME NAME :" cell with the name in the
    next cell along. PPFAS just prints it as the sheet's first line.

    The labelled form is tried first because the fallback is not safe on its
    own: picking the longest line containing "fund" picks the AMC's own
    letterhead, "SBI Mutual Fund" (15 characters), over a genuinely short
    scheme name like "SBI MNC Fund" (12). So the letterhead is excluded from the
    fallback, and a sheet that yields neither is skipped rather than guessed at.
    """
    for index in range(header):
        row = frame.iloc[index].tolist()
        for position, value in enumerate(row):
            if "SCHEME NAME" in _norm(value):
                for candidate in row[position + 1 :]:
                    text = str(candidate).strip()
                    if text and text.lower() != "nan":
                        return text.split("(")[0].strip()

    best = ""
    for index in range(header):
        for value in frame.iloc[index].tolist():
            text = str(value).strip()
            normalised = _norm(text)
            if "FUND" not in normalised or normalised.endswith("MUTUAL FUND"):
                continue
            if len(text) > len(best):
                best = text
    return _strip_title_wrapper(best.split("(")[0].strip()) or None


# Kotak prints "Portfolio of Kotak Flexicap Fund as on 30 Jun 2026" rather than
# the bare name. Left whole, the date becomes part of the scheme key and the
# fund can never be matched -- and the key changes every month.
_TITLE_WRAPPER = (
    re.compile(r"^\s*portfolio\s+(?:of|for)\s+", re.I),
    re.compile(r"\s+as\s+(?:on|at|of)\b.*$", re.I),
)


def _strip_title_wrapper(text: str) -> str:
    for pattern in _TITLE_WRAPPER:
        text = pattern.sub("", text)
    return text.strip(" -–,")


def _parse_sheet(frame) -> SchemePortfolio | None:
    """One sheet of one scheme, or None if this sheet is not a portfolio."""
    header = _header_row(frame)
    if header is None:
        return None

    cells = [_norm(value) for value in frame.iloc[header].tolist()]
    isin_at = _column(cells, "ISIN")
    name_at = _column(cells, "NAME OF THE INSTRUMENT", "INSTRUMENT")
    weight_at = _column(cells, "% TO NAV", "% OF NAV", "% TO NET ASSET", "% TO AUM")
    industry_at = _column(cells, "INDUSTRY", "RATING")
    if isin_at is None or name_at is None or weight_at is None:
        return None

    scheme_name = _scheme_name(frame, header)
    if scheme_name is None:
        return None

    rows: list[Holding] = []
    weights: list[float] = []
    for index in range(header + 1, len(frame)):
        row = frame.iloc[index].tolist()
        isin = str(row[isin_at]).strip().upper()
        if not _ISIN.match(isin):
            continue  # section headers, subtotals, blank rows
        try:
            weight = float(row[weight_at])
        except (TypeError, ValueError):
            continue
        if weight <= 0:
            continue
        industry = (
            str(row[industry_at]).strip()
            if industry_at is not None and str(row[industry_at]).strip().lower()
            not in ("nan", "")
            else None
        )
        rows.append(
            Holding(
                isin=isin,
                name=str(row[name_at]).strip(),
                industry=industry,
                weight=weight,
            )
        )
        weights.append(weight)

    if len(rows) < 5:
        return None
    scaled = _normalise_weights(weights)
    if scaled is None:
        # Refuse rather than emit a portfolio that is 100x off.
        return None

    holdings = [
        Holding(h.isin, h.name, h.industry, round(w, 4))
        for h, w in zip(rows, scaled)
    ]
    return SchemePortfolio(
        scheme_name=scheme_name,
        as_of=date.today(),
        holdings=holdings,
        covered=round(sum(h.weight for h in holdings), 2),
    )


def _frames(blob: bytes):
    """Every candidate portfolio table in a download, whatever it is packaged as.

    Three shapes in the wild and they are all the same problem once opened: one
    workbook with a sheet per scheme (PPFAS, SBI, Nippon, Axis, Kotak), or a zip
    of one workbook per scheme (ICICI's 144 files), or a single-scheme workbook.
    Yielding frames flattens all three, so the parsing below never has to know.
    """
    if blob[:2] == b"PK" and _is_zip(blob):
        with zipfile.ZipFile(BytesIO(blob)) as archive:
            for entry in archive.namelist():
                if entry.endswith("/") or not entry.lower().endswith((".xls", ".xlsx")):
                    continue
                try:
                    inner = _open_workbook(archive.read(entry))
                except HoldingsUnavailable:
                    continue
                for sheet in inner.sheet_names:
                    try:
                        yield inner.parse(sheet, header=None)
                    except Exception:  # noqa: BLE001
                        continue
        return

    book = _open_workbook(blob)
    for sheet in book.sheet_names:
        try:
            yield book.parse(sheet, header=None)
        except Exception:  # noqa: BLE001 - a bad sheet is not a bad file
            continue


def _is_zip(blob: bytes) -> bool:
    """A real archive, not an xlsx -- which is also a PK zip underneath."""
    try:
        with zipfile.ZipFile(BytesIO(blob)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return False
    # An xlsx always carries this; a zip of spreadsheets does not.
    return "[Content_Types].xml" not in names


def _parse_workbook(blob: bytes, as_of: date) -> dict[str, SchemePortfolio]:
    out: dict[str, SchemePortfolio] = {}
    collided: set[str] = set()
    for frame in _frames(blob):
        parsed = _parse_sheet(frame)
        if parsed is None:
            continue
        key = _match_key(parsed.scheme_name)
        if key in out:
            # Two sheets claiming the same scheme. One of them is a plan, a
            # segregated portfolio or a naming clash, and we cannot tell which
            # is wanted, so neither is offered.
            collided.add(key)
            continue
        out[key] = SchemePortfolio(
            scheme_name=parsed.scheme_name,
            as_of=as_of,
            holdings=parsed.holdings,
            covered=parsed.covered,
        )
    for key in collided:
        out.pop(key, None)
    if not out:
        raise HoldingsUnavailable("no scheme portfolio found in the workbook")
    return out


def _month_ends(count: int = 4) -> list[date]:
    """Recent month-ends, newest first. The current month is not published yet."""
    today = date.today()
    year, month = today.year, today.month
    out: list[date] = []
    for _ in range(count):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        # Last day of that month: back one day from the first of the next.
        nxt_y, nxt_m = (year + 1, 1) if month == 12 else (year, month + 1)
        out.append(date(nxt_y, nxt_m, 1) - timedelta(days=1))
    return out


def portfolio_for(scheme_name: str) -> SchemePortfolio:
    """The latest published holdings for a scheme, by its AMFI name.

    Raises HoldingsUnavailable with a reason a user can read -- the AMC is not
    covered, or its file for every recent month was unreachable.
    """
    token = _amc_for(scheme_name)
    if token is None:
        raise HoldingsUnavailable(
            f"{scheme_name.split()[0]} does not publish in a format we read yet"
        )
    _, builder = _AMCS[token]
    wanted = _match_key(scheme_name)

    now = time.time()
    problems: list[str] = []
    for as_of in _month_ends():
        key = f"{token}|{as_of.isoformat()}"
        cached = _read_disk(key, now)
        if cached is None:
            try:
                blob = _download(builder(as_of))
                parsed = _parse_workbook(blob, as_of)
            except HoldingsUnavailable as exc:
                problems.append(f"{as_of.isoformat()}: {exc}")
                continue
            cached = {
                name: {
                    "scheme_name": p.scheme_name,
                    "covered": p.covered,
                    "holdings": [
                        [h.isin, h.name, h.industry, h.weight] for h in p.holdings
                    ],
                }
                for name, p in parsed.items()
            }
            _write_disk(key, cached, now)

        if wanted in cached:
            entry = cached[wanted]
            return SchemePortfolio(
                scheme_name=entry["scheme_name"],
                as_of=as_of,
                holdings=[
                    Holding(isin, name, industry, weight)
                    for isin, name, industry, weight in entry["holdings"]
                ],
                covered=entry["covered"],
            )
        problems.append(f"{as_of.isoformat()}: scheme not in the workbook")

    raise HoldingsUnavailable("; ".join(problems[:3]))


def common_weight(a: SchemePortfolio, b: SchemePortfolio) -> float:
    """Percentage of net assets the two funds hold in the same securities.

    The overlapping-weight measure: for each shared ISIN, the smaller of the two
    weights. Two funds each holding 8% HDFC Bank share 8%; if one holds 8% and
    the other 3%, they share 3%, because only 3% is doubled up.

    Matched on ISIN, never on name -- AMCs spell the same company differently
    ("HDFC Bank Limited" against "HDFC Bank Ltd."), and a name match would
    under-report overlap in exactly the cases that matter.
    """
    theirs = {h.isin: h.weight for h in b.holdings}
    return round(
        sum(min(h.weight, theirs[h.isin]) for h in a.holdings if h.isin in theirs), 2
    )
