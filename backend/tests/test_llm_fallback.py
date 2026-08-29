"""The narration layer degrades to templates, and the numbers never move.

The app's figures are computed by code that never involves a model. The model
only writes sentences about numbers that are already fixed. So the contract is
narrow and absolute: when the model is unavailable the prose gets simpler and
nothing else changes.
"""

from app.config import get_settings
from app.services.llm import client
from app.services.llm.advisor_prompts import get_goal_explanation

_GOAL = {"goal_name": "Ghar", "target_amount": 5_000_000, "years": 10}
_SIP = {"required_monthly_sip": 21_000, "wealth_created": 2_480_000}
_ALLOC = {"equity": 70, "debt": 20, "gold": 10}


def test_the_template_carries_the_same_numbers_the_model_would_have(monkeypatch):
    monkeypatch.setattr(client.gemini, "generate", lambda *_a, **_k: None)
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    try:
        out = get_goal_explanation(_GOAL, _SIP, _ALLOC)
    finally:
        get_settings.cache_clear()

    assert "21,000" in out and "10 saal" in out
    assert "70% equity" in out
    assert "projected hai, guaranteed nahi" in out, (
        "the fallback must keep the disclaimer the prompt asks the model for; "
        "losing it when the model is down is losing it exactly when nobody looks"
    )


def test_a_model_that_answers_is_used(monkeypatch):
    monkeypatch.setattr(
        client.gemini, "generate", lambda *_a, **_k: "Aapka ghar ka plan theek hai."
    )
    out = get_goal_explanation(_GOAL, _SIP, _ALLOC)
    assert out.startswith("Aapka ghar ka plan theek hai."), "the model's words survive"
    assert "guaranteed nahi" in out, (
        "and the disclaimer is added, because the model did not write one — see "
        "test_disclaimer_is_enforced.py"
    )


def test_a_second_provider_that_explodes_becomes_a_template_not_a_500(monkeypatch):
    """A fallback that raises is worse than no fallback: it turns a missing
    sentence into a 500 on a page whose numbers are correct."""
    monkeypatch.setattr(client.gemini, "generate", lambda *_a, **_k: None)
    monkeypatch.setenv("GROQ_API_KEY", "looks-real-but-is-not")
    get_settings.cache_clear()
    try:
        out = get_goal_explanation(_GOAL, _SIP, _ALLOC)
    finally:
        get_settings.cache_clear()
    assert "21,000" in out


def test_call_llm_never_raises(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(client.gemini, "generate", boom)
    try:
        client.call_llm("sys", "msg")
    except RuntimeError:
        raise AssertionError(
            "the narration layer must not be able to take down a page whose "
            "numbers are already computed"
        ) from None
