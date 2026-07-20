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
)
from app.services.advisor.fund_universe import BENCHMARK_SCHEME_CODE
from app.services.marketdata import mutual_fund
from app.services.marketdata.mutual_fund import MutualFundDataError, NavPoint
from app.services.marketdata.pricing import get_current_price
from app.services.portfolio.benchmark import compare_to_benchmark
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
            503, f"Benchmark data is temporarily unavailable — please retry ({exc})"
        ) from exc

    return BenchmarkComparisonOut.model_validate(
        compare_to_benchmark(
            transactions,
            benchmark_navs,
            portfolio_current_value=summary.total_current_value,
            valuation_date=valuation_date,
        )
    )
