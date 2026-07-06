from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Goal
from app.schemas.goal import GoalCreate, GoalOut
from app.schemas.advisor import SipRequest, RiskScoreRequest, AllocationRequest, TaxRequest
from app.services.advisor.sip_calculator import calculate_required_sip
from app.services.advisor.asset_allocator import (
    calculate_risk_score,
    risk_profile_from_score,
    get_allocation,
    recommended_products,
)
from app.services.advisor.tax_advisor import generate_tax_saving_plan

router = APIRouter(prefix="/api/v1", tags=["advisor"])


@router.post("/advisor/calculate-sip")
def calc_sip(req: SipRequest):
    return calculate_required_sip(
        req.target_amount,
        req.years,
        req.annual_return_rate,
        req.current_savings,
        req.inflation_rate,
    )


@router.post("/advisor/risk-score")
def risk_score(req: RiskScoreRequest):
    score = calculate_risk_score(req.answers)
    return {"score": score, "profile": risk_profile_from_score(score)}


@router.post("/advisor/asset-allocation")
def asset_allocation(req: AllocationRequest):
    alloc = get_allocation(req.years, req.risk_profile)
    return {"allocation": alloc, "products": recommended_products(alloc)}


@router.post("/advisor/tax-saving")
def tax_saving(req: TaxRequest):
    return generate_tax_saving_plan(
        req.annual_income, req.existing_80c, req.existing_80d, req.has_nps
    )


@router.post("/goals", response_model=GoalOut)
def create_goal(body: GoalCreate, db: Session = Depends(get_db)):
    sip = calculate_required_sip(
        body.target_amount, int(body.years), body.annual_return_rate, body.current_savings
    )
    alloc = get_allocation(body.years, body.risk_profile)
    goal = Goal(
        user_id=body.user_id,
        goal_type=body.goal_type,
        goal_name=body.goal_name,
        target_amount=body.target_amount,
        current_savings=body.current_savings,
        target_date=body.target_date,
        years=body.years,
        required_monthly_sip=sip["required_monthly_sip"],
        equity_allocation=alloc["equity"],
        debt_allocation=alloc["debt"],
        gold_allocation=alloc["gold"],
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/goals", response_model=list[GoalOut])
def list_goals(user_id: str, db: Session = Depends(get_db)):
    return db.query(Goal).filter(Goal.user_id == user_id).all()


@router.get("/goals/{goal_id}", response_model=GoalOut)
def get_goal(goal_id: str, db: Session = Depends(get_db)):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    return goal
