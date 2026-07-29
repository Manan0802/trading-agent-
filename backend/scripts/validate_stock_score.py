"""Does the stock score predict anything? Measured the same way the fund score was.

The Research page says plainly that this score has never been backtested. That
was true and it was the weakest sentence in the app. This is the test.

**Point-in-time, or it proves nothing.** Every input is reconstructed as it stood
on a past fiscal year end — EPS and net income from that year's income
statement, book value from that year's balance sheet, the share price on that
date — and the sector medians are computed from the same cross-section rather
than from today's table. Scoring 2022 against 2026's medians would be scoring
with the answer sheet.

**The bar is the same one the fund score failed.** Rank each year's cross-section
by score, take the top and bottom quartiles, and compare their forward one-year
returns. A score that predicts beats its own bottom quartile more often than a
coin. Anything less and the screen has to say so.

    python scripts/validate_stock_score.py [--index "NIFTY 50"] [--limit 60]
"""

import argparse
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.advisor.stock_score import StockInputs, score_stock
from app.services.marketdata.stock_universe import list_stocks

# A year of forward return, measured in trading days rather than calendar days
# so a holiday cannot shift the window.
_FORWARD_TRADING_DAYS = 250

# Below this a "sector median" is one or two companies having a strange year.
_MIN_SECTOR_PEERS = 4

# Years of forward returns before the word "predicts" is allowed anywhere near
# the result. The fund score was judged on sixty overlapping three-year windows.
# Two annual observations both landing the same way is what a coin does half the
# time, and an earlier version of this script called that success — which is the
# exact self-flattery this whole app exists to avoid.
_MIN_YEARS_TO_CLAIM = 5


@dataclass(frozen=True)
class Observation:
    ticker: str
    name: str
    sector: str
    as_of: pd.Timestamp
    pe: float | None
    pb: float | None
    roe: float | None
    eps: float | None
    eps_prev: float | None
    price: float
    forward_return: float | None


def _row(frame: pd.DataFrame, *names: str) -> pd.Series | None:
    for name in names:
        if frame is not None and name in frame.index:
            return frame.loc[name]
    return None


def _price_on(history: pd.DataFrame, when: pd.Timestamp) -> float | None:
    """The last close at or before a date. Statements are filed after the year
    end, but the price on the year end is what a scorer would have seen."""
    if history is None or history.empty:
        return None
    window = history.loc[history.index <= when]
    return float(window["Close"].iloc[-1]) if len(window) else None


def _forward_return(history: pd.DataFrame, when: pd.Timestamp) -> float | None:
    start = _price_on(history, when)
    if not start or start <= 0:
        return None
    ahead = history.loc[history.index > when]
    if len(ahead) < _FORWARD_TRADING_DAYS:
        return None
    end = float(ahead["Close"].iloc[_FORWARD_TRADING_DAYS - 1])
    return end / start - 1.0


# Counted, not swallowed. Yahoo rate-limits after roughly a thousand companies,
# and an empty result then reads as "there is no history to test" — a statement
# about the market — when it is really "we were blocked", a statement about the
# connection. Reporting one as the other is how a run gets quietly believed.
_BLOCKED: list[str] = []
_FAILED: list[str] = []


