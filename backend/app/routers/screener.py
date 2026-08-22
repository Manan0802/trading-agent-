"""The fund screener: every category's leaders, on the whole direct-growth universe.

Deliberately NOT under `/api/v1/research`. That prefix is rate-limited at 20/min
because its endpoints price a whole category on demand; these read a table the
nightly job already built. A user pressing "show all", changing a filter and
expanding three rows inside a minute would 429 there, and every non-401 response
of 400 or worse is a `sweep.mjs` failure.

One exception, and it is deliberate: `/funds` returns the entire universe, about
1.2 MB uncompressed, so its exact path is added to the rate limiter's HEAVY list.
Prefix matching means `/top-funds` is untouched -- `"…/top-funds"` does not start
with `"…/funds"` -- and `tests/test_rate_limit.py` pins both, so a future edit to
`_HEAVY_PATHS` cannot silently strangle the screen.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.fastapi_users_app import current_active_user
from app.models import User
from app.schemas.screener import (
    BaseRateOut,
    CategoryCoverageOut,
    CategoryGroupOut,
    CategoryOut,
    DominanceOut,
    FundReasonOut,
    BasketListOut,
    CalculatorRowOut,
    ChartPointOut,
    FundCostOut,
    FundHoldingsOut,
    HoldingOut,
    HorizonRankOut,
    FundAnalysisOut,
    RollingReturnsOut,
    BasketOut,
    BasketSlotOut,
    FundUniverseOut,
    HorizonOut,
    RatioVsSectorOut,
    ScoredStockOut,
    SimilarStockOut,
    StockPageOut,
    StockCoverageOut,
    StockScreenOut,
    UnscorableStockOut,
    ScreenedFundOut,
    ScreenerCoverageOut,
    ThinCategoryOut,
    TopFundsOut,
    UnscorableFundOut,
)
from app.services.advisor import fund_catalogue
from app.services.marketdata import stock_universe
from app.services.screener import (
    base_rates,
    analysis,
    fund_facts,
    plain_words,
    basket_build,
    navstore,
    scoring,
    sector_benchmarks,
    serve,
    stock_analysis_page,
    stock_scoring,
    stocks,
)

router = APIRouter(prefix="/api/v1/screener", tags=["screener"])

GRADES = ("Very Good", "Good", "Avg", "Bad")
DEFAULT_PER_CATEGORY = 5
MAX_PER_CATEGORY = 25

# The full universe is large enough that echoing every unscorable fund's reason
# alongside it doubles the payload for no benefit -- the reasons matter on the
# category view, where the numbers are small enough to read.
UNSCORABLE_SHOWN = 200


def _catalogue() -> dict:
    return {f.code: f for f in fund_catalogue.all_funds()}


def _load_reasons():
    """The claim bullets for the latest run.

    Only fetched for the grouped view and for a single expanded row. The flat
    full-universe response deliberately ships without them: bullets for 1,466
    funds would roughly double a payload that is already the reason that
    endpoint sits on the heavy rate-limit tier. Fetching them per row instead
    would be 195 requests a minute against a 120/min budget, which `sweep.mjs`
    counts as a failure the moment the first 429 lands.
    """
    with navstore.session() as session:
        try:
            return serve.reasons_for_run(session)
        except serve.NoCompletedRun:
            return {}


def _load():
    """The latest accepted run, or a 503 that says how far the rebuild has got.

    Never an empty ranking behind a 200. A screen rendering zero rows with a
    success status is indistinguishable from a market where nothing qualified,
    and it is the silent failure this codebase keeps writing tests against.
    """
    with navstore.session() as session:
        try:
            return serve.build(session, _catalogue())
        except serve.NoCompletedRun as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


def _coverage_out(coverage: serve.Coverage, shown: int, limit: int) -> ScreenerCoverageOut:
    return ScreenerCoverageOut(
        universe=coverage.universe,
        scored=coverage.scored,
        shown=shown,
        new_funds=coverage.new_funds,
        categories_total=coverage.categories_total,
        categories_ranked=coverage.categories_ranked,
        thin_categories=[ThinCategoryOut.model_validate(t) for t in coverage.thin_categories],
        unscorable=[
            UnscorableFundOut(scheme_code=code, reason=reason)
            for code, reason in coverage.unscorable[:limit]
        ],
        missing_columns=coverage.missing_columns,
        as_of=coverage.as_of,
        stale_days=coverage.stale_days,
    )


def _with_reasons(fund: serve.ScreenedFund, reasons: dict) -> ScreenedFundOut:
    """Attach the bullets after validation, never by passing them in.

    `ScreenedFund` is a frozen dataclass that does not carry reasons, so adding
    the field to the constructor call would fail validation. `model_copy` after
    the fact is the house pattern for exactly this.
    """
    out = ScreenedFundOut.model_validate(fund)
    found = reasons.get(fund.scheme_code) or []
    if not found:
        return out
    return out.model_copy(
        update={"reasons": [FundReasonOut.model_validate(r) for r in found]}
    )


def _filtered(
    funds: list[serve.ScreenedFund],
    category: str | None,
    asset_class: str | None,
    grade: str | None,
    risk_tier: str | None,
) -> list[serve.ScreenedFund]:
    """Filters never renumber. `rank` is already on the row and stays put."""
    out = funds
    if category:
        out = [f for f in out if f.sub_category == category or f.category == category]
    if asset_class:
        out = [f for f in out if f.asset_class == asset_class]
    if grade:
        out = [f for f in out if f.grade == grade]
    if risk_tier:
        out = [f for f in out if f.risk_tier == risk_tier]
    return out


def _check_choice(value: str | None, allowed, what: str) -> None:
    """404 naming the valid values, rather than 422 or an empty list.

    An unknown filter returning zero rows looks exactly like a real market in
    which nothing qualified, which is the wrong thing to show someone who has
    just mistyped a category.
    """
    if value is not None and value not in allowed:
        raise HTTPException(
            status_code=404,
            detail=f"unknown {what} {value!r}. Valid values: {sorted(allowed)}",
        )


@router.get("/categories", response_model=CategoryCoverageOut)
def categories(user: User = Depends(current_active_user)) -> CategoryCoverageOut:
    """Every peer group, its size, and whether it is big enough to rank."""
    funds, _new, coverage = _load()

    sizes: dict[tuple, int] = {}
    classes: dict[tuple, str] = {}
    for f in funds:
        key = (f.category, f.sub_category)
        sizes[key] = sizes.get(key, 0) + 1
        classes[key] = f.asset_class

    out = [
        CategoryOut(
            category=category,
            sub_category=sub_category,
            asset_class=classes[(category, sub_category)],
            peer_size=size,
            rankable=size >= serve.MIN_PEERS_TO_RANK,
            caveat=serve.CAVEATED_SUB_CATEGORIES.get(sub_category or ""),
        )
        for (category, sub_category), size in sorted(sizes.items())
    ]
    return CategoryCoverageOut(
        categories=out,
        asset_classes=sorted({c.asset_class for c in out}),
        grades=list(GRADES),
        risk_tiers=list(scoring.RISK_TIERS),
        coverage=_coverage_out(coverage, shown=len(out), limit=UNSCORABLE_SHOWN),
    )


@router.get("/top-funds", response_model=TopFundsOut)
def top_funds(
    per_category: int = Query(DEFAULT_PER_CATEGORY, ge=1, le=MAX_PER_CATEGORY),
    category: str | None = None,
    asset_class: str | None = None,
    grade: str | None = None,
    risk_tier: str | None = None,
    user: User = Depends(current_active_user),
) -> TopFundsOut:
    """Every category's leaders, grouped. The default view of the screen."""
    funds, new_funds, coverage = _load()

    _check_choice(asset_class, set(serve.ASSET_CLASS_OF.values()), "asset class")
    _check_choice(grade, set(GRADES), "grade")
    _check_choice(risk_tier, set(scoring.RISK_TIERS), "risk tier")
    if category is not None:
        known = {f.sub_category for f in funds} | {f.category for f in funds}
        _check_choice(category, known - {None}, "category")

    selected = _filtered(funds, category, asset_class, grade, risk_tier)
    groups = serve.group_by_category(selected, per_category=per_category)
    shown = sum(len(g.funds) for g in groups)
    reasons = _load_reasons()

    return TopFundsOut(
        groups=[
            CategoryGroupOut(
                category=g.category,
                sub_category=g.sub_category,
                asset_class=g.asset_class,
                peer_size=g.peer_size,
                caveat=g.caveat,
                funds=[_with_reasons(f, reasons) for f in g.funds],
            )
            for g in groups
        ],
        new_funds=[ScreenedFundOut.model_validate(f) for f in new_funds],
        # Dominance is computed over the UNFILTERED universe on purpose: "9 of
        # the top 10" is a statement about the market, not about whatever the
        # user has currently narrowed the page down to.
        dominance=[DominanceOut.model_validate(d) for d in serve.dominance(funds)],
        coverage=_coverage_out(coverage, shown=shown, limit=UNSCORABLE_SHOWN),
    )


