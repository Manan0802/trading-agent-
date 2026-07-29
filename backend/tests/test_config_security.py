"""A deployment must not run on the signing key that is public in this repo.

.env.example ships a JWT secret. Anybody who never changed it is running an app
where a stranger can mint a token for any user and read their income, holdings
and goals. A comment saying "change in production" is not a control.
"""

import pytest

from app.config import DEV_JWT_SECRET, MIN_JWT_SECRET_LENGTH, Settings


def test_development_may_use_the_example_secret():
    """Local work must stay frictionless, or the guard gets removed."""
    settings = Settings(environment="development", jwt_secret=DEV_JWT_SECRET)
    assert settings.jwt_secret == DEV_JWT_SECRET


def test_production_refuses_to_start_on_the_example_secret():
    with pytest.raises(ValueError, match="public in this repository"):
        Settings(environment="production", jwt_secret=DEV_JWT_SECRET)


def test_production_refuses_a_secret_too_short_to_be_worth_signing_with():
    with pytest.raises(ValueError, match="characters"):
        Settings(environment="production", jwt_secret="short")


def test_production_accepts_a_real_secret():
    secret = "x" * MIN_JWT_SECRET_LENGTH
    assert Settings(environment="production", jwt_secret=secret).jwt_secret == secret


def test_the_default_environment_is_development_so_nothing_breaks_locally():
    assert Settings().environment == "development"
