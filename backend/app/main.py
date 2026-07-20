from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import advisor, alerts, auth, portfolio
from app.jobs.scheduler import start_scheduler
from app.auth.backend import auth_backend
from app.auth.fastapi_users_app import fastapi_users
from app.schemas.user import UserCreate, UserRead, UserUpdate

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield


app = FastAPI(title="NexTrade API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(advisor.router)
app.include_router(alerts.router)
app.include_router(auth.router)
app.include_router(portfolio.router)
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
