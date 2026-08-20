"""The exact arithmetic Bachatt ranks NSE-listed companies on, transcribed from their source.

Ported from `sip-optimizer`:
    services/stock_scorer.py            -- the ten factors, the bonus/penalty layer, the buckets
    scripts/update_sector_benchmarks.py -- what has to be in `SectorBenchmark` (see below)

Every constant below carries the name it has in their code so the two files can
be diffed by eye. `tests/test_stock_scoring_parity.py` does better than eye: it
executes their real source as an oracle and asserts this module returns the
same numbers.

**The shape of the score, in one block:**

    fundamental 50 = pe 15 + eps_growth 12 + roe 10 + pb 8 + div_yield 5
    technical   50 = rsi 12 + macd 12 + ema_trend 10 + delivery 9 + support 7

    total = clamp(sum(factors) + sum(bonuses and penalties), 0, 100)
    bucket = 80 Strong Buy / 60 Buy / 40 Hold / 20 Weak-Avoid / 0 Bearish

**The tension, named rather than hidden.** Half of this score is chart reading.
Take delivery out of it -- it is a flow measure, not an oscillator -- and RSI,
MACD, EMA trend and support buffer still carry 41 of the 100 points. traa's own
`services/advisor/stock_score.py` excludes exactly those four, and says why:
"For someone deciding what to own for years, a 14-day oscillator is noise with a
decimal point." Both statements are in this repo on purpose. This module
**reproduces** their score, it does not endorse it, and the screen that renders
it discloses the split -- fundamental and technical totals are returned
separately (`fundamental`, `technical`) precisely so the disclosure has numbers
to quote and cannot quietly be dropped.

**Purity.** No network, no database, no clock. Price history arrives as a pandas
Series or a list of `(date, close)` pairs; fundamentals arrive as a plain
record; delivery, promoter holding and financials arrive as arguments. Their
`score_stock` fetches all of that itself from yfinance, NSE and Screener.in,
which is why theirs cannot be differentially tested and this can. Their output
also carries `datetime.now()`, `price_history` and the raw `financials` echo --
presentation, not arithmetic, and deliberately not here.
"""

from __future__ import annotations

from typing import Any, Sequence, TypedDict

import numpy as np
import pandas as pd

# ── Weights (stock_scorer.py WEIGHTS) ────────────────────────────────────────
# Sums to exactly 100. Listed in their order, which is not the order they are
# summed in (that is FACTOR_KEYS) and not the order of FACTOR_CATEGORIES.
WEIGHTS = {
    "pe":          15,
    "eps_growth":  12,
    "roe":         10,
    "pb":           8,
    "div_yield":    5,
    "rsi":         12,
    "macd":        12,
    "ema_trend":   10,
    "delivery":     9,
    "support":      7,
}

# ── Buckets (stock_scorer.py BUCKETS) ────────────────────────────────────────
# Applied to the clamped 0-100 total, first threshold that the score reaches.
# Boundaries are inclusive: exactly 80 is "Strong Buy", exactly 60 is "Buy".
BUCKETS = [
    (80, "Strong Buy"),
    (60, "Buy"),
    (40, "Hold"),
    (20, "Weak / Avoid"),
    (0,  "Bearish"),
]

# The labels alone, in the order they are awarded. A filter offering "Strong
# Buy" has to spell it exactly as the scorer does.
BUCKET_LABELS = tuple(label for _threshold, label in BUCKETS)

# ── Bonus / penalty magnitudes (stock_scorer.py BP) ──────────────────────────
# Their promoter numbers are symmetric (-3 / +3). traa's own scorer is not
# (-6 / +4), on the view that a promoter selling tells you more than a promoter
# buying. Ported as theirs; the asymmetry belongs to the other module.
BP = {
    "dual_growth_bonus_l1":   +3,   # both >= 15%
    "dual_growth_bonus_l2":   +5,   # both >= 30%
    "dual_growth_bonus_l3":   +7,   # both >= 50%
    "profit_decay_penalty":   -4,
    "accumulation_bonus":     +3,
    "distribution_penalty":   -2,
    "confirming_bullish":     +2,
    "confirming_bearish":     -2,
    "promoter_selling":       -3,
    "promoter_buying":        +3,
}


