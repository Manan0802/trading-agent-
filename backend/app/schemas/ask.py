"""The shape of an answer, including the shape of a refusal.

A refusal is a first-class answer here, not an error. It has a reason, an id the
frontend can style, and no HTTP status that says something went wrong -- because
nothing did. Returning 4xx for "we will not answer that" makes a considered
position look like a malfunction.
"""

from pydantic import BaseModel, ConfigDict


class AskRequest(BaseModel):
    question: str


class AskOut(BaseModel):
    answer: str
    # "refused" | "grounded" | "unavailable"
    kind: str
    # Set when kind == "refused", so the screen can show WHICH position this is
    # and link to the reasoning rather than reprinting it.
    refusal_id: str | None = None
    # Whether a language model wrote any of this. False for every refusal, and
    # false when the model was unreachable and a template answered.
    #
    # Named `model_used` because that is what it means to a reader; pydantic
    # reserves the `model_` prefix for its own methods, so the namespace guard
    # is relaxed below rather than the field being renamed to something worse.
    model_used: bool = False
    # What the answer was checked against, when there was something to check.
    grounded: bool | None = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
