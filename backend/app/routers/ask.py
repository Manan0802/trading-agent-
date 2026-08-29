"""One question in, one answer out — with the refusals enforced before the model.

The ordering is the whole design. §5 lists nine things this app will not say,
and a language model asked any of them will answer: fluently, plausibly, and
against measurements this repo already ran. Putting those rules in a system
prompt makes them a request. Putting them here makes them a gate.

So a refused question never reaches a model at all. That is not caution about
tone, it is the difference between a rule and a suggestion: no amount of
rephrasing, insistence or context-stuffing can produce an answer the app has
decided does not exist.

What is NOT here yet, stated rather than implied: the tool layer. §3.2's
eighteen tools do not exist, so a question that is not refused gets the honest
"we cannot answer that yet" rather than a model improvising over a portfolio it
was never handed. An AI layer that hallucinates a number is worse than one that
says nothing, and this app already knows what its numbers are worth.
"""

from fastapi import APIRouter

from app.schemas.ask import AskOut, AskRequest
from app.services.llm.refusals import refusal_for

router = APIRouter(tags=["ask"])

_NO_TOOLS_YET = (
    "We can't answer that one yet. This app only says things it can check "
    "against your own numbers, and the layer that hands those numbers to the "
    "explainer is still being built — so rather than improvise, it says so. "
    "Everything on the portfolio and screener pages is already computed and "
    "already correct."
)


@router.post("/ask", response_model=AskOut)
def ask(req: AskRequest) -> AskOut:
    question = (req.question or "").strip()
    if not question:
        return AskOut(
            answer="Ask me something about your portfolio, a fund, or your tax.",
            kind="unavailable",
        )

    refusal = refusal_for(question)
    if refusal is not None:
        # No model call. Deliberately not even for phrasing: a model asked to
        # "say this nicely" reliably softens a refusal into a maybe.
        return AskOut(answer=refusal.answer, kind="refused", refusal_id=refusal.id)

    return AskOut(answer=_NO_TOOLS_YET, kind="unavailable")
