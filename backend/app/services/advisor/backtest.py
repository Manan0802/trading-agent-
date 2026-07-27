"""Does the score actually pick funds that go on to do better?

A score nobody has tested is a decoration. This answers the only question that
matters about one: pick funds using only what was knowable on a past date, then
measure what those picks went on to return against the alternative the user
actually had, which is any other fund in the same category.

Two rules are enforced rather than trusted:

**No lookahead.** The picker is handed NAV history truncated at the decision
date. It cannot see a single day beyond it, and a fund that had not launched is
not offered at all.

**No silent survivors.** A fund that stopped publishing mid-window has no
forward return, so it is counted as unmeasurable rather than valued at its last
NAV, which would flatter every fund that died. And because our catalogue is
built from funds that are alive today, the whole exercise carries a
survivorship bias that is reported in the result rather than papered over.
That bias is exactly what makes most published backtests worthless, and a
sibling implementation we reviewed filters its historical universe on a *live*
column, so its backtest cannot see a wound-up fund at all.
"""

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from app.services.marketdata.mutual_fund import NavPoint, nav_on_or_before

_DAYS_PER_YEAR = 365.25

# A fund needs at least this much history before the decision date to be
# offered to the picker: below it there is nothing to judge.
_MIN_HISTORY_DAYS = 400

# NAVs skip weekends and holidays, so an exact-date match would fail most days.
_MATCH_TOLERANCE_DAYS = 10

Picker = Callable[[dict[str, list[NavPoint]]], list[str]]


@dataclass(frozen=True)
class BacktestWindow:
    decision_date: date
    picked: list[str]
    picked_return: float | None
    category_median_return: float | None
    candidates: int

    @property
    def spread(self) -> float | None:
        """How much better the picks did than the median fund in the category."""
        if self.picked_return is None or self.category_median_return is None:
            return None
        return self.picked_return - self.category_median_return


@dataclass
class BacktestResult:
    windows: list[BacktestWindow] = field(default_factory=list)
    windows_measured: int = 0
    # Share of measurable windows where the picks beat the category median.
    hit_rate: float = 0.0
    median_spread: float | None = None
    survivorship_note: str = ""


def forward_return(
    navs: list[NavPoint], start: date, years: float
) -> float | None:
    """Annualised return from `start` over `years`, or None if unmeasurable.

    None rather than a partial figure: a fund that stopped publishing part way
    through has no answer, and using its last NAV as the endpoint would credit
    it with surviving a period it did not.
    """
    if not navs:
        return None

    end = start + timedelta(days=round(years * _DAYS_PER_YEAR))
    first = nav_on_or_before(navs, start)
    last = nav_on_or_before(navs, end)
    if first is None or last is None:
        return None
    # The series must actually reach the end of the window, not merely have a
    # last row somewhere before it.
    if (end - last.date).days > _MATCH_TOLERANCE_DAYS:
        return None
    if (start - first.date).days > _MATCH_TOLERANCE_DAYS:
        return None
    if first.nav <= 0:
        return None

    total = last.nav / first.nav
    return total ** (1 / years) - 1 if years >= 1 else total - 1


def _truncate(navs: list[NavPoint], as_of: date) -> list[NavPoint]:
    return [p for p in navs if p.date <= as_of]


def run_backtest(
    universe: dict[str, list[NavPoint]],
    decision_dates: list[date],
    holding_years: float,
    picker: Picker,
    top_n: int = 2,
) -> BacktestResult:
    """Pick on each decision date using only prior data, then measure forward.

    `picker` receives `{code: nav_history_truncated_at_the_decision_date}` and
    returns codes in preference order.
    """
    result = BacktestResult()
    spreads: list[float] = []
    wins = 0

    for decision in decision_dates:
        # Offer only funds that existed and had something to judge.
        candidates: dict[str, list[NavPoint]] = {}
        for code, navs in universe.items():
            history = _truncate(navs, decision)
            if len(history) < 2:
                continue
            if (history[-1].date - history[0].date).days < _MIN_HISTORY_DAYS:
                continue
            candidates[code] = history

        picked = list(picker(candidates))[:top_n] if candidates else []

        forwards = {
            code: forward_return(universe[code], decision, holding_years)
            for code in candidates
        }
        measurable = [r for r in forwards.values() if r is not None]
        picked_returns = [
            forwards.get(code) for code in picked if forwards.get(code) is not None
        ]

        picked_return = (
            statistics.mean(picked_returns) if picked_returns else None
        )
        category_median = statistics.median(measurable) if measurable else None

        window = BacktestWindow(
            decision_date=decision,
            picked=picked,
            picked_return=picked_return,
            category_median_return=category_median,
            candidates=len(candidates),
        )
        result.windows.append(window)

        if window.spread is not None:
            spreads.append(window.spread)
            if window.spread > 0:
                wins += 1

    result.windows_measured = len(spreads)
    result.hit_rate = wins / len(spreads) if spreads else 0.0
    result.median_spread = statistics.median(spreads) if spreads else None
    result.survivorship_note = (
        "Measured over funds that are alive today, so funds wound up or merged "
        "since the decision date are missing from it entirely. Those are "
        "disproportionately the ones that did badly, which makes every figure "
        "here better than the truth by an unknown margin. Read the spread as an "
        "upper bound, not an estimate."
    )
    return result