@router.get("/funds", response_model=FundUniverseOut)
def all_funds(
    category: str | None = None,
    asset_class: str | None = None,
    grade: str | None = None,
    risk_tier: str | None = None,
    include_new: bool = False,
    user: User = Depends(current_active_user),
) -> FundUniverseOut:
    """The flat, fully sortable view. Every ranked fund in one response.

    Sorting happens on the client over this whole array, which is the only way
    "lowest volatility" can mean lowest in the universe rather than lowest among
    the rows that happened to be shipped.
    """
    funds, new_funds, coverage = _load()

    _check_choice(asset_class, set(serve.ASSET_CLASS_OF.values()), "asset class")
    _check_choice(grade, set(GRADES), "grade")
    _check_choice(risk_tier, set(scoring.RISK_TIERS), "risk tier")
    if category is not None:
        known = {f.sub_category for f in funds} | {f.category for f in funds}
        _check_choice(category, known - {None}, "category")

    selected = _filtered(funds, category, asset_class, grade, risk_tier)
    return FundUniverseOut(
        funds=[ScreenedFundOut.model_validate(f) for f in selected],
        new_funds=[ScreenedFundOut.model_validate(f) for f in new_funds] if include_new else [],
        coverage=_coverage_out(coverage, shown=len(selected), limit=UNSCORABLE_SHOWN),
    )


