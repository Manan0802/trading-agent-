"""The screener endpoints: shapes, filters, and the two ways they must not lie.

Users are minted from the 7100-7199 band, which no other test file uses.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from fastapi_users.jwt import generate_jwt

from app.config import get_settings
from app.database import Base, engine
from app.main import app
from app.middleware import rate_limit
from app.services.advisor import fund_catalogue
from app.services.screener import inputs as inputs_mod
from app.services.screener import navstore, pipeline, scoring, serve

client = TestClient(app)
_ids = iter(range(7100, 7200))


def setup_module():
    Base.metadata.create_all(bind=engine)


def auth() -> dict:
    from app.database import SessionLocal
    from app.models import User

    email = f"screener{next(_ids)}@example.com"
    with SessionLocal() as db:
        user = User(email=email, hashed_password="x", is_active=True, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        uid = user.id
    token = generate_jwt(
        {"sub": str(uid), "aud": ["fastapi-users:auth"]}, get_settings().jwt_secret, 3600
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    rate_limit.reset()
    yield
    navstore.reset_engine()
    rate_limit.reset()


def eligible_codes(n: int) -> list[str]:
    """Spread across scheme types, round-robin.

    Taking the first N in catalogue order lands them all in one scheme type,
    which quietly turns the asset-class filter test into a skip -- and a skipped
    test is a test that is not running. Round-robin also gives the grouped view
    more than one group to group.
    """
    by_type: dict[str, list[str]] = {}
    for f in fund_catalogue.all_funds():
        category, sub = inputs_mod.split_category(f.category)
        if inputs_mod.is_eligible(category)[0] and sub:
            by_type.setdefault(category, []).append(f.code)

    out: list[str] = []
    buckets = [iter(v) for v in by_type.values()]
    while len(out) < n and buckets:
        for bucket in list(buckets):
            code = next(bucket, None)
            if code is None:
                buckets.remove(bucket)
                continue
            out.append(code)
            if len(out) == n:
                return out
    if len(out) < n:
        raise AssertionError(f"only {len(out)} eligible funds available")
    return out


def seed(n: int = 40, rows: int = 900) -> None:
    with navstore.session() as s:
        for i, code in enumerate(eligible_codes(n)):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.05 + i * 3)
                 for d in range(rows)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=date.today(), refresh_feed=False)


# ------------------------------------------------------------------ access


@pytest.mark.parametrize(
    "path",
    ["/api/v1/screener/categories", "/api/v1/screener/top-funds",
     "/api/v1/screener/funds", "/api/v1/screener/funds/122639"],
)
def test_every_endpoint_requires_a_signed_in_user(path):
    assert client.get(path).status_code == 401


# --------------------------------------------------- the empty-store contract


def test_an_unbuilt_store_says_it_is_rebuilding_rather_than_showing_nothing():
    """Zero rows behind a 200 is indistinguishable from a market where nothing
    qualified. A 503 that names the progress is the honest answer."""
    response = client.get("/api/v1/screener/top-funds", headers=auth())
    assert response.status_code == 503
    assert "rebuilding" in response.json()["detail"]


# ------------------------------------------------------------------ shapes


def test_the_grouped_view_returns_leaders_coverage_and_dominance():
    seed()
    body = client.get("/api/v1/screener/top-funds", headers=auth()).json()
    assert body["groups"] and body["coverage"]["universe"] > 0
    for group in body["groups"]:
        assert group["peer_size"] >= serve.MIN_PEERS_TO_RANK
        assert len(group["funds"]) <= 5
        assert [f["category_rank"] for f in group["funds"]] == list(
            range(1, len(group["funds"]) + 1)
        )


def test_the_flat_view_returns_every_ranked_fund():
    seed()
    body = client.get("/api/v1/screener/funds", headers=auth()).json()
    assert len(body["funds"]) == body["coverage"]["shown"]
    assert [f["rank"] for f in body["funds"]] == list(range(1, len(body["funds"]) + 1))


def test_one_fund_can_be_fetched_on_its_own():
    seed()
    code = client.get("/api/v1/screener/funds", headers=auth()).json()["funds"][0]["scheme_code"]
    body = client.get(f"/api/v1/screener/funds/{code}", headers=auth()).json()
    assert body["scheme_code"] == code and body["name"]


def test_an_unknown_scheme_is_a_404_not_an_empty_body():
    seed()
    assert client.get("/api/v1/screener/funds/000000", headers=auth()).status_code == 404


def test_the_categories_endpoint_lists_every_filter_value_the_screen_offers():
    seed()
    body = client.get("/api/v1/screener/categories", headers=auth()).json()
    assert body["grades"] == ["Very Good", "Good", "Avg", "Bad"]
    assert body["risk_tiers"] == list(scoring.RISK_TIERS)
    assert body["categories"] and body["asset_classes"]
    for c in body["categories"]:
        assert c["rankable"] == (c["peer_size"] >= serve.MIN_PEERS_TO_RANK)


# ------------------------------------------------------------------ units


def test_no_ratio_leaves_the_api_as_a_percent():
    """`formatPercent()` takes a fraction. A volatility of 12.6 renders as
    "+1260.0%", and nothing upstream of the screen would notice, because the
    scorer's normalisation is scale-invariant."""
    seed()
    fields = ("returns_1m", "returns_3m", "returns_6m", "returns_1y", "returns_3y",
              "rolling_1m", "rolling_3m", "rolling_6m", "rolling_1y", "rolling_3y",
              "volatility", "max_drawdown", "worst_30d")
    body = client.get("/api/v1/screener/funds", headers=auth()).json()
    for fund in body["funds"]:
        for field in fields:
            value = fund[field]
            assert value is None or abs(value) < 2.0, f"{fund['scheme_code']}.{field}={value}"
        for field in ("fund_score", "momentum_signal", "drawdown_signal", "risk_score"):
            value = fund[field]
            assert value is None or 0.0 <= value <= 1.0


