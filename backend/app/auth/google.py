from httpx_oauth.clients.google import GoogleOAuth2

from app.config import get_settings

settings = get_settings()

google_oauth_client = GoogleOAuth2(
    settings.google_oauth_client_id, settings.google_oauth_client_secret
)