@router.get("/funds/{scheme_code}", response_model=ScreenedFundOut)
def one_fund(
    scheme_code: str,
    user: User = Depends(current_active_user),
) -> ScreenedFundOut:
    """One fund's full record, for the expanded row."""
    funds, new_funds, _coverage = _load()
    for f in funds + new_funds:
        if f.scheme_code == scheme_code:
            return _with_reasons(f, _load_reasons())
    raise HTTPException(
        status_code=404,
        detail=f"scheme {scheme_code} is not in the latest ranking",
    )


# ── Stocks ───────────────────────────────────────────────────────────────────

DEFAULT_INDEX = "NIFTY 50"
DEFAULT_STOCK_LIMIT = 50
MAX_STOCK_LIMIT = 200

# What the screen says on every response, because the alternative is a number
# that looks like it means more than it does.
#
# The first is a fact about the exchange: NSE's quote-equity endpoint returns
# 403, so `_score_delivery` awards its neutral half to every stock, forever.
# Upstream never surfaces this and its own scores carry the same constant.
#
# The second is a decision. Forty-one of the hundred points are momentum
# indicators -- RSI, MACD, EMA trend and support -- and traa's own stock scorer
# excludes exactly those on measured grounds. The method is being reproduced
# because it is the one this screen is a port of, not because it is endorsed.
def neutral_factors() -> list[str]:
    """Which factors are not really being scored today, said out loud.

    Delivery was on this list permanently until 2026-08-21. The scorer's
    documented source returns 403, so 9 of every 100 points was the same
    constant for every company -- in the vendor's numbers too. The exchange's
    end-of-day archive was never gated, and now feeds it. The list is computed
    per request rather than hardcoded, because a factor that is live today can
    be dead tomorrow and a hardcoded sentence would keep claiming whichever
    was true when it was written.
    """
    as_of = stocks.delivery_as_of()
    if as_of is None:
        return [
            "Delivery volume (9 points) — the exchange archive could not be read, "
            "so every stock scores the same neutral half on it today.",
        ]
    return []
