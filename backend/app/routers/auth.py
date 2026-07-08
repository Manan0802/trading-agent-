from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback

from app.auth.backend import get_jwt_strategy
from app.auth.google import google_oauth_client
from app.auth.users import UserManager, get_user_manager
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/v1/auth/google", tags=["auth"])

oauth2_callback = OAuth2AuthorizeCallback(google_oauth_client, route_name="auth:google-callback")


def _redirect_uri() -> str:
    return f"{settings.backend_url}/api/v1/auth/google/callback"


@router.get("/authorize")
async def authorize():
    authorization_url = await google_oauth_client.get_authorization_url(_redirect_uri())
    return {"authorization_url": authorization_url}


@router.get("/callback", name="auth:google-callback")
async def callback(
    access_token_state: tuple = Depends(oauth2_callback),
    user_manager: UserManager = Depends(get_user_manager),
):
    token, _state = access_token_state
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