# ------------------------------------------------------------------ filters


def test_a_filter_narrows_the_list_without_renumbering_it():
    """The `#` column must keep meaning "rank in the universe". If it were
    derived client-side it would silently become "third of what is showing"."""
    seed()
    headers = auth()
    everything = client.get("/api/v1/screener/funds", headers=headers).json()["funds"]
    ranks = {f["scheme_code"]: f["rank"] for f in everything}

    # Pick a class that actually appears and is not the whole list -- the seed
    # takes the first N catalogue funds, so which classes turn up is incidental.
    counts: dict[str, int] = {}
    for f in everything:
        counts[f["asset_class"]] = counts.get(f["asset_class"], 0) + 1
    partial = [c for c, n in counts.items() if 0 < n < len(everything)]
    assert partial, f"the seed should span asset classes but gave {counts}"
    chosen = partial[0]

    filtered = client.get(
        f"/api/v1/screener/funds?asset_class={chosen}", headers=headers
    ).json()["funds"]
    assert 0 < len(filtered) < len(everything)
    for f in filtered:
        assert f["rank"] == ranks[f["scheme_code"]]


@pytest.mark.parametrize(
    "query,what",
    [("asset_class=Bonds", "asset class"), ("grade=Excellent", "grade"),
     ("risk_tier=Spicy", "risk tier"), ("category=Nonsense%20Fund", "category")],
)
def test_an_unknown_filter_value_is_a_404_that_names_the_valid_ones(query, what):
    """An unknown filter returning an empty list looks exactly like a real market
    in which nothing qualified, which is the wrong thing to show someone who has
    mistyped."""
    seed()
    response = client.get(f"/api/v1/screener/funds?{query}", headers=auth())
    assert response.status_code == 404
    assert what in response.json()["detail"]


@pytest.mark.parametrize("value", [0, 26, -1])
def test_an_out_of_range_page_size_is_rejected(value):
    seed()
    r = client.get(f"/api/v1/screener/top-funds?per_category={value}", headers=auth())
    assert r.status_code == 422


