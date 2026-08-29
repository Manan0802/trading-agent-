"""No narration reaches a surface without being checked against its own numbers.

§9.1's open item was that `grounding.py` — 792 lines, 50 tests — had zero
non-test callers. Slice 1.4 made it one. This is the other: the goal explanation,
which is the app's oldest piece of model-written prose and was returned to the
screen unexamined.

The design it enforces: every figure is computed BEFORE the model is asked
anything, so the only failure that matters is a sentence carrying a number the
payload does not contain. When that happens the answer is discarded and the
template — built from the same six numbers — replies instead.
"""

import pytest

from app.services.llm import advisor_prompts
from app.services.llm.advisor_prompts import get_goal_explanation

_GOAL = {"goal_name": "Ghar", "target_amount": 5_000_000, "years": 10}
_SIP = {"required_monthly_sip": 21_000, "wealth_created": 2_480_000}
_ALLOC = {"equity": 70, "debt": 20, "gold": 10}


@pytest.mark.parametrize(
    "invented",
    [
        "Aapka SIP Rs 21,000 hai aur 10 saal mein Rs 99,99,999 milega.",
        "Rs 21,000 monthly, aur aapko 18% return milega har saal.",
        "Aapka SIP Rs 21,000 hai, 25 saal ke liye.",
        "Rs 35,000 monthly SIP chahiye.",
    ],
)
def test_a_number_that_is_not_in_the_payload_never_reaches_the_screen(
    monkeypatch, invented
):
    """A fabricated return, horizon or amount is the one thing this app exists
    not to show, and it is the thing a fluent model produces most easily."""
    monkeypatch.setattr(advisor_prompts, "call_llm", lambda *_a, **_k: invented)
    out = get_goal_explanation(_GOAL, _SIP, _ALLOC)
    assert out != invented
    assert "Aapka goal 'Ghar'" in out, "the template must answer instead"


def test_a_narration_built_only_from_the_payload_is_kept(monkeypatch):
    grounded = "Aapka SIP Rs 21,000 hai, 10 saal ke liye. 70% equity mein jayega."
    monkeypatch.setattr(advisor_prompts, "call_llm", lambda *_a, **_k: grounded)
    out = get_goal_explanation(_GOAL, _SIP, _ALLOC)
    assert out.startswith(grounded)


def test_the_check_is_wired_and_not_merely_imported():
    import inspect

    source = inspect.getsource(advisor_prompts.get_goal_explanation)
    assert "check(narration, source)" in source
    assert "if verdict.ok:" in source, (
        "the verdict must gate the return, or the check is decoration"
    )


def test_the_payload_carries_every_figure_the_prompt_states():
    """A number in the prompt and absent from the source is a number the model
    is invited to repeat and the checker will then reject."""
    import inspect

    source = inspect.getsource(advisor_prompts.get_goal_explanation)
    for field in (
        "goal_name",
        "target_amount",
        "years",
        "required_monthly_sip",
        "wealth_created",
        "equity_pct",
        "debt_pct",
        "gold_pct",
    ):
        assert f'"{field}"' in source, f"{field} is in the prompt and not the payload"
