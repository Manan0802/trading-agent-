from typing import AsyncGenerator

from fastapi import Depends
from fastapi_users import BaseUserManager
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_async_db
from app.models import OAuthAccount, User

settings = get_settings()


async def get_user_db(
    session: AsyncSession = Depends(get_async_db),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


class UserManager(BaseUserManager[User, str]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    def parse_id(self, value) -> str:
        return str(value)

    async def on_after_register(self, user: User, request=None):
        if not user.name:
            await self.user_db.update(user, {"name": user.email.split("@")[0]})


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)
