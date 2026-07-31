"""Rate limiting: that it stops abuse, and that it does not stop the owner.

A limiter that fires on ordinary use is worse than none, because the fix people
reach for is to turn it off. So roughly half of these assert that it stays out
of the way.
"""
import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.middleware import rate_limit
from app.middleware.rate_limit import AUTH, DEFAULT, HEAVY, _Counter, tier_for


@pytest.fixture(autouse=True)
def _clean():
    """Counters are process-global, so one test would otherwise exhaust the next."""
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture
def client():
    # The auth-tier tests post real logins, which reach the user table.
    Base.metadata.create_all(bind=engine)
    return TestClient(app)


class TestTierChoice:
    def test_login_is_the_strictest_because_that_is_where_passwords_are_guessed(self):
        assert tier_for("/api/v1/auth/jwt/login") is AUTH
        assert tier_for("/api/v1/auth/register") is AUTH

    def test_the_endpoints_that_fetch_from_six_amcs_are_limited_harder(self):
        assert tier_for("/api/v1/portfolio/overlap") is HEAVY
        assert tier_for("/api/v1/portfolio/cost-review") is HEAVY
        assert tier_for("/api/v1/research/funds") is HEAVY

    def test_ordinary_reads_get_the_generous_tier(self):
        assert tier_for("/api/v1/portfolio") is DEFAULT
        assert tier_for("/api/v1/profile") is DEFAULT

    def test_health_is_never_limited(self):
        # A load balancer polls this. Limiting it takes the app out of rotation
        # under exactly the load the limit exists to survive.
        assert tier_for("/health") is None
        assert tier_for("/openapi.json") is None

    def test_auth_is_stricter_than_heavy_is_stricter_than_default(self):
        assert AUTH.requests < HEAVY.requests < DEFAULT.requests


class TestCounting:
    def test_allows_up_to_the_limit_then_refuses(self):
        counter, now = _Counter(), 1000.0
        for _ in range(AUTH.requests):
            assert counter.hit("ip:1.2.3.4", AUTH, now) is None
        assert counter.hit("ip:1.2.3.4", AUTH, now) is not None

    def test_the_refusal_says_how_long_to_wait(self):
        counter, now = _Counter(), 1000.0
        for _ in range(AUTH.requests):
            counter.hit("ip:1.2.3.4", AUTH, now)
        retry = counter.hit("ip:1.2.3.4", AUTH, now)
        assert 0 < retry <= AUTH.window_seconds + 1

    def test_one_caller_cannot_exhaust_another(self):
        counter, now = _Counter(), 1000.0
        for _ in range(AUTH.requests):
            counter.hit("ip:1.2.3.4", AUTH, now)
        assert counter.hit("ip:5.6.7.8", AUTH, now) is None

    def test_tiers_are_counted_separately(self):
        # Spending the login allowance must not lock someone out of their
        # own portfolio.
        counter, now = _Counter(), 1000.0
        for _ in range(AUTH.requests):
            counter.hit("tok:abc", AUTH, now)
        assert counter.hit("tok:abc", DEFAULT, now) is None

    def test_the_window_slides_rather_than_resetting_on_a_boundary(self):
        # A fixed window lets a caller spend the whole allowance at 11:59:59
        # and the whole next one at 12:00:00 -- double the limit at the one
        # moment it matters.
        counter, now = _Counter(), 1000.0
        for _ in range(AUTH.requests):
            counter.hit("ip:1.2.3.4", AUTH, now)
        assert counter.hit("ip:1.2.3.4", AUTH, now + AUTH.window_seconds - 1) is not None
        assert counter.hit("ip:1.2.3.4", AUTH, now + AUTH.window_seconds + 1) is None

    def test_memory_does_not_grow_without_bound(self):
        counter = _Counter()
        for i in range(500):
            counter.hit(f"ip:10.0.0.{i}", DEFAULT, 1000.0)
        # An hour later, one live caller. The stale buckets should be gone.
        counter.hit("ip:live", DEFAULT, 1000.0 + 4000)
        assert len(counter._buckets) < 10