METHOD_NOTE = (
    "41 of these 100 points are momentum indicators. This is the industry-"
    "standard method reproduced as it is written; our own measurements do not "
    "support those factors, and the Research page ranks the same companies "
    "without them."
)


@router.get("/stocks", response_model=StockScreenOut)
def screen_stocks(
    index: str = Query(DEFAULT_INDEX),
    industry: str | None = None,
    bucket: str | None = None,
    limit: int = Query(DEFAULT_STOCK_LIMIT, ge=1, le=MAX_STOCK_LIMIT),
    user: User = Depends(current_active_user),
) -> StockScreenOut:
    """Every company in the filter, scored on the ported ten-factor model.

    Scored live rather than precomputed, matching the Research page's existing
    stock ranking: the fundamentals fetcher already caches on disk for twelve
    hours, so a cold universe is slow once and warm afterwards. The cap exists
    because a wider index on a cold cache is minutes, not seconds -- and the
    coverage line reports how many companies matched against how many were
    actually priced, so a truncated answer says so.
    """
    _check_choice(index, set(stock_universe.INDEX_CHOICES), "index")
    _check_choice(bucket, set(stock_scoring.BUCKET_LABELS), "bucket")
    known_industries = stock_universe.industries()
    _check_choice(industry, set(known_industries), "industry")

    matched = stock_universe.list_stocks(index=index, industry=industry)
    scored, unscorable = stocks.rank_entries(matched[:limit])

    if bucket:
        scored = [s for s in scored if s.bucket == bucket]

    return StockScreenOut(
        stocks=[ScoredStockOut.model_validate(s) for s in scored],
        buckets=list(stock_scoring.BUCKET_LABELS),
        industries=known_industries,
        indices=list(stock_universe.INDEX_CHOICES),
        coverage=StockCoverageOut(
            index=index,
            matched=len(matched),
            scored=len(scored),
            unscorable=[UnscorableStockOut.model_validate(u) for u in unscorable],
            thin_history=sum(1 for s in scored if s.thin_history),
            benchmark_stocks=sector_benchmarks.built_from(),
            neutral_factors=neutral_factors(),
            method_note=METHOD_NOTE,
        ),
    )


@router.get("/stocks/{ticker}", response_model=ScoredStockOut)
def one_stock(
    ticker: str,
    user: User = Depends(current_active_user),
) -> ScoredStockOut:
    """One company's full factor breakdown, for the expanded row."""
    entry = stock_universe.lookup(ticker)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not in the stock universe")
    scored, unscorable = stocks.rank_entries([entry])
    if scored:
        return ScoredStockOut.model_validate(scored[0])
    reason = unscorable[0].reason if unscorable else "could not be scored"
    raise HTTPException(status_code=404, detail=f"{ticker} could not be scored: {reason}")


# ── Baskets ──────────────────────────────────────────────────────────────────

BASKET_IDS = ("MAXX", "BALANCED")
STRATEGIES = ("conservative", "balanced", "aggressive")
REGIMES = ("bullish", "neutral", "bearish")