def seed_a_dominant_sub_category() -> str:
    """Build a universe where one sub-category genuinely runs away with its class.

    Round-robin seeding spreads funds evenly, which is realistic but produces no
    dominance at all -- and a test that asserts things about an empty list
    asserts nothing. Here one sub-category of one scheme type gets strongly
    rising NAVs and its neighbours get flat ones, so it takes the top ten on
    merit and clears the lift bar.

    Returns the asset class it built.
    """
    by_sub: dict[tuple, list[str]] = {}
    for f in fund_catalogue.all_funds():
        category, sub = inputs_mod.split_category(f.category)
        if inputs_mod.is_eligible(category)[0] and sub:
            by_sub.setdefault((category, sub), []).append(f.code)

    for (category, sub), codes in sorted(by_sub.items(), key=lambda kv: -len(kv[1])):
        others = [
            c for (cat, s), cs in by_sub.items()
            if cat == category and s != sub for c in cs
        ]
        if len(codes) >= 12 and len(others) >= 12:
            winners, losers = codes[:12], others[:12]
            break
    else:
        raise AssertionError("no scheme type has two sub-categories big enough")

    with navstore.session() as s:
        for i, code in enumerate(winners):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.12 + i)
                 for d in range(900)],
            )
            navstore.record_source(s, code, backfilled_at="x")
        for i, code in enumerate(losers):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.002 + i)
                 for d in range(900)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=date.today(), refresh_feed=False)
    return serve.ASSET_CLASS_OF.get(category, "Other")


def test_dominance_describes_the_market_not_the_current_filter():
    """"9 of the top 10" is a statement about the universe. Recomputing it inside
    a filter would make it "9 of the top 10 things you are looking at", which is
    not an observation about anything."""
    dominant_class = seed_a_dominant_sub_category()
    headers = auth()
    everything = client.get("/api/v1/screener/top-funds", headers=headers).json()["dominance"]
    assert everything, "the fixture failed to produce any dominance, so this proves nothing"
    assert any(d["asset_class"] == dominant_class for d in everything)

    # Narrow to an asset class that is NOT the dominant one. If dominance were
    # recomputed over the filtered rows it would come back describing that other
    # class, or empty. Comparing two lists that merely happen to be equal proves
    # nothing -- the first version of this test passed with the bug present.
    other = next(
        (c for c in sorted(set(serve.ASSET_CLASS_OF.values())) if c != dominant_class),
        None,
    )
    narrowed = client.get(
        f"/api/v1/screener/top-funds?asset_class={other}", headers=headers
    ).json()["dominance"]
    assert narrowed == everything, (
        "dominance was recomputed over the filtered rows, so it now describes "
        "only what the user is looking at rather than the market"
    )


# ------------------------------------------------------------ rate limiting


def test_the_full_universe_endpoint_is_rate_limited_and_the_screen_is_not():
    """Both pinned, because they are one `_HEAVY_PATHS` edit apart.

    `/funds` ships the whole universe, about 1.2 MB with no compression
    middleware installed, so 120/min of it is a self-DoS. `/top-funds` is what
    the screen actually calls, and putting it on the 20/min tier would 429 a user
    who changes a filter and expands three rows -- which `sweep.mjs` counts as a
    failure.
    """
    assert rate_limit.tier_for("/api/v1/screener/funds") is rate_limit.HEAVY
    assert rate_limit.tier_for("/api/v1/screener/funds/122639") is rate_limit.HEAVY
    assert rate_limit.tier_for("/api/v1/screener/top-funds") is rate_limit.DEFAULT
    assert rate_limit.tier_for("/api/v1/screener/categories") is rate_limit.DEFAULT


# ------------------------------------------------------------- coverage


def test_the_coverage_line_adds_up_on_every_endpoint():
    seed()
    headers = auth()
    for path in ("/api/v1/screener/top-funds", "/api/v1/screener/funds",
                 "/api/v1/screener/categories"):
        cov = client.get(path, headers=headers).json()["coverage"]
        assert cov["scored"] + cov["universe"] - cov["scored"] == cov["universe"]
        assert cov["categories_ranked"] + len(cov["thin_categories"]) == cov["categories_total"]
        assert cov["as_of"] is not None
        assert cov["missing_columns"] == ["Fund size (AUM)", "Minimum investment"]


