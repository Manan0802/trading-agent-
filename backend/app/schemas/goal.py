from datetime import date
from pydantic import BaseModel, ConfigDict, computed_field

from app.services.advisor.goal_inflation import inflation_note


class GoalCreate(BaseModel):
    goal_type: str
    goal_name: str
    target_amount: float
    current_savings: float = 0.0
    target_date: date
    years: float
    annual_return_rate: float = 0.12
    risk_profile: str = "moderate"
    # None means "use the rate for this goal type". An explicit value overrides
    # it, so the table is a default rather than a policy.
    inflation_rate: float | None = None


class GoalOut(BaseModel):
    id: str
    goal_type: str
    goal_name: str
    target_amount: float
    years: float
    inflation_rate: float | None
    required_monthly_sip: float | None
    equity_allocation: int | None
    debt_allocation: int | None
    gold_allocation: int | None
    llm_explanation: str | None
    status: str

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def inflation_note(self) -> str:
        """Why this goal uses this rate — a number the user cannot interrogate
        is a number they cannot trust."""
        return inflation_note(self.goal_type)


class VerdictOut(BaseModel):
    headline: str
    points: list[str]
    caveat: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FundRecommendationOut(BaseModel):
    asset_class: str
    # Where this fund sits in its own category, so the pick can be questioned.
    rank: int
    scheme_code: str
    scheme_name: str
    category: str
    monthly_amount: float
    score: float
    direct_ter: float | None
    regular_ter: float | None
    verdict: VerdictOut

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
    # Rupees a year the plan avoids by recommending direct plans only, where
    # both plans of a picked fund are published by AMFI.
    annual_commission_avoided: float | None = None