# Said on every basket, because all three were confirmed by running the ported
# optimiser and none of them is visible in its output.
BASKET_METHOD_NOTES = [
    "The strategy and market-view settings do not change the allocation. The "
    "loss floor they set enters the maths as a constant while the constraint is "
    "unmet, and it essentially always is, so all nine combinations return the "
    "same weights.",
    "The final weights can sit slightly above a sleeve's cap. The optimiser "
    "respects every cap, then a momentum adjustment scales the weights and "
    "renormalises without checking them again. Both numbers are shown.",
    "Minimum investment is not considered. That data comes from a distributor "
    "feed we have no equivalent of, so a sleeve may name a fund with a minimum "
    "you cannot meet.",
]


def _basket_out(result) -> BasketOut:
    return BasketOut(
        basket_id=result.basket_id,
        name=result.name,
        strategy=result.strategy,
        regime=result.regime,
        filled=result.filled,
        allocated=result.allocated,
        success=result.success,
        as_of=result.as_of,
        notes=result.notes,
        method_notes=BASKET_METHOD_NOTES,
        slots=[
            BasketSlotOut(
                slot_key=s.slot_key,
                label=s.label,
                scheme_code=s.scheme_code,
                name=s.name,
                category=s.category,
                score=s.score,
                weight=s.weight,
                weight_within_bounds=s.weight_within_bounds,
                cap_asked=s.bounds_asked[1],
                cap_applied=s.bounds_applied[1],
                pool_size=s.pool_size,
                caveat=s.caveat,
                reason=s.reason,
            )
            for s in result.slots
        ],
    )


@router.get("/baskets", response_model=BasketListOut)
def baskets(
    strategy: str | None = None,
    regime: str = "neutral",
    user: User = Depends(current_active_user),
) -> BasketListOut:
    """Every basket, built from the latest scored run."""
    _check_choice(strategy, set(STRATEGIES), "strategy")
    _check_choice(regime, set(REGIMES), "regime")
    with navstore.session() as session:
        try:
            return BasketListOut(
                baskets=[
                    _basket_out(
                        basket_build.build(
                            session, basket_id, strategy=strategy, regime=regime
                        )
                    )
                    for basket_id in BASKET_IDS
                ]
            )
        except serve.NoCompletedRun as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/baskets/{basket_id}", response_model=BasketOut)
def one_basket(
    basket_id: str,
    strategy: str | None = None,
    regime: str = "neutral",
    user: User = Depends(current_active_user),
) -> BasketOut:
    _check_choice(basket_id, set(BASKET_IDS), "basket")
    _check_choice(strategy, set(STRATEGIES), "strategy")
    _check_choice(regime, set(REGIMES), "regime")
    with navstore.session() as session:
        try:
            return _basket_out(
                basket_build.build(session, basket_id, strategy=strategy, regime=regime)
            )
        except serve.NoCompletedRun as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


def base_rate_out(joined_category: str, amount: float | None) -> BaseRateOut | None:
    """One reference class, assembled in one place.

    Both the fund page and the decision screen show this. Assembling it twice
    is how two screens start quoting different loss rates for the same
    category — the failure `scripts/consistency.py` exists to catch.
    """
    rate = base_rates.for_joined(joined_category)
    if rate is None:
        return None
    safe = rate.first_safe_horizon
    at_risk = base_rates.rupees_at_risk(rate, amount) if amount else None
    return BaseRateOut(
        category=rate.category,
        sub_category=rate.sub_category,
        funds=rate.funds,
        funds_wound_up=rate.funds_wound_up,
        horizons=[
            HorizonOut(
                key=h.key, words=h.words, windows=h.windows,
                loss_share=h.loss_share, worst=h.worst,
                p05=h.p05, median=h.median, p95=h.p95,
            )
            for h in rate.horizons
        ],
        worst_fall=rate.worst_fall,
        median_recovery_days=rate.median_recovery_days,
        worst_recovery_days=rate.worst_recovery_days,
        never_recovered=rate.never_recovered,
        first_safe_horizon=safe.key if safe else None,
        rupees_at_risk=at_risk,
        as_of=rate.as_of,
        plain={
            k: v for k, v in {
                "base_rate": plain_words.base_rate_sentence(rate),
                "worst_fall": plain_words.worst_fall_sentence(rate, amount),
                "coverage": plain_words.base_rate_coverage_sentence(rate),
            }.items() if v
        },
    )


