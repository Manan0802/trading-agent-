from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from httpx_oauth.oauth2 import GetAccessTokenError
from loguru import logger

from app.auth.backend import get_jwt_strategy
from app.auth.google import google_oauth_client
from app.auth.pkce import code_challenge_from_verifier, generate_code_verifier
from app.auth.users import UserManager, get_user_manager
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/v1/auth/google", tags=["auth"])

PKCE_COOKIE_NAME = "oauth_code_verifier"


def _redirect_uri() -> str:
    return f"{settings.backend_url}/api/v1/auth/google/callback"


@router.get("/authorize")
async def authorize(response: Response):
    redirect_uri = _redirect_uri()
    code_verifier = generate_code_verifier()
    code_challenge = code_challenge_from_verifier(code_verifier)

    authorization_url = await google_oauth_client.get_authorization_url(
        redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method="S256",
        # NO `access_type=offline`, and that is the whole point of this line
        # existing. It was here, and it is the flag that makes Google mint a
        # long-lived REFRESH TOKEN -- which `fastapi-users` then stores in a
        # plaintext column, in production on Turso, a third party. This flow
        # calls `get_id_email()` once and never refreshes anything, so the
        # credential had no use and every risk. Deleting the request deletes
        # the asset, which beats encrypting it. Scopes are identity-only.
        extras_params={"prompt": "consent"},
    )

    response.set_cookie(
        PKCE_COOKIE_NAME,
        code_verifier,
        max_age=600,
        path="/api/v1/auth/google",
        httponly=True,
        samesite="lax",
    )
    return {"authorization_url": authorization_url}


@router.get("/callback", name="auth:google-callback")
async def callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    user_manager: UserManager = Depends(get_user_manager),
):
    if error or not code:
        raise HTTPException(400, f"Google denied login: {error}")

    redirect_uri = _redirect_uri()
    code_verifier = request.cookies.get(PKCE_COOKIE_NAME)
    # The authorization code is not logged, not even a prefix. It is
    # single-use and short-lived, so the prefix was low risk -- but on a free
    # tier these logs land in the host's dashboard, and "log a bit of the
    # credential" is a habit rather than a decision.
    logger.info(
        "OAuth callback: redirect_uri=%r has_code_verifier=%s",
        redirect_uri,
        code_verifier is not None,
    )

    try:
        token = await google_oauth_client.get_access_token(code, redirect_uri, code_verifier)
    except GetAccessTokenError as e:
        body = e.response.text if e.response is not None else str(e)
        # Status and a short prefix only. The full body from a token endpoint
        # can echo request material back, and on a free tier these logs land in
        # the host's dashboard.
        logger.error(
            "Google token exchange failed: HTTP %s %s",
            e.response.status_code if e.response is not None else "?",
            body[:120],
        )
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
    redirect = RedirectResponse(f"{settings.frontend_url}/auth/callback?token={jwt}")
    redirect.delete_cookie(PKCE_COOKIE_NAME, path="/api/v1/auth/google")
    return redirect
