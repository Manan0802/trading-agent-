"""How much of a fund you are considering you already own.

The question `Find` cannot answer today, and the one that decides whether adding
a fund does anything. Somebody holding two large-cap funds who buys a third is
usually buying the same thirty companies a third time -- and every screen in
this app, including the ranking, will tell them the third fund is good.

**The answer is a share of THE FUND YOU ARE LOOKING AT.** "You already hold 61%
of this fund" means: sum the weights of its positions that you reach through
something you own. Measuring it the other way round -- what share of the user's
portfolio this fund covers -- answers a different question and is smaller for a
big portfolio, which is exactly backwards.

**Unmeasured is `None`, and never 0.** 0% reads as perfectly diversified, which
is the opposite of "we could not tell", and it is the more attractive of the two
readings -- so the failure silently encourages the purchase. Seven AMCs have a
verified monthly disclosure, so this returns None often.
"""

from dataclasses import dataclass

from app.services.marketdata import holdings_store


@dataclass(frozen=True)
class Overlap:
    """What share of a candidate fund the user already reaches, and through what."""

    # 0-100, or None when either side is unreadable. NEVER 0 for unknown.
    share_pct: float | None
    # The funds it arrives through, heaviest overlap first.
    through: tuple[tuple[str, float], ...]
    # Named so a surface can say WHY there is no number.
    reason: str | None = None

    @property
    def measured(self) -> bool:
        return self.share_pct is not None


def overlap_with_holdings(candidate_name: str, held_names: list[str]) -> Overlap:
    """`candidate` against everything already held, as a share of the candidate."""
    candidate = holdings_store.load(candidate_name)
    if candidate is None or not candidate.holdings:
        return Overlap(
            share_pct=None,
            through=(),
            reason=(
                "This fund's AMC does not publish a monthly portfolio we can "
                "read, so we cannot tell how much of it you already own."
            ),
        )

    held = [(name, holdings_store.load(name)) for name in held_names]
    readable = [(name, p) for name, p in held if p is not None and p.holdings]
    if not readable:
        return Overlap(
            share_pct=None,
            through=(),
            reason=(
                "None of the funds you hold publishes a portfolio we can read, "
                "so we cannot tell how much of this one you already own."
                if held_names
                else "You do not hold any funds yet, so there is nothing to overlap with."
            ),
        )

    weights = {h.isin: h.weight for h in candidate.holdings if h.isin}
    reached: dict[str, float] = {}
    through: list[tuple[str, float]] = []
    for name, portfolio in readable:
        # The share of the CANDIDATE that this one fund reaches. Summed across
        # funds it would double-count a company two of them both hold, so the
        # total is taken over the union instead.
        own = 0.0
        for holding in portfolio.holdings:
            weight = weights.get(holding.isin)
            if weight is None:
                continue
            own += weight
            reached[holding.isin] = weight
        if own > 0:
            through.append((name, round(own, 2)))

    return Overlap(
        share_pct=round(sum(reached.values()), 2),
        through=tuple(sorted(through, key=lambda t: -t[1])),
        reason=None,
    )
