"""Whether the funds someone holds are actually different from each other.

The usual product here is a holdings-overlap calculator: pull both funds'
portfolios and report the percentage they share. This measures something else
first, and reports holdings overlap alongside it where the AMC publishes a file
we can read.

Correlation leads because it answers the question the investor actually has.
Two funds are the same position when they move together, and NAV history says
that directly, for every fund. Holdings overlap can miss it: two funds can hold
entirely different mid-caps, share almost no securities, and still be one bet.

But holdings overlap answers the *other* half, and the pair together is worth
more than either alone. Correlation says whether two funds are one position;
holdings say why. Two funds at 0.85 sharing 3% of their assets are the same
market exposure bought different ways. Two funds at 0.85 sharing 40% are
literally the same positions, twice. The second is a worse problem, and only the
holdings number can tell them apart.

Overlap comes from `marketdata/fund_holdings.py`, which reads the monthly
portfolio disclosure SEBI requires every AMC to publish. Coverage is partial by
design — only AMCs whose file has actually been fetched and parsed — so a pair
with no overlap figure is reported as unmeasured, never as zero.

What it deliberately does not do is treat correlation as a fault. Two equity
funds correlating 0.97 is not a defect, it is what equity does. The finding is
comparative — a second flexi-cap adds nothing a first one did not, while a debt
fund at 0.2 is doing real work — and the action is to hold fewer funds, not
better ones.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np

from app.services.marketdata.fund_holdings import common_weight
from app.services.marketdata.mutual_fund import NavPoint

# Below this the correlation is an accident of a short shared window rather
# than a description of how the two funds behave.
MIN_MONTHS = 24

# Above this, holding both is one position with two account statements, two
# sets of paperwork and two exit loads to track.
DUPLICATE_ABOVE = 0.90

# Share of net assets in the same securities that makes a pair literally the
# same shares rather than merely the same exposure. Two diversified Indian
# equity funds routinely share 15-30% simply by both owning the index leaders,
# so the bar sits above that band.
SAME_STOCKS_ABOVE = 40.0


@dataclass(frozen=True)
class Pair:
    a: str
    b: str
    a_name: str
    b_name: str
    correlation: float
    months: int
    # Percentage of net assets held in the same securities, matched on ISIN.
    # None when either AMC's disclosure is not one we read -- which is not the
    # same as zero, and must never be rendered as zero.
    common_weight: float | None = None
    shared_securities: int | None = None


@dataclass(frozen=True)
class OverlapReport:
    pairs: list[Pair]
    # Roughly how many genuinely separate positions the holdings amount to.
    # Four funds that all move together are one bet, not four.
    effective_positions: float | None
    # Funds every other fund could be measured against. The effective-positions
    # figure covers only these; a fund with an unmeasurable pair is excluded
    # rather than credited as independent.
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


def _fully_measured_block(measured: np.ndarray) -> list[int]:
    """The largest set of funds where every pair inside it was measured.

    Not "every fund whose row is complete" — one unmeasurable fund would fail
    every other fund's row and throw away the whole reading. The fund with the
    most gaps is dropped, and the rest are re-checked, until what remains is a
    block with no holes in it.
    """
    keep = list(range(measured.shape[0]))
    while len(keep) > 1:
        block = measured[np.ix_(keep, keep)]
        if block.all():
            break
        gaps = (~block).sum(axis=1)
        keep.pop(int(np.argmax(gaps)))
    return keep


def _shared(portfolios: dict, a: str, b: str) -> tuple[float | None, int | None]:
    """Holdings overlap for one pair, or (None, None) if either is unavailable."""
    first, second = portfolios.get(a), portfolios.get(b)
    if first is None or second is None:
        return None, None
    theirs = {h.isin for h in second.holdings}
    count = sum(1 for h in first.holdings if h.isin in theirs)
    return common_weight(first, second), count


def analyse_overlap(
    funds: list[tuple[str, str, list[NavPoint]]],
    *,
    today: date | None = None,
    portfolios: dict | None = None,
) -> OverlapReport:
    """Correlate every pair of held funds and say what it means.

    `funds` is (identifier, name, nav history) per holding. `portfolios` maps
    identifier to a `fund_holdings.SchemePortfolio` for the funds whose AMC
    disclosure we could read, and may be partial or absent entirely.
    """
    portfolios = portfolios or {}
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
    # Which cells we actually measured. An unset cell keeps np.eye's 0, and 0
    # means "perfectly diversifying" — the opposite of what an unmeasured pair
    # tells us. Left in, a fund we could not correlate against anything was
    # counted as a whole extra independent bet: three funds where two move
    # together at 0.95 read as 2.0 separate bets instead of 1.1.
    measured = np.eye(size, dtype=bool)
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
            measured[i, j] = measured[j, i] = True
            weight, count = _shared(portfolios, usable[i][0], usable[j][0])
            pairs.append(
                Pair(
                    a=usable[i][0],
                    b=usable[j][0],
                    a_name=usable[i][1],
                    b_name=usable[j][1],
                    correlation=round(correlation, 3),
                    months=int(a_returns.size),
                    common_weight=weight,
                    shared_securities=count,
                )
            )

    pairs.sort(key=lambda p: -p.correlation)
    known = _fully_measured_block(measured)
    effective = (
        _effective_positions(matrix[np.ix_(known, known)]) if len(known) > 1 else None
    )

    duplicates = [p for p in pairs if p.correlation >= DUPLICATE_ABOVE]
    # The one sentence neither number can produce alone.
    same_stocks = max(
        (p for p in pairs if p.common_weight is not None),
        key=lambda p: p.common_weight,
        default=None,
    )
    holdings_note = ""
    if same_stocks is not None and same_stocks.common_weight >= SAME_STOCKS_ABOVE:
        holdings_note = (
            f" {same_stocks.a_name} and {same_stocks.b_name} also hold "
            f"{same_stocks.common_weight:.0f}% of their assets in the same "
            f"{same_stocks.shared_securities} securities, so that pair is not "
            "just the same exposure — it is the same shares bought twice."
        )
    elif same_stocks is not None and duplicates:
        holdings_note = (
            f" Their actual holdings barely touch, though — the closest pair "
            f"shares only {same_stocks.common_weight:.0f}% of assets. Same "
            "market, different shares."
        )
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
            f"the {len(known)} funds we could compare against every other, you "
            f"are running about {effective:.1f} genuinely separate bets."
            + holdings_note
            if effective
            else f"{worst.a_name} and {worst.b_name} moved together "
            f"{worst.correlation:.2f} of the time." + holdings_note
        )
    else:
        summary = (
            f"Nothing here is a duplicate of anything else. The closest pair is "
            f"{pairs[0].a_name} and {pairs[0].b_name} at "
            f"{pairs[0].correlation:.2f}, and across the {len(known)} funds we "
            f"could compare against every other, you are running about "
            f"{effective:.1f} separate bets."
            + holdings_note
            if effective
            else "Nothing here is a duplicate of anything else." + holdings_note
        )

    return OverlapReport(
        pairs=pairs,
        effective_positions=round(effective, 2) if effective else None,
        counted=len(known),
        excluded=excluded,
        summary=summary,
    )
