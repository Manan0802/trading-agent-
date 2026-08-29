"""Which companies you actually own, and how much of your money is in each.

Someone holding five equity funds does not own five things. They own a few
hundred companies, several of them through four funds at once, and the position
that matters is invisible on every screen they have: HDFC Bank at 7% of one
fund, 9% of another and 6% of a third is one bet, not three.

This is the arithmetic that makes it visible. Fund value x holding weight,
summed by ISIN.

**Its most important output is what it could NOT see.** Holdings come from AMC
monthly disclosures and seven AMCs have a verified source, covering 482 of the
1,659 buyable funds. So a real portfolio will routinely have funds this cannot
open. A look-through that quietly reports only what it could read tells someone
their largest position is HDFC Bank at 4% when the true answer might be anything
-- and it looks exactly like a complete answer.

So every result carries `covered_value` and `unopened`, and a caller that omits
them is publishing a number it has no right to. The §14 rule, applied to the one
place in this app where a partial answer is indistinguishable from a full one.
"""

from dataclasses import dataclass, field

from app.services.marketdata import holdings_store


@dataclass(frozen=True)
class Company:
    """One company, and the money reaching it through every fund that holds it."""

    isin: str
    name: str
    industry: str | None
    value: float
    # Which funds it arrives through, heaviest first. This is the sentence worth
    # showing: "through 4 of your funds".
    via: tuple[tuple[str, float], ...]

    @property
    def fund_count(self) -> int:
        return len(self.via)


@dataclass(frozen=True)
class LookThrough:
    companies: tuple[Company, ...]
    # The rupee value of funds whose holdings we could actually read.
    covered_value: float
    # And of those we could not, with their names.
    unopened_value: float
    unopened: tuple[str, ...] = ()

    @property
    def total_value(self) -> float:
        return self.covered_value + self.unopened_value

    @property
    def covered_share(self) -> float:
        """0-100. The honesty number: what fraction of the portfolio this saw."""
        total = self.total_value
        return 0.0 if total <= 0 else self.covered_value / total * 100.0

    def share_of_portfolio(self, company: Company) -> float:
        """A company's weight against the WHOLE portfolio, not just the opened part.

        Dividing by `covered_value` would inflate every position by however much
        of the portfolio we failed to read -- and inflate it most exactly when
        coverage is worst, which is when the number is least trustworthy.
        """
        total = self.total_value
        return 0.0 if total <= 0 else company.value / total * 100.0


def look_through(holdings: list[tuple[str, float]]) -> LookThrough:
    """`[(scheme name, value in rupees)]` -> the companies behind them.

    Weights are percentages of net assets, so a fund's contribution to one
    company is `value * weight / 100`. The part of a fund the disclosure does
    not account for -- cash, debt, derivatives -- simply does not appear as any
    company, which is correct: it is not equity in anything.
    """
    totals: dict[str, dict] = {}
    covered = unopened_value = 0.0
    unopened: list[str] = []

    for scheme_name, value in holdings:
        if value <= 0:
            continue
        portfolio = holdings_store.load(scheme_name)
        if portfolio is None or not portfolio.holdings:
            unopened_value += value
            unopened.append(scheme_name)
            continue
        covered += value
        for holding in portfolio.holdings:
            if not holding.isin or holding.weight <= 0:
                continue
            rupees = value * holding.weight / 100.0
            row = totals.setdefault(
                holding.isin,
                {"name": holding.name, "industry": holding.industry,
                 "value": 0.0, "via": []},
            )
            row["value"] += rupees
            row["via"].append((scheme_name, rupees))

    companies = tuple(
        Company(
            isin=isin,
            name=row["name"],
            industry=row["industry"],
            value=row["value"],
            via=tuple(sorted(row["via"], key=lambda v: -v[1])),
        )
        for isin, row in sorted(totals.items(), key=lambda kv: -kv[1]["value"])
    )
    return LookThrough(
        companies=companies,
        covered_value=covered,
        unopened_value=unopened_value,
        unopened=tuple(unopened),
    )


def concentrated(result: LookThrough, threshold_pct: float = 5.0) -> tuple[Company, ...]:
    """Companies above `threshold_pct` of the whole portfolio, heaviest first.

    Reported only when it is a real finding: a single stock past 5% of everything
    someone owns is a concentration they chose by accident, through funds that
    each looked diversified.
    """
    return tuple(
        c for c in result.companies if result.share_of_portfolio(c) >= threshold_pct
    )
