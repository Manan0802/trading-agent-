"""Scoring an NSE-listed company against its sector peers.

Two rules shape everything here.

**Relative, not absolute.** Our own sector medians run from a P/E of 10.9 in
Energy to 49.3 in Consumer Defensive. An absolute valuation screen in India is
therefore a sector bet wearing a valuation costume: it ranks every PSU bank as
cheap and every FMCG name as dear, and says nothing about either company. Every
valuation factor here is scored against its own sector's median.

**A gap in the feed is not evidence against a company.** Anything unknown
scores half marks, so a thinly-covered small cap is neither rewarded nor
punished for our data rather than its business.

What is deliberately not here: price momentum, RSI, MACD and delivery
percentage. Delivery is no longer obtainable — NSE's endpoint returns 403 — and
the rest are trading signals. For someone deciding what to own for years, a
14-day oscillator is noise with a decimal point.
"""

from dataclasses import dataclass, field

# Fundamentals only, summing to 100. Quality (ROE) and earnings direction carry
# more than valuation because a cheap company that is shrinking rarely stays
# cheap in the way a buyer hopes.
FACTOR_WEIGHTS: dict[str, int] = {
    "pe": 22,
    "pb": 15,
    "roe": 25,
    "eps_growth": 25,
    "dividend_yield": 13,
}

_NEUTRAL = 0.5

# A promoter moving this much across four quarters is worth naming either way.
_PROMOTER_MOVE_PP = 2.0
_PROMOTER_BONUS = 4
_PROMOTER_PENALTY = -6


@dataclass(frozen=True)
class StockInputs:
    ticker: str
    name: str
    sector: str | None
    price: float | None = None
    pe: float | None = None
    pb: float | None = None
    roe: float | None = None
    dividend_yield: float | None = None
    eps_ttm: float | None = None
    eps_prev: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    # Oldest to newest, as published quarterly. Empty means genuinely no
    # promoter, which is true of many of India's largest companies.
    promoter_history: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class Factor:
    score: float
    detail: str


@dataclass(frozen=True)
class Adjustment:
    name: str
    points: int
    detail: str


@dataclass(frozen=True)
class StockScore:
    ticker: str
    name: str
    sector: str | None
    benchmark_used: str
    base_total: float
    adjustment_total: float
    total: float
    factors: dict[str, Factor]
    adjustments: list[Adjustment]
    range_position: float | None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _unknown(key: str, what: str) -> Factor:
    return Factor(FACTOR_WEIGHTS[key] * _NEUTRAL, f"Not published, scored neutral ({what})")


def _score_pe(pe: float | None, median: float | None) -> Factor:
    if pe is None or median is None:
        return _unknown("pe", "P/E")
    if pe <= 0:
        # A negative P/E means losses, not a bargain. Left as a raw number it
        # would sort below every cheap profitable company.
        return Factor(
            FACTOR_WEIGHTS["pe"] * 0.15,
            f"Loss-making, so there is no meaningful P/E (sector median {median:.0f})",
        )
    # Half the sector median scores full marks, twice it scores nothing.
    ratio = _clamp((2 * median - pe) / (1.5 * median))
    return Factor(
        FACTOR_WEIGHTS["pe"] * ratio,
        f"P/E {pe:.1f} against a sector median of {median:.1f}",
    )


def _score_pb(pb: float | None, median: float | None) -> Factor:
    if pb is None or median is None or pb <= 0:
        return _unknown("pb", "price to book")
    ratio = _clamp((2 * median - pb) / (1.5 * median))
    return Factor(
        FACTOR_WEIGHTS["pb"] * ratio,
        f"Price/book {pb:.2f} against a sector median of {median:.2f}",
    )


def _score_roe(roe: float | None, median: float | None) -> Factor:
    if roe is None or median is None:
        return _unknown("roe", "return on equity")
    # Twice the sector median is full marks; zero or negative is nothing.
    ratio = _clamp(roe / (2 * median)) if median > 0 else _NEUTRAL
    return Factor(
        FACTOR_WEIGHTS["roe"] * ratio,
        f"Return on equity {roe:.1%} against a sector median of {median:.1%}",
    )


