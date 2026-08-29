"""The Gemini client, tested against the failure it will actually meet: 429.

The free quota is the design constraint, not an edge case. Everything here runs
without a network and without waiting, because a backoff nobody has watched work
is a backoff that does not work.
"""

import json

import httpx
import pytest

from app.config import get_settings
from app.services.llm import gemini


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-one")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _ok(text: str = "Your fund costs more than its peers.") -> httpx.Response:
    return httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]}
    )


def _rate_limited(delay: str | None = "37s") -> httpx.Response:
    details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay}]
    body = {"error": {"code": 429, "message": "quota", "details": details if delay else []}}
    return httpx.Response(429, json=body)


def _client(responses: list[httpx.Response]) -> httpx.Client:
    queue = list(responses)

    def handler(_request: httpx.Request) -> httpx.Response:
        return queue.pop(0)

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestTheServersOwnRetryDelayIsHonoured:
    def test_it_is_parsed_out_of_the_error_details(self):
        body = json.dumps(
            {"error": {"details": [{"@type": "...RetryInfo", "retryDelay": "37s"}]}}
        )
        assert gemini.retry_delay_from(body) == 37.0

    def test_a_response_that_does_not_say_yields_none(self):
        assert gemini.retry_delay_from('{"error": {"code": 429}}') is None
        assert gemini.retry_delay_from("") is None
        assert gemini.retry_delay_from("not json at all") is None

    def test_a_daily_quota_delay_is_refused_rather_than_slept_through(self):
        """A per-minute window refills in under 60s. Anything longer is the DAILY
        quota, and waiting for that on a page load is not a retry, it is a hang."""
        body = '{"error": {"details": [{"retryDelay": "3600s"}]}}'
        assert gemini.retry_delay_from(body) is None

    def test_a_forced_429_is_retried_using_the_number_the_api_gave(self):
        slept: list[float] = []
        result = gemini.generate(
            "sys",
            "msg",
            sleep=slept.append,
            client=_client([_rate_limited("37s"), _ok("recovered")]),
        )
        assert result == "recovered"
        assert slept == [37.0], (
            "guessing a backoff when the server has just told you the number is "
            "how a free quota turns into a ban"
        )

    def test_it_falls_back_to_doubling_only_when_the_api_stays_quiet(self):
        slept: list[float] = []
        result = gemini.generate(
            "sys",
            "msg",
            sleep=slept.append,
            client=_client([_rate_limited(None), _rate_limited(None), _ok("third")]),
        )
        assert result == "third"
        assert slept == [2.0, 8.0]


class TestExhaustionCostsProseAndNothingElse:
    def test_three_rate_limits_yield_none_not_a_partial_answer(self):
        slept: list[float] = []
        result = gemini.generate(
            "sys",
            "msg",
            sleep=slept.append,
            client=_client([_rate_limited("1s")] * 3),
        )
        assert result is None, (
            "None is the contract. A partial or invented sentence about real "
            "money is worse than no sentence"
        )
        assert len(slept) == 2, "no sleep after the final attempt"

    def test_a_non_429_error_is_not_retried(self):
        """A 400 will be a 400 again. Retrying it spends quota to learn nothing."""
        slept: list[float] = []
        result = gemini.generate(
            "sys", "msg", sleep=slept.append,
            client=_client([httpx.Response(400, json={"error": {"code": 400}})]),
        )
        assert result is None
        assert slept == []

    def test_a_network_failure_returns_none_rather_than_raising(self):
        def boom(_request):
            raise httpx.ConnectError("no route to host")

        result = gemini.generate(
            "sys", "msg", sleep=lambda _s: None,
            client=httpx.Client(transport=httpx.MockTransport(boom)),
        )
        assert result is None

    def test_no_key_means_no_call_at_all(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        get_settings.cache_clear()

        def explode(_request):
            raise AssertionError("called the API with no key")

        assert gemini.generate(
            "sys", "msg", client=httpx.Client(transport=httpx.MockTransport(explode))
        ) is None


class TestAResponseThatIsNotPlainlyTextIsNotText:
    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"candidates": []},
            # Cut off by a safety filter: candidates present, no parts.
            {"candidates": [{"finishReason": "SAFETY"}]},
            {"candidates": [{"content": {}}]},
            {"candidates": [{"content": {"parts": []}}]},
            {"candidates": [{"content": {"parts": [{"text": "   "}]}}]},
        ],
    )
    def test_it_returns_none_instead_of_raising_inside_the_success_path(self, payload):
        result = gemini.generate(
            "sys", "msg", sleep=lambda _s: None,
            client=_client([httpx.Response(200, json=payload)]),
        )
        assert result is None

    def test_a_real_answer_comes_back_stripped(self):
        result = gemini.generate(
            "sys", "msg", sleep=lambda _s: None, client=_client([_ok("  spaced  ")])
        )
        assert result == "spaced"


def test_the_key_is_sent_as_a_header_not_in_the_url():
    """A key in a query string lands in every proxy log and referrer header."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["header"] = request.headers.get("x-goog-api-key")
        return _ok()

    gemini.generate(
        "sys", "msg", sleep=lambda _s: None,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert seen["header"] == "test-key-not-a-real-one"
    assert "test-key-not-a-real-one" not in seen["url"]
    assert "key=" not in seen["url"]


def test_the_model_comes_from_configuration_not_from_a_constant():
    """This repo's .env selects gemini-3.1-flash-lite; a fresh checkout gets a
    Flash default. Hardcoding either one strands the other."""
    import os

    from app.services.llm import gemini as mod

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return _ok()

    os.environ["GEMINI_MODEL"] = "some-model-name"
    get_settings.cache_clear()
    try:
        mod.generate(
            "sys", "msg", sleep=lambda _s: None,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    finally:
        os.environ.pop("GEMINI_MODEL", None)
        get_settings.cache_clear()
    assert "some-model-name:generateContent" in seen["url"]
