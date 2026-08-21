"""The parts of a fund page that are not charts: cost, holdings, and "what if".

Everything here already existed somewhere in traa and was not on a fund's own
page. This assembles it. Nothing is fetched at request time -- expense ratios
and holdings are committed data, and the calculator reads the NAV store.

**Cost is first on purpose.** Every fund page in the country shows one expense
ratio. traa has both plans for 1,195 of the 1,477 ranked funds -- 81% -- and the
gap between them is the one number this project has measured as predictive: cost
separated future winners from losers 87% of the time, while picking on past
record managed 68% with three of seven years at or below chance. The median gap
is 0.68 percentage points a year and the widest is 1.89. A fund page that buries
that under a performance chart has its priorities backwards, whatever everyone
else does.

The 19% with no entry say so rather than showing a blank: AMFI publishes TER per
AMC and the parse does not cover every one of them yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.advisor import fund_evidence
from app.services.marketdata import fund_holdings
from app.services.screener import navstore

# What the calculator offers. Anything longer than the fund's own history is
# answered with the fund's history and labelled, never silently shortened.
CALCULATOR_YEARS = (1, 3, 5, 10)

# A lump sum big enough that the rupee answer is legible and round enough that
# nobody mistakes it for advice about how much to invest.
CALCULATOR_AMOUNT = 100_000

# Holdings below this are a long tail that makes a table unreadable. The tail is
# summed into one row rather than dropped, so the weights still total 100.
TOP_HOLDINGS = 15


@dataclass(frozen=True)
class Cost:
    direct_ter: float | None
    regular_ter: float | None
    # What the direct plan saves, in percentage points a year. The whole reason
    # both numbers are kept.
    saving_pct_per_year: float | None
    as_of: str | None
    # Ten years of that saving on a lump sum, compounded. A 1.03pp gap sounds
    # like nothing until it is a rupee figure.
    saving_on_a_lakh_over_10y: float | None


@dataclass(frozen=True)
class HoldingOut:
    isin: str | None
    name: str
    industry: str | None
    weight: float


@dataclass(frozen=True)
class Holdings:
    as_of: str | None
    total_positions: int
    top: list[HoldingOut]
    other_weight: float
    by_industry: list[tuple[str, float]]
    covered: bool


@dataclass(frozen=True)
class CalculatorRow:
    years: int
    invested: float
    value: float | None
    # None when the fund is younger than the period. The row still appears, so
    # a short record is visible rather than absent.
    actual_years: float | None
    annualised: float | None
    # False when the fund is younger than the period asked for, so this row and
    # a longer one hold the same number. Without it, a 2.9-year-old fund shows
    # the same rupee figure for 3, 5 and 10 years and reads as a broken table.
    full_period: bool


def cost_for(scheme_code: str) -> Cost:
    """Both plans' expense ratios, and what the gap is worth."""
    # traa's existing loader, not a second copy of it. It already caches the
    # file and it is what `fund_verdict` reads, so the fund page and the verdict
    # can never quote different expense ratios for the same fund.
    row = fund_evidence.expense_ratios().get(str(scheme_code))
    if not row:
        return Cost(None, None, None, None, None)

    direct, regular = row.get("direct_ter"), row.get("regular_ter")
    saving = None
    if direct is not None and regular is not None:
        saving = round(float(regular) - float(direct), 4)

    # Compounded, not multiplied. A percentage point a year is not ten
    # percentage points over ten years, and quoting it that way would be the
    # same overstatement this project keeps catching elsewhere.
    over_ten = None
    if saving is not None and saving > 0:
        over_ten = round(CALCULATOR_AMOUNT * ((1 + saving / 100) ** 10 - 1), 2)

    return Cost(
        direct_ter=direct,
        regular_ter=regular,
        saving_pct_per_year=saving,
        as_of=row.get("as_of"),
        saving_on_a_lakh_over_10y=over_ten,
    )


