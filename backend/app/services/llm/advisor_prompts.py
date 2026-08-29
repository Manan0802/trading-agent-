"""Narration about a goal plan, and the check that stops it inventing a number.

Every figure here is computed before the model is asked anything. The model's
only job is to put those figures in warm sentences — so the one failure that
matters is a sentence containing a number that is not in the payload.

`grounding.check` is what catches it, and the fallback is a template built from
the same numbers. That ordering is the whole AI design: the app is correct
without a model, and the model only ever makes it readable.
"""

import re

from app.services.llm.client import _FA_SYSTEM_PROMPT, call_llm
from app.services.llm.grounding import check

# The one sentence every projection has to carry. Enforced here rather than
# asked for in the prompt, because a prompt is a request.
#
# This was invisible while `groq_api_key` was empty: no model was ever called,
# every explanation came from the template below, and the template says it. The
# moment Gemini started answering, the model wrote a warm, correct-sounding
# paragraph that said "projected" and never said it was not guaranteed -- and a
# test that had passed for months began to fail. The prompt had been asking for
# this all along and getting it most of the time.
_DISCLAIMER = "Ye projected hai, guaranteed nahi — market ke hisaab se badal sakta hai."
_SAYS_IT = re.compile(r"guarantee", re.I)


def _with_disclaimer(text: str) -> str:
    """A projection that does not say it is a projection gets told to.

    Appended rather than regenerated: the model's sentences are about numbers
    this app already computed and they are fine, and asking again costs a
    request and may fail the same way.
    """
    if _SAYS_IT.search(text):
        return text
    return f"{text.rstrip()} {_DISCLAIMER}"



def get_goal_explanation(goal_data: dict, sip_result: dict, allocation: dict) -> str:
    """The plan in a few sentences, or the template when the model strays.

    The model is given six numbers and asked for prose. If what comes back
    contains a seventh, it is discarded — silently to the user, who gets the
    template, because a number this app cannot source is exactly the thing it
    exists not to show.
    """
    source = {
        "goal_name": goal_data["goal_name"],
        "target_amount": round(goal_data["target_amount"]),
        "years": goal_data["years"],
        "required_monthly_sip": round(sip_result["required_monthly_sip"]),
        "wealth_created": round(sip_result["wealth_created"]),
        "equity_pct": allocation["equity"],
        "debt_pct": allocation["debt"],
        "gold_pct": allocation["gold"],
    }
    msg = (
        f"Explain this financial goal plan in 3-4 warm Hinglish sentences.\n"
        f"Goal: {goal_data['goal_name']}\n"
        f"Target: Rs {goal_data['target_amount']:,.0f} in {goal_data['years']} years\n"
        f"Projected monthly SIP: Rs {sip_result['required_monthly_sip']:,.0f}\n"
        f"Allocation: {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold\n"
        f"Projected wealth created: Rs {sip_result['wealth_created']:,.0f}\n"
        f"Remember: say projected, never guaranteed."
    )
    out = call_llm(_FA_SYSTEM_PROMPT, msg)
    if out:
        narration = _with_disclaimer(out)
        # `check`, not `check_all`: there are no per-figure Claims here because
        # the model is not asked to cite anything, and check_claims on an empty
        # list would pass vacuously. What this catches is the real failure —
        # a rupee figure, a percentage or a horizon that is not one of the six
        # we handed it.
        verdict = check(narration, source)
        if verdict.ok:
            return narration
    return (
        f"Aapka goal '{goal_data['goal_name']}' ke liye projected monthly SIP "
        f"Rs {sip_result['required_monthly_sip']:,.0f} hai, {goal_data['years']} saal ke liye. "
        f"Paisa {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold "
        f"mein lagega. Ye projected hai, guaranteed nahi, market ke hisaab se badal sakta hai. "
        f"Disciplined raho, har mahine invest karo. 📈"
    )
