"""Gemini, with the failure this app is actually going to hit: the free quota.

`services/llm/client.py` is 26 lines of Groq and `Settings` declared exactly one
key, `groq_api_key`, which is empty. `GEMINI_API_KEY` has been sitting in `.env`
unread. So the narration layer has been returning "" and falling back to
templates the whole time, correctly and silently.

**The free tier is the design constraint, not an edge case.** Gemini's free
quota is per-minute and per-day, and when it runs out the API answers 429 with
its own advice about when to come back:

    {"error": {"code": 429, "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo",
         "retryDelay": "37s"}]}}

Guessing a backoff when the server has just told you the number is how a free
quota turns into a ban. So `retryDelay` is parsed and honoured, and only when it
is absent does this fall back to doubling.

**And when the retries are exhausted, nothing breaks.** `generate` returns None,
never a partial or invented answer, and every caller already has template
narration behind it. That ordering is the point of the whole AI layer: the app's
numbers are computed by code that does not involve a model, and the model only
ever writes sentences about them. A quota exhaustion should cost the user some
prose and no correctness at all.
"""

import json
import re
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
_TIMEOUT = 30.0

# Three attempts, because a free-tier per-minute window refills in under a
# minute and a fourth wait is longer than a person will hold a page open.
_MAX_ATTEMPTS = 3
# Only used when the server does NOT say. If it does, its number wins.
_FALLBACK_BACKOFF = (2.0, 8.0)
# A per-minute quota refills in 60s; anything longer is the DAILY quota, and
# waiting for that on a page load is not a retry, it is a hang.
_MAX_HONOURED_DELAY = 60.0

_RETRY_DELAY = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')


@dataclass(frozen=True)
class Attempt:
    """What happened, so a caller can say why there is no narration."""

    ok: bool
    text: str | None = None
    status: int | None = None
    # Seconds the API asked us to wait, when it said.
    retry_after: float | None = None
    reason: str | None = None


def retry_delay_from(body: str) -> float | None:
    """The server's own `retryDelay`, in seconds, or None if it did not say.

    Parsed off the raw body rather than the decoded JSON because the field is
    buried in `error.details[]` behind a `@type` discriminator, and a shape
    change there would raise a KeyError in the middle of error handling -- which
    turns a rate limit into a crash.
    """
    match = _RETRY_DELAY.search(body or "")
    if not match:
        return None
    seconds = float(match.group(1))
    return seconds if 0 < seconds <= _MAX_HONOURED_DELAY else None


def generate(
    system_prompt: str,
    user_message: str,
    *,
    sleep=time.sleep,
    client: httpx.Client | None = None,
) -> str | None:
    """One narration, or None. None is a normal outcome and callers must handle it.

    `sleep` and `client` are injected so the retry path is reachable from a test
    without waiting or a network -- a backoff nobody has watched work is a
    backoff that does not work.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        return None

    owned = client is None
    http = client or httpx.Client(timeout=_TIMEOUT)
    try:
        for attempt in range(_MAX_ATTEMPTS):
            result = _once(http, settings, system_prompt, user_message)
            if result.ok:
                return result.text
            if result.status != 429 or attempt == _MAX_ATTEMPTS - 1:
                return None
            wait = result.retry_after
            if wait is None:
                wait = _FALLBACK_BACKOFF[min(attempt, len(_FALLBACK_BACKOFF) - 1)]
            sleep(wait)
        return None
    finally:
        if owned:
            http.close()


def _once(
    http: httpx.Client, settings, system_prompt: str, user_message: str
) -> Attempt:
    url = f"{_ENDPOINT}/{settings.gemini_model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        # Narration about numbers that are already fixed. Temperature exists to
        # vary wording, and there is nothing here worth varying.
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
    }
    try:
        response = http.post(
            url, json=payload, headers={"x-goog-api-key": settings.gemini_api_key}
        )
    except httpx.HTTPError as exc:
        return Attempt(ok=False, reason=f"{type(exc).__name__}: {exc}")

    if response.status_code == 429:
        return Attempt(
            ok=False,
            status=429,
            retry_after=retry_delay_from(response.text),
            reason="rate limited",
        )
    if response.status_code != 200:
        return Attempt(ok=False, status=response.status_code, reason=response.text[:200])

    text = _text_of(response.text)
    return Attempt(ok=text is not None, text=text, status=200, reason=None if text else "empty")


def _text_of(body: str) -> str | None:
    """The generated text, or None for anything that is not plainly one.

    Every step is guarded. A response that was cut off by a safety filter, or
    truncated, carries `candidates` with no `parts`, and reaching blindly into
    it raises inside the success path -- where the caller has already stopped
    expecting failure.
    """
    try:
        payload = json.loads(body)
    except ValueError:
        return None
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    parts = (candidates[0].get("content") or {}).get("parts")
    if not isinstance(parts, list) or not parts:
        return None
    text = parts[0].get("text")
    return text.strip() if isinstance(text, str) and text.strip() else None
