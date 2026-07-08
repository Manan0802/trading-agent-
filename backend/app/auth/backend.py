from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy

from app.config import get_settings

settings = get_settings()

bearer_transport = BearerTransport(tokenUrl="api/v1/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=60 * 60 * 24 * 30)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
