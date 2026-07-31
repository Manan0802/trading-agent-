from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The value shipped in .env.example. Anyone who never changed it is running with
# a signing key that is public in this repository, which means any stranger can
# mint a token for any user and read their income, holdings and goals.
DEV_JWT_SECRET = "dev-secret-change-in-production-min-32-chars"

# Long enough that brute-forcing the signature is not the weak link.
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./nextrade.db"
    groq_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"
    # Both spellings of the dev server. Vite prints one and the browser is
    # often pointed at the other, and allowing only "localhost" meant the page
    # rendered while every API call failed CORS, which looks like missing data
    # rather than a misconfiguration.
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Anything other than "development" is treated as real, and a real
    # deployment must bring its own signing key.
    environment: Literal["development", "production"] = "development"
    jwt_secret: str = DEV_JWT_SECRET
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    # Whether X-Forwarded-For may be believed for rate-limit counting. Only
    # true behind a reverse proxy we control: anywhere else the caller sets the
    # header themselves and gets a fresh bucket on every request, which turns
    # the limiter off for exactly the attacker it exists to stop.
    trust_proxy_header: bool = False

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return self.database_url

    @model_validator(mode="after")
    def _refuse_to_run_production_on_a_public_key(self) -> "Settings":
        """Fail at startup rather than serve every account to anyone who reads
        this repository.

        A comment saying "change in production" is not a control. The check is
        here, at the only place the value is ever built, so there is no path
        into the app that skips it.
        """
        if self.environment == "development":
            return self
        if self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET is still the example value from .env.example, which "
                "is public in this repository. Anyone could sign a token for any "
                "user. Set JWT_SECRET to something random and secret, or set "
                "ENVIRONMENT=development if this is not a real deployment."
            )
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET is {len(self.jwt_secret)} characters. Use at least "
                f"{MIN_JWT_SECRET_LENGTH} so the signature is not the weak link."
            )

        # A relative SQLite path in production is a container filesystem, and
        # that is wiped on every redeploy. Nothing errors, nothing logs -- the
        # app comes back up with an empty database and every holding, goal and
        # transaction is gone. Absolute paths are allowed because that is a
        # mounted volume, which is a real choice rather than an accident.
        if self.database_url.startswith("sqlite:///") and not self.database_url.startswith(
            "sqlite:////"
        ):
            raise ValueError(
                f"DATABASE_URL is {self.database_url!r}, a SQLite file at a "
                "relative path. On a hosted container that is ephemeral storage: "
                "the first redeploy silently deletes every account. Use Postgres, "
                "or an absolute path on a mounted volume "
                "(sqlite:////data/nextrade.db)."
            )

        # allow_credentials is on, so a wildcard origin would let any site read
        # a logged-in user's portfolio. Browsers reject the combination, which
        # means it fails as a total CORS outage rather than as a clear error.
        if "*" in self.allowed_origins:
            raise ValueError(
                "ALLOWED_ORIGINS contains '*'. This API sends credentials, so a "
                "wildcard origin is both unsafe and silently broken in browsers. "
                "List the frontend's exact origin."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
