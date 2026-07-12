from fastapi_users import schemas


class UserRead(schemas.BaseUser[str]):
    name: str
    phone: str | None
    risk_score: int | None
    risk_profile: str | None
    annual_income: float | None
    monthly_expenses: float | None


class UserUpdate(schemas.BaseUserUpdate):
    name: str | None = None
    phone: str | None = None
    risk_score: int | None = None
    risk_profile: str | None = None
    annual_income: float | None = None
    monthly_expenses: float | None = None


class UserCreate(schemas.BaseUserCreate):
    name: str = ""
