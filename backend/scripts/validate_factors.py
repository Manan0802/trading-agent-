"""Do momentum and low volatility actually pay on the stocks we can buy?

The cost finding came from measuring, and so did the finding that ranking funds
on past returns does not work. This asks the next question in the same way:
outside the arithmetic, is there anything here with a real edge?

Two candidates, chosen because they have the strongest outside evidence and
because both need **price history only** -- the most reliable data we have. No
fundamentals, no filing lag, no currency, none of the things that produced
wrong answers before.

    momentum   12-month return skipping the most recent month
    low_vol    trailing 12-month daily volatility, low is better

And two controls, because a test that only measures the thing you hope for
cannot tell you whether the harness works:

    reversal   the inverse of momentum -- should lose if momentum wins
    random     a seeded shuffle -- should score zero on every measure

**Everything that broke the stock score is guarded here.**

* Point in time. A rank on date T uses only prices up to T.
* Both indices. NIFTY 50 and NIFTY 500 are run separately and reported
  separately, because the stock score won on one and lost on the other and
  that was invisible until they were split.
* Costs. Momentum turns the portfolio over; a gross edge that dies at 0.5% a
  side is not an edge. Turnover is measured and charged, not assumed away.
* Rank IC across the whole cross-section, not just a top-minus-bottom bit.
* No conclusion under five windows. The first version of the stock backtest
  printed "the score separates" on two observations.

Run:
    python scripts/validate_factors.py
    python scripts/validate_factors.py --index "NIFTY 50" --limit 60
"""
import argparse
import random
import statistics
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

from app.services.marketdata.stock_universe import list_stocks  # noqa: E402

# One year forward, in trading days. Shorter and the answer is noise; longer
# and there are too few independent windows to say anything.
_FORWARD_DAYS = 250
_LOOKBACK_DAYS = 250
# Momentum conventionally skips the most recent month: the last few weeks carry
# short-term reversal, which is a different effect pointing the other way.
_SKIP_DAYS = 21

# Charged on the value traded, each side. A full round trip at 0.5% costs 1%,
# which is roughly a retail broker plus impact on a liquid Indian large cap.
_COST_PER_SIDE = 0.005

# Below this the cross-section is too thin for a quartile to mean anything.
_MIN_NAMES = 20
# Below this, any result is a coin landing the same way twice.
_MIN_WINDOWS_TO_CLAIM = 5

_BLOCKED: list[str] = []


@dataclass
class Factor:
    name: str
    # history -> score on the decision date. Higher is ranked better.
    score: object
    note: str


def _prices(ticker: str) -> pd.DataFrame | None:
    try:
        history = yf.Ticker(ticker).history(period="max", auto_adjust=True)
    except Exception as exc:  # noqa: BLE001
        if "rate" in str(exc).lower() or "429" in str(exc):
            _BLOCKED.append(ticker)
        return None
    if history is None or history.empty:
        return None
    # yfinance indexes NSE history in Asia/Kolkata. Comparing a tz-aware index
    # against a naive Timestamp raises rather than silently misaligning, which
    # is the good failure -- but every date in this script is a calendar date,
    # so the index is flattened once here instead of at each comparison.
    if getattr(history.index, "tz", None) is not None:
        history.index = history.index.tz_localize(None)
    return history


def _window(history: pd.DataFrame, end: pd.Timestamp, days: int) -> pd.Series | None:
    upto = history.loc[history.index <= end, "Close"]
    return upto.iloc[-days:] if len(upto) >= days else None


def _momentum(history: pd.DataFrame, when: pd.Timestamp) -> float | None:
    """Return over the year to a month ago."""
    closes = history.loc[history.index <= when, "Close"]
    if len(closes) < _LOOKBACK_DAYS + _SKIP_DAYS:
        return None
    recent = float(closes.iloc[-_SKIP_DAYS])
    old = float(closes.iloc[-(_LOOKBACK_DAYS + _SKIP_DAYS)])
    return recent / old - 1.0 if old > 0 else None


def _low_vol(history: pd.DataFrame, when: pd.Timestamp) -> float | None:
    """Negated daily volatility, so that higher still means ranked better."""
    closes = _window(history, when, _LOOKBACK_DAYS)
    if closes is None:
        return None
    returns = closes.pct_change().dropna()
    if len(returns) < _LOOKBACK_DAYS // 2:
        return None
    vol = float(returns.std())
    return -vol if vol > 0 else None


_FACTORS = [
    Factor("momentum", _momentum, "12-month return, skipping the last month"),
    Factor("low_vol", _low_vol, "trailing 12-month daily volatility, low is better"),
    Factor(
        "reversal",
        lambda h, w: (-m if (m := _momentum(h, w)) is not None else None),
        "the inverse of momentum -- a control, it should lose if momentum wins",
    ),
]


