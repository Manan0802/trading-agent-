from uuid import uuid4
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str]
    phone: Mapped[str]
    risk_score: Mapped[int | None] = mapped_column(default=None)
    risk_profile: Mapped[str | None] = mapped_column(default=None)
    annual_income: Mapped[float | None] = mapped_column(default=None)
    monthly_expenses: Mapped[float | None] = mapped_column(default=None)
