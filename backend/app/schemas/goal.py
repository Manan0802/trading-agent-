from datetime import date
from pydantic import BaseModel, ConfigDict


class GoalCreate(BaseModel):
    goal_type: str
    goal_name: str
    target_amount: float
    current_savings: float = 0.0
    target_date: date
    years: float
    annual_return_rate: float = 0.12
    risk_profile: str = "moderate"


class GoalOut(BaseModel):
    id: str
    goal_name: str
    target_amount: float
    years: float
    required_monthly_sip: float | None
    equity_allocation: int | None
    debt_allocation: int | None
    gold_allocation: int | None
    llm_explanation: str | None
    status: str

    model_config = ConfigDict(from_attributes=True)


class FundRecommendationOut(BaseModel):
    asset_class: str
    scheme_code: str
    scheme_name: str
    category: str
    monthly_amount: float
    score: float
    rationale: str

    model_config = ConfigDict(from_attributes=True)


class SkippedAssetClassOut(BaseModel):
    asset_class: str
    reason: str

    model_config = ConfigDict(from_attributes=True)


class GoalRecommendationsOut(BaseModel):
    goal_id: str
    monthly_sip: float
    allocation: dict[str, int]
    recommendations: list[FundRecommendationOut]
    skipped: list[SkippedAssetClassOut]
