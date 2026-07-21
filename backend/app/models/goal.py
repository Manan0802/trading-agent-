from datetime import date
from uuid import uuid4
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    goal_type: Mapped[str]
    goal_name: Mapped[str]
    target_amount: Mapped[float]
    current_savings: Mapped[float] = mapped_column(default=0.0)
    target_date: Mapped[date]
    years: Mapped[float]
    # Persisted rather than re-derived: the goal-type table can change, and a
    # saved plan must stay reproducible from its own stored inputs.
    inflation_rate: Mapped[float | None] = mapped_column(default=None)
    required_monthly_sip: Mapped[float | None] = mapped_column(default=None)
    equity_allocation: Mapped[int | None] = mapped_column(default=None)
    debt_allocation: Mapped[int | None] = mapped_column(default=None)
    gold_allocation: Mapped[int | None] = mapped_column(default=None)
    llm_explanation: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")
