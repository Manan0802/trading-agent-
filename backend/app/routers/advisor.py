from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth.fastapi_users_app import current_active_user
from app.database import get_db
from app.models import Goal, User
from app.schemas.goal import GoalCreate, GoalOut, GoalRecommendationsOut
from app.schemas.advisor import SipRequest, RiskScoreRequest, AllocationRequest, TaxRequest
from app.services.advisor.sip_calculator import calculate_required_sip
from app.services.advisor.asset_allocator import (
    calculate_risk_score,
    risk_profile_from_score,
    get_allocation,
    recommended_products,
)
from app.services.advisor.fund_recommender import recommend_for_allocation
from app.services.advisor.tax_advisor import generate_tax_saving_plan
from app.services.llm.advisor_prompts import get_goal_explanation
from app.services.marketdata.mutual_fund import MutualFundDataError

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
def create_goal(
    body: GoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    sip = calculate_required_sip(
        body.target_amount, int(body.years), body.annual_return_rate, body.current_savings
    )
    alloc = get_allocation(body.years, body.risk_profile)
    explanation = get_goal_explanation(
        {"goal_name": body.goal_name, "target_amount": body.target_amount, "years": body.years},
        sip,
        alloc,
    )
    goal = Goal(
        user_id=user.id,
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
        llm_explanation=explanation,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/goals", response_model=list[GoalOut])
def list_goals(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return db.query(Goal).filter(Goal.user_id == user.id).all()


@router.get("/goals/{goal_id}", response_model=GoalOut)
def get_goal(
    goal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise HTTPException(404, "Goal not found")
    return goal


@router.get("/goals/{goal_id}/recommendations", response_model=GoalRecommendationsOut)
def get_goal_recommendations(
    goal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """The actual funds to buy for this goal, and how much into each.

    Served separately from the goal itself because it depends on live NAV data
    for the whole fund universe — goal creation should not wait on that.
    """
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise HTTPException(404, "Goal not found")

    allocation = {
        "equity": goal.equity_allocation or 0,
        "debt": goal.debt_allocation or 0,
        "gold": goal.gold_allocation or 0,
    }
    try:
        result = recommend_for_allocation(
            allocation,
            monthly_sip=goal.required_monthly_sip or 0,
            return_skipped=True,
        )
    except MutualFundDataError as exc:
        raise HTTPException(
            503, f"Fund data is temporarily unavailable — please retry ({exc})"
        ) from exc

    return GoalRecommendationsOut(
        goal_id=goal.id,
        monthly_sip=goal.required_monthly_sip or 0,
        allocation=allocation,
        recommendations=result.recommendations,
        skipped=result.skipped,
    )
