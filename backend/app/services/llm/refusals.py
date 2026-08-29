"""The nine things this app will not answer, enforced before the model runs.

§5 lists nine features a reviewer will ask for, each with a reason it is absent.
Every one of them is also a QUESTION a user will type, and a language model asked
"should I sell my worst fund?" will answer it — fluently, plausibly, and against
a measurement this repo already ran.

**So the refusal is code, and it runs first.** Not a line in a system prompt.
A prompt is a request; this is a gate. The model is never called for a refused
question, which means no amount of rephrasing, insistence or context-stuffing
can talk it into an answer that does not exist.

**Each refusal carries the reason, not an apology.** "I can't help with that"
teaches nothing and reads as a limitation. "Ranking on past three-year return put
the WORSE quartile on top by 0.9pp, measured here over 44 windows" tells the
person something true, and it is the more useful answer even though it is not
the one they asked for.

The matcher is deliberately narrow. A refusal that fires on an innocent question
is worse than one that misses: it trains the user that the app is evasive, and
they stop asking it anything.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Refusal:
    """One thing this app will not say, and what it says instead."""

    id: str
    answer: str
    # What the question has to look like. All groups must match, so a rule needs
    # both the SUBJECT and the ASK -- "underperforming" alone is a description,
    # "should I sell my underperforming fund" is a request for a verdict.
    patterns: tuple[re.Pattern, ...]

    def matches(self, question: str) -> bool:
        return all(p.search(question) for p in self.patterns)


def _p(*sources: str) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(s, re.I) for s in sources)


_SELL_VERB = r"\b(sell|exit|switch out|redeem|get rid of|dump|book out|move out)\b"
_ASK = r"\b(should|shall|do i|can i|is it|worth|advice|advise|recommend|ought)\b"

REFUSALS: tuple[Refusal, ...] = (
    Refusal(
        id="sell-the-underperformer",
        patterns=_p(
            _SELL_VERB,
            r"\b(underperform\w*|worst|laggard|loser|bad performer|not performing"
            r"|poor(?:ly)? performing|weakest)\b",
        ),
        answer=(
            "We do not rank funds for selling on past performance, and the reason "
            "is a measurement rather than caution. Sorting funds by past "
            "three-year return put the WORSE quartile on top by 0.9 percentage "
            "points, and won only 19 of 44 windows — worse than a coin toss. The "
            "separate exit-signal test could not support any threshold at all. "
            "What does hold up is cost: switch to the direct plan of the same "
            "fund, and prefer cheaper funds inside the same category."
        ),
    ),
    Refusal(
        id="sell-the-winner",
        patterns=_p(
            _SELL_VERB,
            r"\b(winner|best perform\w*|top perform\w*|outperform\w*|has run up"
            r"|gone up a lot|rallied)\b",
        ),
        answer=(
            "No — and this one is refused despite the evidence pointing that way, "
            "which is worth saying plainly. The strongest column in our own table "
            "suggests trimming winners, but it is one measurement, only two of "
            "twelve intervals exclude zero, and there is no multiple-testing "
            "correction. A sell rule is the most expensive kind to get wrong, so "
            "it needs more than one suggestive result."
        ),
    ),
    Refusal(
        id="concentration-limit",
        patterns=_p(
            r"\b(too concentrated|over.?concentrated|concentration limit"
            r"|diversif\w*|too few (?:stocks|holdings)|concentrated)\b",
            _ASK + r"|" + _SELL_VERB,
        ),
        answer=(
            "We will show you what you actually own through your funds, including "
            "any company that is a large share of everything — that is a fact and "
            "you should see it. We will not call a fund too concentrated and tell "
            "you to exit. The published evidence runs the other way: Kacperczyk, "
            "Sialm and Zheng (2005) and Cremers and Petajisto (2009) both find "
            "concentrated, high-Active-Share funds outperform."
        ),
    ),
    Refusal(
        id="trailing-stop",
        patterns=_p(r"\b(trailing stop|stop.?loss|stop loss)\b"),
        answer=(
            "No stop-losses. The research people cite for them (Kaminski and Lo, "
            "2014) is real, and it was tested on index futures — not on "
            "long-horizon retail fund holdings, which is what you have. Applying "
            "it here would be borrowing a result from a different instrument and "
            "a different holding period."
        ),
    ),
    Refusal(
        id="price-alerts",
        patterns=_p(
            r"\b(price alert|daily p&l|daily pnl|streak|notify me when"
            r"|alert me when|push notification)\b"
        ),
        answer=(
            "No price alerts, streaks or daily profit-and-loss on the home "
            "screen. Not a technical limit — checking more often is associated "
            "with trading more and earning less, and a screen that rewards you "
            "for looking is working against the one behaviour that actually "
            "compounds."
        ),
    ),
    Refusal(
        id="aum-bloat-threshold",
        patterns=_p(
            r"\b(aum|fund size|too big|asset size|size limit)\b",
            r"\b(threshold|limit|too (?:big|large)|max|cap|cutoff|above)\b",
        ),
        answer=(
            "A fund getting very large probably does hurt returns — two "
            "top-journal papers eleven years apart point the same way. But "
            "neither gives a number we could verify, so we will not invent a "
            "cutoff and tell you your fund crossed it. You will see the fund's "
            "size as a fact, without a verdict attached."
        ),
    ),
    Refusal(
        id="manager-change-action",
        patterns=_p(
            r"\b(fund manager|manager (?:change|left|quit|exit|departure)"
            r"|new manager)\b",
            _ASK + r"|" + _SELL_VERB,
        ),
        answer=(
            "We will tell you the manager changed and when — that is a fact worth "
            "knowing. We will not tell you to act on it. We tried four times to "
            "find the research on manager departures and retail outcomes and could "
            "not verify it, and an unverified rule about when to move real money "
            "is not something to ship. This is a gap in what we checked, not "
            "evidence that manager changes do not matter."
        ),
    ),
    Refusal(
        id="behaviour-gap-number",
        patterns=_p(
            r"\b(behaviou?r gap|investor gap|dalbar|how much do investors lose"
            r"|average investor (?:loses|underperform\w*))\b"
        ),
        answer=(
            "There is no number here we would stand behind. Morningstar puts the "
            "gap at −1.2 percentage points; Fulkerson and co-authors (2026) found "
            "three methodology errors that cut it to 0.03%; DALBAR's often-quoted "
            "~6 points compares a lump-sum investor to someone investing monthly, "
            "which is not the same person. The direction is probably real. The "
            "magnitude is contested, so no figure goes on screen."
        ),
    ),
    Refusal(
        id="place-an-order",
        patterns=_p(
            r"\b(buy|sell|invest|place|execute|start|stop|redeem)\b",
            r"\b(order|sip|trade|transaction|for me|on my behalf|automatically)\b",
            r"\b(place|execute|do it|go ahead|book|start|stop|set up)\b",
        ),
        answer=(
            "This app never places an order. It is advisory only, by design and "
            "not by oversight: the layer that picks funds is right about 64% of "
            "the time, and something that is right 64% of the time does not get "
            "to move your money. Everything here is a recommendation you carry "
            "out yourself."
        ),
    ),
    Refusal(
        id="groww-rating-as-a-rating",
        patterns=_p(r"\bgroww (?:rating|star|score)\b"),
        answer=(
            "We do not show Groww's rating as a rating. It is the platform's own "
            "score for funds it sells, which is a conflict we cannot audit, and "
            "we have no way to check what it measures."
        ),
    ),
)


def refusal_for(question: str) -> Refusal | None:
    """The first refusal this question triggers, or None.

    Order matters only where two could match. `sell-the-winner` sits after
    `sell-the-underperformer` because "should I sell my worst performer" contains
    neither winner word, and the reverse is also true -- they are disjoint by
    construction rather than by ordering luck.
    """
    text = question or ""
    for rule in REFUSALS:
        if rule.matches(text):
            return rule
    return None