class SectorBenchmark(TypedDict):
    """The per-sector median record the four valuation factors read.

    Four keys, and the units are not uniform -- this is the part a builder gets
    wrong. From `scripts/update_sector_benchmarks.py`:

      median_pe        float | None. Median `trailingPE` across a hand-picked
                       large+mid-cap basket for the sector, keeping only
                       0 < PE < 200, rounded to 1dp. **None when fewer than 3
                       basket members returned a usable PE** -- and `_score_pe`
                       divides by it without checking, so a None here is a
                       TypeError at scoring time, not a neutral score. Whoever
                       builds the table has to decide what to do about that;
                       upstream simply has not hit it yet.
      median_pb        float | None. Median `priceToBook`, keeping 0 < PB < 50,
                       rounded to 2dp. None below 3 usable values. Same
                       division-by-None exposure in `_score_pb`.
      median_roe       float, in PERCENT (14.0 means 14%). Median of
                       `returnOnEquity` * 100, keeping 0 < roe < 2.0 in raw
                       decimal, rounded to 1dp, needing only 2 usable values,
                       and falling back to a hard-coded per-sector constant
                       below that -- so this key is never None. Note the unit
                       flip: the benchmark is a percent, the company's own ROE
                       reaches `_score_roe` as a decimal fraction.
      median_div_yield float, in PERCENT (1.68 means 1.68%). NOT from yfinance:
                       they take the `dy` field of NSE's `allIndices` response
                       for a hand-mapped index per sector, because yfinance
                       "returns erroneous values like 13% for banks". 0.0 on any
                       failure, which is safe -- `_score_div_yield` floors the
                       target at 1.5.

    The table itself is `{sector_name: SectorBenchmark}` plus a default record
    used when the sector is unknown or absent; `resolve_benchmark` reproduces
    their lookup. Building the table is a separate task and deliberately not
    done here -- it is a live fetch from two flaky sources, and this module is
    pure.
    """

    median_pe: float | None
    median_pb: float | None
    median_roe: float
    median_div_yield: float


class Fundamentals(TypedDict, total=False):
    """What their `_fetch_fundamentals` returns, as a plain record.

    Units, again, because they are not uniform: `roe` and `insider_pct` are raw
    decimal fractions from yfinance (0.23 means 23%), while `div_yield` is
    already a percent (3.57 means 3.57%). Nothing in the scorer reconciles
    those; each factor function just knows which it is being handed.
    """

    trailing_pe: float | None
    price_to_book: float | None
    roe: float | None
    div_yield: float | None
    eps_ttm: float | None
    eps_prev: float | None
    current_price: float | None
    name: str
    sector: str | None
    industry: str | None
    insider_pct: float | None


# ─────────────────────────────────────────────────────────────────────────────
# Technical indicators (pure pandas, unchanged from theirs)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_rsi(close: pd.Series, period: int = 14) -> float:
    """Wilder RSI via `ewm(com=period-1)`.

    `min_periods=period` means this needs **14 non-null deltas**, i.e. 15
    closes, and returns NaN below that rather than raising. Their caller guards
    with `len(close) >= 14`, which is one short.

    What that costs is not a NaN in the output. `_score_rsi` propagates the NaN
    through `np.exp`, `base_total` becomes NaN, and then the display clamp runs
    `max(0.0, min(100.0, nan))` -- and Python's `min` returns 100.0, because
    `nan < 100.0` is False. So a company with exactly 14 closes of history
    scores **100.0 and is bucketed "Strong Buy"**, the highest score the model
    can produce, on no information at all. Newly listed companies are precisely
    the ones with 14 days of history.

    Reproduced, with the guard reproduced too -- see `score_stock`, where the
    clamp is. `tests/test_stock_scoring_parity.py` pins the number so it cannot
    quietly change, and the screen must never rank on it.
    """
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss
    return float((100 - (100 / (1 + rs))).iloc[-1])


def _compute_macd(close: pd.Series, fast=12, slow=26, signal_span=9):
    """`adjust=False` and no `min_periods`, so this returns a number at any
    length -- a 3-day "26-day EMA" is arithmetically fine and economically
    meaningless. Their `len(close) >= 26` guard is what stops that, not this."""
    ema_fast    = close.ewm(span=fast,        adjust=False).mean()
    ema_slow    = close.ewm(span=slow,        adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_span, adjust=False).mean()
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1])


def _compute_ema(close: pd.Series, span: int) -> float:
    return float(close.ewm(span=span, adjust=False).mean().iloc[-1])


def _compute_support(close: pd.Series, lookback: int = 180, window: int = 10) -> float:
    """Most-recent swing low within `lookback` days.

    Falls back to the 90-day minimum when no swing low is found -- which is
    every series under 21 rows, because the scan range is empty. The fallback is
    what makes this the one indicator that always returns a real number.
    """
    recent = close.tail(lookback)
    arr    = recent.values
    swing_lows = []
    for i in range(window, len(arr) - window):
        val = arr[i]
        if val < arr[i - window:i].min() and val < arr[i + 1:i + window + 1].min():
            swing_lows.append(val)
    return float(swing_lows[-1]) if swing_lows else float(close.tail(90).min())


# ─────────────────────────────────────────────────────────────────────────────
# Base scoring functions
# ─────────────────────────────────────────────────────────────────────────────

def _clamp(x, lo=-1.0, hi=1.0):
    """Default bounds are **-1 to 1**, not 0 to 1.

    Load-bearing and easy to mistype. `_score_roe` and `_score_pe` call it with
    the defaults; `_score_pb`, `_score_div_yield`, `_score_delivery` and
    `_score_support` pass 0, 1 explicitly. `_score_pe` maps -1..1 onto 0..1
    afterwards, but `_score_roe` does not -- see there.
    """
    return max(lo, min(hi, x))


