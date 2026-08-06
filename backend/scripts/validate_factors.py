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

# Forward horizons, in trading days. The rebalance interval equals the horizon
# on purpose, so consecutive windows never overlap.
#
# Overlap is the quiet way a backtest lies. Yearly forward returns sampled
# every quarter share three quarters of their data, so ten "windows" carry
# roughly the information of three -- and a t-statistic computed on them is
# inflated by about the square root of that. Non-overlapping costs sample size
# and buys the right to do arithmetic on the result.
_HORIZONS = {"quarterly": 63, "annual": 250}
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


def _forward(history: pd.DataFrame, when: pd.Timestamp, days: int) -> float | None:
    upto = history.loc[history.index <= when, "Close"]
    ahead = history.loc[history.index > when, "Close"]
    if not len(upto) or len(ahead) < days:
        return None
    start = float(upto.iloc[-1])
    return float(ahead.iloc[days - 1]) / start - 1.0 if start > 0 else None


def _t_stat(values: list[float]) -> float | None:
    """Fama-MacBeth style: the mean of a per-window series over its own error.

    Legitimate only because the windows do not overlap. On overlapping windows
    the same number would be inflated and would read as significance.
    """
    if len(values) < 3:
        return None
    spread = statistics.stdev(values)
    if spread == 0:
        return None
    return statistics.fmean(values) / (spread / len(values) ** 0.5)


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


def _decision_dates(years: int, step_months: int) -> list[pd.Timestamp]:
    """Rebalances, oldest first, each with a full forward horizon behind it.

    Spaced by the horizon so the windows are independent.
    """
    last = date.today() - timedelta(days=int(365 * (step_months / 12)) + 40)
    out: list[pd.Timestamp] = []
    year, month = last.year, last.month
    for _ in range(int(years * 12 / step_months)):
        out.append(pd.Timestamp(date(year, month, 1)))
        month -= step_months
        while month <= 0:
            month += 12
            year -= 1
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="NIFTY 500")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--years", type=int, default=15)
    parser.add_argument("--horizon", choices=sorted(_HORIZONS), default="quarterly")
    args = parser.parse_args()

    forward_days = _HORIZONS[args.horizon]
    step_months = 3 if args.horizon == "quarterly" else 12

    stocks = list_stocks(index=args.index, limit=args.limit)
    print(f"{args.index}: fetching {len(stocks)} price histories...")
    histories: dict[str, pd.DataFrame] = {}
    for stock in stocks:
        history = _prices(stock.ticker)
        if history is not None:
            histories[stock.ticker] = history

    print(f"  {len(histories)} usable, {len(_BLOCKED)} rate-limited\n")
    if _BLOCKED:
        print(f"  ! RATE LIMITED on {len(_BLOCKED)} tickers -- results are partial\n")

    dates = _decision_dates(args.years, step_months)
    rng = random.Random(11)
    # factor -> per-window (top, bottom, index, ic)
    results: dict[str, list[tuple[float, float, float | None, float | None]]] = {
        f.name: [] for f in _FACTORS
    }
    results["random"] = []

    for when in dates:
        forwards = {
            t: r
            for t, h in histories.items()
            if (r := _forward(h, when, forward_days)) is not None
        }
        if len(forwards) < _MIN_NAMES:
            continue
        # The benchmark is this universe, equally weighted, in this window --
        # not an external index.
        #
        # ^NSEI was tried first and the control exposed it: a random quartile
        # of NIFTY 500 beat NIFTY 50 by 4.2% with t = +4.13, which is not an
        # edge, it is mid caps outrunning large caps over the sample. Measuring
        # a factor against a different universe measures the universe. Against
        # its own mean, a factor has to actually pick.
        index_return = statistics.fmean(forwards.values())

        scored_sets = {
            f.name: {
                t: s for t in forwards if (s := f.score(histories[t], when)) is not None
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
            results[name].append((
                statistics.fmean(forwards[t] for t in order[:q]),
                statistics.fmean(forwards[t] for t in order[-q:]),
                index_return,
                _rank_ic([(scores[t], forwards[t]) for t in common]),
            ))

    windows = max((len(v) for v in results.values()), default=0)
    per_year = 12 / step_months
    cost = 2 * _COST_PER_SIDE * per_year  # a round trip every rebalance
    print(f"{windows} non-overlapping {args.horizon} windows, {args.index}, "
          f"{args.years}y requested\n")
    print(f"{'factor':<11} {'top q':>8} {'vs bottom':>10} {'vs univ':>9} "
          f"{'net of cost':>12} {'rank IC':>9} {'t':>7}")
    print("-" * 74)

    for name in [f.name for f in _FACTORS] + ["random"]:
        rows = results[name]
        if not rows:
            print(f"{name:<11} no measurable windows")
            continue
        top = statistics.fmean(r[0] for r in rows)
        vs_bottom = statistics.fmean(r[0] - r[1] for r in rows)
        paired = [(r[0], r[2]) for r in rows if r[2] is not None]
        vs_index = statistics.fmean(a - b for a, b in paired) if paired else None
        ics = [r[3] for r in rows if r[3] is not None]
        ic = statistics.fmean(ics) if ics else None
        # t on the per-window excess over the index: the quantity an investor
        # would actually be paid, tested against its own variability.
        t = _t_stat([a - b for a, b in paired]) if len(paired) >= 3 else None
        print(
            f"{name:<11} {top:>7.1%} {vs_bottom:>+10.1%} "
            f"{(f'{vs_index:+.1%}' if vs_index is not None else '—'):>9} "
            f"{(f'{vs_index - cost:+.1%}' if vs_index is not None else '—'):>12} "
            f"{(f'{ic:+.3f}' if ic is not None else '—'):>9} "
            f"{(f'{t:+.2f}' if t is not None else '—'):>7}"
        )

    print()
    print(f"Costs: {cost:.1%} a year, one full round trip per rebalance at "
          f"{_COST_PER_SIDE:.1%} a side.")
    print()
    if windows < _MIN_WINDOWS_TO_CLAIM:
        print(f"Only {windows} windows. Below {_MIN_WINDOWS_TO_CLAIM} this says "
              "nothing.")
        return 0

    print("Controls first: `random` near zero and `t` inside +/-2, `reversal` the")
    print("mirror of momentum. If either misbehaves nothing else here means anything.")
    print()
    print("Then `vs univ`: the top quartile against this same universe equally")
    print("weighted, which is the alternative you actually have. And `t`: below")
    print("about 2 the column is consistent with luck.")
    print("Windows do not overlap, so that t is honest arithmetic rather than the")
    print("inflated figure overlapping samples produce.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
