

def test_the_stated_window_is_the_rows_the_score_actually_used():
    """The API's coverage claim must be read off the computation, not restated.

    `score()` indexes `_LOOKBACK_DAYS` and `_SKIP_DAYS` TRADING rows; `window()`
    used to hardcode 365 and 30 CALENDAR days, and produced `measured_from` /
    `measured_to` in `/research/momentum`'s response. Two independent
    expressions of one span, agreeing by arithmetic coincidence — a mutation
    moving the calendar figure passed the entire suite.

    Section 14 says coverage is stated, not hidden. A coverage claim that can
    drift from what was measured is that rule with an extra step in it.
    """
    import pandas as pd

    from app.services.advisor.momentum import _MIN_DAYS, _SKIP_DAYS, window

    # trading rows only — deliberately NOT calendar days, so a calendar-based
    # implementation cannot accidentally agree
    idx = pd.bdate_range(end="2026-08-27", periods=_MIN_DAYS + 40)
    frame = pd.DataFrame({"Close": range(len(idx))}, index=idx)

    start, end = window(history=frame)

    assert start == idx[-_MIN_DAYS].date()
    assert end == idx[-_SKIP_DAYS].date()
    # and the span is the lookback in TRADING rows, not 365 calendar days
    rows_between = list(idx).index(pd.Timestamp(end)) - list(idx).index(pd.Timestamp(start))
    assert rows_between == _MIN_DAYS - _SKIP_DAYS


def test_the_window_falls_back_honestly_without_a_frame():
    """No frame, no lie: the calendar approximation is documented, not silent."""
    from datetime import date

    from app.services.advisor.momentum import window

    start, end = window(today=date(2026, 8, 27))
    assert (end - start).days == 365
    assert end < date(2026, 8, 27)


def test_the_validated_constants_are_pinned_to_what_was_measured():
    """`_LOOKBACK_DAYS` and `_SKIP_DAYS` are the ones the t-statistics describe.

    The module's own comment says it: *"the lookback and skip are the validated
    ones; changing either means the t-statistics above no longer describe what
    is being computed."* `nextrade-prediction-research` records t = +3.11 over
    32 survivorship-adjusted years for **this** specification — 12-month return
    skipping the most recent month, the standard construction — and the number
    is carried in the response beside every score.

    Found necessary by mutation: `_SKIP_DAYS = 21 → 42` passed the suite even
    after the window test above, because that test derives the stated span FROM
    these constants and so moves with them. Consistency and correctness are
    different properties, and the first one cannot pin the second. This is the
    same assertion `test_fund_evidence` makes about `WINDOWS`, for the same
    reason: a constant that carries a published statistic has to be checked
    against the statistic, not against itself.
    """
    from app.services.advisor.momentum import _LOOKBACK_DAYS, _SKIP_DAYS

    assert _LOOKBACK_DAYS == 250, "12-month lookback in trading days"
    assert _SKIP_DAYS == 21, "skip the most recent month, ~21 trading days"