def _score_pe(pe, weight, benchmark):
    """A loss-making company scores half marks here, not zero.

    `pe <= 0` means the company lost money, and it takes the same neutral
    treatment as a missing P/E. At 10x the sector median a profitable company
    scores 0.0, so upstream ranks a company with no earnings above a company
    with expensive ones. traa's own scorer gives losses 0.15 of the weight
    instead, deliberately. Ported as theirs.
    """
    if pe is None or pe <= 0:
        return weight * 0.5, "N/A (neutral)"
    median = benchmark["median_pe"]
    ratio  = (median - pe) / median
    score  = weight * ((_clamp(ratio) + 1) / 2)
    return score, f"PE {pe:.1f} vs sector median {median:.0f}"


def _score_eps_growth(eps_ttm, eps_prev, weight):
    """Growth off a negative base, scored as if it meant something.

    The denominator is `abs(eps_prev)`, so a company that went from -10 to +5
    reads as "+150%" and takes **full marks**. That is a return to profit, not
    150% growth, and the arithmetic cannot tell the difference. traa's own
    scorer refuses the calculation outright in that case and says so in words.
    Reproduced here, including the `eps_prev == 0` -> neutral escape (which is
    the only zero-division guard).
    """
    if eps_ttm is None or eps_prev is None or eps_prev == 0:
        return weight * 0.5, "N/A (neutral)"
    growth = (eps_ttm - eps_prev) / abs(eps_prev)
    score  = weight * ((_clamp(growth, -1, 1) + 1) / 2)
    pct    = growth * 100
    return score, f"TTM ₹{eps_ttm:.2f}, Prev ₹{eps_prev:.2f} ({'+' if pct >= 0 else ''}{pct:.1f}%)"


def _score_roe(roe_dec, weight, benchmark):
    """The only factor that can return a **negative** score.

    `_clamp` is called with its -1..1 defaults and the result is used as the
    multiplier directly, with no `(x+1)/2` remap. A company with ROE of -30%
    against a 15% median therefore contributes -10 points out of a possible +10,
    a 20-point swing on a 10-point factor. Every other factor is bounded to
    [0, weight]. Whether that is intended is not ours to decide; it is
    reproduced exactly, and it is why a stock total can go below zero before
    the final clamp.

    `roe_dec` is a decimal fraction (0.23), `median_roe` is a percent (23.0);
    the `* 100` is what reconciles them. A `median_roe` of 0 would divide by
    zero -- the benchmark builder's fallback table is what prevents it.
    """
    if roe_dec is None:
        return weight * 0.5, "N/A (neutral)"
    roe_pct = roe_dec * 100
    median  = benchmark["median_roe"]
    ratio   = _clamp(roe_pct / (median * 2))
    score   = weight * ratio
    return score, f"ROE {roe_pct:.1f}% vs sector median {median:.0f}%"


def _score_pb(pb, weight, benchmark):
    """Clamped 0..1 and inverted, so this one cannot go negative. A P/B at or
    above twice the sector median scores nothing; a missing or non-positive P/B
    scores half."""
    if pb is None or pb <= 0:
        return weight * 0.5, "N/A (neutral)"
    median = benchmark["median_pb"]
    ratio  = _clamp(pb / (median * 2), 0, 1)
    score  = weight * (1 - ratio)
    return score, f"P/B {pb:.2f} vs sector median {median:.1f}"


def _score_div_yield(dy_pct, weight, benchmark):
    """The asymmetry: **missing scores 0.0 here, not half marks.**

    Every other factor treats an absent input as "we do not know" and awards
    half the weight. This one treats it as "there is no dividend" and awards
    nothing. That is defensible -- yfinance omits `dividendYield` for companies
    that pay none, so absence usually is evidence -- but it is not always true,
    and a company whose yield simply failed to fetch is punished for our feed.
    Five points of the hundred hang on that reading.

    The 0.7 haircut above 8% is theirs and is the right instinct: a double-digit
    yield in India is usually a collapsed share price, not generosity. Note the
    comparison is strict, so exactly 8.00% keeps full credit.
    """
    if dy_pct is None:
        return 0.0, "No dividend"
    median     = benchmark["median_div_yield"]
    target     = max(median * 2, 1.5)
    normalized = _clamp(dy_pct / target, 0, 1)
    if dy_pct > 8:
        normalized *= 0.7
    score = weight * normalized
    return score, f"Yield {dy_pct:.2f}% vs sector median {median:.1f}%"


def _score_rsi(rsi, weight):
    """A Gaussian centred on RSI 50 with a width of 15.

    Peak marks go to a stock doing nothing in particular, and both oversold and
    overbought are punished symmetrically -- so this factor rewards the absence
    of a trend, while `_score_ema_trend` twelve lines down rewards its presence.
    NaN in (see `_compute_rsi`) is NaN out: `np.exp` propagates it silently and
    the stock's whole total becomes NaN.
    """
    if rsi is None:
        return weight * 0.5, "N/A (neutral)"
    score = weight * np.exp(-0.5 * ((rsi - 50) / 15) ** 2)
    zone  = "Oversold" if rsi < 30 else ("Overbought" if rsi > 70 else "Neutral")
    return score, f"RSI {rsi:.1f} ({zone})"


