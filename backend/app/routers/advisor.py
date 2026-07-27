from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth.fastapi_users_app import current_active_user
from app.database import get_db
from app.models import Goal, User
from app.schemas.goal import (
    GoalCreate,
    GoalOut,
    GoalRecommendationsOut,
    FundRecommendationOut,
    SkippedAssetClassOut,
)
from app.schemas.advisor import (
    SipRequest,
    RiskScoreRequest,
    AllocationRequest,
    TaxRequest,
    WholePortfolioRequest,
    ProfileUpdate,
    ProfileOut,
    TaxComparisonOut,
)
from app.services.advisor.sip_calculator import calculate_required_sip
from app.services.advisor.asset_allocator import (
    calculate_risk_score,
    risk_profile_from_score,
    get_allocation,
    recommended_products,
)
from app.services.advisor.goal_fund_plan import build_fund_plan
from app.services.advisor.goal_inflation import inflation_for_goal
from app.services.advisor.whole_portfolio import (
    ExternalAsset,
    classify_asset,
    plan_new_money,
)
from app.services.advisor.tax_advisor import generate_tax_saving_plan
from app.services.advisor.tax_regime import compare_regimes
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
        req.annual_income,
        req.existing_80c,
        req.existing_80d,
        req.has_nps,
        is_salaried=req.is_salaried,
        other_deductions=req.other_deductions,
        basic_salary=req.basic_salary,
    )


@router.post("/advisor/whole-portfolio")
def whole_portfolio(req: WholePortfolioRequest):
    """Where this month's money should go, given everything the user owns.

    Separate from /asset-allocation, which answers the narrower question of what
    the target mix should be. This one answers what to actually buy, and the
    two differ sharply for anyone with a large EPF balance.
    """
    target = get_allocation(req.years, req.risk_profile)

    assets: list[ExternalAsset] = []
    unclassified: list[str] = []
    for item in req.external_assets:
        asset_class = item.asset_class or classify_asset(item.name)
        if asset_class not in ("equity", "debt", "gold"):
            unclassified.append(item.name)
            continue
        assets.append(
            ExternalAsset(name=item.name, amount=item.amount, asset_class=asset_class)
        )

    existing = {c: float(req.tracked.get(c, 0.0)) for c in ("equity", "debt", "gold")}
    for asset in assets:
        existing[asset.asset_class] += asset.amount

    plan = plan_new_money(target, existing, req.monthly_investable, assets)
    return {
        "target_mix": plan.target_mix,
        "current_mix": plan.current_mix,
        "monthly_allocation": plan.allocation,
        "insights": plan.insights,
        # Surfaced rather than silently dropped: an unclassified holding is
        # missing from the mix, which the user needs to know to read the rest.
        "unclassified_assets": unclassified,
    }


def _profile_out(user: User) -> ProfileOut:
    """The stored situation, plus the answer the income was collected for."""
    tax = None
    if user.annual_income and user.annual_income > 0:
        comparison = compare_regimes(
            user.annual_income,
            is_salaried=user.is_salaried,
            deductions=(user.existing_80c or 0)
            + (user.existing_80d or 0)
            + (user.other_deductions or 0),
        )
        tax = TaxComparisonOut(
            recommended=comparison.recommended,
            new_regime_tax=comparison.new_regime_tax,
            old_regime_tax=comparison.old_regime_tax,
            saving=comparison.saving,
            breakeven_deductions=comparison.breakeven_deductions,
            rationale=comparison.rationale,
        )
    return ProfileOut(
        annual_income=user.annual_income,
        basic_salary=user.basic_salary,
        monthly_expenses=user.monthly_expenses,
        is_salaried=user.is_salaried,
        existing_80c=user.existing_80c or 0.0,
        existing_80d=user.existing_80d or 0.0,
        other_deductions=user.other_deductions or 0.0,
        years_to_goal=user.years_to_goal,
        tax=tax,
    )


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(current_active_user)):
    """What we know about this person's situation, and nothing invented.

    A new profile comes back empty rather than defaulted: putting a confident
    rupee figure on the tax lever from a number nobody supplied would be worse
    than showing no figure at all.
    """
    return _profile_out(user)


@router.patch("/profile", response_model=ProfileOut)
def update_profile(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Partial update: fields left out keep their stored value, so the form can
    be filled in over time rather than all at once."""
    # Re-read in this request's session. The authenticated user arrives on the
    # auth session, and writing it through a second one raises rather than
    # silently picking a winner.
    stored = db.get(User, user.id)
    if stored is None:
        raise HTTPException(404, "User not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(stored, field, value)
    db.commit()
    db.refresh(stored)
    return _profile_out(stored)


@router.post("/goals", response_model=GoalOut)
def create_goal(
    body: GoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    # The rate comes from the goal type unless the user overrode it: inflating
    # an education target at headline CPI is what left these goals under-funded.
    inflation_rate = (
        body.inflation_rate
        if body.inflation_rate is not None
        else inflation_for_goal(body.goal_type)
    )
    sip = calculate_required_sip(
        body.target_amount,
        int(body.years),
        body.annual_return_rate,
        body.current_savings,
        inflation_rate,
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
        inflation_rate=inflation_rate,
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
        plan = build_fund_plan(
            allocation,
            monthly_sip=goal.required_monthly_sip or 0,
            years=int(goal.years) if goal.years else None,
        )
    except MutualFundDataError as exc:
        raise HTTPException(
            503, f"Fund data is temporarily unavailable, please retry ({exc})"
        ) from exc

    return GoalRecommendationsOut(
        goal_id=goal.id,
        monthly_sip=goal.required_monthly_sip or 0,
        allocation=allocation,
        recommendations=[
            FundRecommendationOut.model_validate(p) for p in plan.picks
        ],
        skipped=[SkippedAssetClassOut.model_validate(s) for s in plan.skipped],
        annual_commission_avoided=plan.annual_commission_avoided,
    )
