from concurrent.futures import ThreadPoolExecutor
from datetime import date
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.fastapi_users_app import current_active_user
from app.database import get_db
from app.models import Holding, Transaction, User
from app.schemas.portfolio import (
    BenchmarkComparisonOut,
    HoldingCreate,
    HoldingOut,
    PortfolioHistoryOut,
    PortfolioSummaryOut,
    TransactionCreate,
    TransactionOut,
    HistoryPointOut,
    CostReviewOut,
    LeversOut,
    AlreadyOwnOut,
    AnnouncementOut,
    AnnouncementsOut,
    CompanyOut,
    LookThroughOut,
    OverlapOut,
    OverlapPairOut,
    LeverOut,
    TrackRecordOut,
    UnpricedLeverOut,
)
from app.services.advisor.fund_universe import BENCHMARK_SCHEME_CODE
from app.services.marketdata import fund_holdings, mutual_fund
from app.services.marketdata.mutual_fund import MutualFundDataError, NavPoint
from app.services.marketdata.pricing import get_current_price, price_as_of
from app.services.portfolio.benchmark import compare_to_benchmark
from app.services.advisor.fund_evidence import expense_ratios
from app.services.portfolio.history import HoldingSeries, build_history
from app.services.advisor.fund_overlap import analyse_overlap
from app.services.marketdata import holdings_store
from app.services.portfolio.already_own import overlap_with_holdings
from app.services.portfolio.look_through import concentrated, look_through
from app.services.marketdata import announcements as filings
from app.routers import screener as screener_router
from app.services.advisor import asset_mix, track_record
from app.services.advisor import levers as levers_mod
from app.services.screener import plain_words
from app.services.advisor.levers import rank_levers
from app.services.advisor.tax_regime import compare_regimes, regime_switch_saving
from app.services.portfolio.holding_cost import cost_review
from app.services.portfolio.freshness import stale_days, stale_holdings
from app.services.portfolio.plan_identity import identify, misnamed_as
from app.services.portfolio.fifo import TxnInput, apply_fifo
from app.services.portfolio.valuation import HoldingInput, value_portfolio


def get_benchmark_navs() -> list[NavPoint]:
    return mutual_fund.get_nav_history(BENCHMARK_SCHEME_CODE)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


def _owned_holding(holding_id: str, db: Session, user: User) -> Holding:
    holding = db.get(Holding, holding_id)
    if not holding or holding.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Holding not found")
    return holding


def _to_input(holding: Holding) -> HoldingInput:
    return HoldingInput(
        holding_id=holding.id,
        name=holding.name,
        asset_type=holding.asset_type,
        identifier=holding.identifier,
        category=holding.category,
        transactions=[
            TxnInput(
                txn_date=t.txn_date,
                txn_type=t.txn_type,
                units=t.units,
                price=t.price,
            )
            for t in holding.transactions
        ],
    )


