"""The one thing in this app measured to predict a stock's next year.

Everything else the app does well is arithmetic: what a fund costs, what a tax
regime costs, what a portfolio is worth. This is the only forecast that
survived testing, and it survived twice --

    our own universe, 60 non-overlapping quarterly windows   t = +2.99
    IIMA's 32-year survivorship-adjusted factor series       t = +3.11

Two datasets, two constructions, the same answer. `docs/do-factors-work-here.md`
has the method and the controls that caught a broken benchmark on the way.

**The definition is the one that was validated, not a variant.** Twelve-month
return, skipping the most recent month. The skip matters: the last few weeks
carry short-term reversal, which is a different effect pointing the other way,
and including them dilutes the signal that was measured.

**And the risk is not optional decoration.** Momentum holds up while the market
falls and then loses violently when it turns:

    2008 crash    market -64.7%   momentum  +5.3%
    2009 rebound  market +91.6%   momentum -53.5%

A rank here is not a recommendation to buy. It says this stock is in the group
that has historically done a little better than average over the following
year, and that the group loses a third to a half of its value when the market
rebounds from a fall. Both halves have to travel together or the number is
misleading on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.services.marketdata import stock

# Trading days. The lookback and skip are the validated ones; changing either
# means the t-statistics above no longer describe what is being computed.
_LOOKBACK_DAYS = 250
_SKIP_DAYS = 21

# A stock needs the full window plus the skip before it can be ranked at all.
_MIN_DAYS = _LOOKBACK_DAYS + _SKIP_DAYS

# What the same measurement did in the last market rebound. Carried with every
# score rather than left in a document, because it is the number that decides
# how much of this anyone holds.
REBOUND_LOSS_2009 = -53.5


@dataclass(frozen=True)
class Momentum:
    ticker: str
    symbol: str
    name: str
    industry: str | None
    # Return over the twelve months to a month ago.
    score: float
    # Where the window actually ran, so the number can be checked.
    measured_from: date
    measured_to: date


def score(ticker: str, history=None) -> float | None:
    """Twelve-month return to a month ago, or None if the history is too short.

    None rather than a partial figure: a stock listed eight months ago has no
    twelve-month momentum, and computing one from what exists would rank it
    against stocks measured over a different period.
    """
    try:
        frame = history if history is not None else stock.get_price_history(ticker)
    except Exception:  # noqa: BLE001 - an unavailable stock is simply unranked
        return None
    if frame is None or len(frame) < _MIN_DAYS:
        return None

    closes = frame["Close"]
    recent = float(closes.iloc[-_SKIP_DAYS])
    old = float(closes.iloc[-_MIN_DAYS])
    return recent / old - 1.0 if old > 0 else None


def window(today: date | None = None, history=None) -> tuple[date, date]:
    """The calendar span the score covers — derived from the same rows when it can be.

    This used to hardcode 365 and 30 CALENDAR days while `score()` indexes
    `_LOOKBACK_DAYS = 250` and `_SKIP_DAYS = 21` TRADING rows. Two independent
    expressions of one span, tied together by nothing. They agreed only by
    arithmetic coincidence — 250 trading days is about a year, 21 about a month
    — and the comment above those constants says in as many words that changing
    either invalidates the statistics, so they are exactly the kind that get
    changed on purpose. A mutation moving the calendar figure passed the whole
    suite, because the API's `measured_from`/`measured_to` is the app's *claim*
    about its own coverage and nothing compared it to the computation.

    Given a price frame, the span is read off the very rows `score()` uses, so
    the claim cannot drift from the measurement. Without one it falls back to
    the calendar approximation, which is honest for a label and is why the
    fallback is documented rather than silent.
    """
    if history is not None and len(history) >= _MIN_DAYS:
        index = history.index
        return _as_date(index[-_MIN_DAYS]), _as_date(index[-_SKIP_DAYS])
    end = (today or date.today()) - timedelta(days=30)
    return end - timedelta(days=365), end


def _as_date(value) -> date:
    """A pandas timestamp, a datetime or a date, all reduced to a date."""
    return value.date() if hasattr(value, "date") else value


def band(rank: int, total: int) -> str:
    """Which quartile, in the words the measurement actually supports.

    The top quartile is the group that was measured. Saying anything sharper --
    "this stock will rise" -- claims something the rank IC of 0.07 does not
    support: it separates groups over many names and many years, not
    individual stocks.
    """
    if total < 4:
        return "too few stocks to rank"
    quartile = (rank - 1) * 4 // total
    return [
        "Top quarter — the group that has done better",
        "Second quarter",
        "Third quarter",
        "Bottom quarter — the group that has done worse",
    ][min(quartile, 3)]