def holdings_for(fund_name: str) -> Holdings:
    """What the fund actually owns, for the seven AMCs that publish it.

    Not a gap worth hiding: the other AMCs do publish monthly portfolios, they
    are simply not parsed yet, and `covered` says which case a reader is in.
    """
    # It raises rather than returning None for an AMC it cannot parse, which is
    # the right shape for a caller that wants to know -- here the answer is a
    # `covered=False` record, because a fund page should say "we do not have
    # this AMC's portfolio" rather than fail.
    try:
        portfolio = fund_holdings.portfolio_for(fund_name)
    except fund_holdings.HoldingsUnavailable:
        portfolio = None
    if portfolio is None or not portfolio.holdings:
        return Holdings(None, 0, [], 0.0, [], covered=False)

    rows = sorted(portfolio.holdings, key=lambda h: -(h.weight or 0.0))
    top = [
        HoldingOut(h.isin, h.name, h.industry, round(float(h.weight or 0.0), 4))
        for h in rows[:TOP_HOLDINGS]
    ]
    other = round(sum(float(h.weight or 0.0) for h in rows[TOP_HOLDINGS:]), 4)

    industries: dict[str, float] = {}
    for h in rows:
        key = h.industry or "Not classified"
        industries[key] = industries.get(key, 0.0) + float(h.weight or 0.0)

    return Holdings(
        as_of=str(portfolio.as_of) if portfolio.as_of else None,
        total_positions=len(rows),
        top=top,
        other_weight=other,
        by_industry=sorted(
            ((k, round(v, 4)) for k, v in industries.items()), key=lambda kv: -kv[1]
        )[:12],
        covered=True,
    )


def calculator(session, scheme_code: str, as_of: date) -> list[CalculatorRow]:
    """What a lakh invested N years ago would be worth today.

    The single most-used thing on a fund page anywhere, and it is a NAV lookup:
    units bought then, valued now. A fund younger than the period is answered
    with the period it has, and `actual_years` says so -- the alternative is a
    blank row, which reads as a data problem rather than a young fund.
    """
    navs = navstore.nav_window(session, scheme_code)
    if len(navs) < 2:
        return [
            CalculatorRow(y, float(CALCULATOR_AMOUNT), None, None, None, False)
            for y in CALCULATOR_YEARS
        ]

    latest_date, latest_nav = navs[-1]
    rows: list[CalculatorRow] = []
    for years in CALCULATOR_YEARS:
        target = date(latest_date.year - years, latest_date.month, min(latest_date.day, 28))
        entry = next((p for p in navs if p[0] >= target), None) or navs[0]
        entry_date, entry_nav = entry
        if entry_nav <= 0 or entry_date >= latest_date:
            rows.append(
                CalculatorRow(years, float(CALCULATOR_AMOUNT), None, None, None, False)
            )
            continue

        units = CALCULATOR_AMOUNT / entry_nav
        value = units * latest_nav
        actual = (latest_date - entry_date).days / 365.25
        # A tolerance, not `>= 1`. A one-year row lands on 364 days when the
        # entry date falls on a holiday, `364/365.25` is 0.9986, and the row
        # rendered "1.0 years" beside a blank annualised figure -- which reads
        # as a bug rather than as arithmetic.
        annualised = (
            round((value / CALCULATOR_AMOUNT) ** (1 / actual) - 1, 6)
            if actual >= 0.95
            else None
        )
        rows.append(
            CalculatorRow(
                years=years,
                invested=float(CALCULATOR_AMOUNT),
                value=round(value, 2),
                actual_years=round(actual, 2),
                annualised=annualised,
                full_period=actual >= years - 0.05,
            )
        )
    return rows


def rank_at_horizons(target, peers: list) -> dict[str, dict]:
    """Where the fund sits among its peers on each return horizon.

    Groww shows this and it is the most directly useful number on their page:
    "rank 22 of 47 over three years" answers a question a percentage cannot.
    Only funds that actually have a number for that horizon are counted, so a
    rank is never inflated by peers with no data.
    """
    out: dict[str, dict] = {}
    for field, label in (
        ("returns_1y", "1Y"), ("returns_3y", "3Y"),
        ("rolling_1y", "1Y rolling"), ("returns_3m", "3M"),
    ):
        mine = getattr(target, field, None)
        if mine is None:
            continue
        values = [
            v for p in peers
            if (v := getattr(p, field, None)) is not None
        ]
        if len(values) < 2:
            continue
        better = sum(1 for v in values if v > mine)
        out[label] = {"rank": better + 1, "of": len(values), "value": mine}
    return out
