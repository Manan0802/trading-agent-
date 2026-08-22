"""How often this app's own claims have actually been right.

Built by `scripts/build_track_record.py`, which re-runs the validators rather
than transcribing their output — hand-copied numbers rot silently and this
product's whole argument rests on these being true.

## What this is for

Fifteen Indian investing apps were surveyed while designing the decision
screens. **Not one publishes an audited track record for its own engine.**
Univest comes closest, printing *"Price moved −196.70 (21.23%) since then"*
under its verdict — one call marked to market, with no denominator. You cannot
tell from it whether that call was typical or the worst one they have.

This is the denominator. Every predictive claim on a screen can carry the
measured hit rate for *that kind of claim*, rather than a generic disclaimer.

## Why that is the right shape, per the evidence

Dietvorst, Simmons & Massey (2015) found people abandon an algorithm outright
after seeing it err once, even when it remains statistically superior. Hiding
the error record does not prevent that — it just means the discovery happens
later and costs more trust. Showing it, with the sample it rests on, is what
lets a reader calibrate instead of flipping between blind faith and rejection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "track_record.json"

# Below this a signal is not distinguishable from a coin over these samples.
CHANCE = 0.50


@dataclass(frozen=True)
class Measured:
    """One figure, with the range it moved across repeated runs.

    A single number would be a lie of precision: the validators fetch from mfapi
    at 24 threads and which fetches succeed changes the sample, so five runs of
    the identical script gave 37, 35, 36, 35 and 35 windows out of 44.
    """

    median: float
    low: float
    high: float

    @property
    def moves(self) -> bool:
        return self.high > self.low


@dataclass(frozen=True)
class Claim:
    key: str
    """What was tested, in the words a reader would use."""
    title: str
    wins: Measured
    windows: Measured
    """Percentage points of forward return a year, top quartile minus bottom."""
    spread_pp: Measured
    """Average Spearman correlation between the signal's rank and what followed.
    Zero means the signal carried no information at all."""
    rank_ic: Measured | None

    @property
    def hit_rate(self) -> float:
        return self.wins.median / self.windows.median if self.windows.median else 0.0

    @property
    def beats_chance(self) -> bool:
        return self.hit_rate > CHANCE


@dataclass(frozen=True)
class TrackRecord:
    measured_on: str
    runs: int
    why_ranges: str
    claims: tuple[Claim, ...]

    def claim(self, key: str) -> Claim | None:
        return next((c for c in self.claims if c.key == key), None)

    @property
    def best(self) -> Claim | None:
        """The single strongest thing we have found. It is cost, and it is not
        anything the fund screen ranks on beyond cost's own weight in it."""
        ranked = [c for c in self.claims if c.rank_ic is not None]
        return max(ranked, key=lambda c: c.rank_ic.median) if ranked else None


TITLES = {
    "cost": "Picking the cheaper fund",
    "past_3y": "Picking the fund with the better three-year record",
    "nav_level": "Picking the fund with the lower NAV per unit",
    "blend": "Half past record, half cost",
    "cost_alone": "Picking the cheaper fund",
    "shipped_score": "The score this app ranks funds on",
}


def _measured(block: dict) -> Measured:
    return Measured(block["median"], block["low"], block["high"])


@lru_cache(maxsize=1)
def load() -> TrackRecord:
    payload = json.loads(_DATA.read_text())
    claims: list[Claim] = []
    for key, block in payload["signals"].items():
        claims.append(
            Claim(
                key=key,
                title=TITLES.get(key, key),
                wins=_measured(block["wins"]),
                windows=_measured(block["windows"]),
                spread_pp=_measured(block["spread_pp"]),
                rank_ic=_measured(block["rank_ic"]),
            )
        )
    for key in ("cost_alone", "shipped_score"):
        block = payload[key]
        claims.append(
            Claim(
                key=key,
                title=TITLES[key],
                wins=_measured(block["wins"]),
                windows=_measured(block["windows"]),
                spread_pp=_measured(block["spread_pp"]),
                rank_ic=None,
            )
        )
    return TrackRecord(
        measured_on=payload["measured_on"],
        runs=payload["runs_per_measurement"],
        why_ranges=payload["why_ranges"],
        claims=tuple(claims),
    )


def for_fund_ranking() -> Claim | None:
    """What to show beside a fund's rank: the record of the score doing the
    ranking, not of cost, which is only part of it."""
    return load().claim("shipped_score")


def for_past_returns() -> Claim | None:
    """What to show beside any trailing-return column."""
    return load().claim("past_3y")


def for_cost() -> Claim | None:
    return load().claim("cost_alone")
