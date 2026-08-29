from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.screener import BaseRateOut


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
    # Holdings priced from a frozen NAV, by name, with the reason. Present on
    # every view built from portfolio value, so a figure that gets acted on
    # cannot be computed from a dead scheme in silence.
    stale: dict[str, str] = {}

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
    # Holdings priced from a frozen NAV, by name, with the reason. Present on
    # every view built from portfolio value, so a figure that gets acted on
    # cannot be computed from a dead scheme in silence.
    stale: dict[str, str] = {}
    summary: str

    model_config = ConfigDict(from_attributes=True)


class TrackRecordOut(BaseModel):
    """How often a claim of this kind has actually been right.

    The thing no Indian investing app publishes about itself. Univest comes
    closest, printing "Price moved −196.70 (21.23%) since then" under its
    verdict — one call marked to market, with no denominator, so you cannot
    tell whether it was typical or their worst.

    `wins` out of `windows` is that denominator, and it is required rather than
    optional for exactly that reason.
    """

    key: str
    title: str
    wins: int
    windows: int
    """0 to 1."""
    hit_rate: float
    """Percentage points of forward return a year, top quartile minus bottom."""
    spread_pp: float
    """False when the claim is no better than a coin over this sample. Shown
    rather than rounded up."""
    beats_chance: bool
    """The sentence a reader sees; the numbers above are for the layout."""
    plain: str
    measured_on: str


class LeverOut(BaseModel):
    key: str
    title: str
    annual_value: float
    lifetime_value: float
    detail: str
    action: str
    """What kind of claim this is, because they must not be read as one list.

    `certain` is arithmetic — a fee difference, a slab calculation, an
    exemption. `behaviour` is sound arithmetic whose value depends on the person
    actually doing it. `trade` buys return by taking risk and is never sorted in
    among the others. `gate` earns nothing and prevents a forced sale.
    """
    kind: str = "certain"
    """Bottom and top of the value where it turns on an assumption we cannot
    pin. Null when the figure does not move with one. `save_more` has a band
    because it scales WITH the return assumption; a cost gap does not."""
    low: float | None = None
    high: float | None = None
    """How we know, and how well. A number with no provenance is
    indistinguishable from one we made up."""
    evidence: str = ""
    """What would change this answer."""
    revisit: str = ""

    model_config = ConfigDict(from_attributes=True)


class UnpricedLeverOut(BaseModel):
    """A decision we know matters and cannot value for this person yet.

    Returned rather than omitted: a list containing only what we could compute
    reads as a complete list of what matters.
    """

    key: str
    title: str
    why: str
    what_we_need: str

    model_config = ConfigDict(from_attributes=True)


class LeversOut(BaseModel):
    """Which decisions are worth money to this user, biggest first.

    Four lists rather than one, and the separation is the point. Sorting a
    guaranteed fee saving, a bet on holding through a 40% fall, and a credit
    card at 42% into a single ranked list would present three different kinds
    of claim as though they were the same kind.
    """

    """Do these first. They earn nothing and they stop a forced sale."""
    gates: list[LeverOut] = []
    """Then these, biggest first."""
    levers: list[LeverOut]
    """Bought with risk, not free. Shown apart from the levers on purpose."""
    trades: list[LeverOut] = []
    """What we know matters and could not value, with what we would need."""
    unpriced: list[UnpricedLeverOut] = []
    # What the category holding most of this person's money has done
    # before. Null when nothing could be classified, or the category is
    # too thin for an honest base rate — never a broader one in its place.
    base_rate: BaseRateOut | None = None
    # What the figures were built on, echoed back because the value may have
    # been clamped — someone who typed 40% has to see the 16% actually used.
    assumed_return: float = 0.12
    # What the reader is allowed to move it to. Bounded on purpose: Dietvorst
    # (2018) found bounded adjustment restores reliance, while an unalterable
    # verdict (2015) gets abandoned the first time it errs. An unbounded box
    # would let someone type 40% and be told to do something absurd.
    return_bounds: list[float] = [0.04, 0.16]
    # How often the score this app ranks funds on has actually been right, and
    # — when one of its own ingredients beats it — that too.
    track_record: TrackRecordOut | None = None
    better_signal: str | None = None
    years_remaining: float
    portfolio_value: float
    # Holdings priced from a frozen NAV, by name, with the reason. Present on
    # every view built from portfolio value, so a figure that gets acted on
    # cannot be computed from a dead scheme in silence.
    stale: dict[str, str] = {}


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
    # Which month's disclosure the overlap was read from. Shown because AMCs
    # file up to ten days after month end, so this can lag by five weeks.
    holdings_as_of: date | None = None

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


class CompanyOut(BaseModel):
    """One company, and every rupee reaching it through every fund that holds it."""

    isin: str
    name: str
    industry: str | None
    value: float
    # Against the WHOLE portfolio, including the funds we could not open. See
    # LookThroughOut.covered_share for why that denominator and not the other.
    share_pct: float
    # (fund name, rupees) heaviest first. "through 4 of your funds" is the
    # sentence worth showing, and it needs the names to be believable.
    via: list[tuple[str, float]]

    model_config = ConfigDict(from_attributes=True)


class LookThroughOut(BaseModel):
    """The companies behind the funds, and how much of the portfolio was readable.

    `covered_share` is not a footnote. Holdings come from AMC monthly
    disclosures and seven AMCs have a verified source, so a real portfolio will
    routinely contain funds this cannot open. Reporting only what was read
    produces a number that looks exactly like a complete answer and is not one.
    """

    companies: list[CompanyOut]
    concentrated: list[CompanyOut]
    covered_value: float
    unopened_value: float
    # Named, so the user can see WHICH funds are missing from the picture.
    unopened: list[str]
    # 0-100. Below 100 the whole answer is partial and the screen must say so.
    covered_share: float
    summary: str

    model_config = ConfigDict(from_attributes=True)


class AlreadyOwnOut(BaseModel):
    """How much of a fund you are considering you already reach through your own.

    `share_pct` is null, never 0, when it could not be measured. 0% reads as
    perfectly diversified — the opposite of "we could not tell", and the more
    attractive of the two readings, so a silent zero encourages the purchase it
    should have questioned. §14.
    """

    scheme_code: str
    share_pct: float | None
    # (fund name, share of the candidate it reaches), heaviest first.
    through: list[tuple[str, float]]
    # Why there is no number, when there is none.
    reason: str | None = None
    summary: str

    model_config = ConfigDict(from_attributes=True)