def _score_macd(macd_val, signal_val, weight):
    """Normalised by `abs(macd_val)`, not by the signal or the histogram.

    So the score depends on how large the gap is *relative to the MACD line
    itself*, and a MACD line near zero makes the ratio explode into the clamp
    regardless of how small the actual crossover is. The `1e-9` is the only
    thing standing between this and a division by zero. Labelling is off by a
    tie: `diff == 0` prints "Bearish cross" while scoring exactly neutral.
    """
    if macd_val is None or signal_val is None:
        return weight * 0.5, "N/A (neutral)"
    diff   = macd_val - signal_val
    ratio  = _clamp(diff / (abs(macd_val) + 1e-9), -1, 1)
    score  = weight * ((ratio + 1) / 2)
    signal = "Bullish cross" if diff > 0 else "Bearish cross"
    return score, f"MACD {macd_val:.2f}, Signal {signal_val:.2f} — {signal}"


def _score_ema_trend(price, ema50, ema200, weight):
    """Distance above the 200-day EMA, saturating at +/-20%, plus a cross bonus.

    `ema50 is None` (fewer than 50 closes) means no bonus and no label at all --
    not a death cross, just silence. When ema50 is present, `ema50 == ema200`
    falls to the else branch and prints "Death Cross"; ties go bearish. The
    golden-cross bonus is 10% of the weight and `min(weight, ...)` caps the
    factor, so a stock already 20% above its 200-day EMA gains nothing from the
    cross -- the bonus only moves stocks in the middle of the range.
    """
    if price is None or ema200 is None:
        return weight * 0.5, "N/A (neutral)"
    pct_above = (price - ema200) / ema200
    base      = weight * ((_clamp(pct_above, -0.2, 0.2) / 0.2 + 1) / 2)
    bonus     = 0
    label     = ""
    if ema50 is not None:
        if ema50 > ema200:
            bonus = weight * 0.1
            label = " · Golden Cross"
        else:
            label = " · Death Cross"
    score = min(weight, base + bonus)
    if ema50 is not None:
        return score, f"Price ₹{price:.0f} · EMA50 ₹{ema50:.0f} · EMA200 ₹{ema200:.0f}{label}"
    return score, f"Price ₹{price:.0f} · EMA200 ₹{ema200:.0f}{label}"


def _score_delivery(delivery_pct, weight):
    """9% of every score is a constant 4.5 points, and upstream never says so.

    Delivery percentage has exactly one source in their code: NSE's
    `quote-equity?section=trade_info` endpoint. That endpoint returns **403** --
    verified today, for us and for them; their fetcher swallows the exception
    and returns None, and None lands here. So `weight * 0.5` is not an edge
    case, it is the value this factor takes for every stock on every run, and
    it is 9 of the 100 points. Their UI renders it as a scored factor reading
    "Market closed / data unavailable" at 50%, which is not the same as saying
    the factor is dead.

    We reproduce the neutral score, because parity is the point. The screen
    states the fact, because honesty is also the point.
    """
    if delivery_pct is None:
        return weight * 0.5, "Market closed / data unavailable"
    normalized = _clamp(delivery_pct / 80.0, 0, 1)
    score      = weight * normalized
    return score, f"Delivery {delivery_pct:.1f}% (>65% = strong conviction)"


def _score_support(price, support, weight):
    """How far above the nearest swing low the price sits, full marks at +20%.

    Rewards a stock for having already run up off its support, which is the
    opposite of what a value buyer wants and the opposite of what `_score_pe`
    rewards. Clamped 0..1, so a price below support scores zero rather than
    negative.
    """
    if price is None or support is None or price == 0:
        return weight * 0.5, "N/A (neutral)"
    distance = (price - support) / price
    score    = weight * _clamp(distance / 0.20, 0, 1)
    return score, f"₹{price:.0f} · Support ₹{support:.0f} · {distance*100:.1f}% buffer"


# ─────────────────────────────────────────────────────────────────────────────
# Bonus / penalty layer
#
# All four of these are already pure in their source -- they take records and
# return records. They are the only part of their scorer that could be tested
# upstream, and it is not.
# ─────────────────────────────────────────────────────────────────────────────

def _check_profit_decay(financials: dict) -> dict | None:
    """Penalty: QoQ net profit declined 2 consecutive quarters.

    Note it filters out `None` profits *before* taking the last three, so three
    non-adjacent quarters with a gap between them are compared as if they were
    consecutive. `abs()` in the denominators means a swing through a loss
    produces a percentage that reads backwards in the detail string.
    """
    quarters = financials.get("quarterly", [])
    profits  = [q["profit"] for q in quarters if q.get("profit") is not None]

    # profits is in chronological order (oldest -> newest)
    if len(profits) < 3:
        return None

    # Take the 3 most recent
    p_older, p_prev, p_latest = profits[-3], profits[-2], profits[-1]

    if p_latest < p_prev < p_older:
        delta1 = ((p_prev   - p_older) / abs(p_older)) * 100
        delta2 = ((p_latest - p_prev)  / abs(p_prev))  * 100
        return {
            "key":    "profit_decay_penalty",
            "label":  "⚠️ Consecutive Profit Decline",
            "points": BP["profit_decay_penalty"],
            "detail": (
                f"Net profit fell {delta1:.1f}% then {delta2:.1f}% in last 2 quarters "
                f"(₹{p_older:.0f}Cr → ₹{p_prev:.0f}Cr → ₹{p_latest:.0f}Cr)"
            ),
            "type": "penalty",
        }
    return None


