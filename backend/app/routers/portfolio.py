from concurrent.futures import ThreadPoolExecutor
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
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
    AnnouncementOut,
    AnnouncementsOut,
    OverlapOut,
    OverlapPairOut,
    LeverOut,
)
from app.services.advisor.fund_universe import BENCHMARK_SCHEME_CODE
from app.services.marketdata import fund_holdings, mutual_fund
from app.services.marketdata.mutual_fund import MutualFundDataError, NavPoint
from app.services.marketdata.pricing import get_current_price, price_as_of
from app.services.portfolio.benchmark import compare_to_benchmark
from app.services.advisor.fund_evidence import expense_ratios
from app.services.portfolio.history import HoldingSeries, build_history
from app.services.advisor.fund_overlap import analyse_overlap
from app.services.marketdata import announcements as filings
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
    funds = [h for h in holdings if h.asset_type == "MF"]
    if not funds:
        return {}
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
    funds = {h.id: h for h in holdings if h.asset_type == "MF"}
    if funds:
        with ThreadPoolExecutor(max_workers=8) as pool:
            resolved = dict(
                pool.map(
                    lambda h: (
                        h.id,
                        (
                            misnamed_as(h.identifier, h.name),
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
    monthly_sip: float = 0,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Which decisions are actually worth money to this user, ranked.

    Fund selection appears at zero rather than being left off: we measured it
    and it does not work, and the zero is the point.
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

    return LeversOut(
        levers=[
            LeverOut.model_validate(lever)
            for lever in rank_levers(
                portfolio_value=flagged_value,
                annual_income=user.annual_income or 0,
                monthly_sip=monthly_sip,
                years_remaining=horizon,
                regular_plan_cost_gap=weighted_gap,
                tax_saving=tax_saving,
                tax_regime_gap=regime_gap,
                current_regime=user.current_tax_regime,
            )
        ],
        years_remaining=horizon,
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
