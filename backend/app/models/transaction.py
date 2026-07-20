from datetime import date
from uuid import uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    """A single buy or sell against a holding.

    Every purchase is its own row — a monthly SIP instalment, a one-off lump sum
    and an ad-hoc top-up are all just BUY rows on different dates. Keeping the
    raw per-transaction ledger (rather than aggregating into "units held") is
    what lets us compute XIRR and FIFO capital gains correctly later.
    """

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    holding_id: Mapped[str] = mapped_column(ForeignKey("holdings.id"), index=True)
    txn_date: Mapped[date]
    txn_type: Mapped[str]  # "BUY" | "SELL"
    units: Mapped[float]
    price: Mapped[float]  # NAV (MF) or price per share (stock) on txn_date
    amount: Mapped[float]  # units * price

    holding: Mapped["Holding"] = relationship(  # noqa: F821
        "Holding", back_populates="transactions"
    )
