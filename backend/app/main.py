from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import advisor, alerts, ask, auth, portfolio, research, screener
from app.jobs.scheduler import start_scheduler
from app.auth.backend import auth_backend
from app.auth.fastapi_users_app import fastapi_users
from app.schemas.user import UserCreate, UserRead, UserUpdate

settings = get_settings()


def _warn_if_the_nav_store_is_empty() -> None:
    """Say so loudly at boot, and say exactly what to run.

    Deliberately NOT an automatic backfill. That would crawl mfapi for 4,957
    funds on every container restart -- three minutes of startup and a lot of
    load on a free API, repeated for a problem that only exists once. The
    screener already answers 503 with the rebuild progress in the message, so a
    request explains itself; this makes the logs explain it too, because the
    operator is the one who can fix it.
    """
    import logging

    from app.services.screener import navstore

    log = logging.getLogger("nextrade.startup")
    try:
        navstore.ensure_schema()
        with navstore.session() as session:
            stats = navstore.store_stats(session)
            served = navstore.latest_run_id(session)
    except Exception:  # noqa: BLE001 -- never block startup on a cache
        log.exception("could not check the NAV store")
        return

    if stats["funds"] == 0:
        log.warning(
            "NAV store at %s is empty, so the fund screener will answer 503. "
            "Build it with: venv/bin/python scripts/backfill_nav_history.py",
            navstore.db_path(),
        )
    elif served is None:
        log.warning(
            "NAV store holds %s funds but nothing has been scored yet, so the "
            "fund screener will answer 503. The nightly job runs at 00:15 IST, "
            "or run it now with: python -c "
            "'from app.services.screener import pipeline; pipeline.run_nightly()'",
            f"{stats['funds']:,}",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    _warn_if_the_nav_store_is_empty()
    yield


app = FastAPI(title="NexTrade API", version="0.1.0", lifespan=lifespan)

# Read by the rate limiter, which runs before any dependency and so cannot take
# Settings by injection.
app.state.trust_proxy_header = settings.trust_proxy_header

# Middleware runs outermost-last, so this order means: CORS answers preflight
# first, then the limiter decides, then headers are stamped on whatever comes
# back. A 429 therefore still carries CORS headers -- without that the browser
# reports a CORS failure and the real cause never reaches the user.
app.add_middleware(SecurityHeadersMiddleware, production=settings.environment == "production")
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(advisor.router)
app.include_router(alerts.router)
app.include_router(ask.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(research.router)
app.include_router(screener.router)
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/api/v1/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/api/v1/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/api/v1/users", tags=["users"]
)


@app.get("/health")
def health():
    return {"status": "ok"}
