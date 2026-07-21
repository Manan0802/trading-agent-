"""Read-only endpoints for looking things up before deciding anything."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.fastapi_users_app import current_active_user
from app.models import User
from app.schemas.research import (
    CategoryRankingOut,
    FundDetailOut,
    FundSearchResultOut,
    StockFundamentalsOut,
)
from app.services.advisor import fund_metrics
from app.services.advisor.fund_recommender import load_scored_universe
from app.services.advisor.fund_universe import (
    BENCHMARK_BY_ASSET_CLASS,
    BENCHMARK_CAVEAT,
    BENCHMARK_NAME,
    UNIVERSE,
)
from app.services.marketdata import mutual_fund, stock

router = APIRouter(prefix="/api/v1/research", tags=["research"])

# A multi-year chart does not need every daily NAV, and sending 3,000+ points
# per fund would dominate the payload.
_CHART_POINTS = 260


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
        nav_series=_downsample(navs),
    )


@router.get("/categories/{asset_class}", response_model=CategoryRankingOut)
def rank_category(
    asset_class: str,
    user: User = Depends(current_active_user),
):
    """Every fund we track in a category, scored against each other."""
    if asset_class not in UNIVERSE:
        raise HTTPException(404, f"Unknown asset class: {asset_class}")

    try:
        result = load_scored_universe(asset_class)
    except mutual_fund.MutualFundDataError as exc:
        raise HTTPException(503, f"Fund data is temporarily unavailable ({exc})") from exc

    benchmarked = BENCHMARK_BY_ASSET_CLASS.get(asset_class) is not None
    return CategoryRankingOut(
        asset_class=asset_class,
        benchmarked=benchmarked,
        benchmark_name=BENCHMARK_NAME if benchmarked else None,
        benchmark_caveat=BENCHMARK_CAVEAT if benchmarked else None,
        ranked=result.ranked,
        unscorable=result.unscorable,
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
