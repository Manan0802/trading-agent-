from uuid import uuid4
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(SQLAlchemyBaseUserTable[str], Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(default="")
    phone: Mapped[str | None] = mapped_column(default=None)
    risk_score: Mapped[int | None] = mapped_column(default=None)
    risk_profile: Mapped[str | None] = mapped_column(default=None)
    annual_income: Mapped[float | None] = mapped_column(default=None)
    monthly_expenses: Mapped[float | None] = mapped_column(default=None)
    # What the tax comparison needs. Salaried is the common case but changes
    # the standard deduction, so it is asked rather than assumed.
    is_salaried: Mapped[bool] = mapped_column(default=True)
    # Basic salary, not CTC: the 80CCD(2) cap is a percentage of basic, and a
    # guess from CTC would be a made-up number.
    basic_salary: Mapped[float | None] = mapped_column(default=None)
    # Everything claimed outside 80C/80D/80CCD(1B): HRA, home loan interest,
    # 80E, 80G. Without it the old regime looks worse than it is for anyone
    # paying rent or a mortgage.
    other_deductions: Mapped[float] = mapped_column(default=0.0)
    existing_80c: Mapped[float] = mapped_column(default=0.0)
    existing_80d: Mapped[float] = mapped_column(default=0.0)
    # Years until the money is needed. Drives every lifetime figure we show.
    years_to_goal: Mapped[float | None] = mapped_column(default=None)

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(  # noqa: F821
        "OAuthAccount", lazy="joined"
    )