def test_the_same_fund_carries_the_same_score_on_every_endpoint():
    """Three paths, one number. Two different right-looking values for the same
    thing is what `scripts/consistency.py` exists to catch."""
    seed()
    headers = auth()
    flat = client.get("/api/v1/screener/funds", headers=headers).json()["funds"][0]
    single = client.get(
        f"/api/v1/screener/funds/{flat['scheme_code']}", headers=headers
    ).json()
    grouped = [
        f
        for g in client.get("/api/v1/screener/top-funds", headers=headers).json()["groups"]
        for f in g["funds"]
        if f["scheme_code"] == flat["scheme_code"]
    ]
    assert single["fund_score"] == flat["fund_score"]
    if grouped:
        assert grouped[0]["fund_score"] == flat["fund_score"]
        assert grouped[0]["rank"] == flat["rank"]


# ------------------------------------------------------------------ reasons


def test_the_grouped_view_ships_its_bullets_inline():
    """Not fetched per row. 195 rows x one request each against a 120/min budget
    is a 429, and `sweep.mjs` counts any response of 400 or worse as a failure."""
    seed()
    body = client.get("/api/v1/screener/top-funds", headers=auth()).json()
    everyone = [f for g in body["groups"] for f in g["funds"]]
    assert everyone
    assert all("reasons" in f for f in everyone)


def test_the_rank_never_reaches_the_client_in_any_form():
    """The rule is that a fund speaks only when it is genuinely near the top of
    its peer group, and that the rank itself is never printed -- only the value.
    Keeping it off the wire is the strongest available enforcement: a template
    cannot render what it never receives."""
    seed()
    body = client.get("/api/v1/screener/top-funds", headers=auth()).json()
    for group in body["groups"]:
        for fund in group["funds"]:
            for reason in fund["reasons"]:
                assert "rank" not in reason, reason
                assert "#" not in reason["text"], reason["text"]


def test_most_funds_say_nothing_which_is_the_whole_point():
    """A bullet appears only for a fund genuinely in the top 15% AND top 5 of its
    peer group. If most funds had something to say, the rule would have stopped
    meaning anything."""
    seed()
    body = client.get("/api/v1/screener/top-funds", headers=auth()).json()
    everyone = [f for g in body["groups"] for f in g["funds"]]
    silent = [f for f in everyone if not f["reasons"]]
    assert silent, "every single fund had a claim to make, which cannot be right"


def test_the_flat_universe_view_ships_without_bullets():
    """Deliberate. Bullets for the whole universe would roughly double a payload
    that is already the reason this endpoint is rate-limited."""
    seed()
    body = client.get("/api/v1/screener/funds", headers=auth()).json()
    assert all(f["reasons"] == [] for f in body["funds"])


def test_an_expanded_row_gets_its_bullets():
    seed()
    headers = auth()
    grouped = client.get("/api/v1/screener/top-funds", headers=headers).json()
    with_bullets = [
        f for g in grouped["groups"] for f in g["funds"] if f["reasons"]
    ]
    if not with_bullets:
        pytest.skip("the seeded universe produced no claims at all")
    code = with_bullets[0]["scheme_code"]
    single = client.get(f"/api/v1/screener/funds/{code}", headers=headers).json()
    assert single["reasons"] == with_bullets[0]["reasons"]


# ═══════════════════════════════════════════════════════════ stocks


import pandas as pd  # noqa: E402

from app.services.marketdata import stock as stock_data  # noqa: E402
from app.services.marketdata.stock import StockFundamentals  # noqa: E402
from app.services.screener import stock_scoring  # noqa: E402


def _fundamentals(**over) -> StockFundamentals:
    base = dict(
        ticker="X.NS", name="Test Ltd", price=600.0, previous_close=595.0,
        currency="INR", sector="Technology", industry="Software", market_cap=1e12,
        pe_ratio=24.0, eps=25.0, book_value=120.0, dividend_yield_pct=1.4,
        week52_high=700.0, week52_low=400.0, roe=0.18,
        eps_reported=25.0, eps_previous_year=20.0,
    )
    base.update(over)
    return StockFundamentals(**base)


@pytest.fixture
def offline_stocks(monkeypatch):
    """Every stock endpoint test runs without a network.

    The real path fetches yfinance once per company; a test suite that did that
    would be slow and would fail whenever yfinance did.
    """
    closes = pd.Series(
        [400.0 + i * 0.5 for i in range(400)],
        index=pd.bdate_range("2025-01-01", periods=400),
    )
    monkeypatch.setattr(
        stock_data, "get_stock_fundamentals",
        lambda t: _fundamentals(ticker=t, name=f"{t} Ltd"),
    )
    monkeypatch.setattr(
        stock_data, "get_price_history",
        lambda t, period="2y": pd.DataFrame({"Close": closes}),
    )


