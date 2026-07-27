"""Rolling-window returns, and the dispersion around them.

A point-to-point CAGR is one observation: it answers "what did this fund return
between these two dates", and both dates are accidents. Roll the window across
the whole history instead and you get every answer the fund could have given a
real investor, because real investors do not all start on the same day.

The mean of those windows is the headline. The rest of the distribution is the
part almost nobody shows, and it is the part that matters for a goal: a fund can
average 14% a year and still have handed someone a losing three-year stretch.
`worst` and `share_positive` are that number.
"""

from dataclasses import dataclass

import numpy as np

from app.services.marketdata.mutual_fund import NavPoint

_DAYS_PER_YEAR = 365.25

# Single-day moves beyond this are splits, restatements or bad NAV rows, not
# returns. Indian equity funds genuinely move 8-10% in a day; they do not move
# 25%. Left in, one such row corrupts volatility, drawdown and every rolling
# window that contains it at once.
_MAX_DAILY_MOVE = 0.25


@dataclass(frozen=True)
class RollingStats:
    """Every window of one length, summarised."""

    mean: float
    best: float
    worst: float
    std: float
    # Share of windows that made money. For a long-horizon goal this is closer
    # to the real question than the average is.
    share_positive: float
    count: int


def neutralise_nav_artefacts(navs: list[NavPoint]) -> tuple[list[NavPoint], int]:
    """Rebuild the series with impossible one-day moves flattened.

    The NAV level after the artefact is rebased rather than the row dropped, so
    dates stay intact and every calendar window keeps its alignment.
    """
    if len(navs) < 2:
        return list(navs), 0

    moves = [b.nav / a.nav - 1.0 for a, b in zip(navs, navs[1:])]
    if not any(abs(m) > _MAX_DAILY_MOVE for m in moves):
        # Returned as-is rather than rebuilt: multiplying a clean series back
        # through itself only accumulates floating-point drift.
        return list(navs), 0

    out = [navs[0]]
    neutralised = 0
    for current, move in zip(navs[1:], moves):
        if abs(move) > _MAX_DAILY_MOVE:
            neutralised += 1
            out.append(NavPoint(date=current.date, nav=out[-1].nav))
        else:
            out.append(NavPoint(date=current.date, nav=out[-1].nav * (1.0 + move)))
    return out, neutralised


def rolling_return_stats(
    navs: list[NavPoint], window_days: int
) -> RollingStats | None:
    """Returns over every overlapping `window_days` window, or None if the fund
    has no complete window of that length.

    Windows longer than a year are annualised; shorter ones are left cumulative,
    because compounding a quarter's return up to a year overstates it.
    """
    if len(navs) < 2:
        return None

    dates = np.array([p.date.toordinal() for p in navs])
    values = np.array([p.nav for p in navs], dtype=float)
    if np.any(values <= 0):
        return None

    # For each row, the first row at or after (its date - window). Windows are
    # measured on the calendar, not on row counts: NAVs skip weekends and
    # holidays, so a row-counted "year" drifts by weeks.
    starts = np.searchsorted(dates, dates - window_days, side="left")
    complete = dates[starts] <= dates - window_days
    if not complete.any():
        # Nothing spans a full window; fall back to rows whose start is the
        # earliest available only when the total history genuinely covers it.
        if dates[-1] - dates[0] < window_days:
            return None
        complete = np.zeros(len(dates), dtype=bool)
        complete[-1] = True
        starts[-1] = 0

    end_values = values[complete]
    start_values = values[starts[complete]]
    returns = end_values / start_values - 1.0

    years = window_days / _DAYS_PER_YEAR
    if years > 1:
        returns = (1.0 + returns) ** (1.0 / years) - 1.0

    return RollingStats(
        mean=float(returns.mean()),
        best=float(returns.max()),
        worst=float(returns.min()),
        std=float(returns.std()),
        share_positive=float((returns > 0).mean()),
        count=int(returns.size),
    )
