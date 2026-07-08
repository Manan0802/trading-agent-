from uuid import uuid4
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseOAuthAccountTable
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class OAuthAccount(SQLAlchemyBaseOAuthAccountTable[str], Base):
    __tablename__ = "oauth_account"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
