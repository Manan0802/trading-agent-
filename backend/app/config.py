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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