@router.get("/funds/{scheme_code}/analysis", response_model=FundAnalysisOut)
def fund_analysis(
    scheme_code: str,
    range: str = Query(analysis.DEFAULT_RANGE),
    amount: float | None = Query(
        None, ge=0,
        description="What the reader has in this fund, so the worst historical "
                    "fall can be shown in rupees rather than as a percentage. "
                    "Omitted rather than guessed when unknown.",
    ),
    user: User = Depends(current_active_user),
) -> FundAnalysisOut:
    """One fund's charts, drawn from the local NAV store.

    No network call: five million NAV rows are on disk, so this is a read.
    Measured at 22-93ms depending on range.

    The comparison line is the fund's own category median, not an index. Judging
    a liquid fund or a gold fund against the Nifty says only that equity and
    gold are different things.
    """
    _check_choice(range, set(analysis.RANGES), "range")
    funds, new_funds, _coverage = _load()

    target = next(
        (f for f in funds + new_funds if f.scheme_code == scheme_code), None
    )
    if target is None:
        raise HTTPException(
            status_code=404, detail=f"scheme {scheme_code} is not in the latest ranking"
        )

    peers = [
        f.scheme_code
        for f in funds
        if f.category == target.category and f.sub_category == target.sub_category
    ]

    peer_rows = [
        f for f in funds
        if f.category == target.category and f.sub_category == target.sub_category
    ]

    with navstore.session() as session:
        result = analysis.analyse(
            session, scheme_code, peers, date.today(), range_key=range
        )
        rolling = analysis.rolling_returns(session, scheme_code, date.today())
        calculator = fund_facts.calculator(session, scheme_code, date.today())

    cost = fund_facts.cost_for(scheme_code)
    holdings = fund_facts.holdings_for(target.name)
    ranks = fund_facts.rank_at_horizons(target, peer_rows)

    return FundAnalysisOut(
        scheme_code=scheme_code,
        name=target.name,
        category=target.category,
        sub_category=target.sub_category,
        range=result.range_key,
        ranges=list(analysis.RANGES),
        start=result.start,
        end=result.end,
        nav=[ChartPointOut(date=p.date, value=p.value) for p in result.nav],
        peer_median=[ChartPointOut(date=p.date, value=p.value) for p in result.peer_median],
        drawdown=[ChartPointOut(date=p.date, value=p.value) for p in result.drawdown],
        total_return=result.total_return,
        peer_total_return=result.peer_total_return,
        peers_compared=result.peers_compared,
        clipped_to_fund_history=result.clipped_to_fund_history,
        base_rate=base_rate_out(
            f"{target.category} - {target.sub_category}"
            if target.sub_category else target.category,
            amount,
        ),
        first_nav_date=result.first_nav_date,
        latest_nav=result.latest_nav,
        latest_nav_date=result.latest_nav_date,
        nav_points_available=result.nav_points_available,
        rolling_1y=RollingReturnsOut(**rolling),
        cost=FundCostOut(
            direct_ter=cost.direct_ter, regular_ter=cost.regular_ter,
            saving_pct_per_year=cost.saving_pct_per_year,
            saving_on_a_lakh_over_10y=cost.saving_on_a_lakh_over_10y,
            as_of=cost.as_of,
        ),
        holdings=FundHoldingsOut(
            covered=holdings.covered, as_of=holdings.as_of,
            total_positions=holdings.total_positions,
            top=[HoldingOut(isin=h.isin, name=h.name, industry=h.industry, weight=h.weight)
                 for h in holdings.top],
            other_weight=holdings.other_weight,
            by_industry=holdings.by_industry,
        ),
        calculator=[
            CalculatorRowOut(years=r.years, invested=r.invested, value=r.value,
                             actual_years=r.actual_years, annualised=r.annualised,
                             full_period=r.full_period)
            for r in calculator
        ],
        ranks={k: HorizonRankOut(**v) for k, v in ranks.items()},
        plain={
            k: v
            for k, v in {
                "cost": plain_words.cost_sentence(cost),
                "calculator": plain_words.calculator_sentence(calculator),
                "peers": plain_words.peer_sentence(
                    result.total_return, result.peer_total_return,
                    result.peers_compared, result.clipped_to_fund_history,
                ),
                "rolling": plain_words.rolling_sentence(rolling),
                "drawdown": plain_words.drawdown_sentence(target),
                "risk": plain_words.risk_sentence(target),
                "holdings": plain_words.holdings_sentence(holdings),
            }.items()
            if v
        },
        fund=_with_reasons(target, _load_reasons()),
    )


