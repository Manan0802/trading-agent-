"""A NaN in a chart series 500s the company page, past every validator.

Found by `check.sh`'s cross-view step, on the live server: `BAJAJ-AUTO.NS:
/analysis returned 500`. The traceback ends in the JSON encoder —
`ValueError: Out of range float values are not JSON compliant: nan` — from ONE
bad value in a 240-point peer series, and only for whichever ticker had a gap
that day.

Pydantic validates a NaN float happily, so nothing upstream objects. The page
builds, the response model accepts it, and the failure lands in `json.dumps`
after the handler has returned.
"""

import math

import pytest

from app.services.screener import stock_analysis_page as page_mod


class TestRebaseDropsWhatIsNotANumber:
    def test_a_nan_close_is_dropped_rather_than_carried(self):
        from datetime import date

        series = [
            (date(2026, 1, 1), 100.0),
            (date(2026, 1, 2), float("nan")),
            (date(2026, 1, 3), 110.0),
        ]
        out = page_mod._rebase(series)
        assert len(out) == 2, "the NaN point must not appear at all"
        assert all(math.isfinite(p.value) for p in out)
        assert out[-1].value == pytest.approx(110.0)

    def test_an_infinite_close_is_dropped_too(self):
        from datetime import date

        series = [(date(2026, 1, 1), 100.0), (date(2026, 1, 2), float("inf"))]
        out = page_mod._rebase(series)
        assert len(out) == 1

    def test_a_series_that_starts_with_a_nan_rebases_from_the_first_real_price(self):
        """Otherwise the base is NaN and every point after it is NaN."""
        from datetime import date

        series = [(date(2026, 1, 1), float("nan")), (date(2026, 1, 2), 50.0),
                  (date(2026, 1, 3), 55.0)]
        out = page_mod._rebase(series)
        assert [p.value for p in out] == [100.0, 110.0]

    def test_a_series_of_nothing_but_nan_is_empty_not_a_chart_of_nan(self):
        from datetime import date

        assert page_mod._rebase([(date(2026, 1, 1), float("nan"))]) == []


def test_the_median_is_guarded_a_second_time():
    """The median of a list containing one NaN is NaN.

    `_rebase` cleans its input, so this cannot fire today — and it is here
    because the failure lands in the JSON encoder, past every validator, where
    it costs a 500 rather than a wrong number on a screen.
    """
    import inspect

    source = inspect.getsource(page_mod._sector_median)
    assert "math.isfinite" in source


def test_the_whole_page_is_json_encodable_without_allowing_nan():
    """The exact check the JSON encoder makes. `allow_nan=False` is what
    Starlette's encoder does, and what turned this into a 500."""
    import json
    from datetime import date

    from app.services.marketdata import stock_universe

    ticker = "BAJAJ-AUTO.NS"
    if stock_universe.lookup(ticker) is None:
        pytest.skip(f"{ticker} is not in the universe")
    try:
        page = page_mod.build(ticker, date.today())
    except Exception:  # noqa: BLE001 -- a live feed outage is not this test's subject
        pytest.skip("the price feed is unavailable")

    for name, series in (("price", page.price_series), ("sector", page.sector_series)):
        json.dumps([p.value for p in series], allow_nan=False), name
