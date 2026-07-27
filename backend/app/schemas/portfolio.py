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

    model_config = ConfigDict(from_attributes=True)


class OverlapOut(BaseModel):
    """Whether the funds someone holds are actually different from each other.

    Correlation of monthly returns rather than shared holdings: no holdings
    feed exists for Indian funds, and moving together is what shared holdings
    are a proxy for anyway.
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
