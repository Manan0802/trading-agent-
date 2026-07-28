"""What a fund's record actually says, and what it does not say.

Two rules, and the second one is the harder discipline.

**Say it in the terms a holder uses.** Not "Sortino 1.40" but "across 1,414
possible three-year holding periods this fund never lost money, and its worst
stretch still returned 0.8% a year". Same evidence; the second answers the
question the investor is really asking.

**Never let a description sound like a forecast.** Ranking funds by their past
record was tested over sixty three-year windows and does not predict which will
do better; see docs/does-the-score-work.md. So the record is reported as what
holding this fund has felt like, which is a real and useful thing to know
because it decides whether somebody stays invested through a bad year. It is
not reported as a reason to expect more of the same.

The cost line leads on funds where both plans are published, because the
expense ratio is the one thing here that was tested and did predict.
"""

from app.services.advisor.money import inr
from dataclasses import dataclass

from app.services.advisor.fund_score import FundEvidence, evidence_strength

# Below this, a record is short enough that its rolling windows overlap almost
# entirely and describe a single stretch of market.
_THIN_EVIDENCE = 0.5


@dataclass(frozen=True)
class Verdict:
    headline: str
    points: list[str]
    # Present only when something about the evidence limits what can be claimed.
    caveat: str | None = None


def _short_category(category: str) -> str:
    """"Equity Scheme - Large Cap Fund" -> "Large Cap". The trailing "Fund" is
    dropped because the sentence supplies its own."""
    label = category.split(" - ")[-1] if " - " in category else category
    return label.removesuffix(" Fund").strip()


def _sip_future_value(monthly: float, years: int, annual_rate: float) -> float:
    rate = annual_rate / 12
    n = years * 12
    return monthly * (((1 + rate) ** n - 1) / rate) * (1 + rate)


def build_verdict(
    evidence: FundEvidence,
    rank: int,
    peers: int,
    *,
    monthly_sip: float | None = None,
    years: int | None = None,
    assumed_return: float = 0.12,
) -> Verdict:
    """What this fund's own record says, in the terms a holder would use."""
    window = evidence.windows.get("3y")
    category = _short_category(evidence.category)
    points: list[str] = []

    if window is None:
        return Verdict(
            headline=(
                f"Ranked {rank} of {peers} {category} funds, but without three "
                "years of history there is no holding period to judge it over."
            ),
            points=[],
            caveat="Too new to compare against funds with a full record.",
        )

    losing_share = 1 - window.share_positive
    if losing_share <= 0:
        headline = (
            f"Across {window.count:,} possible three-year holding periods, this "
            f"fund never lost money. Its worst stretch still returned "
            f"{window.worst:+.1%} a year."
        )
    else:
        headline = (
            f"Across {window.count:,} possible three-year holding periods, "
            f"{losing_share:.0%} lost money. The worst of them returned "
            f"{window.worst:+.1%} a year."
        )

    points.append(
        f"Averaged {window.mean:+.1%} a year across those windows. That is what "
        "it did, not what it will do: ranking funds on past returns does not "
        "predict which of them go on to do better."
    )

    if evidence.max_drawdown is not None:
        points.append(
            f"Anyone holding through its worst run watched {abs(evidence.max_drawdown):.0%} "
            "of their money disappear before it came back. That is the part a "
            "SIP has to survive."
        )

    if evidence.direct_ter is not None:
        line = (
            f"Costs {evidence.direct_ter:.2%} a year in the direct plan, and cost "
            f"is why it sits at {rank} of {peers} here. Across 52 three-year "
            "windows the cheapest quarter of funds beat the dearest quarter in "
            "45 of them."
        )
        gap = (
            evidence.regular_ter - evidence.direct_ter
            if evidence.regular_ter is not None
            else None
        )
        if gap and gap > 0:
            line += (
                f" The regular plan of the same fund costs {evidence.regular_ter:.2%}, "
                f"so a distributor takes {gap * 100:.2f}pp of your return every year"
            )
            if monthly_sip and years:
                gross = _sip_future_value(monthly_sip, years, assumed_return)
                net = _sip_future_value(monthly_sip, years, assumed_return - gap)
                line += (
                    f", about {inr(gross - net)} on {inr(monthly_sip)} a month "
                    f"over {years} years"
                )
            line += "."
        points.append(line)

    strength = evidence_strength(evidence.history_years)
    caveat = None
    if strength < _THIN_EVIDENCE and evidence.history_years is not None:
        caveat = (
            f"Only {evidence.history_years:.1f} years of history, so its "
            f"{window.count:,} three-year windows nearly all describe the same "
            "stretch of market. A record that has not been through a bad one "
            "cannot yet show how it behaves in one, so its consistency counts "
            "for less here than a longer record would."
        )

    return Verdict(headline=headline, points=points, caveat=caveat)
