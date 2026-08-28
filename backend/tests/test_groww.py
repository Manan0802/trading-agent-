"""Groww's catalogue, and the four ways it lies quietly.

Every fixture below is real, copied out of the live endpoints on 2026-08-27.
Three of these tests exist because of a specific thing that happened while
probing, not because of a category of bug someone imagined:

  * `test_a_wrong_slug_returns_a_complete_object_of_nulls` -- a hand-built slug
    for PPFAS returned HTTP 200 and the full object shape with every value
    null. The real slug is `parag-parikh-long-term-value-fund-direct-growth`.
    Nothing about the response said no.
  * `test_a_shifted_holdings_column_is_caught_by_the_weight_sum` -- holdings are
    positional arrays. A column insertion keeps every row well-formed and moves
    sector and weight one place, and every value stays plausible.
  * `test_a_truncated_page_is_not_a_smaller_universe` -- a short page reads as
    funds having been delisted.

Nothing here touches the network.
"""

import json
from datetime import date

import pytest

from app.services.marketdata import groww
from app.services.marketdata.groww import GrowwUnavailable


def _row(**over):
    """A real SBI Gold row, trimmed to the fields the parser reads."""
    row = {
        "scheme_code": "119788",
        "search_id": "sbi-gold-fund-direct-growth",
        "scheme_name": "SBI Gold Direct Plan Growth",
        "amc": "SBI",
        "fund_house": "SBI Mutual Fund",
        "category": "Other",
        "sub_category": "Gold",
        "scheme_type": "Growth",
        "plan_type": "Direct",
        "available_for_investment": 1,
        "expense_ratio": "0.24",
        "aum": 15811.8654,
        "fund_manager": "Raviprakash Sharma",
        "min_investment_amount": 5000.0,
        "min_sip_investment": 500.0,
        "exit_load": "Exit load of 1% if redeemed within 15 days.",
        "risk": "High",
        "groww_rating": 4,
        "sip_allowed": True,
        "lumpsum_allowed": True,
    }
    row.update(over)
    return row


def _universe(rows):
    return {"content": rows, "total_results": len(rows)}


def _many(n, **over):
    return [_row(scheme_code=str(100000 + i), search_id=f"fund-{i}", **over) for i in range(n)]


@pytest.fixture(autouse=True)
def low_floor(monkeypatch):
    """The real floor is 1,200 funds; these fixtures are a handful.

    Lowered rather than disabled, so `test_an_empty_universe_is_an_error` can
    still fire. A guard switched off in tests is a guard that only exists in
    production.
    """
    monkeypatch.setattr(groww, "_MIN_GROWTH_ROWS", 3)


# --------------------------------------------------------------------------
# The universe feed
# --------------------------------------------------------------------------


def test_parses_a_real_row_into_the_fields_the_screener_joins_on():
    fund = groww.parse_universe(_universe(_many(3)))[0]
    assert fund.scheme_code == "100000"
    assert fund.expense_ratio == 0.24, "expense_ratio arrives as a string"
    assert fund.aum_crore == pytest.approx(15811.8654)
    assert fund.fund_manager == "Raviprakash Sharma"
    assert fund.min_sip == 500.0
    assert fund.sip_allowed is True


def test_dividend_and_idcw_variants_of_the_same_fund_are_excluded():
    """The live feed carries 951 Dividend and 582 IDCW rows.

    They are the same funds under a payout option this app never recommends.
    Counting them would inflate the universe by more than half.
    """
    rows = _many(3) + [
        _row(scheme_code="900001", search_id="a", scheme_type="IDCW"),
        _row(scheme_code="900002", search_id="b", scheme_type="Dividend"),
        _row(scheme_code="900003", search_id="c", scheme_type="Dividend Monthly"),
    ]
    codes = {f.scheme_code for f in groww.parse_universe(_universe(rows))}
    assert codes == {"100000", "100001", "100002"}


