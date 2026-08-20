"""Rate limiting, sized to what each endpoint actually costs us.

One flat limit across the API would be the wrong shape. `/health` costs
nothing; `/api/v1/portfolio/overlap` downloads multi-megabyte spreadsheets from
six asset managers and correlates twelve years of NAV history. And a login
endpoint is not rate limited to protect the server at all -- it is rate limited
because it is where passwords get guessed.

So there are three tiers, and the tier is chosen by what an abuser would gain:

    auth        brute force            strictest, counted per IP, FAILURES ONLY
    heavy       our upstreams' cost    strict, counted per user
    default     ordinary reads         generous

Counted per authenticated user where we know who is calling, and per client IP
where we do not -- which is exactly the login case, since an attacker trying
passwords has no account yet.

**On the auth tier only failed attempts are counted.** Brute force *is* failed
attempts, so charging successes protects nothing and punishes the wrong people:
locally every script shares 127.0.0.1, and a handful run back to back spent the
allowance between them -- which is how a limiter ends up switched off. A
guessing run never earns a success to spend, so it still stops at the same
count.

**Deliberately in-process.** State lives in this worker's memory, so N workers
allow N times the limit, and a restart forgets everything. That is the honest
trade for a single-instance personal deployment: it needs no Redis to run and
no operational story to get wrong. It is a real limitation rather than a hidden
one, and the fix when it matters is to move `_Bucket` behind Redis, not to
rewrite this. What it does stop -- an unattended script hammering the API, a
credential-stuffing run -- is what a single-instance app is actually exposed to.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass(frozen=True)
class Tier:
    name: str
    requests: int
    window_seconds: int

    @property
    def described(self) -> str:
        per = "minute" if self.window_seconds == 60 else f"{self.window_seconds}s"
        return f"{self.requests} per {per}"


# Ten failed passwords a minute is far more than a person mistypes and far less
# than a guessing run needs. Successes are free.
AUTH = Tier("auth", requests=10, window_seconds=60)

# One overlap call can fetch six AMC workbooks. The disk cache absorbs repeats,
# so this bites only on genuinely novel work.
HEAVY = Tier("heavy", requests=20, window_seconds=60)

DEFAULT = Tier("default", requests=120, window_seconds=60)

# Matched as prefixes against the request path.
_AUTH_PATHS = (
    "/api/v1/auth/jwt/login",
    "/api/v1/auth/register",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
)
_HEAVY_PATHS = (
    "/api/v1/portfolio/overlap",
    "/api/v1/portfolio/cost-review",
    "/api/v1/portfolio/history",
    "/api/v1/portfolio/announcements",
    "/api/v1/research",
    "/api/v1/advisor",
    # The full-universe screener response is ~1.2 MB and there is no
    # GZipMiddleware installed, so 120/min of it is a self-DoS on one instance.
    # Prefix matching leaves "/api/v1/screener/top-funds" on the default tier,
    # which is what the screen actually uses -- "…/top-funds" does not start
    # with "…/funds". test_rate_limit.py pins both so this cannot drift.
    "/api/v1/screener/funds",
)

# Costs nothing and is what a load balancer polls. Limiting it would take the
# app out of rotation under exactly the load the limit exists to survive.
_EXEMPT = ("/health", "/docs", "/openapi.json", "/redoc")


def tier_for(path: str) -> Tier | None:
    if path.startswith(_EXEMPT):
        return None
    if path.startswith(_AUTH_PATHS):
        return AUTH
    if path.startswith(_HEAVY_PATHS):
        return HEAVY
    return DEFAULT


@dataclass
class _Bucket:
    """Timestamps of recent hits, oldest first."""

    hits: deque = field(default_factory=deque)


class _Counter:
    """A sliding window per (caller, tier).

    Sliding rather than fixed: a fixed window lets someone spend the whole
    allowance at 11:59:59 and the whole next allowance at 12:00:00, which is
    double the limit at the one moment it matters.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = Lock()
        self._last_swept = 0.0

    def hit(self, key: str, tier: Tier, now: float) -> int | None:
        """None if allowed, else seconds until the caller may retry."""
        with self._lock:
            self._sweep(now)
            bucket = self._buckets.setdefault((key, tier.name), _Bucket())
            cutoff = now - tier.window_seconds
            while bucket.hits and bucket.hits[0] <= cutoff:
                bucket.hits.popleft()
            if len(bucket.hits) >= tier.requests:
                return max(1, int(bucket.hits[0] + tier.window_seconds - now) + 1)
            bucket.hits.append(now)
            return None

    def peek(self, key: str, tier: Tier, now: float) -> int | None:
        """Whether this caller is already over, without spending an attempt."""
        with self._lock:
            bucket = self._buckets.get((key, tier.name))
            if bucket is None:
                return None
            cutoff = now - tier.window_seconds
            while bucket.hits and bucket.hits[0] <= cutoff:
                bucket.hits.popleft()
            if len(bucket.hits) < tier.requests:
                return None
            return max(1, int(bucket.hits[0] + tier.window_seconds - now) + 1)

    def _sweep(self, now: float) -> None:
        """Drop buckets nobody has touched, so memory does not grow with IPs."""
        if now - self._last_swept < 300:
            return
        self._last_swept = now
        dead = [
            key
            for key, bucket in self._buckets.items()
            if not bucket.hits or bucket.hits[-1] < now - 3600
        ]
        for key in dead:
            del self._buckets[key]

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._last_swept = 0.0


_counter = _Counter()


def reset() -> None:
    """Clear all counters. For tests, so one does not leak into the next."""
    _counter.reset()


def _caller(request: Request) -> str:
    """Who to count against: the user if we know them, else the client IP.

    The bearer token identifies the caller without a database round trip in
    middleware. It is used only as a counting key -- never trusted as proof of
    identity, which the auth dependency does properly further down the stack.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return f"tok:{auth_header[7:][-32:]}"

    # X-Forwarded-For only when a proxy we configured is in front; otherwise a
    # caller could set the header themselves and get a fresh bucket per request.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and request.app.state.trust_proxy_header:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _refused(tier: Tier, retry_after: int) -> JSONResponse:
    """Says the limit and when to come back, so a caller can behave rather than
    guess. It does not say who was counted."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                f"Too many requests. This endpoint allows {tier.described}. "
                f"Try again in {retry_after}s."
            )
        },
        headers={"Retry-After": str(retry_after)},
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tier = tier_for(request.url.path)
        if tier is None:
            return await call_next(request)

        caller = _caller(request)
        now = time.time()

        # On the auth tier, only failures count. Brute force *is* failed
        # attempts, so budgeting successes protects nothing and punishes the
        # wrong people: locally every tool shares 127.0.0.1, and a few scripts
        # run back to back exhausted the allowance between them, which is how
        # a limiter ends up switched off. A guessing run never gets a success
        # to spend, so it still hits the wall at the same count.
        if tier is AUTH:
            retry_after = _counter.peek(caller, tier, now)
            if retry_after is not None:
                return _refused(tier, retry_after)
            response = await call_next(request)
            if response.status_code >= 400:
                _counter.hit(caller, tier, now)
            return response

        retry_after = _counter.hit(caller, tier, now)
        if retry_after is None:
            return await call_next(request)

        return _refused(tier, retry_after)