def observe(entry, lag_months: int = 0) -> list[Observation]:
    """Every fiscal year end we can reconstruct this company's numbers for."""
    try:
        ticker = yf.Ticker(entry.ticker)
        income = ticker.income_stmt
        balance = ticker.balance_sheet
        history = ticker.history(period="10y", auto_adjust=True)
        sector = (ticker.info or {}).get("sector") or "Unknown"
    except Exception as exc:  # noqa: BLE001
        if "RateLimit" in type(exc).__name__ or "Too Many Requests" in str(exc):
            _BLOCKED.append(entry.ticker)
        else:
            _FAILED.append(entry.ticker)
        return []

    if income is None or income.empty or history is None or history.empty:
        return []
    if getattr(history.index, "tz", None) is not None:
        history.index = history.index.tz_localize(None)

    eps_row = _row(income, "Diluted EPS", "Basic EPS")
    net_income = _row(income, "Net Income", "Net Income Common Stockholders")
    equity = _row(balance, "Common Stock Equity", "Stockholders Equity")
    shares = _row(balance, "Ordinary Shares Number", "Share Issued")
    if eps_row is None:
        return []

    out: list[Observation] = []
    years = list(income.columns)
    for i, year_end in enumerate(years):
        # The prior year is the next column along; without it there is no
        # growth figure and the factor would score neutral for everyone.
        prior = years[i + 1] if i + 1 < len(years) else None
        if prior is None:
            continue

        # The fundamentals are the year's; the date they became actionable is
        # the year end plus the filing lag, and that is when the clock starts.
        when = pd.Timestamp(year_end).tz_localize(None) + pd.DateOffset(
            months=lag_months
        )
        price = _price_on(history, when)
        if not price:
            continue

        eps = eps_row.get(year_end)
        eps_prev = eps_row.get(prior)
        eps = float(eps) if pd.notna(eps) else None
        eps_prev = float(eps_prev) if pd.notna(eps_prev) else None

        book_value = None
        if equity is not None and shares is not None:
            e, s = equity.get(year_end), shares.get(year_end)
            if pd.notna(e) and pd.notna(s) and s:
                book_value = float(e) / float(s)

        roe = None
        if net_income is not None and equity is not None:
            n, e = net_income.get(year_end), equity.get(year_end)
            if pd.notna(n) and pd.notna(e) and e:
                roe = float(n) / float(e)

        out.append(
            Observation(
                ticker=entry.ticker,
                name=entry.name,
                sector=sector,
                as_of=when,
                pe=price / eps if eps and eps > 0 else None,
                pb=price / book_value if book_value and book_value > 0 else None,
                roe=roe,
                eps=eps,
                eps_prev=eps_prev,
                price=price,
                forward_return=_forward_return(history, when),
            )
        )
    return out


