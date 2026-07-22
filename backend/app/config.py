from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    jwt_secret: str = "dev-secret-change-in-production-min-32-chars"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
