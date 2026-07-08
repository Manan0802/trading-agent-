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

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(  # noqa: F821
        "OAuthAccount", lazy="joined"
    )