def _point_in_time_benchmarks(cohort: list[Observation]) -> dict[str, dict]:
    """Sector medians from this cross-section only.

    Using today's committed table to score 2022 would be handing the model the
    answer sheet — the medians already reflect what happened next.
    """
    benchmarks: dict[str, dict] = {}
    by_sector: dict[str, list[Observation]] = {}
    for o in cohort:
        by_sector.setdefault(o.sector, []).append(o)

    def median_of(values):
        clean = [v for v in values if v is not None and v > 0]
        return statistics.median(clean) if len(clean) >= _MIN_SECTOR_PEERS else None

    for sector, members in by_sector.items():
        entry = {
            "pe": median_of([m.pe for m in members]),
            "pb": median_of([m.pb for m in members]),
            "roe": median_of([m.roe for m in members]),
            "dividend_yield": None,
        }
        if any(v is not None for v in entry.values()):
            benchmarks[sector] = entry

    benchmarks["_ALL"] = {
        "pe": median_of([o.pe for o in cohort]),
        "pb": median_of([o.pb for o in cohort]),
        "roe": median_of([o.roe for o in cohort]),
        "dividend_yield": None,
    }
    return benchmarks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="NIFTY 50")
    parser.add_argument("--limit", type=int, default=60)
    # Indian companies file annual results up to six months after the year end.
    # Scoring on the year-end date uses numbers nobody had yet, and starts the
    # forward return before the market could have reacted to them — which is
    # worth a great deal in a year the market ran. This is the lag that turns
    # the test from "what the data says" into "what an investor could have done".
    parser.add_argument("--lag-months", type=int, default=0)
    args = parser.parse_args()

    entries = list_stocks(index=args.index)[: args.limit]
    print(f"reconstructing {len(entries)} companies from {args.index}…", flush=True)

    if args.lag_months:
        print(
            f"scoring {args.lag_months} months after each year end, so only "
            "numbers that had actually been filed are used",
            flush=True,
        )
    with ThreadPoolExecutor(max_workers=12) as pool:
        observations = [
            o
            for group in pool.map(lambda e: observe(e, args.lag_months), entries)
            for o in group
        ]

    by_year: dict[pd.Timestamp, list[Observation]] = {}
    for o in observations:
        by_year.setdefault(o.as_of, []).append(o)

    print(f"{len(observations)} company-years reconstructed")
    if _BLOCKED:
        print(
            f"\nRATE LIMITED on {len(_BLOCKED)} of {len(entries)} companies. "
            "Yahoo blocks after roughly a\nthousand requests. This run is "
            "incomplete — wait an hour and run it again.\nDo not read anything "
            "below as a result."
        )
        return 1
    if _FAILED:
        print(f"{len(_FAILED)} companies could not be read at all: {_FAILED[:5]}")
    print()

    rows = []
    for year, cohort in sorted(by_year.items()):
        scorable = [o for o in cohort if o.forward_return is not None]
        if len(scorable) < 12:
            continue
        benchmarks = _point_in_time_benchmarks(scorable)

        scored = []
        for o in scorable:
            result = score_stock(
                StockInputs(
                    ticker=o.ticker,
                    name=o.name,
                    sector=o.sector,
                    price=o.price,
                    pe=o.pe,
                    pb=o.pb,
                    roe=o.roe,
                    dividend_yield=None,
                    eps_ttm=o.eps,
                    eps_prev=o.eps_prev,
                    promoter_history=[],
                ),
                benchmarks,
            )
            scored.append((result.total, o.forward_return, o.name))

        scored.sort(key=lambda t: -t[0])
        n = max(1, len(scored) // 4)
        top = [r for _, r, _ in scored[:n]]
        bottom = [r for _, r, _ in scored[-n:]]
        rows.append(
            {
                "year": year.date().isoformat(),
                "n": len(scored),
                "top": statistics.mean(top),
                "bottom": statistics.mean(bottom),
                "spread": statistics.mean(top) - statistics.mean(bottom),
                "best": scored[0][2],
            }
        )

    if not rows:
        print(
            "No year had enough companies with both a reconstructable score and "
            "a\nfull forward year. Nothing can be claimed either way."
        )
        return 1

    print(f"{'year':<12}{'n':>4}{'top qtr':>10}{'bottom qtr':>12}{'spread':>10}  top pick")
    print("-" * 78)
    for r in rows:
        print(
            f"{r['year']:<12}{r['n']:>4}{r['top']:>9.1%}{r['bottom']:>12.1%}"
            f"{r['spread']:>10.1%}  {r['best'][:26]}"
        )

    wins = sum(1 for r in rows if r["spread"] > 0)
    mean_spread = statistics.mean(r["spread"] for r in rows)
    print("-" * 78)
    print(f"\ntop quartile beat bottom quartile in {wins} of {len(rows)} years")
    print(f"average spread: {mean_spread:+.1%} a year")
    print()

    if len(rows) < _MIN_YEARS_TO_CLAIM:
        # The sample decides what may be said, before the result does.
        chance = 0.5 ** len(rows)
        print(
            f"NOT ENOUGH EVIDENCE TO CLAIM ANYTHING. {len(rows)} annual "
            f"observations.\nA score with no skill lands them all the same way "
            f"{chance:.0%} of the time,\nso this cannot separate a real edge "
            f"from a coin. At least {_MIN_YEARS_TO_CLAIM} years are needed\n"
            "before the word 'predicts' is defensible."
        )
        if mean_spread > 0:
            print(
                "\nThe direction is encouraging and worth re-running as the "
                "data deepens.\nIt is not a finding, and the screen must keep "
                "saying the score has not\nbeen shown to predict."
            )
        return 0

    if wins == len(rows) and mean_spread > 0.03:
        print("The score separates on this evidence. The screen can say so.")
    elif wins <= len(rows) / 2 or mean_spread <= 0:
        print(
            "The score does not separate. On this evidence the screen must keep\n"
            "saying it describes a balance sheet rather than predicts a return."
        )
    else:
        print("Mixed. The page should keep saying so rather than round it up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
