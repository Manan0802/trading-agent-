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


# ── Stocks ───────────────────────────────────────────────────────────────────


class StockFactorOut(BaseModel):
    """One of the ten scoring factors, as the expanded row renders it.

    `max` is the factor's weight -- the port calls it that and the name is kept
    so the wire shape and the source agree. `pct` is `score / max`, precomputed
    upstream; it is what a bar in the UI is drawn from.
    """

    key: str
    label: str
    category: str
    max: float
    score: float
    pct: float
    detail: str


class StockAdjustmentOut(BaseModel):
    """A bonus or penalty applied on top of the ten factors.

    `points` can be zero: several of these are informational rows upstream
    pushes in purely so the UI has something to render, and a zero-point row is
    not a scoring event. The screen should show the detail and not the number.
    """

    key: str
    label: str
    points: float
    detail: str
    type: str


class ScoredStockOut(BaseModel):
    ticker: str
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    # 0-100, unlike the fund score which is 0-1. Different model, different
    # scale, and pretending otherwise would invite a comparison that means
    # nothing.
    total: float
    bucket: str
    # The two halves of the score, as upstream splits them. Worth showing
    # separately: the disclosure says how much of the total is momentum, and a
    # reader should be able to see it rather than take it on trust.
    fundamental: float
    technical: float
    price: float | None
    factors: list[StockFactorOut]
    adjustments: list[StockAdjustmentOut]
    # True when the long-window indicators fell back to stubs: the stock has a
    # real RSI and MACD but no 200-day average, so its trend factor is measured
    # against a shorter history than every other stock's.
    thin_history: bool
    # Which peer group the valuation factors actually compared against, and how
    # many companies are in it. Upstream silently uses a default for an unmapped
    # sector and never says so.
    benchmark_sector: str
    benchmark_constituents: int

    model_config = ConfigDict(from_attributes=True)


class UnscorableStockOut(BaseModel):
    ticker: str
    symbol: str
    name: str
    reason: str

    model_config = ConfigDict(from_attributes=True)


class StockCoverageOut(BaseModel):
    index: str
    matched: int
    scored: int
    unscorable: list[UnscorableStockOut]
    thin_history: int
    # Peer medians drift with the market; "cheap versus peers" needs to say
    # when peers was measured and how many of them there were.
    benchmark_stocks: int
    # Stated on every response: delivery is 9 of the 100 points and its only
    # source refuses to serve us, so every stock scores the same neutral half.
    neutral_factors: list[str]
    # 41 of the 100 points are momentum indicators, which traa's own stock
    # scorer excludes on measured grounds. Ported faithfully and disclosed.
    method_note: str


class StockScreenOut(BaseModel):
    stocks: list[ScoredStockOut]
    buckets: list[str]
    industries: list[str]
    indices: list[str]
    coverage: StockCoverageOut


# ── Baskets ──────────────────────────────────────────────────────────────────


class BasketSlotOut(BaseModel):
    """One sleeve of a basket: which fund fills it, at what weight.

    Two weights, not one, and the difference matters. `weight` is what the
    ported method produces and what the reference would display. `weight_within_
    bounds` is what the optimiser itself agreed to, before a tactical overlay
    multiplies every weight and renormalises without re-checking the caps. On
    real data the first has come back at 16.0% against a 15% cap.
    """

    slot_key: str
    # The sleeve in plain words. The key is upstream's and carries its
    # punctuation; the optimiser's notes quote the label too, so the page and
    # its notes name the same thing.
    label: str
    scheme_code: str | None
    name: str | None
    category: str | None
    score: float | None
    weight: float | None
    weight_within_bounds: float | None
    # What the caller asked for, and what the optimiser actually enforced. They
    # differ when the per-slot maxima cannot sum to 1, at which point they are
    # silently rescaled -- four slots capped at 15% come back allowed 25%.
    cap_asked: float
    cap_applied: float
    # How many funds competed for this sleeve. "Best index fund" out of two is a
    # different claim from out of ninety.
    pool_size: int
    caveat: str | None
    reason: str | None


class BasketOut(BaseModel):
    basket_id: str
    name: str
    strategy: str
    regime: str
    slots: list[BasketSlotOut]
    # Sleeves that found a fund, and sleeves that actually got money. They
    # differ: MAXX fills all five and allocates one of them 0.0%, so "5 of 5
    # filled" over a table containing an empty sleeve is true and misleading at
    # the same time.
    filled: int
    allocated: int
    success: bool
    as_of: date | None
    # Anything the ported optimiser did that a reader would not otherwise be
    # told: a rewritten cap, a breached cap, a basket too small to build.
    notes: list[str]
    # Standing disclosures, on every response rather than in a footnote.
    method_notes: list[str]


class BasketListOut(BaseModel):
    baskets: list[BasketOut]
