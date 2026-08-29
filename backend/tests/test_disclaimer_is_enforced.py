"""A projection has to say it is a projection, and the prompt cannot be trusted to.

This one hid for months. `Settings` declared only `groq_api_key`, it was empty,
so no model was ever called and every explanation came from the template — which
says it. The day Gemini started answering, the model produced a warm and
otherwise correct paragraph that said "projected" and never said "not
guaranteed", and a test that had been green for months went red.

The prompt had been asking for it the whole time. It was getting it most of the
time. Most of the time is not a property you can ship on a page about somebody's
money.
"""

from app.services.llm import advisor_prompts
from app.services.llm.advisor_prompts import get_goal_explanation

_GOAL = {"goal_name": "House", "target_amount": 2_000_000, "years": 5}
_SIP = {"required_monthly_sip": 25_000, "wealth_created": 500_000}
_ALLOC = {"equity": 50, "debt": 40, "gold": 10}


def test_a_model_answer_that_omits_the_disclaimer_gets_it_added(monkeypatch):
    """Every figure in the stub is one of the six handed to the model.

    A first version of this test used "₹5 lakh", which is not in the payload —
    so `grounding.check` discarded the whole answer and the template replied,
    and the test failed for a better reason than the one it was written for.
    """
    monkeypatch.setattr(
        advisor_prompts,
        "call_llm",
        lambda *_a, **_k: "Aapka SIP Rs 25,000 hai, 5 saal ke liye.",
    )
    out = get_goal_explanation(_GOAL, _SIP, _ALLOC)
    assert "guaranteed nahi" in out
    assert out.startswith("Aapka SIP Rs 25,000"), "the model's own sentences survive"


def test_a_model_answer_that_already_says_it_is_left_alone(monkeypatch):
    answer = "Ye projected hai, guaranteed nahi. SIP Rs 25,000."
    monkeypatch.setattr(advisor_prompts, "call_llm", lambda *_a, **_k: answer)
    assert get_goal_explanation(_GOAL, _SIP, _ALLOC) == answer, (
        "appending a second disclaimer reads as a stutter and trains people to "
        "skip the line"
    )


def test_the_template_already_carried_it(monkeypatch):
    monkeypatch.setattr(advisor_prompts, "call_llm", lambda *_a, **_k: "")
    out = get_goal_explanation(_GOAL, _SIP, _ALLOC)
    assert "guaranteed nahi" in out


def test_it_is_enforced_in_code_not_asked_for_in_the_prompt():
    """A prompt is a request. This has to hold when the model ignores it."""
    import inspect

    source = inspect.getsource(advisor_prompts)
    assert "_with_disclaimer(out)" in source, (
        "the model's answer is returned unchecked, so the disclaimer is back to "
        "being whatever the model felt like writing"
    )
