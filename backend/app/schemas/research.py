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