def test_a_fund_groww_has_stopped_selling_is_not_in_the_universe():
    rows = _many(3) + [_row(scheme_code="900001", search_id="x", available_for_investment=0)]
    codes = {f.scheme_code for f in groww.parse_universe(_universe(rows))}
    assert "900001" not in codes


def test_the_same_fund_under_two_slugs_is_one_fund():
    """1,741 live rows carry 1,686 distinct AMFI codes. The 55 are not an error."""
    rows = _many(3) + [_row(scheme_code="100000", search_id="sbi-gold-fund-direct-growth-alt")]
    funds = groww.parse_universe(_universe(rows))
    assert len(funds) == 3
    assert len({f.scheme_code for f in funds}) == 3


def test_a_truncated_page_is_not_a_smaller_universe():
    """`total_results` disagreeing with the row count is the only signal.

    Without this the screen would rank a partial universe and describe it as
    every fund on Groww, which is a false claim rather than a missing feature.
    """
    payload = {"content": _many(5), "total_results": 1741}
    with pytest.raises(GrowwUnavailable, match="truncated"):
        groww.parse_universe(payload)


def test_an_empty_universe_is_an_error():
    with pytest.raises(GrowwUnavailable, match="expected at least"):
        groww.parse_universe(_universe([]))


def test_a_payload_with_no_content_key_names_what_it_got():
    with pytest.raises(GrowwUnavailable, match="content"):
        groww.parse_universe({"results": [], "total_results": 0})


def test_an_unreadable_expense_ratio_is_none_and_never_zero():
    """Zero would sort the fund to the top of a cost ranking.

    Cost carries 55% of the fund score in this app, so an unparsed TER reading
    as free is the single most damaging possible coercion.
    """
    fund = groww.parse_universe(_universe(_many(3, expense_ratio="n/a")))[0]
    assert fund.expense_ratio is None


def test_the_two_disagreeing_sip_return_fields_are_not_read():
    """`sip_return3y` = 43.44 and `sipReturn3y` = 27.43 on the same live row.

    Which is which was never established. This test pins the decision to read
    neither, so that a later change has to argue with it rather than slip past.
    """
    fields = set(vars(groww.parse_universe(_universe(_many(3)))[0]))
    assert not {f for f in fields if "return" in f.lower()}


# --------------------------------------------------------------------------
# Scheme detail
# --------------------------------------------------------------------------

# A real PPFAS holdings slice. Positional, unlabelled, twelve wide.
_HOLDINGS = [
    ["122639", "2026-07-31", "HDFC Bank Ltd", "EQUITY", "Financial",
     "Equity", None, "11201.84", "7.55", None, None, "hdfc-bank-ltd"],
    ["122639", "2026-07-31", "Power Grid Corporation of India Ltd", "EQUITY",
     "Energy & Utilities", "Equity", None, "8869.25", "5.98", None, None, "power-grid"],
    ["122639", "2026-07-31", "ITC Ltd", "EQUITY", "Consumer Staples",
     "Equity", None, "8523.87", "5.74", None, None, "itc-ltd"],
    ["122639", "2026-07-31", "Cash and equivalents", "CASH", None,
     "Cash", None, "0", "80.73", None, None, None],
]


def _detail(**over):
    payload = {
        "isin": "INF879O01027",
        "scheme_code": "122639",
        "benchmark_name": "NIFTY 500 Total Return Index",
        "registrar_agent": "CAMS",
        "launch_date": "24-May-2013",
        "holdings": _HOLDINGS,
        "fund_manager_details": [
            {"person_name": "Mansi Kariya", "date_from": "2023-12-21T18:30:00.000Z"},
            {"person_name": "Raunak Onkar", "date_from": "2013-05-12T18:30:00.000Z"},
        ],
    }
    payload.update(over)
    return payload


