"""Delivery percentage, from the exchange file that was never actually blocked.

Nine of every hundred points in the stock score were a constant 4.5 for every
company, because the scorer's documented source returns 403. These tests hold
the replacement, and the fallback for when it too goes quiet.
"""

from datetime import date

import pytest

from app.services.marketdata import nse_delivery
from app.services.screener import stocks

# Real rows from sec_bhavdata_full_20082026.csv, including the two things that
# make naive parsing wrong: a space after every comma in the header, and BE
# series rows whose delivery is literally "-".
REAL = """SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
HDFCBANK, EQ, 20-Aug-2026, 720.00, 725.50, 728.30, 724.30, 725.05, 725.05, 726.11, 17603805, 127822.34, 210154, 12270042, 69.70
ITC, EQ, 20-Aug-2026, 267.05, 268.20, 271.65, 265.00, 271.65, 271.65, 268.31, 28272797, 75858.11, 238619, 18907919, 66.88
RELIANCE, EQ, 20-Aug-2026, 1311.00, 1315.50, 1316.50, 1307.00, 1313.20, 1313.20, 1312.27, 5546227, 72781.69, 125718, 2637500, 47.55
SUZLON, EQ, 20-Aug-2026, 46.77, 46.82, 47.55, 46.80, 47.00, 47.00, 47.19, 31120638, 14685.45, 51123, 11003444, 35.36
3IINFOLTD, BE, 20-Aug-2026, 23.15, 22.00, 22.75, 22.00, 22.34, 22.25, 22.23, 451936, 100.45, 1999, -, -
AAKAAR, SM, 20-Aug-2026, 55.65, 58.35, 58.40, 58.35, 58.40, 58.40, 58.39, 12800, 7.47, 8, 12800, 100.00
574GS2026, GS, 20-Aug-2026, 100.93, 100.85, 100.85, 100.85, 100.85, 100.85, 100.85, 2, 0.00, 1, 2, 100.00
"""


@pytest.fixture(autouse=True)
def clean():
    nse_delivery.clear_cache()
    yield
    nse_delivery.clear_cache()


# ------------------------------------------------------------------ parsing


def test_the_real_exchange_format_parses():
    out = nse_delivery._parse(REAL)
    assert out["HDFCBANK"] == pytest.approx(69.70)
    assert out["ITC"] == pytest.approx(66.88)
    assert out["SUZLON"] == pytest.approx(35.36)


def test_the_header_has_a_space_after_every_comma():
    """`SYMBOL, SERIES, ...` -- csv.DictReader keys them with the space, so an
    unstripped lookup finds nothing and returns an empty map, which looks
    exactly like a holiday."""
    assert " SERIES" in REAL.split("\n")[0]
    assert nse_delivery._parse(REAL), "stripping is what makes this non-empty"


def test_a_dash_delivery_is_dropped_not_read_as_zero():
    """The exchange prints "-" when it published no delivery figure. Zero
    delivery and no reported delivery are different facts, and one of them
    scores the company at the bottom of a nine-point factor.

    The row is constructed rather than taken from the file: on 20-Aug-2026
    every dash sits on a BE row, which the series filter drops first, so the
    real file cannot exercise this rule at all. An EQ scrip suspended mid-session
    is what produces one, and that is the day this would matter."""
    suspended = REAL + (
        "SOMESCRIP, EQ, 20-Aug-2026, 10.00, 10.00, 10.00, 10.00, 10.00, "
        "10.00, 10.00, 0, 0.00, 0, -, -\n"
    )
    out = nse_delivery._parse(suspended)
    assert "SOMESCRIP" not in out, "a dash was read as a number"
    assert out.get("HDFCBANK") == pytest.approx(69.70), "the good rows still parse"


def test_only_ordinary_equity_is_kept():
    """Of the thirteen series in one day's file, four carry a numeric delivery
    and are not ordinary equity: SM and ST are the SME platform (362 + 98
    scrips), GS and GB are government bonds (55 + 45). All print 100.00%,
    because a handful of units changing hands is by definition all delivered.
    Let them in and a hundred bonds join the stock screen at a perfect score.

    BE (trade-to-trade) is excluded too, but every BE row in the real file
    prints "-", so the dash rule already catches it and this filter is what
    catches the rest."""
    out = nse_delivery._parse(REAL)
    assert "AAKAAR" not in out, "an SME scrip entered the equity map"
    assert "574GS2026" not in out, "a government bond entered the equity map"
    assert "3IINFOLTD" not in out
    assert set(out) == {"HDFCBANK", "ITC", "RELIANCE", "SUZLON"}


