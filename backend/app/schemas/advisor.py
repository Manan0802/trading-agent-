from pydantic import BaseModel


class SipRequest(BaseModel):
    target_amount: float
    years: int
    annual_return_rate: float = 0.12
    current_savings: float = 0.0
    inflation_rate: float = 0.06


class RiskScoreRequest(BaseModel):
    answers: list[int]


class AllocationRequest(BaseModel):
    years: float
    risk_profile: str


class TaxRequest(BaseModel):
    annual_income: float
    existing_80c: float = 0
    existing_80d: float = 0
    has_nps: bool = False