def test_the_stock_screen_requires_a_signed_in_user():
    assert client.get("/api/v1/screener/stocks").status_code == 401
    assert client.get("/api/v1/screener/stocks/TCS.NS").status_code == 401


def test_the_stock_screen_returns_scored_companies_and_its_coverage(offline_stocks):
    body = client.get("/api/v1/screener/stocks?limit=8", headers=auth()).json()
    assert len(body["stocks"]) == 8
    cov = body["coverage"]
    assert cov["matched"] >= cov["scored"]
    assert cov["scored"] + len(cov["unscorable"]) == 8
    assert cov["benchmark_stocks"] > 100


def test_the_stocks_come_back_best_first(offline_stocks):
    body = client.get("/api/v1/screener/stocks?limit=10", headers=auth()).json()
    totals = [s["total"] for s in body["stocks"]]
    assert totals == sorted(totals, reverse=True)


def test_every_stock_carries_all_ten_factors_with_their_weights(offline_stocks):
    body = client.get("/api/v1/screener/stocks?limit=4", headers=auth()).json()
    for stock in body["stocks"]:
        assert len(stock["factors"]) == 10
        assert sum(f["max"] for f in stock["factors"]) == pytest.approx(100.0)
        for f in stock["factors"]:
            assert f["detail"], "a factor with no explanation is a number with no meaning"
            assert 0.0 <= f["score"] <= f["max"] or f["key"] == "roe"


def test_the_two_halves_of_the_score_are_shown_separately(offline_stocks):
    """The disclosure says how much of the total is momentum. A reader should be
    able to see it rather than take it on trust."""
    stock = client.get("/api/v1/screener/stocks?limit=1", headers=auth()).json()["stocks"][0]
    assert stock["fundamental"] > 0 and stock["technical"] > 0
    assert stock["fundamental"] + stock["technical"] == pytest.approx(stock["total"], abs=0.05)


def test_the_dead_delivery_factor_is_disclosed_on_every_response(offline_stocks):
    """NSE's quote-equity returns 403, so 9 of the 100 points are the same
    neutral half for every stock, forever. Upstream never says so."""
    cov = client.get("/api/v1/screener/stocks?limit=2", headers=auth()).json()["coverage"]
    assert cov["neutral_factors"]
    assert "9 points" in cov["neutral_factors"][0]
    assert "403" in cov["neutral_factors"][0] or "refuses" in cov["neutral_factors"][0]


def test_the_momentum_share_is_disclosed_on_every_response(offline_stocks):
    """41 of the 100 points are indicators traa's own scorer excludes on
    measured grounds. Ported faithfully and said out loud."""
    cov = client.get("/api/v1/screener/stocks?limit=2", headers=auth()).json()["coverage"]
    assert "41" in cov["method_note"]
    assert "Research" in cov["method_note"]


def test_the_peer_group_each_stock_was_priced_against_is_named(offline_stocks):
    """Upstream silently uses a default benchmark for an unmapped sector and
    never surfaces it."""
    for stock in client.get(
        "/api/v1/screener/stocks?limit=4", headers=auth()
    ).json()["stocks"]:
        assert stock["benchmark_sector"]
        assert stock["benchmark_constituents"] > 0


def test_a_company_too_new_to_score_is_named_not_dropped(monkeypatch):
    """Fourteen closes is a perfect 100 "Strong Buy" in the unguarded port. It
    must reach the screen as a named exclusion instead."""
    short = pd.Series(
        [400.0 + i for i in range(14)], index=pd.bdate_range("2026-01-01", periods=14)
    )
    monkeypatch.setattr(stock_data, "get_stock_fundamentals", lambda t: _fundamentals(ticker=t))
    monkeypatch.setattr(
        stock_data, "get_price_history", lambda t, period="2y": pd.DataFrame({"Close": short})
    )
    cov = client.get("/api/v1/screener/stocks?limit=5", headers=auth()).json()["coverage"]
    assert cov["scored"] == 0
    assert len(cov["unscorable"]) == 5
    assert all("15 needed" in u["reason"] for u in cov["unscorable"])


