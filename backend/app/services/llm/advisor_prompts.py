import re

from app.services.llm.client import _FA_SYSTEM_PROMPT, call_llm

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
        return _with_disclaimer(out)
    return (
        f"Aapka goal '{goal_data['goal_name']}' ke liye projected monthly SIP "
        f"Rs {sip_result['required_monthly_sip']:,.0f} hai, {goal_data['years']} saal ke liye. "
        f"Paisa {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold "
        f"mein lagega. Ye projected hai, guaranteed nahi, market ke hisaab se badal sakta hai. "
        f"Disciplined raho, har mahine invest karo. 📈"
    )
