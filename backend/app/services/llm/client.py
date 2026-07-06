from app.config import get_settings

_FA_SYSTEM_PROMPT = (
    "You are NexTrade's friendly Indian financial advisor. Explain financial plans "
    "in simple Hinglish (Hindi-English mix). Be warm, practical, concise (3-4 sentences). "
    "Never guarantee returns. Always say 'projected' not 'guaranteed'. Use emojis sparingly."
)


def call_llm(system_prompt: str, user_message: str) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        return ""  # caller supplies fallback
    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage

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