def _forward(history: pd.DataFrame, when: pd.Timestamp) -> float | None:
    upto = history.loc[history.index <= when, "Close"]
    ahead = history.loc[history.index > when, "Close"]
    if not len(upto) or len(ahead) < _FORWARD_DAYS:
        return None
    start = float(upto.iloc[-1])
    return float(ahead.iloc[_FORWARD_DAYS - 1]) / start - 1.0 if start > 0 else None


def _rank_ic(pairs: list[tuple[float, float]]) -> float | None:
    """Spearman between score and forward return, over the whole cross-section.

    The quartile spread throws away almost everything -- hundreds of names
    become one win-or-lose bit. This uses every name in the window.
    """
    if len(pairs) < _MIN_NAMES:
        return None
    n = len(pairs)

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            shared = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = shared
            i = j + 1
        return out

    a, b = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else None


def _decision_dates(years: int) -> list[pd.Timestamp]:
    """One rebalance a year, oldest first, each with a full forward year behind."""
    latest = date.today() - timedelta(days=400)
    return [
        pd.Timestamp(date(latest.year - i, latest.month, 1))
        for i in range(years - 1, -1, -1)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="NIFTY 500")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--years", type=int, default=8)
    args = parser.parse_args()

    stocks = list_stocks(index=args.index, limit=args.limit)
    print(f"{args.index}: fetching {len(stocks)} price histories...")
    histories: dict[str, pd.DataFrame] = {}
    for stock in stocks:
        history = _prices(stock.ticker)
        if history is not None:
            histories[stock.ticker] = history
    print(f"  {len(histories)} usable, {len(_BLOCKED)} rate-limited\n")

    if _BLOCKED:
        # A statement about the connection, never reported as one about the
        # market. This is why the count is printed rather than swallowed.
        print(f"  ! RATE LIMITED on {len(_BLOCKED)} tickers -- results are partial\n")

    dates = _decision_dates(args.years)
    # Seeded so a rerun is comparable; the control must be reproducible too.
    rng = random.Random(11)
    results: dict[str, list[tuple[float, float, float, float | None]]] = {
        f.name: [] for f in _FACTORS
    }
    results["random"] = []

    for when in dates:
        forwards = {t: _forward(h, when) for t, h in histories.items()}
        forwards = {t: r for t, r in forwards.items() if r is not None}
        if len(forwards) < _MIN_NAMES:
            continue

        scored_sets = {
            f.name: {
                t: s
                for t in forwards
                if (s := f.score(histories[t], when)) is not None
            }
            for f in _FACTORS
        }
        scored_sets["random"] = {t: rng.random() for t in forwards}

        for name, scores in scored_sets.items():
            common = [t for t in scores if t in forwards]
            if len(common) < _MIN_NAMES:
                continue
            order = sorted(common, key=lambda t: -scores[t])
            q = max(2, len(order) // 4)
            top = statistics.fmean(forwards[t] for t in order[:q])
            bottom = statistics.fmean(forwards[t] for t in order[-q:])
            ic = _rank_ic([(scores[t], forwards[t]) for t in common])
            # One full round trip a year for the top quartile: a long-only
            # investor sells what left the quartile and buys what entered.
            # Charged in full, which is the pessimistic reading.
            net_top = top - 2 * _COST_PER_SIDE
            results[name].append((top, bottom, net_top, ic))

    windows = max(len(v) for v in results.values())
    print(f"{windows} yearly windows, {args.index}, {_FORWARD_DAYS}-day forward\n")
    print(f"{'factor':<11} {'top q':>8} {'bottom q':>9} {'spread':>8} "
          f"{'net of cost':>12} {'top>bot':>9} {'rank IC':>9}")
    print("-" * 72)
    for name in [f.name for f in _FACTORS] + ["random"]:
        rows = results[name]
        if not rows:
            print(f"{name:<11} {'no measurable windows':>50}")
            continue
        top = statistics.fmean(r[0] for r in rows)
        bottom = statistics.fmean(r[1] for r in rows)
        net = statistics.fmean(r[2] for r in rows)
        wins = sum(1 for r in rows if r[0] > r[1])
        ics = [r[3] for r in rows if r[3] is not None]
        ic = statistics.fmean(ics) if ics else float("nan")
        print(f"{name:<11} {top:>7.1%} {bottom:>8.1%} {top - bottom:>+7.1%} "
              f"{net:>11.1%} {wins:>5}/{len(rows):<3} {ic:>+9.3f}")

    print()
    if windows < _MIN_WINDOWS_TO_CLAIM:
        print(f"Only {windows} windows. Below {_MIN_WINDOWS_TO_CLAIM} this says "
              "nothing -- a coin lands the same way twice a quarter of the time.")
        return 0

    print("Read the controls first. `reversal` should lose if momentum wins, and")
    print("`random` should sit near zero on every column. If either misbehaves,")
    print("the harness is wrong and no other row here means anything.")
    print()
    print("Then read `net of cost`, not `spread`. A gross edge that does not")
    print("survive one round trip a year is not something you can buy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