@router.get("/stocks/{ticker}/analysis", response_model=StockPageOut)
def stock_page(
    ticker: str,
    range: str = Query(stock_analysis_page.DEFAULT_RANGE),
    user: User = Depends(current_active_user),
) -> StockPageOut:
    """One company's page: price against its sector, ratios against their medians.

    Every ratio carries its sector median, not just P/E. A P/B of 7.6 is
    expensive for a bank and ordinary for a software company, and the bare
    number cannot say which. The medians are true medians over traa's own NSE
    universe -- an index P/E is market-cap weighted, so Nifty IT reads near 21
    because two companies dominate it.

    Four seconds on a cold cache, instant afterwards: peer prices are fetched
    sixteen at a time and held in process.
    """
    _check_choice(range, set(stock_analysis_page.RANGES), "range")
    if stock_universe.lookup(ticker) is None:
        raise HTTPException(status_code=404, detail=f"{ticker} is not in the stock universe")

    try:
        page = stock_analysis_page.build(ticker, date.today(), range_key=range)
    except Exception as exc:  # noqa: BLE001 -- an unpriceable stock is a 503, not a crash
        raise HTTPException(
            status_code=503, detail=f"{ticker} could not be priced right now: {exc}"
        ) from exc

    entry = stock_universe.lookup(ticker)
    scored, _unscorable = stocks.rank_entries([entry])
    score = ScoredStockOut.model_validate(scored[0]) if scored else None

    return StockPageOut(
        ticker=page.ticker, symbol=page.symbol, name=page.name,
        sector=page.sector, industry=page.industry,
        price=page.price, previous_close=page.previous_close,
        day_change_pct=page.day_change_pct,
        day_low=page.day_low, day_high=page.day_high,
        week52_low=page.week52_low, week52_high=page.week52_high,
        position_in_52w=page.position_in_52w,
        volume=page.volume, market_cap=page.market_cap,
        range=page.range_key, ranges=list(stock_analysis_page.RANGES),
        price_series=[ChartPointOut(date=p.date, value=p.value) for p in page.price_series],
        sector_series=[ChartPointOut(date=p.date, value=p.value) for p in page.sector_series],
        peers_compared=page.peers_compared,
        ratios=[RatioVsSectorOut(**r.__dict__) for r in page.ratios],
        similar=[SimilarStockOut(**s.__dict__) for s in page.similar],
        similar_group=page.similar_group,
        benchmark_sector=page.benchmark_sector,
        benchmark_constituents=page.benchmark_constituents,
        score=score,
        plain={
            k: v for k, v in {
                "position": plain_words.price_position_sentence(page),
                "valuation": plain_words.valuation_sentence(page),
                "quality": plain_words.quality_sentence(page),
                "size": plain_words.size_sentence(page),
                "dividend": plain_words.dividend_sentence(page),
                "score": plain_words.stock_score_sentence(
                    score.total if score else None,
                    score.bucket if score else None,
                    score.fundamental if score else None,
                    score.technical if score else None,
                ),
            }.items() if v
        },
    )
