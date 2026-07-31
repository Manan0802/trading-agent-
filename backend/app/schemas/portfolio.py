from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HoldingCreate(BaseModel):
    name: str
    asset_type: Literal["MF", "STOCK"]
    # AMFI scheme code for a fund, yfinance ticker (e.g. RELIANCE.NS) for a stock.
    identifier: str
    category: str | None = None


class TransactionCreate(BaseModel):
    txn_date: date
    txn_type: Literal["BUY", "SELL"]
    units: float = Field(gt=0)
    price: float = Field(gt=0)


class TransactionOut(BaseModel):
    id: str
    txn_date: date
    txn_type: str
    units: float
    price: float
    amount: float

    model_config = ConfigDict(from_attributes=True)


class HoldingOut(BaseModel):
    id: str
    name: str
    asset_type: str
    identifier: str
    category: str | None
    transactions: list[TransactionOut]
    # Set ONLY when AMFI's name for this scheme code is a different fund from
    # the one `name` says. Non-null means every figure on this holding is
    # correct and correct about something else. Null is the normal case.
    misnamed_as: str | None = None

    model_config = ConfigDict(from_attributes=True)


class HoldingSummaryOut(BaseModel):
    holding_id: str
    name: str
    asset_type: str
    identifier: str
    category: str | None
    units_held: float
    invested: float
    current_price: float | None
    current_value: float | None
    # See HoldingOut.misnamed_as. Repeated here because this is the shape the
    # portfolio page actually renders, and a warning nobody sees is not one.
    misnamed_as: str | None = None
    # The date the price above is actually from. Shown so a frozen NAV cannot
    # masquerade as today's value.
    price_as_of: date | None = None
    # Days behind the rest of this portfolio. Set only when it is far enough
    # behind to mean the feed stopped rather than the market was shut.
    stale_days: int | None = None
    unrealised_gain: float | None
    realised_gain: float
    absolute_return: float | None
    xirr: float | None
    price_error: str | None

    # Reads the valuation dataclass directly, computed properties included.
    model_config = ConfigDict(from_attributes=True)


class BenchmarkComparisonOut(BaseModel):
    comparable: bool
    portfolio_value: float
    benchmark_value: float | None
    portfolio_xirr: float | None
    benchmark_xirr: float | None
    outperformance: float | None
    reason: str | None

    model_config = ConfigDict(from_attributes=True)


class PortfolioSummaryOut(BaseModel):
    holdings: list[HoldingSummaryOut]
    total_invested: float
    total_current_value: float
    total_unrealised_gain: float
    total_realised_gain: float
    absolute_return: float
    xirr: float | None
    unpriced_invested: float
    has_pricing_errors: bool

    model_config = ConfigDict(from_attributes=True)


class FlaggedHoldingOut(BaseModel):
    name: str
    value: float
    ter_gap: float
    annual_cost: float
    # The scheme to buy instead, when we can name it with confidence. Without
    # this "switch to the direct plan" is a sentiment, and the user is left in
    # a broker's search box guessing which of eleven similar names is the pair.
    direct_code: str | None = None
    direct_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CostReviewOut(BaseModel):
    """What the regular-plan holdings in a portfolio cost their owner."""

    annual_cost: float
    lifetime_cost: float
    flagged: list[FlaggedHoldingOut]
    # Regular plans AMFI publishes no direct-plan TER for, so the cost is
    # unknown rather than averaged.
    unpriced: list[str]
    summary: str

    model_config = ConfigDict(from_attributes=True)


class LeverOut(BaseModel):
    key: str
    title: str
    annual_value: float
    lifetime_value: float
    detail: str
    action: str

    model_config = ConfigDict(from_attributes=True)


class LeversOut(BaseModel):
    """Which decisions are worth money to this user, biggest first."""

    levers: list[LeverOut]
    years_remaining: float
    portfolio_value: float


class OverlapPairOut(BaseModel):
    a: str
    b: str
    a_name: str
    b_name: str
    correlation: float
    months: int
    # Share of net assets in the same securities, matched on ISIN. None means
    # unmeasured -- one of the two AMCs does not publish a file we read yet --
    # and the UI must not render it as zero.
    common_weight: float | None = None
    shared_securities: int | None = None

    model_config = ConfigDict(from_attributes=True)


class OverlapOut(BaseModel):
    """Whether the funds someone holds are actually different from each other.

    Correlation of monthly returns leads, because moving together is what
    shared holdings are a proxy for, and two funds can hold different stocks
    and still be one bet. Real holdings overlap rides alongside it wherever the
    AMC publishes a monthly portfolio we can parse -- it answers the second
    half, whether a correlated pair is the same exposure or the same shares.
    """

    pairs: list[OverlapPairOut]
    # Roughly how many genuinely separate bets the holdings amount to. Four
    # funds that all move together are one.
    effective_positions: float | None
    counted: int
    # Funds left out, by name, with the reason. Never dropped silently.
    excluded: dict[str, str]
    summary: str

    model_config = ConfigDict(from_attributes=True)


class HistoryPointOut(BaseModel):
    date: date
    invested: float
    portfolio_value: float
    benchmark_value: float | None

    model_config = ConfigDict(from_attributes=True)


class PortfolioHistoryOut(BaseModel):
    """The line, and everything the line does not cover.

    Previously a bare list of points, which left nowhere to say what had been
    left out -- so a portfolio with a stock drew a chart 29% below the total
    printed directly above it, with nothing anywhere explaining the gap.
    """

    points: list["HistoryPointOut"]
    # Holding name -> why it is not in the line. Never silent.
    excluded: dict[str, str] = {}
    # What those holdings are worth today, so the gap between this chart and
    # the headline total is a stated number rather than something to notice.
    excluded_value: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class AnnouncementOut(BaseModel):
    symbol: str
    company: str
    category: str
    summary: str
    published: date
    attachment: str | None

    model_config = ConfigDict(from_attributes=True)


class AnnouncementsOut(BaseModel):
    """Filings about things the user owns, not a news feed.

    The dropped count is sent because the filter is the whole point: NSE
    publishes around a hundred announcements per large company per half-year,
    and a screen showing four of them should be able to say what happened to
    the other ninety-six.
    """

    announcements: list[AnnouncementOut]
    # Material filings held back only by the display cap, so the page never
    # implies the list is everything.
    withheld: int
    # Routine filings dropped as noise: conference calls, newspaper copies.
    filtered_out: int
    # Holdings we could not check at all, by name, with the reason. A fund is
    # in here permanently: exchange filings are per company and AMC addenda
    # have no feed.
    not_covered: dict[str, str]
