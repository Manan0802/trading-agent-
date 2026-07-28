from datetime import date
from pydantic import BaseModel, ConfigDict, Field, computed_field

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


class GoalUpdate(BaseModel):
    """Every field optional: an edit changes one thing and leaves the rest.

    Everything derived — the monthly SIP, the equity split, the fund plan — is
    recomputed from whatever the new inputs are, never patched, so a goal can
    never carry a plan for a target it no longer has.
    """

    goal_type: str | None = None
    goal_name: str | None = None
    target_amount: float | None = Field(default=None, gt=0)
    current_savings: float | None = Field(default=None, ge=0)
    target_date: date | None = None
    years: float | None = Field(default=None, gt=0)
    status: str | None = None
    inflation_rate: float | None = None
    risk_profile: str | None = None
    annual_return_rate: float | None = None


class GoalOut(BaseModel):
    id: str
    goal_type: str
    goal_name: str
    target_amount: float
    # Both needed by the goals list: a goal without its due date or what is
    # already saved toward it is a name and a number, not a plan.
    current_savings: float
    target_date: date
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
        """Why this goal uses this rate, a number the user cannot interrogate
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


class ReallocationOut(BaseModel):
    asset_class: str
    amount: float
    moved_to: dict[str, float]
    note: str

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
    # Where the plan had to leave the target mix to stay buyable, and the mix
    # that is actually being bought. Sent because a plan quietly differing from
    # the allocation it claims to implement is worse than one that says so.
    reallocations: list[ReallocationOut] = []
    actual_mix: dict[str, float] = {}


class GoalDemandOut(BaseModel):
    goal_id: str
    goal_name: str
    monthly_sip: float
    years: float

    model_config = ConfigDict(from_attributes=True)


class CommitmentOut(BaseModel):
    """What every goal together demands each month, against what there is."""

    total_monthly: float
    goals: list[GoalDemandOut]
    # None when income or expenses are unknown. A shortfall invented from a
    # missing number is worse than no figure at all.
    affordable_monthly: float | None
    shortfall: float | None
    verdict: str

    model_config = ConfigDict(from_attributes=True)
