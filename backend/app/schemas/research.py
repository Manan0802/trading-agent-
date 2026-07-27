from datetime import date

from pydantic import BaseModel, ConfigDict


class FundSearchResultOut(BaseModel):
    scheme_code: str
    scheme_name: str

    model_config = ConfigDict(from_attributes=True)


class FundMetricsOut(BaseModel):
    cagr_1y: float | None
    cagr_3y: float | None
    cagr_5y: float | None
    volatility: float | None
    sortino: float | None
    max_drawdown: float | None
    alpha: float | None
    downside_capture: float | None
    consistency: float | None

    model_config = ConfigDict(from_attributes=True)


class NavPointOut(BaseModel):
    date: date
    nav: float

    model_config = ConfigDict(from_attributes=True)


class FundDetailOut(BaseModel):
    scheme_code: str
    scheme_name: str
    fund_house: str
    category: str
    is_direct_growth: bool
    latest_nav: float
    latest_nav_date: date
    metrics: FundMetricsOut
    nav_series: list[NavPointOut]


class RankedFundOut(BaseModel):
    scheme_code: str
    scheme_name: str
    category: str
    score: float
    breakdown: dict[str, float]
    metrics: FundMetricsOut

    model_config = ConfigDict(from_attributes=True)


class UnscorableFundOut(BaseModel):
    scheme_code: str
    scheme_name: str
    reason: str

    model_config = ConfigDict(from_attributes=True)


class CategoryRankingOut(BaseModel):
    asset_class: str
    benchmarked: bool
    # Named, and its limits stated, so an alpha figure is never read bare.
    benchmark_name: str | None
    benchmark_caveat: str | None
    ranked: list[RankedFundOut]
    unscorable: list[UnscorableFundOut]


class StockFundamentalsOut(BaseModel):
    ticker: str
    name: str
    price: float
    previous_close: float | None
    currency: str
    day_change_pct: float | None
    sector: str | None
    industry: str | None
    market_cap: float | None
    pe_ratio: float | None
    eps: float | None
    book_value: float | None
    dividend_yield_pct: float | None
    week52_high: float | None
    week52_low: float | None

    model_config = ConfigDict(from_attributes=True)


class UniverseStockOut(BaseModel):
    ticker: str
    symbol: str
    name: str
    industry: str | None
    indices: list[str]

    model_config = ConfigDict(from_attributes=True)


class StockUniverseOut(BaseModel):
    stocks: list[UniverseStockOut]
    # Total before the limit was applied, so the UI can say "showing 50 of 500"
    # rather than implying the list is complete.
    total: int
    available_indices: list[str]
    available_industries: list[str]


class WindowOut(BaseModel):
    """One rolling-window length, summarised over every overlapping window."""

    mean: float
    worst: float
    share_positive: float
    count: int

    model_config = ConfigDict(from_attributes=True)


class VerdictOut(BaseModel):
    headline: str
    points: list[str]
    caveat: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RankedFundV2Out(BaseModel):
    rank: int
    scheme_code: str
    scheme_name: str
    category: str
    score: float
    breakdown: dict[str, float]
    # How far the record can be trusted to describe more than one market, 0-1.
    evidence_strength: float
    history_years: float | None
    windows: dict[str, WindowOut]
    volatility: float | None
    max_drawdown: float | None
    direct_ter: float | None
    regular_ter: float | None
    verdict: VerdictOut


class CategoryRankingV2Out(BaseModel):
    category: str
    ranked: list[RankedFundV2Out]
    unscorable: list[UnscorableFundOut]
    # How many funds we can price the direct-vs-regular gap for.
    priced: int


class FactorOut(BaseModel):
    score: float
    detail: str

    model_config = ConfigDict(from_attributes=True)


class AdjustmentOut(BaseModel):
    name: str
    points: int
    detail: str

    model_config = ConfigDict(from_attributes=True)


class StockScoreOut(BaseModel):
    ticker: str
    name: str
    sector: str | None
    # The peer group the valuation was judged against; "_ALL" means the sector
    # had too few peers to median and the whole market stood in.
    benchmark_used: str
    base_total: float
    adjustment_total: float
    total: float
    factors: dict[str, FactorOut]
    adjustments: list[AdjustmentOut]
    range_position: float | None
    verdict: VerdictOut