@router.post("/holdings", response_model=HoldingOut, status_code=status.HTTP_201_CREATED)
def create_holding(
    body: HoldingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    holding = Holding(user_id=user.id, **body.model_dump())
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def _stale(holdings: list[Holding]) -> dict[str, str]:
    """Holdings whose price is frozen, for any view built on portfolio value.

    Called by every endpoint that prices the portfolio, not just the table, so
    a lever worth "Rs X a year" cannot be computed from a NAV that stopped
    moving in 2022 without saying so.
    """
    if not holdings:
        return {}
    funds = list(holdings)
    with ThreadPoolExecutor(max_workers=8) as pool:
        priced = dict(
            pool.map(lambda h: (h.name, price_as_of(h.asset_type, h.identifier)), funds)
        )
    return stale_holdings(priced, today=date.today())


def _with_identity(holding: Holding) -> HoldingOut:
    """Serialise a holding, flagging a label that names a different fund.

    Checked for funds only: `misnamed_as` compares against AMFI's scheme
    register, which has nothing to say about a stock ticker.
    """
    out = HoldingOut.model_validate(holding)
    if holding.asset_type == "MF":
        out = out.model_copy(
            update={"misnamed_as": misnamed_as(holding.identifier, holding.name)}
        )
    return out


@router.get("/holdings", response_model=list[HoldingOut])
def list_holdings(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(_with_identity, holdings))


@router.get("/holdings/{holding_id}", response_model=HoldingOut)
def get_holding(
    holding_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return _with_identity(_owned_holding(holding_id, db, user))


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(
    holding_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    db.delete(_owned_holding(holding_id, db, user))
    db.commit()


@router.post(
    "/holdings/{holding_id}/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_transaction(
    holding_id: str,
    body: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    holding = _owned_holding(holding_id, db, user)
    txn = Transaction(
        holding_id=holding.id,
        txn_date=body.txn_date,
        txn_type=body.txn_type,
        units=body.units,
        price=body.price,
        # Derived here rather than trusted from the client.
        amount=body.units * body.price,
    )

    # Reject a sell the ledger cannot support before it corrupts the history.
    existing = [
        TxnInput(t.txn_date, t.txn_type, t.units, t.price) for t in holding.transactions
    ]
    try:
        apply_fifo(existing + [TxnInput(body.txn_date, body.txn_type, body.units, body.price)])
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.get("", response_model=PortfolioSummaryOut)
def get_portfolio(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    summary = value_portfolio(
        [_to_input(h) for h in holdings], get_current_price, date.today()
    )
    out = PortfolioSummaryOut.model_validate(summary)

    # Resolved here rather than inside value_portfolio, which is pure arithmetic
    # over lots and should not acquire a network dependency on AMFI.
    # Stocks included: a suspended ticker freezes exactly as a wound-up scheme
    # does, and price_as_of answers for both now.
    funds = {h.id: h for h in holdings}
    if funds:
        with ThreadPoolExecutor(max_workers=8) as pool:
            resolved = dict(
                pool.map(
                    lambda h: (
                        h.id,
                        (
                            # AMFI's register has nothing to say about a ticker.
                            misnamed_as(h.identifier, h.name)
                            if h.asset_type == "MF"
                            else None,
                            price_as_of(h.asset_type, h.identifier),
                        ),
                    ),
                    funds.values(),
                )
            )
        # Each price is judged against the others in this portfolio, so a
        # market holiday cannot read as a frozen feed. See
        # services/portfolio/freshness.py.
        dates = [d for _, d in resolved.values() if d is not None]
        today = date.today()
        out = out.model_copy(
            update={
                "holdings": [
                    row.model_copy(
                        update={
                            "misnamed_as": resolved.get(row.holding_id, (None, None))[0],
                            "price_as_of": resolved.get(row.holding_id, (None, None))[1],
                            "stale_days": stale_days(
                                resolved.get(row.holding_id, (None, None))[1],
                                peer_dates=dates,
                                today=today,
                            ),
                        }
                    )
                    for row in out.holdings
                ]
            }
        )
    return out


@router.get("/benchmark", response_model=BenchmarkComparisonOut)
def get_benchmark_comparison(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """What the same money, invested on the same dates, would be worth in the index."""
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    valuation_date = date.today()
    summary = value_portfolio(
        [_to_input(h) for h in holdings], get_current_price, valuation_date
    )

    transactions = [
        TxnInput(t.txn_date, t.txn_type, t.units, t.price)
        for h in holdings
        for t in h.transactions
    ]
    try:
        benchmark_navs = get_benchmark_navs() if transactions else []
    except MutualFundDataError as exc:
        raise HTTPException(
            503, f"Benchmark data is temporarily unavailable, please retry ({exc})"
        ) from exc

    out = BenchmarkComparisonOut.model_validate(
        compare_to_benchmark(
            transactions,
            benchmark_navs,
            portfolio_current_value=summary.total_current_value,
            valuation_date=valuation_date,
        )
    )
    # Attached after validation, not passed in: compare_to_benchmark
    # returns a dataclass that knows nothing about data freshness.
    return out.model_copy(update={"stale": _stale(holdings)})


def _priced_holdings(holdings: list[Holding], values: dict[str, float]) -> list[dict]:
    """Each holding resolved to what it actually is, and what it costs.

    Two things used to go wrong here and cancelled into a plausible-looking
    number. Plan type was read off the name the user typed, so a direct plan
    labelled "Regular" was billed for a switch it did not need. And the expense
    ratio was looked up under the holding's own scheme code — but AMFI files
    both plans' ratios under the *direct* code, so a genuine regular holding
    found nothing and was quietly dropped as unpriceable. The people the cost
    review exists for were the only ones it did not work for.

    Both are the same fix: resolve the scheme, then price the pair.
    """
    fees = expense_ratios()
    priced: list[dict] = []
    for holding in holdings:
        if holding.asset_type != "MF":
            continue
        identity = identify(holding.identifier, holding.name)
        # The TER pair lives under the direct code, whichever plan is held.
        entry = fees.get(identity.direct_code or holding.identifier) or {}
        direct, regular = entry.get("direct_ter"), entry.get("regular_ter")
        gap = (
            (regular - direct) / 100
            if direct is not None and regular is not None and regular > direct
            else None
        )
        priced.append(
            {
                # The official name, so the row says what AMFI says.
                "name": identity.official_name or holding.name,
                "plan": identity.plan,
                "value": values.get(holding.id, 0.0),
                "ter_gap": gap,
                "direct_code": identity.direct_code,
                "direct_name": identity.direct_name,
            }
        )
    return priced


@router.get("/cost-review", response_model=CostReviewOut)
def get_cost_review(
    years_remaining: float = 15,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """What the regular-plan funds in this portfolio cost against their direct
    equivalents.

    Both plans own the identical portfolio; the difference is a distributor
    commission taken out of the regular plan's NAV every day, and AMFI publishes
    both figures. Only funds we can actually price are counted.
    """
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    summary = value_portfolio(
        [_to_input(h) for h in holdings], get_current_price, date.today()
    )
    values = {s.holding_id: (s.current_value or s.invested) for s in summary.holdings}

    priced = _priced_holdings(holdings, values)

    out = CostReviewOut.model_validate(cost_review(priced, years_remaining))
    return out.model_copy(update={"stale": _stale(holdings)})


@router.get("/levers", response_model=LeversOut)
def get_levers(
    years_remaining: float | None = None,
    monthly_sip: float | None = Query(
        None, ge=0,
        description="What you add each month. Derived from your own buys over "
                    "the last year when not given — it used to default to zero, "
                    "which silently removed the largest lever on the page.",
    ),
    liquid_savings: float | None = Query(
        None, ge=0,
        description="Cash, sweep account or liquid funds you can reach this "
                    "week. Without it we cannot say whether the emergency fund "
                    "is a gate, so we ask rather than assume it is fine.",
    ),
    high_interest_debt: float | None = Query(
        None, ge=0,
        description="What you owe on cards or personal loans. A card at 42% "
                    "beats every investment here, guaranteed.",
    ),
    high_interest_rate: float = Query(0.42, gt=0, le=1),
    assumed_return: float | None = Query(
        None,
        description="What you think markets will do, as a fraction. Clamped to "
                    "0.04–0.16 — outside that the arithmetic stops describing "
                    "any decision a person could be making. Omit for 0.12.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Which decisions are actually worth money to this user, ranked.

    Four lists, not one. Gates first (they earn nothing and stop a forced sale),
    then levers biggest first, then trades kept separate because they buy return
    with risk, then what we could not price and what we would need.

    Fund selection appears at zero rather than being left off: we measured it
    three times and it failed three times, and the zero is the point.
    """
    # The horizon and the income come from the stored profile unless the caller
    # overrides the horizon, so the biggest lever we can price is not silently
    # zero just because the query string was empty.
    horizon = years_remaining if years_remaining is not None else (user.years_to_goal or 15)

    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    summary = value_portfolio(
        [_to_input(h) for h in holdings], get_current_price, date.today()
    )
    values = {s.holding_id: (s.current_value or s.invested) for s in summary.holdings}

    priced = _priced_holdings(holdings, values)

    review = cost_review(priced, horizon)
    # The gap that matters is the one on the money actually sitting in regular
    # plans, not an average across everything the user owns.
    flagged_value = sum(f.value for f in review.flagged)
    weighted_gap = (
        sum(f.value * f.ter_gap for f in review.flagged) / flagged_value
        if flagged_value > 0
        else None
    )

    # Priced from the regime the user is actually in, not from the worse of the
    # two. Most people are on the new one by default and have already banked
    # this saving; telling them they could earn it again would be a lie the
    # size of the biggest number on the page.
    tax_saving = 0.0
    regime_gap = 0.0
    if user.annual_income and user.annual_income > 0:
        deductions = (
            (user.existing_80c or 0)
            + (user.existing_80d or 0)
            + (user.other_deductions or 0)
        )
        regime_gap = compare_regimes(
            user.annual_income,
            is_salaried=user.is_salaried,
            deductions=deductions,
        ).saving
        tax_saving = regime_switch_saving(
            user.annual_income,
            user.current_tax_regime,
            is_salaried=user.is_salaried,
            deductions=deductions,
        )

    # Derived rather than asked for: we already hold the categories. Built from
    # `holdings` and not from `priced`, because `_priced_holdings` drops every
    # stock — classifying only the mutual funds would report a portfolio of
    # equities and one gilt fund as 0% equity. Returns None when too much of
    # the money cannot be classified, which leaves the equity trade unpriced
    # rather than built on a guess.
    if monthly_sip is None:
        transactions = [t for h in holdings for t in h.transactions]
        monthly_sip = asset_mix.monthly_contribution(transactions, date.today())

    mix = asset_mix.classify(
        SimpleNamespace(
            name=h.name,
            asset_type=h.asset_type,
            identifier=h.identifier,
            category=h.category,
            current_value=values.get(h.id, 0.0),
        )
        for h in holdings
    )

    ranked = rank_levers(
        # The whole portfolio, for the levers that apply to all of it — the
        # yearly LTCG exemption, and the equity trade.
        portfolio_value=summary.total_current_value or 0.0,
        # Only the money in regular plans, which is the only money a switch to
        # direct is worth anything on.
        regular_plan_value=flagged_value,
        annual_income=user.annual_income or 0,
        monthly_sip=monthly_sip,
        years_remaining=horizon,
        regular_plan_cost_gap=weighted_gap,
        tax_saving=tax_saving,
        tax_regime_gap=regime_gap,
        current_regime=user.current_tax_regime,
        monthly_expenses=user.monthly_expenses,
        liquid_savings=liquid_savings,
        high_interest_debt=high_interest_debt,
        high_interest_rate=high_interest_rate,
        assumed_return=assumed_return,
        equity_share=mix.equity_share,
    )

    # The reference class for wherever most of their money actually is, with
    # their own money in it. Assembled by the screener router's function rather
    # than rebuilt here, so this screen and the fund page cannot end up quoting
    # different loss rates for the same category.
    dominant = asset_mix.dominant_category(
        SimpleNamespace(
            name=h.name, asset_type=h.asset_type, identifier=h.identifier,
            category=h.category, current_value=values.get(h.id, 0.0),
        )
        for h in holdings
    )
    base_rate = (
        screener_router.base_rate_out(dominant[0], dominant[1]) if dominant else None
    )

    record = track_record.load()
    shipped = track_record.for_fund_ranking()
    best = record.best

    return LeversOut(
        gates=[LeverOut.model_validate(g) for g in ranked.gates],
        levers=[LeverOut.model_validate(l) for l in ranked.levers],
        trades=[LeverOut.model_validate(t) for t in ranked.trades],
        unpriced=[UnpricedLeverOut.model_validate(u) for u in ranked.unpriced],
        base_rate=base_rate,
        track_record=(
            TrackRecordOut(
                key=shipped.key,
                title=shipped.title,
                wins=round(shipped.wins.median),
                windows=round(shipped.windows.median),
                hit_rate=round(shipped.hit_rate, 4),
                spread_pp=shipped.spread_pp.median,
                beats_chance=shipped.beats_chance,
                plain=plain_words.track_record_sentence(shipped) or "",
                measured_on=record.measured_on,
            )
            if shipped
            else None
        ),
        # Said out loud when our own composite is beaten by one of its own
        # ingredients. It currently is: cost alone works 83 times in 100, the
        # score we ship 61.
        better_signal=plain_words.better_signal_sentence(shipped, best),
        years_remaining=horizon,
        # Echoed back, because it may have been clamped: a reader who typed 40%
        # must see the 16% the numbers were actually built on.
        assumed_return=levers_mod.clamp_return(assumed_return),
        return_bounds=list(levers_mod.RETURN_BOUNDS),
        portfolio_value=summary.total_current_value,
        stale=_stale(holdings),
    )


@router.get("/history", response_model=PortfolioHistoryOut)
def get_portfolio_history(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Month-end value of the portfolio and of the same money in the index.

    Only mutual funds carry a usable price history on the free feeds, so stock
    holdings are excluded from the line rather than pinned at their purchase
    price, which would draw a flat segment that looks like a real result.

    What is excluded is returned with the line. It used to be dropped silently,
    which put a chart 29% below the total printed directly above it on the same
    page, with nothing to explain the gap -- two plausible numbers disagreeing,
    which is worse than one visible error.
    """
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    series: list[HoldingSeries] = []
    excluded: dict[str, str] = {}
    for holding in holdings:
        if not holding.transactions:
            continue
        if holding.asset_type != "MF":
            excluded[holding.name] = (
                "stocks have no price history on the free feeds, so this is not "
                "in the line"
            )
            continue
        try:
            navs = mutual_fund.get_nav_history(holding.identifier)
        except MutualFundDataError as exc:
            excluded[holding.name] = f"NAV history could not be fetched ({exc})"
            continue
        series.append(
            HoldingSeries(
                key=holding.id,
                transactions=[
                    TxnInput(t.txn_date, t.txn_type, t.units, t.price)
                    for t in holding.transactions
                ],
                navs=navs,
            )
        )

    # Priced once so the chart can state, in rupees, how much sits outside it.
    missing_value = 0.0
    if excluded:
        priced = value_portfolio(
            [_to_input(h) for h in holdings if h.name in excluded],
            get_current_price,
            date.today(),
        )
        missing_value = priced.total_current_value

    if not series:
        return PortfolioHistoryOut(
            points=[], excluded=excluded, excluded_value=round(missing_value, 2)
        )

    try:
        benchmark_navs = get_benchmark_navs()
    except MutualFundDataError:
        # The portfolio line is still worth drawing without a comparison.
        benchmark_navs = []

    points = [
        HistoryPointOut.model_validate(p)
        for p in build_history(series, benchmark_navs, date.today())
    ]
    return PortfolioHistoryOut(
        points=points, excluded=excluded, excluded_value=round(missing_value, 2)
    )


@router.get("/overlap", response_model=OverlapOut)
def get_overlap(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Whether the funds this user holds are actually different from each other.

    Correlation of monthly returns leads: two funds are one position when they
    move together, and NAV history says so directly for every fund. Real
    holdings overlap rides alongside wherever the AMC publishes a monthly
    portfolio we can parse, because it answers the half correlation cannot —
    whether a correlated pair is the same exposure or literally the same shares.

    Stocks are excluded rather than mixed in. A single company against a
    diversified fund correlates for reasons that have nothing to do with
    whether the pair is a duplicate.
    """
    holdings = [
        h
        for h in db.query(Holding).filter(Holding.user_id == user.id).all()
        if h.asset_type == "MF"
    ]

    funds = []
    unreachable: dict[str, str] = {}
    for holding in holdings:
        try:
            funds.append(
                (holding.identifier, holding.name, mutual_fund.get_nav_history(holding.identifier))
            )
        except MutualFundDataError as exc:
            unreachable[holding.name] = f"NAV history could not be fetched ({exc})"

    # Best effort, and concurrent because each one is a multi-megabyte
    # spreadsheet from a different AMC. A fund with no readable disclosure is
    # simply absent from the map, which the engine reports as unmeasured rather
    # than as zero overlap.
    def _portfolio(holding: Holding):
        name = identify(holding.identifier, holding.name).official_name or holding.name
        # The store first. It holds the same parsed disclosures and answers in
        # one query, so a portfolio that is already stored costs no download at
        # all -- which is the whole point of building it.
        stored = holdings_store.load(name)
        if stored is not None:
            return holding.identifier, stored
        try:
            return holding.identifier, fund_holdings.portfolio_for(name)
        except Exception:  # noqa: BLE001 - overlap must survive any AMC outage
            return holding.identifier, None

    portfolios: dict[str, object] = {}
    if len(funds) > 1:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for identifier, portfolio in pool.map(_portfolio, holdings):
                if portfolio is not None:
                    portfolios[identifier] = portfolio

    report = analyse_overlap(funds, portfolios=portfolios)
    return OverlapOut(
        pairs=[OverlapPairOut.model_validate(p) for p in report.pairs],
        effective_positions=report.effective_positions,
        counted=report.counted,
        excluded={**report.excluded, **unreachable},
        summary=report.summary,
    )


# Enough to see what changed without becoming a feed. More than this and the
# page stops being "three things worth knowing" and starts being a timeline.
_ANNOUNCEMENT_LIMIT = 12
_ANNOUNCEMENT_WORKERS = 8

# Per holding as well as overall. Without it one talkative company takes the
# whole list: Tata Steel files a litigation-pendency notice most months and
# filled eleven of twelve rows, hiding the only thing the other holding had to
# say. A cap per company is what makes this a portfolio view.
_ANNOUNCEMENT_PER_HOLDING = 3


@router.get("/announcements", response_model=AnnouncementsOut)
def get_announcements(
    days: int = 180,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """What changed about the companies this user owns.

    Deliberately not news. The evidence on retail investors and attention runs
    one way — more watching, more trading — and turnover and tax are two of the
    few things this app has measured as decisive. So the unit is "something
    changed about a thing you own", the filter drops the routine, and what is
    dropped is counted rather than hidden.
    """
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()

    not_covered: dict[str, str] = {}
    symbols: list[tuple[str, str]] = []
    for holding in holdings:
        if holding.asset_type != "STOCK":
            not_covered[holding.name] = (
                "exchange filings are published per company, and the AMC "
                "addenda that carry fund changes have no feed we can read"
            )
            continue
        symbols.append(
            (holding.identifier.upper().removesuffix(".NS"), holding.name)
        )

    def load(entry: tuple[str, str]):
        symbol, name = entry
        try:
            return name, *filings.material_announcements(symbol, days=days)
        except filings.AnnouncementError as exc:
            return name, None, str(exc)

    found: list[filings.Announcement] = []
    withheld = 0
    filtered_out = 0
    if symbols:
        with ThreadPoolExecutor(max_workers=_ANNOUNCEMENT_WORKERS) as pool:
            for name, kept, extra in pool.map(load, symbols):
                if kept is None:
                    not_covered[name] = str(extra)
                    continue
                # Newest few from each holding, so every company gets a voice.
                found.extend(kept[:_ANNOUNCEMENT_PER_HOLDING])
                withheld += max(len(kept) - _ANNOUNCEMENT_PER_HOLDING, 0)
                filtered_out += extra

    found.sort(key=lambda a: a.published, reverse=True)
    shown = found[:_ANNOUNCEMENT_LIMIT]
    withheld += len(found) - len(shown)
    return AnnouncementsOut(
        announcements=[AnnouncementOut.model_validate(a) for a in shown],
        withheld=withheld,
        filtered_out=filtered_out,
        not_covered=not_covered,
    )


@router.get("/look-through", response_model=LookThroughOut)
def get_look_through(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Which companies this user actually owns, through all their funds at once.

    Five equity funds are not five things. They are a few hundred companies,
    several of them held through four funds at once, and that position is
    invisible on every other screen: HDFC Bank at 7% of one fund, 9% of another
    and 6% of a third is ONE bet.

    The response leads with what it could not read. Holdings come from AMC
    monthly disclosures and seven AMCs have a verified source, so a real
    portfolio routinely contains funds this cannot open — and a look-through
    that silently reports only the readable part produces a number that looks
    exactly like a complete answer.
    """
    holdings = [
        h
        for h in db.query(Holding).filter(Holding.user_id == user.id).all()
        if h.asset_type == "MF"
    ]

    priced: list[tuple[str, float]] = []
    for holding in holdings:
        name = identify(holding.identifier, holding.name).official_name or holding.name
        value = float(holding.quantity or 0) * float(holding.avg_price or 0)
        if value > 0:
            priced.append((name, value))

    result = look_through(priced)

    def _out(company) -> CompanyOut:
        return CompanyOut(
            isin=company.isin,
            name=company.name,
            industry=company.industry,
            value=round(company.value, 2),
            share_pct=round(result.share_of_portfolio(company), 2),
            via=[(n, round(v, 2)) for n, v in company.via],
        )

    heavy = concentrated(result)
    if not priced:
        summary = "Add a fund holding and this will show the companies behind it."
    elif result.covered_share <= 0:
        summary = (
            f"None of your {len(priced)} funds publishes a portfolio we can read, "
            "so we cannot show what is inside them."
        )
    else:
        parts = [
            f"We could read {result.covered_share:.0f}% of your portfolio "
            f"({len(result.companies)} companies)."
        ]
        if heavy:
            top = heavy[0]
            parts.append(
                f"{top.name} is {result.share_of_portfolio(top):.1f}% of everything "
                f"you hold, through {top.fund_count} "
                f"{'fund' if top.fund_count == 1 else 'funds'}."
            )
        if result.unopened:
            parts.append(
                f"{len(result.unopened)} "
                f"{'fund does' if len(result.unopened) == 1 else 'funds do'} not "
                "publish a portfolio we can read, so nothing here counts them."
            )
        summary = " ".join(parts)

    return LookThroughOut(
        companies=[_out(c) for c in result.companies[:50]],
        concentrated=[_out(c) for c in heavy],
        covered_value=round(result.covered_value, 2),
        unopened_value=round(result.unopened_value, 2),
        unopened=list(result.unopened),
        covered_share=round(result.covered_share, 2),
        summary=summary,
    )


@router.get("/already-own/{scheme_code}", response_model=AlreadyOwnOut)
def get_already_own(
    scheme_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """How much of this fund the user already reaches through the funds they hold.

    The question `Find` could not answer, and the one that decides whether adding
    a fund does anything at all. Somebody with two large-cap funds who buys a
    third is usually buying the same thirty companies a third time — and every
    other number on the screen, including the rank, will say the third fund is
    good.

    Null, never zero, when it cannot be measured.
    """
    from app.services.advisor.fund_catalogue import all_funds

    names = {f.code: f.name for f in all_funds()}
    candidate = names.get(str(scheme_code))
    if candidate is None:
        raise HTTPException(404, f"No fund with scheme code {scheme_code}")

    held = [
        identify(h.identifier, h.name).official_name or h.name
        for h in db.query(Holding).filter(Holding.user_id == user.id).all()
        if h.asset_type == "MF" and h.identifier != str(scheme_code)
    ]

    result = overlap_with_holdings(candidate, held)
    if not result.measured:
        summary = result.reason or "We could not measure the overlap."
    elif result.share_pct < 1:
        summary = "Almost nothing in this fund is already in your portfolio."
    else:
        lead = result.through[0][0] if result.through else "your funds"
        summary = (
            f"You already own {result.share_pct:.0f}% of this fund through the "
            f"funds you hold, most of it through {lead}."
        )

    return AlreadyOwnOut(
        scheme_code=str(scheme_code),
        share_pct=result.share_pct,
        through=[list(t) for t in result.through[:6]],
        reason=result.reason,
        summary=summary,
    )