def test_no_stock_ever_comes_back_at_a_perfect_hundred(offline_stocks):
    """The signature of a NaN passing through `max(0, min(100, nan))`."""
    for stock in client.get(
        "/api/v1/screener/stocks?limit=20", headers=auth()
    ).json()["stocks"]:
        assert stock["total"] < 100.0


@pytest.mark.parametrize(
    "query,what",
    [("index=NIFTY%20999", "index"), ("bucket=Screaming%20Buy", "bucket"),
     ("industry=Nonsense", "industry")],
)
def test_an_unknown_stock_filter_is_a_404_that_names_the_valid_values(query, what, offline_stocks):
    r = client.get(f"/api/v1/screener/stocks?{query}&limit=2", headers=auth())
    assert r.status_code == 404
    assert what in r.json()["detail"]


@pytest.mark.parametrize("limit", [0, 201, -1])
def test_an_out_of_range_stock_limit_is_rejected(limit, offline_stocks):
    assert client.get(
        f"/api/v1/screener/stocks?limit={limit}", headers=auth()
    ).status_code == 422


def test_the_bucket_filter_uses_the_scorers_own_labels(offline_stocks):
    body = client.get("/api/v1/screener/stocks?limit=2", headers=auth()).json()
    assert body["buckets"] == list(stock_scoring.BUCKET_LABELS)
    for label in body["buckets"]:
        assert client.get(
            f"/api/v1/screener/stocks?bucket={label}&limit=4", headers=auth()
        ).status_code == 200


def test_one_stock_can_be_fetched_on_its_own(offline_stocks):
    listed = client.get("/api/v1/screener/stocks?limit=1", headers=auth()).json()["stocks"][0]
    body = client.get(f"/api/v1/screener/stocks/{listed['ticker']}", headers=auth()).json()
    assert body["ticker"] == listed["ticker"]
    assert body["total"] == listed["total"]
    assert len(body["factors"]) == 10


def test_a_ticker_outside_the_universe_is_a_404(offline_stocks):
    assert client.get(
        "/api/v1/screener/stocks/NOTAREALTICKER.NS", headers=auth()
    ).status_code == 404


def test_the_stock_screen_is_on_the_heavy_rate_limit_tier():
    """One yfinance fetch per company. 120/min of a cold NIFTY 500 is a way to
    get the whole app throttled by upstream rather than by us."""
    assert rate_limit.tier_for("/api/v1/screener/stocks") is rate_limit.HEAVY
    assert rate_limit.tier_for("/api/v1/screener/stocks/TCS.NS") is rate_limit.HEAVY


# ═══════════════════════════════════════════════════════════ baskets


from app.services.screener import basket as basket_port  # noqa: E402
from app.services.screener import basket_slots  # noqa: E402


def seed_basket_universe(rows: int = 900) -> None:
    codes: list[str] = []
    for slot in basket_slots.SLOT_CATEGORIES:
        codes.extend(basket_slots.codes_for_slot(slot)[:12])
    codes = list(dict.fromkeys(codes))
    with navstore.session() as s:
        for i, code in enumerate(codes):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i * 0.7)
                 for d in range(rows)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=date.today(), refresh_feed=False)


def test_the_basket_endpoints_require_a_signed_in_user():
    assert client.get("/api/v1/screener/baskets").status_code == 401
    assert client.get("/api/v1/screener/baskets/MAXX").status_code == 401


def test_an_unbuilt_store_says_it_is_rebuilding_rather_than_returning_no_baskets():
    r = client.get("/api/v1/screener/baskets", headers=auth())
    assert r.status_code == 503
    assert "rebuilding" in r.json()["detail"]


def test_every_basket_comes_back_with_its_sleeves_filled():
    seed_basket_universe()
    body = client.get("/api/v1/screener/baskets", headers=auth()).json()
    assert len(body["baskets"]) == 2
    for b in body["baskets"]:
        assert b["filled"] == len(b["slots"]), [
            (s["slot_key"], s["reason"]) for s in b["slots"] if not s["scheme_code"]
        ]
        assert b["success"]


def test_the_weights_of_a_basket_sum_to_one():
    seed_basket_universe()
    for b in client.get("/api/v1/screener/baskets", headers=auth()).json()["baskets"]:
        total = sum(s["weight"] for s in b["slots"] if s["weight"] is not None)
        assert total == pytest.approx(1.0, abs=0.01)