def _check_dual_growth(financials: dict) -> list[dict]:
    """Bonus: latest annual revenue AND profit both grew >= 15/30/50% YoY.

    Graded on `min(revenue growth, profit growth)`, so both have to clear the
    bar -- that part is sound. The `abs()` denominators are not: a company
    recovering from a loss-making year clears 50% trivially and collects +7.
    Same defect as `_score_eps_growth`, in a different function.

    Also appends a zero-point QoQ row purely so the UI has something to render.
    It is in `adjustments`, it sums into `adjustment_total` as 0, and it is not
    a signal.
    """
    results: list[dict] = []

    # ── YoY bonus ─────────────────────────────────────────────────────────────
    annual = financials.get("annual", [])
    if len(annual) >= 2:
        latest = annual[-1]
        prev   = annual[-2]
        rev_l, rev_p = latest.get("revenue"), prev.get("revenue")
        pnl_l, pnl_p = latest.get("profit"),  prev.get("profit")

        if None not in (rev_l, rev_p, pnl_l, pnl_p) and rev_p != 0 and pnl_p != 0:
            rev_growth = ((rev_l - rev_p) / abs(rev_p)) * 100
            pnl_growth = ((pnl_l - pnl_p) / abs(pnl_p)) * 100
            min_growth = min(rev_growth, pnl_growth)

            if min_growth >= 50:
                pts, label = BP["dual_growth_bonus_l3"], "🟢 Dual Growth YoY (Revenue + Profit ≥ 50%)"
            elif min_growth >= 30:
                pts, label = BP["dual_growth_bonus_l2"], "🟢 Dual Growth YoY (Revenue + Profit ≥ 30%)"
            elif min_growth >= 15:
                pts, label = BP["dual_growth_bonus_l1"], "🟢 Dual Growth YoY (Revenue + Profit ≥ 15%)"
            else:
                pts, label = None, None

            if pts is not None:
                results.append({
                    "key":    "dual_growth_bonus",
                    "label":  label,
                    "points": pts,
                    "detail": (
                        f"Revenue {rev_growth:+.1f}% · Profit {pnl_growth:+.1f}% YoY "
                        f"(₹{rev_p:.0f}Cr → ₹{rev_l:.0f}Cr  |  ₹{pnl_p:.0f}Cr → ₹{pnl_l:.0f}Cr)"
                    ),
                    "type": "bonus",
                })

    # ── QoQ info (0 pts) ──────────────────────────────────────────────────────
    quarterly = financials.get("quarterly", [])
    if len(quarterly) >= 2:
        q_latest = quarterly[-1]
        q_prev   = quarterly[-2]
        rev_ql, rev_qp = q_latest.get("revenue"), q_prev.get("revenue")
        pnl_ql, pnl_qp = q_latest.get("profit"),  q_prev.get("profit")

        if None not in (rev_ql, rev_qp, pnl_ql, pnl_qp) and rev_qp != 0 and pnl_qp != 0:
            rev_qg = ((rev_ql - rev_qp) / abs(rev_qp)) * 100
            pnl_qg = ((pnl_ql - pnl_qp) / abs(pnl_qp)) * 100
            results.append({
                "key":    "dual_growth_qoq_info",
                "label":  "ℹ️ QoQ Growth (Revenue + Profit)",
                "points": 0,
                "detail": (
                    f"Revenue {rev_qg:+.1f}% · Profit {pnl_qg:+.1f}% QoQ "
                    f"(₹{rev_qp:.0f}Cr → ₹{rev_ql:.0f}Cr  |  ₹{pnl_qp:.0f}Cr → ₹{pnl_ql:.0f}Cr)"
                ),
                "type": "neutral",
            })

    return results


def _check_promoter_holding(promoter_data: dict | None, insider_pct_fallback: float | None) -> list[dict]:
    """Promoter holding level (0 points) and change (+/-3 points).

    Two things to know about the fallback. yfinance's `heldPercentInsiders` is
    not promoter holding -- it is an American disclosure concept that maps onto
    India's promoter category only loosely -- and when it is used, `history` is
    empty, so the change signal silently never fires. A stock scored off the
    fallback can never earn or lose the +/-3.

    Their docstring says the level bonus is "0-5 pts based on current holding
    %". It is not: every level branch emits `"points": 0`. The docstring is
    stale, the code is what ships, and the code is what is ported.
    """
    adjustments = []

    # Resolve current promoter %
    if promoter_data is not None:
        pct     = promoter_data["latest"]
        history = promoter_data["history"]
    elif insider_pct_fallback is not None:
        pct     = insider_pct_fallback * 100   # yfinance returns 0-1 fraction
        history = []
    else:
        return adjustments

    # ── 1. Static level info (0 pts — informational only) ────────────────────
    if pct > 50:
        label = "🟢 Promoter Holding Very Healthy (>50%)"
        tier  = "very_healthy"
    elif pct > 40:
        label = "🟢 Promoter Holding Healthy (40–50%)"
        tier  = "healthy"
    elif pct >= 20:
        label = "⚠️ Promoter Holding Moderate (20–40%)"
        tier  = "moderate"
    else:
        label = "🔴 Promoter Holding Low (<20%)"
        tier  = "bad"

    adjustments.append({
        "key":    f"promoter_{tier}",
        "label":  label,
        "points": 0,
        "detail": f"Promoter / Insider holding: {pct:.1f}%",
        "type":   "neutral",
    })

    # ── 2. Change-based bonus / penalty ──────────────────────────────────────
    if len(history) >= 2:
        oldest  = history[0]
        latest  = history[-1]
        change  = latest - oldest   # positive = holding increased

        if change <= -2.0:
            adjustments.append({
                "key":    "promoter_selling",
                "label":  "🔴 Promoter Reducing Stake",
                "points": BP["promoter_selling"],
                "detail": (
                    f"Promoter holding fell {abs(change):.1f}pp over last {len(history)} quarters "
                    f"({oldest:.1f}% → {latest:.1f}%)"
                ),
                "type": "penalty",
            })
        elif change >= 2.0:
            adjustments.append({
                "key":    "promoter_buying",
                "label":  "🟢 Promoter Increasing Stake",
                "points": BP["promoter_buying"],
                "detail": (
                    f"Promoter holding rose {change:.1f}pp over last {len(history)} quarters "
                    f"({oldest:.1f}% → {latest:.1f}%)"
                ),
                "type": "bonus",
            })

    return adjustments


