from uuid import uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Holding(Base):
    """One instrument the user owns — a mutual fund scheme or a listed stock.

    `identifier` is the key we fetch live prices with: an AMFI scheme code for
    MF holdings, a yfinance ticker (e.g. RELIANCE.NS) for stocks.
    """

    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str]
    asset_type: Mapped[str]  # "MF" | "STOCK"
    identifier: Mapped[str]
    category: Mapped[str | None] = mapped_column(default=None)

    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction",
        back_populates="holding",
        cascade="all, delete-orphan",
        order_by="Transaction.txn_date",
    )