class TestThroughTheApp:
    def test_health_survives_a_burst(self, client):
        for _ in range(DEFAULT.requests + 20):
            assert client.get("/health").status_code == 200

    def test_repeated_bad_logins_are_eventually_refused(self, client):
        codes = {
            client.post(
                "/api/v1/auth/jwt/login",
                data={"username": "nobody@example.com", "password": "wrong"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ).status_code
            for _ in range(AUTH.requests + 5)
        }
        assert 429 in codes

    def test_the_429_explains_itself(self, client):
        last = None
        for _ in range(AUTH.requests + 5):
            last = client.post(
                "/api/v1/auth/jwt/login",
                data={"username": "nobody@example.com", "password": "wrong"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert last.status_code == 429
        assert "Retry-After" in last.headers
        detail = last.json()["detail"]
        assert "Too many requests" in detail
        # It must say the limit and the wait, so a caller can behave.
        assert "per minute" in detail and "Try again in" in detail

    def test_a_normal_session_is_never_limited(self, client):
        # What the app itself does on one page load, several times over.
        for _ in range(20):
            assert client.get("/health").status_code == 200
            assert client.get("/api/v1/portfolio").status_code in (200, 401)


class TestSecurityHeaders:
    def test_json_cannot_be_sniffed_as_html(self, client):
        assert client.get("/health").headers["X-Content-Type-Options"] == "nosniff"

    def test_the_api_cannot_be_framed(self, client):
        headers = client.get("/health").headers
        assert headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]

    def test_no_hsts_in_development(self, client):
        # Sending it on plain HTTP would pin localhost to HTTPS in the
        # developer's own browser for two years.
        assert "Strict-Transport-Security" not in client.get("/health").headers


class TestProductionGuards:
    """Configuration that would lose data or leak it must not start.

    Each of these is a failure that produces no error at runtime -- an empty
    database after a redeploy, or a CORS outage that reads as "the API is down".
    Refusing at startup is the only place they are visible.
    """

    def _settings(self, **overrides):
        from app.config import Settings

        base = {
            "environment": "production",
            "jwt_secret": "x" * 40,
            "database_url": "postgresql://u:p@host/db",
            "allowed_origins": "https://app.example.com",
        }
        return Settings(_env_file=None, **{**base, **overrides})

    def test_a_sane_production_config_starts(self):
        assert self._settings().environment == "production"

    def test_relative_sqlite_is_refused_because_a_redeploy_erases_it(self):
        with pytest.raises(ValueError, match="ephemeral"):
            self._settings(database_url="sqlite:///./nextrade.db")

    def test_sqlite_on_a_mounted_volume_is_allowed(self):
        # An absolute path is a deliberate choice, not the container default.
        assert self._settings(database_url="sqlite:////data/nextrade.db")

    def test_a_wildcard_origin_is_refused(self):
        with pytest.raises(ValueError, match="wildcard"):
            self._settings(allowed_origins="*")

    def test_development_is_left_alone(self):
        from app.config import Settings

        # Local work must not need Postgres or a generated secret.
        assert Settings(_env_file=None, environment="development")


class TestOnlyFailuresCountOnAuth:
    """Brute force is failed attempts, so successes must not spend the budget.

    Found the hard way: the screenshot tooling, the consistency harness and an
    ad-hoc script all log in from 127.0.0.1, and running them back to back
    exhausted the shared allowance between them. Every tool then got 401s,
    which is exactly how a limiter gets turned off.
    """

    def _register(self, client, email):
        return client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "correct-horse-battery",
                "name": "T",
                "phone": "+919000009999",
            },
        )

    def _login(self, client, email, password):
        return client.post(
            "/api/v1/auth/jwt/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def test_many_successful_logins_are_never_refused(self, client):
        email = "ratelimit-success@example.com"
        self._register(client, email)
        for _ in range(AUTH.requests * 3):
            assert self._login(client, email, "correct-horse-battery").status_code == 200

    def test_failures_still_hit_the_wall_at_the_same_count(self, client):
        email = "ratelimit-fail@example.com"
        self._register(client, email)
        codes = [
            self._login(client, email, "wrong").status_code
            for _ in range(AUTH.requests + 3)
        ]
        assert 429 in codes
        assert codes.count(429) >= 3

    def test_a_success_does_not_clear_the_wall_a_guesser_already_hit(self, client):
        # Otherwise one correct password would reset the budget for everyone
        # sharing that IP.
        email = "ratelimit-mixed@example.com"
        self._register(client, email)
        for _ in range(AUTH.requests + 1):
            self._login(client, email, "wrong")
        assert self._login(client, email, "correct-horse-battery").status_code == 429