def _check_price_delivery_correlation(close: pd.Series, delivery_today: float | None) -> dict | None:
    """20-day price direction crossed with today's delivery percentage.

    Dead in practice for the same reason `_score_delivery` is: `delivery_today`
    is always None, the first line returns None, and none of the four signals
    below has ever fired in production. Their own docstring calls the method a
    proxy and flags true correlation as a future enhancement.

    Kept and ported anyway, because the moment a delivery source exists this is
    the code that decides -3 to +3 on a stock, and it should be under test
    before then rather than after.
    """
    if delivery_today is None or len(close) < 25:
        return None

    # 20-day price trend
    price_now  = float(close.iloc[-1])
    price_20d  = float(close.iloc[-21])
    price_trend_pct = ((price_now - price_20d) / price_20d) * 100
    price_falling = price_trend_pct < -3     # down >3% in 20 days
    price_rising  = price_trend_pct > +3     # up >3% in 20 days

    # Delivery signal: >65% = high conviction; <40% = speculative
    delivery_high = delivery_today >= 65
    delivery_low  = delivery_today < 40

    # Scenario classification
    if price_falling and delivery_high:
        # Smart money accumulating on dip — most bullish divergence
        return {
            "key":    "accumulation_bonus",
            "label":  "✅ Accumulation Signal (Price ↓ + Delivery ↑)",
            "points": BP["accumulation_bonus"],
            "detail": (
                f"Price down {abs(price_trend_pct):.1f}% over 20 days but delivery "
                f"{delivery_today:.1f}% — investors buying the dip, not panic-selling"
            ),
            "type": "bonus",
        }

    if price_rising and delivery_low:
        # Speculative rally — price driven by intraday traders, no real conviction
        return {
            "key":    "distribution_penalty",
            "label":  "⚠️ Distribution Signal (Price ↑ + Delivery ↓)",
            "points": BP["distribution_penalty"],
            "detail": (
                f"Price up {price_trend_pct:.1f}% over 20 days but delivery only "
                f"{delivery_today:.1f}% — rally driven by intraday speculation, not investors"
            ),
            "type": "penalty",
        }

    if price_rising and delivery_high:
        return {
            "key":    "confirming_bullish",
            "label":  "✅ Confirming Bullish (Price ↑ + Delivery ↑)",
            "points": BP["confirming_bullish"],
            "detail": (
                f"Price up {price_trend_pct:.1f}% with high delivery {delivery_today:.1f}% "
                f"— genuine investor-driven uptrend"
            ),
            "type": "bonus",
        }

    if price_falling and delivery_low:
        return {
            "key":    "confirming_bearish",
            "label":  "🔴 Confirming Bearish (Price ↓ + Delivery ↓)",
            "points": BP["confirming_bearish"],
            "detail": (
                f"Price down {abs(price_trend_pct):.1f}% with low delivery {delivery_today:.1f}% "
                f"— real investors exiting, not just intraday noise"
            ),
            "type": "penalty",
        }

    # Neutral zone — no strong signal
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Composition
# ─────────────────────────────────────────────────────────────────────────────

# Display order, and the order the totals are accumulated in.
FACTOR_KEYS = [
    ("PE Valuation",   "pe"),
    ("EPS Growth",     "eps_growth"),
    ("ROE",            "roe"),
    ("Price / Book",   "pb"),
    ("Dividend Yield", "div_yield"),
    ("RSI",            "rsi"),
    ("MACD",           "macd"),
    ("EMA Trend",      "ema_trend"),
    ("Delivery %",     "delivery"),
    ("Support Buffer", "support"),
]

