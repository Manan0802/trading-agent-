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
    PortfolioSummaryOut,
    TransactionCreate,
    TransactionOut,
    HistoryPointOut,
    CostReviewOut,
    LeversOut,
    LeverOut,
)
from app.services.advisor.fund_universe import BENCHMARK_SCHEME_CODE
from app.services.marketdata import mutual_fund
from app.services.marketdata.mutual_fund import MutualFundDataError, NavPoint
from app.services.marketdata.pricing import get_current_price
from app.services.portfolio.benchmark import compare_to_benchmark
from app.services.advisor.fund_evidence import expense_ratios
from app.services.portfolio.history import HoldingSeries, build_history
from app.services.advisor.levers import rank_levers
from app.services.advisor.tax_regime import compare_regimes
from app.services.portfolio.holding_cost import cost_review
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


@router.get("/holdings", response_model=list[HoldingOut])
def list_holdings(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return db.query(Holding).filter(Holding.user_id == user.id).all()


@router.get("/holdings/{holding_id}", response_model=HoldingOut)
def get_holding(
    holding_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return _owned_holding(holding_id, db, user)


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
    return PortfolioSummaryOut.model_validate(summary)


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

    return BenchmarkComparisonOut.model_validate(
        compare_to_benchmark(
            transactions,
            benchmark_navs,
            portfolio_current_value=summary.total_current_value,
            valuation_date=valuation_date,
        )
    )


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

    fees = expense_ratios()
    priced = []
    for holding in holdings:
        entry = fees.get(holding.identifier) or {}
        direct, regular = entry.get("direct_ter"), entry.get("regular_ter")
        gap = (
            (regular - direct) / 100
            if direct is not None and regular is not None
            else None
        )
        priced.append(
            {
                "name": holding.name,
                "value": values.get(holding.id, 0.0),
                "ter_gap": gap,
            }
        )

    return CostReviewOut.model_validate(cost_review(priced, years_remaining))


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

    fees = expense_ratios()
    priced = []
    for holding in holdings:
        entry = fees.get(holding.identifier) or {}
        direct, regular = entry.get("direct_ter"), entry.get("regular_ter")
        gap = (
            (regular - direct) / 100
            if direct is not None and regular is not None
            else None
        )
        priced.append({"name": holding.name, "value": values.get(holding.id, 0.0), "ter_gap": gap})

    review = cost_review(priced, horizon)
    # The gap that matters is the one on the money actually sitting in regular
    # plans, not an average across everything the user owns.
    flagged_value = sum(f.value for f in review.flagged)
    weighted_gap = (
        sum(f.value * f.ter_gap for f in review.flagged) / flagged_value
        if flagged_value > 0
        else None
    )

    tax_saving = 0.0
    if user.annual_income and user.annual_income > 0:
        tax_saving = compare_regimes(
            user.annual_income,
            is_salaried=user.is_salaried,
            deductions=(user.existing_80c or 0)
            + (user.existing_80d or 0)
            + (user.other_deductions or 0),
        ).saving

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
            )
        ],
        years_remaining=horizon,
        portfolio_value=summary.total_current_value,
    )


@router.get("/history", response_model=list[HistoryPointOut])
def get_portfolio_history(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Month-end value of the portfolio and of the same money in the index.

    Only mutual funds carry a usable price history on the free feeds, so stock
    holdings are excluded from the line rather than pinned at their purchase
    price, which would draw a flat segment that looks like a real result.
    """
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    series: list[HoldingSeries] = []
    for holding in holdings:
        if holding.asset_type != "MF" or not holding.transactions:
            continue
        try:
            navs = mutual_fund.get_nav_history(holding.identifier)
        except MutualFundDataError:
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

    if not series:
        return []

    try:
        benchmark_navs = get_benchmark_navs()
    except MutualFundDataError:
        # The portfolio line is still worth drawing without a comparison.
        benchmark_navs = []

    return [
        HistoryPointOut.model_validate(p)
        for p in build_history(series, benchmark_navs, date.today())
    ]
