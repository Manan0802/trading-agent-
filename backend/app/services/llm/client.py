"""One door to the model, and the fallback behind it.

Groq was the only provider and `Settings` declared only `groq_api_key`, which is
empty -- so every narration in this app has been silently returning "" and
falling through to a template. `GEMINI_API_KEY` sat in `.env` unread.

Gemini is tried first because it is the key that exists. Groq stays as a second
provider rather than being deleted: it costs four lines, and a narration layer
with exactly one provider fails completely the day that provider's free tier
changes.

**Returning "" is a supported outcome, not a failure.** Every caller has
template narration behind it, and the app's numbers are computed by code that
never involves a model -- the model only writes sentences about figures that are
already fixed. So a quota exhaustion costs prose and nothing else.
"""

from app.config import get_settings
from app.services.llm import gemini

_FA_SYSTEM_PROMPT = (
    "You are NexTrade's friendly Indian financial advisor. Explain financial plans "
    "in simple Hinglish (Hindi-English mix). Be warm, practical, concise (3-4 sentences). "
    "Never guarantee returns. Always say 'projected' not 'guaranteed'. Use emojis sparingly."
)


def call_llm(system_prompt: str, user_message: str) -> str:
    """The narration, or "" for the caller's template. Never raises.

    The blanket catch is the contract, not laziness. `gemini.generate` already
    handles the failures it can name -- HTTP errors, 429, a malformed body --
    but "never raises" has to hold for the ones nobody named: a client library
    that changes an exception type, a config error, an SSL failure at import.
    Every caller of this function is rendering a page whose numbers are already
    computed and already correct, so the worst acceptable outcome is plainer
    prose. A traceback here is a 500 on a page that had nothing wrong with it.
    """
    try:
        text = gemini.generate(system_prompt, user_message)
    except Exception:  # noqa: BLE001 -- see above
        text = None
    if text:
        return text
    return _groq(system_prompt, user_message)


def _groq(system_prompt: str, user_message: str) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        return ""  # caller supplies fallback
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_groq import ChatGroq

        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=settings.groq_api_key,
            temperature=0.1,
            max_tokens=500,
            timeout=30,
        )
        return llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        ).content
    except Exception:  # noqa: BLE001
        # A second provider that raises is worse than no second provider: it
        # turns a missing sentence into a 500 on a page whose numbers are fine.
        return ""
