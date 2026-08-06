import json
from pathlib import Path
"""Read-only endpoints for looking things up before deciding anything."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.fastapi_users_app import current_active_user
from app.models import User
from app.schemas.research import (
    FundDetailOut,
    FundSearchResultOut,
    StockFundamentalsOut,
    StockUniverseOut,
    UniverseStockOut,
    CategoryRankingV2Out,
    RankedFundV2Out,
    UnscorableFundOut,
    VerdictOut,
    WindowOut,
    StockScoreOut,
    RankedStockOut,
    StockRankingOut,
    UnscorableStockOut,
    FactorOut,
    AdjustmentOut,
    FundEvidenceOut,
)
from app.services.advisor import fund_metrics
from app.services.advisor.category_ranking import rank_category as build_category_ranking
from app.services.advisor.fund_evidence import build_evidence
from app.services.advisor.fund_score import evidence_strength
from app.services.advisor.stock_analysis import analyse as analyse_stock
from app.services.advisor.stock_ranking import rank_stocks as rank_stock_universe
from app.services.advisor.fund_catalogue import BROWSABLE_CATEGORIES, is_browsable
from app.services.advisor.fund_universe import BENCHMARK_BY_ASSET_CLASS
from app.services.marketdata import mutual_fund, stock, stock_universe

router = APIRouter(prefix="/api/v1/research", tags=["research"])

# A multi-year chart does not need every daily NAV, and sending 3,000+ points
# per fund would dominate the payload.
_CHART_POINTS = 260

# Hard ceiling on a ranked screen regardless of what the caller asks for. Each
# company is two Yahoo requests on a cold cache, and a request that tries to
# price 751 of them times out rather than finishing slowly.
_MAX_RANKED = 120


def _downsample(points: list, limit: int = _CHART_POINTS) -> list:
    if len(points) <= limit:
        return points
    step = len(points) / limit
    return [points[int(i * step)] for i in range(limit)] + [points[-1]]


@router.get("/funds/search", response_model=list[FundSearchResultOut])
def search_funds(
    q: str = Query(min_length=3),
    user: User = Depends(current_active_user),
):
    try:
        return mutual_fund.search_schemes(q)
    except mutual_fund.MutualFundDataError as exc:
        raise HTTPException(503, f"Fund search is temporarily unavailable ({exc})") from exc


@router.get("/funds/{scheme_code}", response_model=FundDetailOut)
def get_fund(
    scheme_code: str,
    user: User = Depends(current_active_user),
):
    try:
        meta = mutual_fund.get_scheme_meta(scheme_code)
        navs = mutual_fund.get_nav_history(scheme_code)
        benchmark = mutual_fund.get_nav_history(
            BENCHMARK_BY_ASSET_CLASS["equity"]
        ) if "equity" in meta.scheme_category.lower() else None
    except mutual_fund.MutualFundDataError as exc:
        raise HTTPException(503, f"Fund data is temporarily unavailable ({exc})") from exc

    return FundDetailOut(
        scheme_code=meta.scheme_code,
        scheme_name=meta.scheme_name,
        fund_house=meta.fund_house,
        category=meta.scheme_category,
        is_direct_growth=meta.is_direct_growth,
        latest_nav=navs[-1].nav,
        latest_nav_date=navs[-1].date,
        metrics=fund_metrics.compute_metrics(navs, benchmark),
        # The same evidence the ranking is built from, so a fund's detail view
        # and its position in the list cannot tell two different stories.
        evidence=_evidence_out(
            build_evidence(meta.scheme_code, meta.scheme_name, meta.scheme_category, navs)
        ),
        nav_series=_downsample(navs),
    )


def _evidence_out(evidence) -> "FundEvidenceOut | None":
    if evidence is None:
        return None
    return FundEvidenceOut(
        history_years=(
            round(evidence.history_years, 1)
            if evidence.history_years is not None
            else None
        ),
        evidence_strength=round(evidence_strength(evidence.history_years), 4),
        windows={k: WindowOut.model_validate(v) for k, v in evidence.windows.items()},
        direct_ter=evidence.direct_ter,
        regular_ter=evidence.regular_ter,
    )


@router.get("/fund-categories", response_model=list[str])
def list_fund_categories(user: User = Depends(current_active_user)):
    """Every SEBI category with enough funds to rank against each other."""
    return BROWSABLE_CATEGORIES


@router.get("/fund-rankings/{category:path}", response_model=CategoryRankingV2Out)
def rank_category_v2(
    category: str,
    monthly_sip: float | None = None,
    years: int | None = None,
    user: User = Depends(current_active_user),
):
    """Every fund in a SEBI category, ranked on the shape of its record.

    `monthly_sip` and `years` only price the direct-vs-regular commission gap
    in rupees over the caller's horizon; the ranking itself does not depend on
    them, so an anonymous browse and a specific goal see the same order.
    """
    if not is_browsable(category):
        raise HTTPException(404, f"Unknown fund category: {category}")

    try:
        result = build_category_ranking(category, monthly_sip=monthly_sip, years=years)
    except mutual_fund.MutualFundDataError as exc:
        raise HTTPException(503, f"Fund data is temporarily unavailable ({exc})") from exc

    return CategoryRankingV2Out(
        category=result.category,
        priced=result.priced,
        unscorable=[UnscorableFundOut.model_validate(u) for u in result.unscorable],
        ranked=[
            RankedFundV2Out(
                rank=r.rank,
                scheme_code=r.fund.scheme_code,
                scheme_name=r.fund.scheme_name,
                category=r.fund.category,
                score=r.fund.score,
                breakdown=r.fund.breakdown,
                evidence_strength=r.fund.evidence_strength,
                history_years=(
                    round(r.fund.evidence.history_years, 1)
                    if r.fund.evidence.history_years is not None
                    else None
                ),
                windows={
                    k: WindowOut.model_validate(v)
                    for k, v in r.fund.evidence.windows.items()
                },
                volatility=r.fund.evidence.volatility,
                max_drawdown=r.fund.evidence.max_drawdown,
                direct_ter=r.fund.evidence.direct_ter,
                regular_ter=r.fund.evidence.regular_ter,
                verdict=VerdictOut.model_validate(r.verdict),
            )
            for r in result.ranked
        ],
    )


@router.get("/stocks", response_model=StockUniverseOut)
def browse_stocks(
    index: str | None = None,
    industry: str | None = None,
    q: str | None = None,
    limit: int = 100,
    user: User = Depends(current_active_user),
):
    """The browsable NSE universe, from the committed index constituent lists.

    Names only. Live prices and fundamentals are fetched per stock when one is
    opened, because 751 yfinance calls is not a page anyone waits for.
    """
    matches = stock_universe.list_stocks(index=index, industry=industry, query=q)
    return StockUniverseOut(
        stocks=[UniverseStockOut.model_validate(s) for s in matches[:limit]],
        total=len(matches),
        available_indices=stock_universe.INDEX_CHOICES,
        available_industries=stock_universe.industries(),
    )


# Declared before /stocks/{ticker}: FastAPI matches in order, and the dynamic
# route would otherwise swallow "ranked" as a ticker symbol.
@router.get("/stocks/ranked", response_model=StockRankingOut)
def rank_stocks_endpoint(
    index: str = "NIFTY 50",
    industry: str | None = None,
    q: str | None = None,
    limit: int = 50,
    user: User = Depends(current_active_user),
):
    """Every company in the filter, ranked against each other.

    Defaults to the NIFTY 50 because it is the only slice that is fast on a
    cold cache. Widening the index is allowed and honest — the response reports
    how many companies matched against how many were actually priced, so a
    partial ranking never presents itself as the whole market.
    """
    matches = stock_universe.list_stocks(index=index, industry=industry, query=q)
    label = " · ".join(p for p in (index, industry, q) if p) or "All stocks"
    result = rank_stock_universe(label, matches, limit=min(limit, _MAX_RANKED))

    return StockRankingOut(
        label=result.label,
        ranked=[
            RankedStockOut(
                rank=r.rank,
                ticker=r.score.ticker,
                name=r.score.name,
                sector=r.score.sector,
                benchmark_used=r.score.benchmark_used,
                total=r.score.total,
                factors={
                    k: FactorOut.model_validate(v) for k, v in r.score.factors.items()
                },
                range_position=r.score.range_position,
            )
            for r in result.ranked
        ],
        unscorable=[
            UnscorableStockOut.model_validate(u) for u in result.unscorable
        ],
        matched=result.matched,
        covered=result.covered,
    )


@router.get("/stocks/{ticker}/score", response_model=StockScoreOut)
def score_stock_endpoint(
    ticker: str,
    user: User = Depends(current_active_user),
):
    """Score one company against its sector peers, with the reasoning attached.

    Valuation is judged against the sector median rather than an absolute bar:
    our own medians run from a P/E of 10.9 in energy to 49.3 in consumer
    defensive, so an absolute screen would be a sector bet in disguise.
    """
    try:
        result, verdict = analyse_stock(ticker)
    except stock.StockDataError as exc:
        raise HTTPException(404, str(exc)) from exc

    return StockScoreOut(
        ticker=result.ticker,
        name=result.name,
        sector=result.sector,
        benchmark_used=result.benchmark_used,
        base_total=result.base_total,
        adjustment_total=result.adjustment_total,
        total=result.total,
        factors={k: FactorOut.model_validate(v) for k, v in result.factors.items()},
        adjustments=[AdjustmentOut.model_validate(a) for a in result.adjustments],
        range_position=result.range_position,
        verdict=VerdictOut.model_validate(verdict),
    )


@router.get("/stocks/{ticker}", response_model=StockFundamentalsOut)
def get_stock(
    ticker: str,
    user: User = Depends(current_active_user),
):
    try:
        return stock.get_stock_fundamentals(ticker)
    except stock.StockDataError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/evidence")
def get_factor_evidence():
    """What has actually been shown to work, and what has not.

    Deliberately unauthenticated and deliberately static. This is not the
    user's data -- it is thirty-two years of published Indian factor returns,
    survivorship-bias adjusted, built by academics with no stake in this app.

    Served from a committed file rather than computed: the underlying series
    updates monthly and a thirty-two-year regression has no business running on
    a page load. `built_on` travels with it so a stale file cannot pass for a
    fresh one. Rebuild with scripts/build_factor_evidence.py.
    """
    path = Path(__file__).resolve().parent.parent / "data" / "factor_evidence.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        # A missing file is an outage, not an empty result. Returning {} would
        # render as "nothing has been shown to work", which is a claim.
        raise HTTPException(
            503,
            "The factor evidence file is missing or unreadable. Run "
            "scripts/build_factor_evidence.py to rebuild it.",
        ) from exc