def test_parses_a_real_scheme_detail():
    d = groww.parse_scheme_detail(_detail())
    assert d.isin == "INF879O01027"
    assert d.benchmark == "NIFTY 500 Total Return Index"
    assert d.launch_date == date(2013, 5, 24)
    assert len(d.holdings) == 4
    assert d.holdings[0].name == "HDFC Bank Ltd"
    assert d.holdings[0].weight_pct == 7.55
    assert d.holdings[0].sector == "Financial"
    assert d.holdings[0].as_of == date(2026, 7, 31)


def test_manager_tenure_dates_survive_parsing():
    """Tenure is the point. A manager list without dates cannot answer
    "has the person running this fund changed since you bought it"."""
    d = groww.parse_scheme_detail(_detail())
    assert {m.name for m in d.managers} == {"Mansi Kariya", "Raunak Onkar"}
    assert d.managers[1].since == date(2013, 5, 12)


def test_a_wrong_slug_returns_a_complete_object_of_nulls():
    """THE INCIDENT. HTTP 200, full shape, every field null.

    A hand-built slug (`parag-parikh-flexi-cap-fund-direct-growth`) returned
    exactly this. There is no status code and no error field to catch; the ISIN
    is the only thing that distinguishes it from a real fund with an unusually
    empty portfolio.
    """
    nulls = {k: None for k in _detail()}
    with pytest.raises(GrowwUnavailable, match="no ISIN"):
        groww.parse_scheme_detail(nulls)


def test_a_shifted_holdings_column_is_caught_by_the_weight_sum():
    """Every row stays well-formed; only the meaning moves.

    Inserting a column shifts weight_pct onto the rupee market value, so the
    weights become thousands. A per-row type check passes -- the values are
    still floats. Only the portfolio-level sum can see it.
    """
    shifted = [row[:2] + ["INSERTED"] + row[2:] for row in _HOLDINGS]
    with pytest.raises(GrowwUnavailable, match="shifted column"):
        groww.parse_holdings(shifted)


def test_a_fund_that_discloses_nothing_is_empty_not_an_error():
    """Missing disclosure and a broken feed must not look the same.

    An index fund mid-rebuild genuinely returns no holdings; raising here would
    turn a normal gap into an outage.
    """
    assert groww.parse_holdings([]) == ()
    assert groww.parse_holdings(None) == ()
    d = groww.parse_scheme_detail(_detail(holdings=[]))
    assert d.holdings == ()


def test_holdings_weights_are_the_funds_share_not_the_users():
    total = sum(h.weight_pct for h in groww.parse_holdings(_HOLDINGS))
    assert 85.0 <= total <= 115.0


def test_a_launch_date_is_parsed_without_locale_dependence():
    """`%b` is locale-dependent; on a German LC_TIME host Oct and Dec stop
    parsing and two months a year vanish. Same map, same reason, as the AMFI
    parser."""
    assert groww._parse_launch("24-May-2013") == date(2013, 5, 24)
    assert groww._parse_launch("01-Oct-2020") == date(2020, 10, 1)
    assert groww._parse_launch("01-Dec-2020") == date(2020, 12, 1)
    assert groww._parse_launch("garbage") is None
    assert groww._parse_launch(None) is None


def test_unavailability_is_its_own_type_so_callers_can_degrade():
    """The screener must still rank funds when Groww is unreachable.

    Groww is `Disallow: /v1/api/*` in robots.txt and could stop answering at any
    time. If this raised a plain RuntimeError, a caller would have to catch
    everything -- including its own bugs -- to keep the screen alive.
    """
    assert issubclass(GrowwUnavailable, RuntimeError)


def test_a_cached_payload_round_trips_through_json():
    """What is cached is the raw payload, not the parsed objects.

    So that a parser fix applies to yesterday's cache instead of needing the
    data pulled again -- and so a payload that failed to parse is still on disk
    to be read.
    """
    payload = _detail()
    assert groww.parse_scheme_detail(json.loads(json.dumps(payload))).isin == "INF879O01027"


# --------------------------------------------------------------------------
# The v5 shape -- named keys, which is what the module actually calls
# --------------------------------------------------------------------------

