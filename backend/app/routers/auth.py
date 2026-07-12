from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from httpx_oauth.oauth2 import GetAccessTokenError
from loguru import logger

from app.auth.backend import get_jwt_strategy
from app.auth.google import google_oauth_client
from app.auth.users import UserManager, get_user_manager
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/v1/auth/google", tags=["auth"])


def _redirect_uri() -> str:
    return f"{settings.backend_url}/api/v1/auth/google/callback"


@router.get("/authorize")
async def authorize():
    authorization_url = await google_oauth_client.get_authorization_url(_redirect_uri())
    return {"authorization_url": authorization_url}


@router.get("/callback", name="auth:google-callback")
async def callback(
    code: str | None = None,
    error: str | None = None,
    user_manager: UserManager = Depends(get_user_manager),
):
    if error or not code:
        raise HTTPException(400, f"Google denied login: {error}")

    try:
        token = await google_oauth_client.get_access_token(code, _redirect_uri())
    except GetAccessTokenError as e:
        body = e.response.text if e.response is not None else str(e)
        logger.error(f"Google token exchange failed: {body}")
        raise HTTPException(400, f"Google token exchange failed: {body}")

    account_id, account_email = await google_oauth_client.get_id_email(token["access_token"])
    user = await user_manager.oauth_callback(
        google_oauth_client.name,
        token["access_token"],
        account_id,
        account_email,
        token.get("expires_at"),
        token.get("refresh_token"),
        associate_by_email=True,
        is_verified_by_default=True,
    )
    jwt = await get_jwt_strategy().write_token(user)
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?token={jwt}")
