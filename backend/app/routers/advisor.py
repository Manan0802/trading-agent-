from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth.fastapi_users_app import current_active_user
from app.database import get_db
from app.models import Goal, User
from app.schemas.goal import (
    CommitmentOut,
    GoalCreate,
    GoalOut,
    GoalUpdate,
    GoalRecommendationsOut,
    FundRecommendationOut,
    ReallocationOut,
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
from app.services.advisor.goal_commitment import GoalDemand, assess_commitment
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
        current_tax_regime=user.current_tax_regime,
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


def _reprice(goal: Goal, *, annual_return_rate: float = 0.12) -> tuple[dict, dict]:
    """Recompute everything a goal's inputs decide, in place.

    Shared by create and edit rather than written twice. An edit that changed
    the target date but left the old monthly SIP sitting beside it would be a
    plan describing a goal that no longer exists.

    Returns the full SIP and allocation results, not just the fields stored on
    the goal: the projection carries figures like the wealth created that the
    explanation uses and the row does not keep.
    """
    sip = calculate_required_sip(
        goal.target_amount,
        # Not truncated: a goal 16.8 years away is priced over 16.8 years. The
        # arithmetic below is continuous in it, and rounding down quietly asks
        # for a bigger monthly figure than the goal needs.
        goal.years,
        annual_return_rate,
        goal.current_savings,
        goal.inflation_rate,
    )
    # From the goal's own stored risk profile. Taking it from the request meant
    # an edit that did not mention risk — a rename, a new target — silently fell
    # back to "moderate" and rebuilt the split around it.
    alloc = get_allocation(goal.years, goal.risk_profile)
    goal.required_monthly_sip = sip["required_monthly_sip"]
    goal.equity_allocation = alloc["equity"]
    goal.debt_allocation = alloc["debt"]
    goal.gold_allocation = alloc["gold"]
    return sip, alloc


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
    goal = Goal(
        user_id=user.id,
        goal_type=body.goal_type,
        goal_name=body.goal_name,
        target_amount=body.target_amount,
        current_savings=body.current_savings,
        target_date=body.target_date,
        years=body.years,
        inflation_rate=inflation_rate,
        risk_profile=body.risk_profile,
    )
    sip, alloc = _reprice(goal, annual_return_rate=body.annual_return_rate)
    goal.llm_explanation = get_goal_explanation(
        {"goal_name": goal.goal_name, "target_amount": goal.target_amount, "years": goal.years},
        sip,
        alloc,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: str,
    body: GoalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Change a goal's target, date or name, and reprice it.

    This is the other half of the affordability check. Telling someone their
    goals cost more than they earn and that a target or date has to move, while
    giving them no way to move one, is advice with the door locked.

    Everything derived is recomputed rather than patched: change the date and
    the monthly SIP, the equity split and the fund plan all follow from it.
    """
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise HTTPException(404, "Goal not found")

    fields = body.model_dump(exclude_unset=True)
    for field in ("goal_name", "target_amount", "current_savings", "target_date", "years", "status"):
        if fields.get(field) is not None:
            setattr(goal, field, fields[field])

    if fields.get("goal_type") is not None:
        goal.goal_type = fields["goal_type"]
        # The stored rate came from the old type, so it has to follow unless the
        # user has pinned one explicitly.
        if fields.get("inflation_rate") is None:
            goal.inflation_rate = inflation_for_goal(goal.goal_type)
    if fields.get("inflation_rate") is not None:
        goal.inflation_rate = fields["inflation_rate"]

    if fields.get("risk_profile") is not None:
        goal.risk_profile = fields["risk_profile"]
    sip, alloc = _reprice(goal, annual_return_rate=body.annual_return_rate or 0.12)
    # Regenerated, not kept. The explanation names the monthly figure and the
    # split; left alone after an edit it would describe a plan that is no
    # longer on the page it sits on.
    goal.llm_explanation = get_goal_explanation(
        {"goal_name": goal.goal_name, "target_amount": goal.target_amount, "years": goal.years},
        sip,
        alloc,
    )
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(
    goal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Remove a goal outright.

    A hard delete rather than an archive flag: this is the user's own plan, and
    a goal they have decided against should stop showing up in what their goals
    cost them every month.
    """
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise HTTPException(404, "Goal not found")
    db.delete(goal)
    db.commit()


@router.get("/goals", response_model=list[GoalOut])
def list_goals(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return db.query(Goal).filter(Goal.user_id == user.id).all()


# Declared before /goals/{goal_id}: FastAPI matches in order, and the dynamic
# route would otherwise swallow "commitment" as a goal id.
@router.get("/goals/commitment", response_model=CommitmentOut)
def get_commitment(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """What every goal together asks for each month, against what there is.

    Each goal's own page says what that goal needs. Nobody adds them up, and
    three affordable-looking plans are how a user ends up committing more than
    they earn and discovering it by missing an instalment.
    """
    goals = db.query(Goal).filter(Goal.user_id == user.id).all()
    demands = [
        GoalDemand(
            goal_id=g.id,
            goal_name=g.goal_name,
            monthly_sip=g.required_monthly_sip or 0.0,
            years=g.years or 0.0,
        )
        for g in goals
        if g.status == "active"
    ]
    return CommitmentOut.model_validate(
        assess_commitment(
            demands,
            annual_income=user.annual_income,
            monthly_expenses=user.monthly_expenses,
        )
    )


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
        reallocations=[
            ReallocationOut.model_validate(r) for r in plan.reallocations
        ],
        actual_mix=plan.actual_mix,
    )