# A real PPFAS v5 holdings slice.
_V5_HOLDINGS = [
    {"scheme_code": "122639", "portfolio_date": "2026-07-30T18:30:00.000Z",
     "company_name": "HDFC Bank Ltd", "nature_name": "EQUITY",
     "sector_name": "Financial", "instrument_name": "Equity", "rating": None,
     "market_value": 11201.8423, "corpus_per": 7.54693626,
     "stock_search_id": "hdfc-bank-ltd"},
    # A real DEBT line. `rating` is None because that is what Groww actually
    # sends -- measured across 14 debt funds and 913 holdings on 2026-08-27,
    # including Credit Risk, Corporate Bond and Gilt funds: **zero** carried a
    # credit rating. The field exists in the payload and is always null.
    #
    # An earlier version of this fixture invented "SOV" here and the test
    # passed, asserting a behaviour the live feed never produces. That is the
    # exact failure this repo keeps recording: build the fixture from the real
    # mechanism, not from the one you assume.
    {"scheme_code": "122639", "portfolio_date": "2026-07-30T18:30:00.000Z",
     "company_name": "Treasury Bill", "nature_name": "DEBT",
     "sector_name": None, "instrument_name": "Debt", "rating": None,
     "market_value": 5000.0, "corpus_per": 92.45306374,
     "stock_search_id": None},
]


def test_v5_named_holdings_do_not_depend_on_column_order():
    """The whole reason the module calls v5.

    Reordering the keys of a dict changes nothing, which is exactly the property
    the v1 positional array does not have.
    """
    shuffled = [dict(reversed(list(r.items()))) for r in _V5_HOLDINGS]
    a = groww.parse_holdings(_V5_HOLDINGS)
    b = groww.parse_holdings(shuffled)
    assert a == b
    assert a[0].name == "HDFC Bank Ltd"
    assert a[0].weight_pct == 7.54693626
    assert a[0].sector == "Financial"
    assert a[0].as_of == date(2026, 7, 30)


def test_v5_carries_the_join_to_the_company_page():
    """`stock_search_id` is what makes look-through a lookup, not a name match.

    It is absent on cash and debt lines, and that absence must stay None rather
    than becoming an empty string that later joins to nothing and reports 0%.
    """
    h = groww.parse_holdings(_V5_HOLDINGS)
    assert h[0].stock_search_id == "hdfc-bank-ltd"
    assert h[1].stock_search_id is None


def test_credit_rating_is_carried_but_groww_never_populates_it():
    """Measured, not assumed: 0 of 913 holdings across 14 debt funds had one.

    The field is parsed because it is in the payload and may start arriving.
    It is pinned as None so that the day it *does* arrive, this test fails and
    somebody looks -- rather than a debt screen quietly starting to rank on a
    field that was blank for a year.

    This matters for the open defect in [[nextrade-code-defects]]: debt funds
    are still ranked on equity metrics, and the fix needs the SEBI Potential
    Risk Class. Groww does not carry PRC either -- probed for "potential risk",
    "risk class", "macaulay" and "interest rate risk"; none appear anywhere in
    the payload. So that defect cannot be closed from this source.
    """
    h = groww.parse_holdings(_V5_HOLDINGS)
    assert all(x.rating is None for x in h)


def test_both_endpoint_shapes_reach_the_same_guard():
    """An under-100% disclosure is wrong on v5 too, for a different reason.

    On v1 a short sum means a shifted column. On v5 it means the disclosure
    itself is incomplete -- which would silently understate every look-through
    exposure computed from it. Same tripwire, both shapes.
    """
    partial = [dict(_V5_HOLDINGS[0], corpus_per=7.5)]
    with pytest.raises(GrowwUnavailable, match="incomplete disclosure"):
        groww.parse_holdings(partial)


def test_a_mixed_or_unknown_row_shape_is_skipped_not_crashed():
    rows = list(_V5_HOLDINGS) + ["nonsense", 42, None]
    assert len(groww.parse_holdings(rows)) == 2