def test_both_the_shown_weight_and_the_agreed_one_reach_the_client():
    """The optimiser respects every cap and then a momentum adjustment scales
    and renormalises without re-checking. A reader who cares about the cap needs
    the second number, and it does not otherwise exist."""
    seed_basket_universe()
    for b in client.get("/api/v1/screener/baskets", headers=auth()).json()["baskets"]:
        for s in b["slots"]:
            if s["weight"] is None:
                continue
            assert s["weight_within_bounds"] is not None
            assert s["weight_within_bounds"] <= s["cap_applied"] + 1e-9


def test_the_cap_asked_for_and_the_cap_enforced_are_both_reported():
    """They differ when the per-slot maxima cannot sum to 1, at which point the
    optimiser silently rescales them."""
    seed_basket_universe()
    for b in client.get("/api/v1/screener/baskets", headers=auth()).json()["baskets"]:
        for s in b["slots"]:
            assert s["cap_asked"] > 0 and s["cap_applied"] > 0


def test_the_three_standing_disclosures_are_on_every_basket():
    """All three were confirmed by running the ported optimiser, and none is
    visible in its own output."""
    seed_basket_universe()
    for b in client.get("/api/v1/screener/baskets", headers=auth()).json()["baskets"]:
        joined = " ".join(b["method_notes"])
        assert "do not change the allocation" in joined
        assert "above a sleeve's cap" in joined
        assert "Minimum investment is not considered" in joined


def test_the_two_mega_bucket_sleeves_carry_their_caveat():
    """A basket filling its index sleeve from 364 funds tracking different
    indices is making a sector bet whether or not anyone intended to."""
    seed_basket_universe()
    slots = {
        s["slot_key"]: s
        for b in client.get("/api/v1/screener/baskets", headers=auth()).json()["baskets"]
        for s in b["slots"]
    }
    assert slots["Equity Index Fund"]["caveat"]
    assert slots["Sectoral/ Thematic"]["caveat"]
    assert slots["Debt Scheme::Liquid Fund"]["caveat"] is None


def test_how_many_funds_competed_for_each_sleeve_is_reported():
    seed_basket_universe()
    for b in client.get("/api/v1/screener/baskets", headers=auth()).json()["baskets"]:
        for s in b["slots"]:
            if s["scheme_code"]:
                assert s["pool_size"] > 0


def test_one_basket_can_be_fetched_on_its_own():
    seed_basket_universe()
    listed = client.get("/api/v1/screener/baskets", headers=auth()).json()["baskets"][0]
    body = client.get(
        f"/api/v1/screener/baskets/{listed['basket_id']}", headers=auth()
    ).json()
    assert body["basket_id"] == listed["basket_id"]
    assert [s["scheme_code"] for s in body["slots"]] == [
        s["scheme_code"] for s in listed["slots"]
    ]


@pytest.mark.parametrize(
    "query,what",
    [("strategy=reckless", "strategy"), ("regime=sideways", "regime")],
)
def test_an_unknown_basket_setting_is_a_404_that_names_the_valid_values(query, what):
    seed_basket_universe()
    r = client.get(f"/api/v1/screener/baskets?{query}", headers=auth())
    assert r.status_code == 404 and what in r.json()["detail"]


def test_an_unknown_basket_is_a_404():
    seed_basket_universe()
    assert client.get(
        "/api/v1/screener/baskets/INSTA_FD", headers=auth()
    ).status_code == 404


def test_the_strategy_setting_reaches_the_response_even_though_it_changes_nothing():
    """It is offered because the reference offers it, and the disclosure says it
    does nothing. Both halves have to be true: the setting is honoured in the
    response, and the numbers do not move."""
    seed_basket_universe()
    weights = {}
    for strategy in ("conservative", "aggressive"):
        b = client.get(
            f"/api/v1/screener/baskets/MAXX?strategy={strategy}", headers=auth()
        ).json()
        assert b["strategy"] == strategy
        weights[strategy] = [s["weight"] for s in b["slots"]]
    assert weights["conservative"] == pytest.approx(weights["aggressive"], abs=1e-4)