# Their own split, and it is not the one the module docstring's "41%" uses:
# `delivery` is filed under technical, which puts technical at 50 of 100, not
# 41. Both numbers are true of the same table; this is the one their API
# reports as `technical`.
FACTOR_CATEGORIES = {
    "pe":         "fundamental",
    "eps_growth": "fundamental",
    "roe":        "fundamental",
    "pb":         "fundamental",
    "div_yield":  "fundamental",
    "rsi":        "technical",
    "macd":       "technical",
    "ema_trend":  "technical",
    "delivery":   "technical",
    "support":    "technical",
}

# Minimum closes before each indicator is computed at all, from their
# `score_stock`. The RSI one is wrong by one row -- see `_compute_rsi`.
MIN_ROWS_RSI = 14
MIN_ROWS_MACD = 26
MIN_ROWS_EMA50 = 50
MIN_ROWS_EMA200 = 200


def resolve_benchmark(
    sector: str | None,
    table: dict[str, SectorBenchmark],
    default: SectorBenchmark,
) -> SectorBenchmark:
    """Their lookup, exactly: `table.get(sector or "", default)`.

    A `None` sector becomes `""`, which is never a key, so it takes the default.
    An unrecognised sector name does the same silently -- there is no signal
    anywhere in the output that a stock was scored against the all-market
    default rather than its own peers. traa's own scorer returns
    `benchmark_used` for precisely that reason.
    """
    return table.get(sector or "", default)


def to_close_series(history: pd.Series | Sequence[tuple[Any, float]]) -> pd.Series:
    """Accept either a close Series or `(date, close)` pairs, and drop nulls.

    Their pipeline does `hist["Close"].dropna()` on a yfinance frame. The
    dropna matters: it changes `len(close)`, and `len(close)` is what every
    indicator guard below tests.
    """
    if isinstance(history, pd.Series):
        return history.dropna()
    dates = [d for d, _ in history]
    closes = [c for _, c in history]
    return pd.Series(closes, index=pd.Index(dates)).dropna()


