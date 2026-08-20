"""Wire shapes for the fund screener.

UNITS. Every `returns_*`, `rolling_*`, `volatility`, `max_drawdown` and
`worst_30d` here is a **fraction**: 0.126 means 12.6%. The frontend's
`formatPercent()` takes a fraction and does the multiply itself, and handing it
a percent renders "+1260.0%" -- a mistake this codebase has made four times.
`sortino` is a bare ratio. `fund_score`, `momentum_signal`, `drawdown_signal`
and `risk_score` are 0-1.

`ConfigDict(from_attributes=True)` appears only on leaves that really are
validated straight from a dataclass. `TopFundsOut` and friends are assembled by
keyword and deliberately do not carry it.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class FundReasonOut(BaseModel):
    """One "why this fund" bullet.

    There is no `rank` field and there must not be one. The rule is that a fund
    speaks only when it is genuinely near the top of its peer group, and that
    the rank itself is never printed -- only the value. Keeping the rank off the
    wire is the strongest available enforcement: a future template cannot render
    what it never receives.
    """

    kind: str
    label: str
    value: float
    unit: str
    peer_group: str
    text: str

    model_config = ConfigDict(from_attributes=True)


class ScreenedFundOut(BaseModel):
    """One fund as the table renders it."""

    scheme_code: str
    name: str
    fund_house: str
    category: str
    sub_category: str | None
    asset_class: str

    rank: int
    category_rank: int

    fund_score: float
    grade: str | None
    peer_median: float | None
    peer_size: int | None

    returns_1m: float | None
    returns_3m: float | None
    returns_6m: float | None
    returns_1y: float | None
    returns_3y: float | None

    rolling_1m: float | None
    rolling_3m: float | None
    rolling_6m: float | None
    rolling_1y: float | None
    rolling_3y: float | None

    sortino: float | None
    volatility: float | None
    max_drawdown: float | None
    worst_30d: float | None

    # Named `_signal` on purpose. `drawdown_signal` is a 0-1 measure of the last
    # fortnight's downward pressure, higher being worse; `max_drawdown` is the
    # worst peak-to-trough fall, a negative fraction. Two utterly different
    # numbers whose obvious names differ by one word, which is a collision the
    # reference has and we are not inheriting.
    momentum_signal: float | None
    drawdown_signal: float | None

    risk_score: float | None
    risk_tier: str | None

    history_years: float | None
    nav_rows: int | None
    is_new: bool

    reasons: list[FundReasonOut] = []

    model_config = ConfigDict(from_attributes=True)


class ThinCategoryOut(BaseModel):
    category: str
    sub_category: str | None
    peer_size: int

    model_config = ConfigDict(from_attributes=True)


class UnscorableFundOut(BaseModel):
    scheme_code: str
    reason: str


class ScreenerCoverageOut(BaseModel):
    """What the screen is and is not showing, beside every result.

    `as_of` and `stale_days` are not optional. A nightly precompute that quietly
    goes stale returns 200 with old numbers and nothing catches it.
    """

    universe: int
    scored: int
    shown: int
    new_funds: int
    categories_total: int
    categories_ranked: int
    thin_categories: list[ThinCategoryOut]
    unscorable: list[UnscorableFundOut]
    missing_columns: list[str]
    as_of: date | None
    stale_days: int


class DominanceOut(BaseModel):
    asset_class: str
    sub_category: str
    count: int
    of: int
    share: float
    # Below 2.0 a "boom" is just the sub-category being large; see serve.py.
    lift: float

    model_config = ConfigDict(from_attributes=True)


class CategoryGroupOut(BaseModel):
    category: str
    sub_category: str | None
    asset_class: str
    peer_size: int
    caveat: str | None
    funds: list[ScreenedFundOut]


class TopFundsOut(BaseModel):
    groups: list[CategoryGroupOut]
    new_funds: list[ScreenedFundOut]
    dominance: list[DominanceOut]
    coverage: ScreenerCoverageOut


class FundUniverseOut(BaseModel):
    funds: list[ScreenedFundOut]
    new_funds: list[ScreenedFundOut]
    coverage: ScreenerCoverageOut


class CategoryOut(BaseModel):
    category: str
    sub_category: str | None
    asset_class: str
    peer_size: int
    rankable: bool
    caveat: str | None


class CategoryCoverageOut(BaseModel):
    categories: list[CategoryOut]
    asset_classes: list[str]
    grades: list[str]
    risk_tiers: list[str]
    coverage: ScreenerCoverageOut
