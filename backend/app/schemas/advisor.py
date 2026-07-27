from typing import Literal

from pydantic import BaseModel, Field


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


class ExternalAssetIn(BaseModel):
    name: str
    amount: float
    # Optional: inferred from the name when omitted, and the asset is skipped
    # with a warning rather than guessed if inference fails.
    asset_class: str | None = None


class WholePortfolioRequest(BaseModel):
    years: float
    risk_profile: str
    monthly_investable: float
    # Everything owned outside this app — EPF, PPF, FDs, employer stock. The
    # single biggest reason allocation advice goes wrong is that this is empty.
    external_assets: list[ExternalAssetIn] = []
    # Balances already tracked inside the app, by asset class.
    tracked: dict[str, float] = {}


class ProfileUpdate(BaseModel):
    """Everything the advice needs to know about a person's situation.

    Every field is optional: a partial update leaves the rest alone, so the
    form can be filled in over time rather than all at once.
    """

    annual_income: float | None = Field(default=None, ge=0)
    # Basic salary, not CTC. The 80CCD(2) cap is a percentage of basic and a
    # guess from CTC would be a made-up number.
    basic_salary: float | None = Field(default=None, ge=0)
    monthly_expenses: float | None = Field(default=None, ge=0)
    is_salaried: bool | None = None
    existing_80c: float | None = Field(default=None, ge=0)
    existing_80d: float | None = Field(default=None, ge=0)
    # HRA, home loan interest, 80E, 80G. Without it the old regime looks worse
    # than it is for anyone paying rent or a mortgage.
    other_deductions: float | None = Field(default=None, ge=0)
    # Which regime they are in today, not the one we recommend. Defaults to
    # "new" on the model because that is the statutory default since FY2023-24.
    current_tax_regime: Literal["new", "old"] | None = None
    years_to_goal: float | None = Field(default=None, ge=0)


class TaxComparisonOut(BaseModel):
    recommended: str
    new_regime_tax: float
    old_regime_tax: float
    saving: float
    breakeven_deductions: float | None
    rationale: str


class ProfileOut(BaseModel):
    annual_income: float | None
    basic_salary: float | None
    monthly_expenses: float | None
    is_salaried: bool
    existing_80c: float
    existing_80d: float
    other_deductions: float
    current_tax_regime: str
    years_to_goal: float | None
    # The answer the income was collected for, so it does not need a second call.
    tax: TaxComparisonOut | None = None
