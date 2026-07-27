"""Fetching what a company's score needs, and turning the result into a verdict.

Separated from the scoring itself so the score stays a pure function of its
inputs and can be tested without the network.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.advisor.stock_score import StockInputs, StockScore, score_stock
from app.services.marketdata import stock as stock_data
from app.services.marketdata.promoter import promoter_history

_BENCHMARKS = (
    Path(__file__).resolve().parent.parent.parent / "data" / "sector_benchmarks.json"
)


@lru_cache(maxsize=1)
def sector_benchmarks() -> dict[str, dict]:
    try:
        return json.loads(_BENCHMARKS.read_text())
    except (OSError, ValueError):
        # Without the table every valuation factor scores neutral, which is
        # honest: we cannot say whether a P/E is high without a peer group.
        return {}


@dataclass(frozen=True)
class StockVerdict:
    headline: str
    points: list[str]
    caveat: str | None = None


def analyse(ticker: str, *, with_promoter: bool = True) -> tuple[StockScore, StockVerdict]:
    """Score one NSE company and say what the score means."""
    fundamentals = stock_data.get_stock_fundamentals(ticker)
    symbol = ticker.upper().removesuffix(".NS")

    history = promoter_history(symbol) if with_promoter else []

    inputs = StockInputs(
        ticker=fundamentals.ticker,
        name=fundamentals.name,
        sector=fundamentals.sector,
        price=fundamentals.price,
        pe=fundamentals.pe_ratio,
        pb=(
            fundamentals.price / fundamentals.book_value
            if fundamentals.book_value
            else None
        ),
        roe=fundamentals.roe,
        dividend_yield=(
            fundamentals.dividend_yield_pct / 100
            if fundamentals.dividend_yield_pct is not None
            else None
        ),
        # The statement's own latest year, not .info's TTM: the growth
        # factor divides these two and they must come from one source.
        eps_ttm=fundamentals.eps_reported,
        eps_prev=fundamentals.eps_previous_year,
        week52_high=fundamentals.week52_high,
        week52_low=fundamentals.week52_low,
        promoter_history=history,
    )
    result = score_stock(inputs, sector_benchmarks())
    return result, build_stock_verdict(result)


def build_stock_verdict(result: StockScore) -> StockVerdict:
    """What the score says, in the terms a buyer would use."""
    sector = result.sector or "the market"
    if result.benchmark_used == "_ALL":
        peer_phrase = "the whole listed market, since its sector has too few peers to median"
    else:
        peer_phrase = f"other {sector} companies"

    headline = (
        f"Scores {result.total:.0f} out of 100 against {peer_phrase}, on what the "
        "business earns and what you pay for it."
    )

    points = [
        f.detail
        for key, f in result.factors.items()
        if not f.detail.startswith("Not published")
    ]

    for adjustment in result.adjustments:
        points.append(f"{adjustment.detail} ({adjustment.points:+d} points).")

    if result.range_position is not None:
        points.append(
            f"Trading {result.range_position:.0%} of the way up its 52-week range. "
            "That is where the price sits, not a view on where it goes next."
        )

    missing = [
        key for key, f in result.factors.items() if f.detail.startswith("Not published")
    ]
    caveat = None
    if missing:
        caveat = (
            f"{len(missing)} of {len(result.factors)} measures are not published for "
            "this company, so they were scored neutral rather than guessed. The score "
            "rests on less evidence than it does for a better-covered name."
        )

    return StockVerdict(headline=headline, points=points, caveat=caveat)