def test_a_rounding_artefact_above_a_hundred_is_clamped_not_dropped():
    row = REAL.replace("12270042, 69.70", "12270042, 100.30")
    assert nse_delivery._parse(row)["HDFCBANK"] == 100.0


def test_a_nonsense_percentage_is_dropped():
    row = REAL.replace("12270042, 69.70", "12270042, banana")
    assert "HDFCBANK" not in nse_delivery._parse(row)


# ------------------------------------------------------- fetching and holidays


def test_a_weekend_walks_back_to_the_last_trading_day(monkeypatch):
    asked = []

    def fake(day):
        asked.append(day)
        return REAL * 400 if day == date(2026, 8, 21) else None

    monkeypatch.setattr(nse_delivery, "_fetch_one", fake)
    monkeypatch.setattr(nse_delivery, "_parse", lambda t: {f"S{i}": 50.0 for i in range(600)})
    _, day = nse_delivery.latest(as_of=date(2026, 8, 23))
    assert day == date(2026, 8, 21)
    assert asked[:3] == [date(2026, 8, 23), date(2026, 8, 22), date(2026, 8, 21)]


def test_giving_up_raises_rather_than_returning_an_empty_map(monkeypatch):
    """An empty map and a holiday are indistinguishable to a caller, and one of
    them means every stock silently scores neutral again."""
    monkeypatch.setattr(nse_delivery, "_fetch_one", lambda d: None)
    with pytest.raises(nse_delivery.DeliveryUnavailable):
        nse_delivery.latest(as_of=date(2026, 8, 20))


def test_a_stub_file_is_refused_rather_than_scored_on(monkeypatch):
    """The NSE lists well over a thousand EQ scrips. A file with five is the
    format having moved, and scoring on it is worse than scoring neutral."""
    monkeypatch.setattr(nse_delivery, "_fetch_one", lambda d: REAL)
    with pytest.raises(nse_delivery.DeliveryUnavailable):
        nse_delivery.latest(as_of=date(2026, 8, 20))


def test_the_file_is_fetched_once_a_day_not_once_a_stock(monkeypatch, tmp_path):
    """Both layers, because disabling one still reads the other and the test
    passes on half a cache."""
    monkeypatch.setattr(nse_delivery, "_DISK_CACHE_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(nse_delivery, "_fetch_one", lambda d: (calls.append(d), REAL)[1])
    monkeypatch.setattr(nse_delivery, "_parse", lambda t: {f"S{i}": 50.0 for i in range(600)})
    for _ in range(5):
        nse_delivery.latest(as_of=date(2026, 8, 20))
    assert len(calls) == 1, f"fetched {len(calls)} times"


# ------------------------------------------------------------- the wiring


def test_an_unreadable_archive_scores_neutral_and_never_raises(monkeypatch):
    """A screen that fails because a supplementary factor is missing is worse
    than one that scores it neutral and says so."""
    def boom():
        raise nse_delivery.DeliveryUnavailable("nothing published")

    monkeypatch.setattr(nse_delivery, "latest", lambda *a, **k: boom())
    assert stocks.delivery_for_today() == {}
    assert stocks.delivery_as_of() is None


def test_the_screen_stops_claiming_delivery_is_dead_once_it_is_live(monkeypatch):
    """This sentence was hardcoded and permanent. It has to follow the data, or
    it goes on asserting whichever was true the day it was written."""
    from app.routers import screener as router

    monkeypatch.setattr(stocks, "delivery_as_of", lambda: date(2026, 8, 20))
    assert router.neutral_factors() == []

    monkeypatch.setattr(stocks, "delivery_as_of", lambda: None)
    said = router.neutral_factors()
    assert len(said) == 1 and "neutral half" in said[0]


def test_a_company_missing_from_the_file_scores_neutral_not_zero(monkeypatch):
    """A newly listed or suspended scrip is absent from the bhavcopy. Absent
    must mean unknown, not zero conviction."""
    from app.services.screener import stock_scoring

    weight = stock_scoring.FACTOR_WEIGHTS["delivery"] if hasattr(
        stock_scoring, "FACTOR_WEIGHTS") else 9
    neutral, _ = stock_scoring._score_delivery(None, weight)
    zero, _ = stock_scoring._score_delivery(0.0, weight)
    assert neutral == pytest.approx(weight * 0.5)
    assert zero == 0.0
    assert neutral > zero, "absent must not be scored as the worst possible"