def score_stock(
    fundamentals: Fundamentals,
    history: pd.Series | Sequence[tuple[Any, float]],
    benchmark: SectorBenchmark,
    *,
    delivery_pct: float | None = None,
    financials: dict | None = None,
    promoter_data: dict | None = None,
) -> dict:
    """Their `score_stock`, with every fetch hoisted into an argument.

    `delivery_pct` defaults to None because that is what their NSE fetcher
    returns every single time (403). `financials` and `promoter_data` default to
    empty for the same reason a caller may not have them -- an absent record
    contributes no adjustments rather than an exception.

    A stock with nothing fetched at all scores **47.5 and lands in "Hold"**:
    7.5 + 6 + 5 + 4 + 0 + 6 + 6 + 5 + 4.5 + 3.5. That is not a neutral outcome,
    it is a recommendation, and it is the one every stock whose data fails to
    load will silently receive.
    """
    close = to_close_series(history)
    financials = financials if financials is not None else {}
    price = fundamentals.get("current_price")

    # Their guards, reproduced including the off-by-one on RSI: at exactly 14
    # closes `_compute_rsi` returns NaN and every downstream total goes NaN.
    rsi_val           = _compute_rsi(close)      if len(close) >= MIN_ROWS_RSI    else None
    macd_val, sig_val = _compute_macd(close)     if len(close) >= MIN_ROWS_MACD   else (None, None)
    ema50             = _compute_ema(close, 50)  if len(close) >= MIN_ROWS_EMA50  else None
    ema200            = _compute_ema(close, 200) if len(close) >= MIN_ROWS_EMA200 else None
    # No guard on support: the 90-day-minimum fallback covers any length. An
    # empty series would raise, and their pipeline cannot produce one.
    support           = _compute_support(close) if len(close) else None

    raw = {
        "pe":         _score_pe(fundamentals.get("trailing_pe"), WEIGHTS["pe"], benchmark),
        "eps_growth": _score_eps_growth(fundamentals.get("eps_ttm"), fundamentals.get("eps_prev"),
                                        WEIGHTS["eps_growth"]),
        "roe":        _score_roe(fundamentals.get("roe"), WEIGHTS["roe"], benchmark),
        "pb":         _score_pb(fundamentals.get("price_to_book"), WEIGHTS["pb"], benchmark),
        "div_yield":  _score_div_yield(fundamentals.get("div_yield"), WEIGHTS["div_yield"], benchmark),
        "rsi":        _score_rsi(rsi_val, WEIGHTS["rsi"]),
        "macd":       _score_macd(macd_val, sig_val, WEIGHTS["macd"]),
        "ema_trend":  _score_ema_trend(price, ema50, ema200, WEIGHTS["ema_trend"]),
        "delivery":   _score_delivery(delivery_pct, WEIGHTS["delivery"]),
        "support":    _score_support(price, support, WEIGHTS["support"]),
    }

    factors = []
    fund_total = tech_total = 0.0
    for label, key in FACTOR_KEYS:
        s, detail = raw[key]
        w   = WEIGHTS[key]
        cat = FACTOR_CATEGORIES[key]
        factors.append({
            "key": key, "label": label,
            "score": round(s, 2), "max": w,
            "pct": round(s / w * 100, 1),
            "detail": detail, "category": cat,
        })
        if cat == "fundamental":
            fund_total += s
        else:
            tech_total += s

    base_total = fund_total + tech_total

    adjustments: list[dict] = []

    adj = _check_profit_decay(financials)
    if adj:
        adjustments.append(adj)

    adjustments.extend(_check_dual_growth(financials))

    adjustments.extend(_check_promoter_holding(promoter_data, fundamentals.get("insider_pct")))

    adj = _check_price_delivery_correlation(close, delivery_pct)
    if adj:
        adjustments.append(adj)

    adjustment_total = sum(a["points"] for a in adjustments)
    adjusted_total   = base_total + adjustment_total

    # Clamped for display and for the bucket, but `base_total` and
    # `adjustment_total` are returned unclamped so an adjustment is never hidden
    # inside a number that cannot be questioned.
    #
    # This clamp is also where a NaN turns into a perfect score: `min(100.0,
    # nan)` is 100.0 in Python, because the comparison is False. A single NaN
    # factor -- and RSI produces one at exactly 14 closes, see `_compute_rsi` --
    # therefore does not surface as missing data, it surfaces as "Strong Buy".
    # Left exactly as theirs; the caller is what has to refuse to rank a NaN.
    display_total = max(0.0, min(100.0, adjusted_total))
    bucket        = next(lbl for threshold, lbl in BUCKETS if display_total >= threshold)

    return {
        "name":             fundamentals.get("name"),
        "sector":           fundamentals.get("sector") or "Unknown",
        "industry":         fundamentals.get("industry") or "Unknown",
        "price":            price,
        "base_total":       round(base_total, 2),
        "adjustment_total": round(adjustment_total, 2),
        "total":            round(display_total, 2),
        "fundamental":      round(fund_total, 2),
        "technical":        round(tech_total, 2),
        "bucket":           bucket,
        "factors":          factors,
        "adjustments":      adjustments,
        "promoter_holding": promoter_data["latest"] if promoter_data is not None else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NOT part of the port. The boundary that stops the port's worst behaviour
# reaching a screen.
# ─────────────────────────────────────────────────────────────────────────────

# `_compute_rsi` needs 14 non-null deltas, which needs 15 closes. Upstream's
# `score_stock` guards with `len(close) >= 14` -- one short -- so at exactly 14
# closes RSI is NaN, `base_total` is NaN, and the display clamp
# `max(0.0, min(100.0, nan))` returns **100.0**, because `nan < 100.0` is False.
#
# A newly listed company therefore scores a perfect 100 and buckets as
# "Strong Buy", on a model that has computed nothing about it. Companies with
# exactly 14 days of price history are, by definition, the newest listings on
# the exchange.
#
# The port reproduces that, correctly -- its job is parity and
# `test_a_company_with_fourteen_days_of_history_scores_a_perfect_hundred` pins
# it. This is the other half: nothing may rank on `total` without coming
# through here first. Same arrangement as the fund side, where the arithmetic is
# faithful and `universe.is_scoreable` decides who is allowed into the ranking.
MIN_ROWS_TO_SCORE = MIN_ROWS_RSI + 1

# Below this the technical half is computed on stubs. The stock is still
# scoreable -- the fundamental factors are real -- but a screen should say so,
# which is what `thin_history` is for.
MIN_ROWS_FOR_FULL_TECHNICALS = MIN_ROWS_EMA200


def is_scoreable(history, fundamentals: Fundamentals | None = None) -> tuple[bool, str]:
    """Whether a stock may be ranked, and why not if it may not.

    A reason string rather than a bare False, for the same reason the fund side
    gives one: a screen that silently drops stocks is indistinguishable from one
    that lost them.
    """
    rows = 0 if history is None else len(history)
    if rows == 0:
        return False, "no price history"
    if rows < MIN_ROWS_TO_SCORE:
        return False, (
            f"only {rows} days of price history, {MIN_ROWS_TO_SCORE} needed before "
            "the momentum indicators produce a number rather than a blank"
        )
    if fundamentals is not None and not any(
        fundamentals.get(k) is not None
        for k in ("trailing_pe", "price_to_book", "roe", "eps_ttm")
    ):
        return False, "no fundamentals published"
    return True, ""


def thin_history(history) -> bool:
    """Whether the long-window indicators fell back to stubs.

    A stock with 60 closes has a real RSI and a real MACD but no 200-day EMA, so
    its trend factor is scored against a shorter average than every other
    stock's. Not a reason to exclude it; a reason to say so.
    """
    return history is not None and len(history) < MIN_ROWS_FOR_FULL_TECHNICALS


def is_meaningless(result: dict) -> bool:
    """Whether a scored result is the NaN-became-100 case, or any relative.

    Belt to `is_scoreable`'s braces. If a NaN ever reaches a total by another
    route -- a new factor, a changed window -- this catches it at the point of
    use rather than letting it sort to the top of the page.
    """
    total = result.get("total")
    if total is None:
        return True
    try:
        value = float(total)
    except (TypeError, ValueError):
        return True
    if value != value:  # NaN
        return True
    # An exact 100.0 is the signature of the clamp swallowing a NaN. A genuine
    # perfect score would require every one of ten factors to max out at once,
    # which the mutually-opposing RSI and EMA-trend factors make impossible.
    return value >= 100.0