def _score_eps_growth(ttm: float | None, previous: float | None) -> Factor:
    if ttm is None or previous is None or previous == 0:
        return _unknown("eps_growth", "earnings history")
    growth = (ttm - previous) / abs(previous)
    # -50% scores nothing, +50% scores full marks.
    ratio = _clamp((growth + 0.5) / 1.0)
    return Factor(
        FACTOR_WEIGHTS["eps_growth"] * ratio,
        f"Earnings per share {growth:+.0%} year on year",
    )


def _score_dividend_yield(yield_: float | None, median: float | None) -> Factor:
    if yield_ is None or median is None:
        return _unknown("dividend_yield", "dividend")
    target = max(median * 1.5, 0.01)
    ratio = _clamp(yield_ / target)
    if yield_ > 0.10:
        # A double-digit yield is usually a collapsed price, not generosity.
        ratio *= 0.5
    return Factor(
        FACTOR_WEIGHTS["dividend_yield"] * ratio,
        f"Dividend yield {yield_:.2%} against a sector median of {median:.2%}",
    )


def _promoter_adjustments(history: list[float]) -> list[Adjustment]:
    """Governance is India's dominant equity risk, and a promoter changing
    their own stake is the cheapest read on it available."""
    if len(history) < 2:
        return []
    move = history[-1] - history[0]
    if move <= -_PROMOTER_MOVE_PP:
        return [
            Adjustment(
                name="Promoter selling",
                points=_PROMOTER_PENALTY,
                detail=(
                    f"Promoter stake fell from {history[0]:.1f}% to {history[-1]:.1f}% "
                    "over the last four quarters"
                ),
            )
        ]
    if move >= _PROMOTER_MOVE_PP:
        return [
            Adjustment(
                name="Promoter buying",
                points=_PROMOTER_BONUS,
                detail=(
                    f"Promoter stake rose from {history[0]:.1f}% to {history[-1]:.1f}% "
                    "over the last four quarters"
                ),
            )
        ]
    return []


def score_stock(inputs: StockInputs, benchmarks: dict[str, dict]) -> StockScore:
    """Score one company. `benchmarks` is the sector-median table, which must
    carry an `_ALL` fallback for sectors we have too few peers for."""
    sector_key = inputs.sector if inputs.sector in benchmarks else "_ALL"
    bench = benchmarks.get(sector_key, {})

    factors = {
        "pe": _score_pe(inputs.pe, bench.get("pe")),
        "pb": _score_pb(inputs.pb, bench.get("pb")),
        "roe": _score_roe(inputs.roe, bench.get("roe")),
        "eps_growth": _score_eps_growth(inputs.eps_ttm, inputs.eps_prev),
        "dividend_yield": _score_dividend_yield(
            inputs.dividend_yield, bench.get("dividend_yield")
        ),
    }

    base_total = sum(f.score for f in factors.values())
    adjustments = _promoter_adjustments(inputs.promoter_history)
    adjustment_total = float(sum(a.points for a in adjustments))

    range_position = None
    if inputs.price and inputs.week52_high and inputs.week52_low:
        span = inputs.week52_high - inputs.week52_low
        if span > 0:
            range_position = _clamp((inputs.price - inputs.week52_low) / span)

    return StockScore(
        ticker=inputs.ticker,
        name=inputs.name,
        sector=inputs.sector,
        benchmark_used=sector_key,
        base_total=round(base_total, 2),
        adjustment_total=adjustment_total,
        # Reported separately above so an adjustment is never hidden inside a
        # total that cannot be questioned.
        total=round(_clamp(base_total + adjustment_total, 0.0, 100.0), 2),
        factors=factors,
        adjustments=adjustments,
        range_position=range_position,
    )
