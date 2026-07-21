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
    is_salaried: bool = True
    # HRA, home loan interest, 80E, 80G — without these the old regime looks
    # worse than it is for anyone paying rent or a mortgage.
    other_deductions: float = 0
    # Basic salary, not CTC. Left None rather than guessed, because the
    # 80CCD(2) cap is a percentage of basic and a guess would be a made-up number.
    basic_salary: float | None = None
