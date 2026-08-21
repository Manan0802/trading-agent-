"""Turning a fund's numbers into sentences a person can read once and follow.

Every screen in this app already leads with a sentence and puts the arithmetic
one click behind -- that is what `Plain` is for. This is the same idea applied to
a fund's own page, and the sentences live here rather than in JSX for three
reasons: they are claims about data and belong where pytest can hold them to
fixtures; two screens quoting the same fact must not word it differently; and
the frontend has no test runner.

The rule for every sentence below: **say what happened, in rupees or in plain
comparison, before naming the statistic.** "Sortino 1.59" is a fact about a
formula. "It made money in every one of the last 1,204 twelve-month stretches"
is a fact about the fund, and it is the same underlying data.

Nothing here rounds away a caveat. A fund younger than the period says so, a
missing number produces no sentence at all rather than a hedged one, and no
sentence is generated from data the fund does not have.
"""

from __future__ import annotations


def _inr(amount: float) -> str:
    """Indian digit grouping: 2,21,766 rather than 221,766.

    A rupee figure written the international way is read wrong by the people
    this is for -- 12,50,000 and 1,250,000 are the same number and only one of
    them parses at a glance here.
    """
    whole = int(round(amount))
    sign = "-" if whole < 0 else ""
    digits = str(abs(whole))
    if len(digits) <= 3:
        return f"{sign}{digits}"
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return f"{sign}{','.join(parts)},{tail}"


def rupees(amount: float | None) -> str | None:
    return None if amount is None else f"₹{_inr(amount)}"


def cost_sentence(cost) -> str | None:
    """What the fund costs, and what the direct plan is worth.

    Led with the rupee figure because a percentage point a year does not feel
    like anything. It is the number this project measured as most predictive, so
    it is the one sentence on the page that is worth reading twice.
    """
    if cost.direct_ter is None:
        return None
    base = f"This fund charges {cost.direct_ter:.2f}% a year in the direct plan"
    if cost.regular_ter is None or not cost.saving_pct_per_year:
        return base + "."
    return (
        f"{base}, against {cost.regular_ter:.2f}% if you buy it through a "
        f"distributor. On ₹1 lakh left alone for ten years, that "
        f"{cost.saving_pct_per_year:.2f}% difference is about "
        f"{rupees(cost.saving_on_a_lakh_over_10y)} — money that goes to you "
        f"instead of to fees."
    )


def calculator_sentence(rows) -> str | None:
    """The longest period the fund has actually lived, in rupees."""
    usable = [r for r in rows if r.value is not None]
    if not usable:
        return None
    row = max(usable, key=lambda r: r.actual_years or 0)
    direction = "would be worth" if row.value >= row.invested else "would have shrunk to"
    if row.full_period:
        opening = f"{rupees(row.invested)} put in {row.years} years ago"
    else:
        # The fund is younger than any period offered, so name its own age
        # rather than a period it never lived. An earlier version read
        # "put in when it launched, 2.9 years ago would be worth", which is
        # two clauses fighting over one comma.
        opening = (
            f"{rupees(row.invested)} put in at launch "
            f"{row.actual_years:.1f} years ago"
        )
    return f"{opening} {direction} {rupees(row.value)} today."


def rolling_sentence(rolling) -> str | None:
    """Every entry date, not one.

    A headline "1-year return" is whatever happened to one person who bought on
    one day. This is the same question asked on every day the fund has existed,
    which is the honest version and usually the more sobering one.
    """
    if not rolling.get("windows"):
        return None
    windows = rolling["windows"]
    worst, best = rolling["worst"], rolling["best"]
    median, positive = rolling["median"], rolling["positive_share"]

    if positive >= 0.999:
        outcome = "every single one of them made money"
    elif positive <= 0.001:
        outcome = "not one of them made money"
    else:
        outcome = f"{positive:.0%} of them made money and {1 - positive:.0%} lost"

    return (
        f"Someone could have bought this fund on any of {windows:,} days and held "
        f"it a year. {outcome[0].upper() + outcome[1:]}. The worst of those years "
        f"returned {worst:+.1%}, the best {best:+.1%}, and the middle one "
        f"{median:+.1%}."
    )


def drawdown_sentence(fund) -> str | None:
    """The fall, in words. A percentage does not convey sitting through it."""
    worst = getattr(fund, "max_drawdown", None)
    if worst is None:
        return None
    fell = abs(worst)
    if fell < 0.02:
        return "It has never fallen more than 2% below its own high."
    return (
        f"At its worst, this fund was {fell:.0%} below its own previous high. "
        f"₹1 lakh would have shown as {rupees(100_000 * (1 - fell))} at that "
        f"point, and staying invested was the only way back."
    )


def peer_sentence(total_return, peer_return, peers_compared, clipped) -> str | None:
    """Did it beat the funds it actually competes with?

    Against its own category, never against the Nifty. Telling someone their
    liquid fund lagged an equity index is true and useless.
    """
    if total_return is None or peer_return is None or not peers_compared:
        return None
    gap = total_return - peer_return
    verb = "ahead of" if gap > 0 else "behind"
    window = (
        " over the period this fund has existed, which is shorter than the range "
        "you picked"
        if clipped
        else ""
    )
    return (
        f"It returned {total_return:+.1%} against {peer_return:+.1%} for the "
        f"middle fund in its category{window} — {abs(gap):.1%} {verb} "
        f"{peers_compared} funds doing the same job."
    )


def holdings_sentence(holdings) -> str | None:
    """What it actually owns, and how concentrated that is."""
    if not holdings.covered or not holdings.top:
        return None
    top_five = sum(h.weight for h in holdings.top[:5])
    biggest_industry = holdings.by_industry[0] if holdings.by_industry else None
    parts = [
        f"It holds {holdings.total_positions} companies, and the largest five are "
        f"{top_five:.0f}% of the fund."
    ]
    if biggest_industry:
        parts.append(
            f"{biggest_industry[1]:.0f}% of it sits in {biggest_industry[0].lower()}."
        )
    if top_five >= 40:
        parts.append("That is a concentrated fund; a few names will drive the result.")
    return " ".join(parts)


def risk_sentence(fund) -> str | None:
    """Volatility as a range, not a number.

    "Volatility 17.5%" means nothing to most readers. The same figure expressed
    as a normal year's swing is immediately legible.
    """
    vol = getattr(fund, "volatility", None)
    tier = getattr(fund, "risk_tier", None)
    if vol is None:
        return None
    swing = vol * 100
    band = f"{tier.lower()} risk" if tier else "this risk level"
    return (
        f"In a normal year this fund moves about {swing:.0f}% either way, which "
        f"is what {band} means here. A bad year can be worse than that, and has "
        f"been."
    )
