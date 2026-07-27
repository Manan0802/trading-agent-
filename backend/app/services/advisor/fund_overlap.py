"""Whether the funds someone holds are actually different from each other.

The usual product here is a holdings-overlap calculator: pull both funds'
portfolios and report the percentage of stocks they share. We cannot build that
one honestly. There is no holdings feed — mfapi has no such endpoint, Kuvera
returns an empty list, AMFI's monthly-portfolio page is gone — and what remains
is scraping a different spreadsheet layout from every AMC once a month.

So this measures the thing holdings overlap is a proxy for. Two funds are the
same position when they move together, and NAV history says that directly, for
every fund, without a new data source. It is also the better measure: two funds
can hold different mid-caps and still be one bet, and holdings overlap would
call them diversified.

What it deliberately does not do is treat correlation as a fault. Two equity
funds correlating 0.97 is not a defect, it is what equity does. The finding is
comparative — a second flexi-cap adds nothing a first one did not, while a debt
fund at 0.2 is doing real work — and the action is to hold fewer funds, not
better ones.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np

from app.services.marketdata.mutual_fund import NavPoint

# Below this the correlation is an accident of a short shared window rather
# than a description of how the two funds behave.
MIN_MONTHS = 24

# Above this, holding both is one position with two account statements, two
# sets of paperwork and two exit loads to track.
DUPLICATE_ABOVE = 0.90


@dataclass(frozen=True)
class Pair:
    a: str
    b: str
    a_name: str
    b_name: str
    correlation: float
    months: int


@dataclass(frozen=True)
class OverlapReport:
    pairs: list[Pair]
    # Roughly how many genuinely separate positions the holdings amount to.
    # Four funds that all move together are one bet, not four.
    effective_positions: float | None
    counted: int
    # Funds left out, and why. Never dropped silently.
    excluded: dict[str, str]
    summary: str


def _month_ends(navs: list[NavPoint]) -> dict[tuple[int, int], float]:
    """The last published NAV in each calendar month.

    Monthly rather than daily: daily returns of two Indian equity funds are
    dominated by the market's own day-to-day move and correlate near 1.0 for
    any pair whatsoever, which would make the measure say nothing. A month is
    long enough for a manager's choices to show up in the number.
    """
    out: dict[tuple[int, int], float] = {}
    for point in sorted(navs, key=lambda p: p.date):
        if point.nav > 0:
            out[(point.date.year, point.date.month)] = point.nav
    return out


def _aligned_returns(
    first: dict[tuple[int, int], float], second: dict[tuple[int, int], float]
) -> tuple[np.ndarray, np.ndarray]:
    """Month-on-month returns over the window both funds actually cover.

    Consecutive months only. A gap in either series would otherwise turn into a
    single multi-month return sitting beside a one-month return in the other,
    which is two different questions compared as though they were one.
    """
    shared = sorted(set(first) & set(second))
    a_returns: list[float] = []
    b_returns: list[float] = []
    for previous, current in zip(shared, shared[1:]):
        gap = (current[0] - previous[0]) * 12 + (current[1] - previous[1])
        if gap != 1:
            continue
        a_returns.append(first[current] / first[previous] - 1.0)
        b_returns.append(second[current] / second[previous] - 1.0)
    return np.array(a_returns), np.array(b_returns)


def _effective_positions(matrix: np.ndarray) -> float | None:
    """How many independent bets an equally-weighted set of funds amounts to.

    From the eigenvalues of the correlation matrix: perfectly uncorrelated
    holdings give back the number of funds, identical ones give 1. It answers
    "am I diversified" with a number rather than a colour.
    """
    if matrix.shape[0] < 2:
        return None
    values = np.linalg.eigvalsh(matrix)
    values = values[values > 1e-9]
    if values.size == 0:
        return None
    weights = values / values.sum()
    # Exponential of the entropy: the standard participation-ratio reading of
    # how many components genuinely carry the variance.
    entropy = -np.sum(weights * np.log(weights))
    return float(np.exp(entropy))


def analyse_overlap(
    funds: list[tuple[str, str, list[NavPoint]]],
    *,
    today: date | None = None,
) -> OverlapReport:
    """Correlate every pair of held funds and say what it means.

    `funds` is (identifier, name, nav history) per holding.
    """
    excluded: dict[str, str] = {}
    usable: list[tuple[str, str, dict]] = []
    for identifier, name, navs in funds:
        months = _month_ends(navs)
        if len(months) < MIN_MONTHS + 1:
            excluded[name] = (
                f"only {max(len(months) - 1, 0)} months of NAV history, and "
                f"{MIN_MONTHS} are needed before a correlation describes "
                "behaviour rather than one stretch of market"
            )
            continue
        usable.append((identifier, name, months))

    if len(usable) < 2:
        return OverlapReport(
            pairs=[],
            effective_positions=None,
            counted=len(usable),
            excluded=excluded,
            summary=(
                "Two funds with enough history are needed before overlap means "
                "anything. Nothing here to compare yet."
            ),
        )

    pairs: list[Pair] = []
    size = len(usable)
    matrix = np.eye(size)
    for i in range(size):
        for j in range(i + 1, size):
            a_returns, b_returns = _aligned_returns(usable[i][2], usable[j][2])
            if a_returns.size < MIN_MONTHS:
                continue
            if a_returns.std() == 0 or b_returns.std() == 0:
                # A fund whose NAV never moved over the window. Correlation is
                # undefined rather than zero, and 0 would read as "perfectly
                # diversifying", which is the opposite of what we know.
                continue
            correlation = float(np.corrcoef(a_returns, b_returns)[0, 1])
            matrix[i, j] = matrix[j, i] = correlation
            pairs.append(
                Pair(
                    a=usable[i][0],
                    b=usable[j][0],
                    a_name=usable[i][1],
                    b_name=usable[j][1],
                    correlation=round(correlation, 3),
                    months=int(a_returns.size),
                )
            )

    pairs.sort(key=lambda p: -p.correlation)
    effective = _effective_positions(matrix)

    duplicates = [p for p in pairs if p.correlation >= DUPLICATE_ABOVE]
    if not pairs:
        summary = (
            "No two of these funds share enough months for a correlation to "
            "mean anything yet."
        )
    elif duplicates:
        worst = duplicates[0]
        summary = (
            f"{worst.a_name} and {worst.b_name} moved together "
            f"{worst.correlation:.2f} of the time over {worst.months} months. "
            "Holding both is one position with two sets of paperwork. Across "
            f"all {size} funds you are running about "
            f"{effective:.1f} genuinely separate bets."
            if effective
            else f"{worst.a_name} and {worst.b_name} moved together "
            f"{worst.correlation:.2f} of the time."
        )
    else:
        summary = (
            f"Nothing here is a duplicate of anything else. The closest pair is "
            f"{pairs[0].a_name} and {pairs[0].b_name} at "
            f"{pairs[0].correlation:.2f}, and across all {size} funds you are "
            f"running about {effective:.1f} separate bets."
            if effective
            else "Nothing here is a duplicate of anything else."
        )

    return OverlapReport(
        pairs=pairs,
        effective_positions=round(effective, 2) if effective else None,
        counted=size,
        excluded=excluded,
        summary=summary,
    )
