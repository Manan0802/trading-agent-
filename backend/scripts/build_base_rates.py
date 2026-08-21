"""How often each fund category has lost money, and how badly, since 2006.

This is the honest answer to "what could go wrong", and it is the one thing on
the whole screen that is neither a forecast nor an opinion: every number here is
a stretch of time an Indian investor could actually have lived through.

## Why this exists

Fifteen Indian investing apps were surveyed while designing this. **Not one of
them turns volatility into a loss a reader can picture.** The closest anyone
gets is a "34.67% fall from 52-week high" figure. Meanwhile our own harnesses
have shown three times over that we cannot predict which fund will do better —
50%, 38%, and 68%-but-unstable across three separate tests. What we *can* say,
from 5.18 million NAV rows, is what this category has done to people before.

And the finding is worth the whole exercise: **holding period decides whether
you lose money, and fund choice does not.** Every equity category runs 16-22%
losing years and 0-2% losing five-year stretches.

## Method

Entry points are the first of each month, so windows overlap heavily and are
**not independent**. That is deliberate and it is what a base rate is: the
question is "of all the moments someone could have started, how many ended
badly", not "what is the sampling distribution of the mean".

    python scripts/build_base_rates.py

Output: app/data/base_rates.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.services.advisor import fund_catalogue  # noqa: E402
from app.services.screener import navstore  # noqa: E402

OUT = ROOT / "app" / "data" / "base_rates.json"

HORIZONS = {"1y": 365, "3y": 1095, "5y": 1826, "7y": 2557, "10y": 3653}

# The fund screen's own floor for calling a group a peer group. Reused rather
# than reinvented so a category that is too thin to rank is also too thin to
# quote a base rate for.
MIN_FUNDS = 8

# Below this a percentile is describing noise. 200 monthly entry points is
# roughly 17 years of starts across the category's funds.
MIN_WINDOWS = 200

# A fund needs enough history to contribute a window at all.
MIN_NAVS = 300


def split_category(category: str) -> tuple[str, str]:
    return tuple(category.split(" - ", 1)) if " - " in category else (category, "")


def bad_row_mask(nav: np.ndarray) -> np.ndarray:
    """True where a NAV is a filing error rather than a price.

    **A fall that comes straight back is an error; a fall that stays is
    history.** No threshold on the size of the fall can tell the two apart, and
    both matter here for opposite reasons.

    Invesco India Gold FoF prints 11.86 -> 0.19 -> 12.00 across four days in
    October 2019: down 98.4%, then up 6,161%. Gold did not do that. Left in, it
    made FoF Domestic's worst fall -98%.

    DHFL Pramerica Medium Term prints 15.30 -> 7.19 in a single day and never
    recovers, because DHFL defaulted. That one has to stay: a fund halving on a
    credit event is exactly what this file is for.
    """
    bad = np.zeros(len(nav), dtype=bool)
    for i in range(1, len(nav) - 1):
        if nav[i - 1] <= 0 or nav[i] <= 0:
            continue
        if nav[i] / nav[i - 1] - 1 > -0.5:
            continue
        back = nav[i + 1 : i + 6]
        if len(back) and back.max() >= nav[i - 1] * 0.8:
            bad[i] = True
    return bad


def load_catalogue() -> tuple[dict[str, tuple[str, str]], int]:
    """Scheme code to (scheme type, sub-category), minus what nobody can buy.

    Side-pocketed portfolios are created *after* a credit event to ring-fence
    paper that has already defaulted. Their NAV falling is the write-down of
    that paper, and no investor could have entered one. Left in, they made
    Credit Risk read as a category that loses 70%; the real worst fall is 34%.
    """
    mapping: dict[str, tuple[str, str]] = {}
    skipped = 0
    for fund in fund_catalogue.all_funds():
        if "segregated" in fund.name.lower():
            skipped += 1
            continue
        mapping[fund.code] = split_category(fund.category)
    return mapping, skipped


def load_series() -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], int]:
    """Every fund's NAV history, streamed once in scheme order."""
    series: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    bad_rows = 0
    with navstore.session() as session:
        rows = session.execute(
            text(
                "SELECT scheme_code, nav_date, nav FROM nav_history "
                "ORDER BY scheme_code, nav_date"
            )
        )
        current, dates, navs = None, [], []

        def flush() -> int:
            if current is None or len(dates) <= MIN_NAVS:
                return 0
            d = np.array(dates, dtype="datetime64[D]")
            v = np.array(navs, dtype=float)
            mask = bad_row_mask(v)
            if mask.any():
                d, v = d[~mask], v[~mask]
            series[current] = (d, v)
            return int(mask.sum())

        for code, nav_date, nav in rows:
            if code != current:
                bad_rows += flush()
                current, dates, navs = code, [], []
            dates.append(nav_date)
            navs.append(nav)
        bad_rows += flush()
    return series, bad_rows


def build() -> dict:
    category_of, skipped_segregated = load_catalogue()
    print("reading NAV history...", flush=True)
    series, bad_rows = load_series()
    print(f"  {len(series)} funds with more than {MIN_NAVS} NAVs", flush=True)

    returns: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    falls: dict[tuple, list[tuple[float, int]]] = defaultdict(list)
    members: dict[tuple, set[str]] = defaultdict(set)
    wound_up: dict[tuple, set[str]] = defaultdict(set)

    newest = max(d[-1] for d, _ in series.values())
    a_year_ago = newest - np.timedelta64(365, "D")

    for code, (dates, nav) in series.items():
        key = category_of.get(code)
        if key is None:
            continue
        members[key].add(code)
        if dates[-1] < a_year_ago:
            wound_up[key].add(code)

        # Entry on the first of each month the fund was alive.
        starts = np.arange(
            dates[0].astype("datetime64[M]"), dates[-1].astype("datetime64[M]")
        ).astype("datetime64[D]")
        entry = np.searchsorted(dates, starts)
        entry = entry[entry < len(dates)]
        if len(entry) < 12:
            continue

        for name, days in HORIZONS.items():
            exit_ = np.searchsorted(dates, dates[entry] + np.timedelta64(days, "D"))
            inside = exit_ < len(dates)
            if not inside.any():
                continue
            opened, closed = nav[entry[inside]], nav[exit_[inside]]
            live = opened > 0
            years = days / 365.25
            returns[key][name].extend(
                ((closed[live] / opened[live]) ** (1 / years) - 1).tolist()
            )

        peak = np.maximum.accumulate(nav)
        underwater = nav / peak - 1
        worst = int(underwater.argmin())
        if underwater[worst] < 0:
            recovered = np.nonzero(nav[worst:] >= peak[worst])[0]
            # -1 means it never got back inside the record, which is itself the
            # answer for some funds and must not be silently dropped.
            days_back = (
                int((dates[worst + recovered[0]] - dates[worst]).astype(int))
                if len(recovered)
                else -1
            )
            falls[key].append((float(underwater[worst]), days_back))

    out = []
    for key in sorted(returns):
        if len(members[key]) < MIN_FUNDS:
            continue
        scheme_type, sub_category = key
        record: dict = {
            "category": scheme_type,
            "sub_category": sub_category,
            "funds": len(members[key]),
            # Stated, because most published fund studies cannot: the backfill
            # pulled dead schemes too, so these windows include funds that were
            # wound up rather than only the ones that made it to today.
            "funds_wound_up": len(wound_up[key]),
            "horizons": {},
        }
        for name in HORIZONS:
            values = np.array(returns[key].get(name, []))
            if len(values) < MIN_WINDOWS:
                continue
            record["horizons"][name] = {
                "windows": int(len(values)),
                "loss_share": round(float((values < 0).mean()), 4),
                "worst": round(float(values.min()), 4),
                "p05": round(float(np.percentile(values, 5)), 4),
                "median": round(float(np.percentile(values, 50)), 4),
                "p95": round(float(np.percentile(values, 95)), 4),
            }
        if not record["horizons"]:
            continue
        drops = falls.get(key) or []
        if drops:
            record["worst_fall"] = round(min(d for d, _ in drops), 4)
            recoveries = [r for _, r in drops if r > 0]
            record["median_recovery_days"] = (
                int(np.median(recoveries)) if recoveries else None
            )
            record["worst_recovery_days"] = max(recoveries) if recoveries else None
            record["never_recovered"] = sum(1 for _, r in drops if r == -1)
        out.append(record)

    return {
        "as_of": str(newest),
        "categories": out,
        "coverage": {
            "funds_read": len(series),
            "categories_rated": len(out),
            "skipped_segregated": skipped_segregated,
            "bad_nav_rows_dropped": bad_rows,
            "min_funds": MIN_FUNDS,
            "min_windows": MIN_WINDOWS,
        },
    }


# Hand-checked against the table this file first produced. Pinned as ranges
# because one more year of NAVs moves a twenty-year base rate slightly, and a
# pinned exact value would fail every rebuild for no reason. A count would not
# catch a reversed sign or a units change; a loss share and a worst fall do.
CANARY = {
    ("Equity Scheme", "Large Cap Fund"): {"1y_loss": (0.10, 0.25), "worst_fall": (-0.60, -0.30)},
    ("Equity Scheme", "Small Cap Fund"): {"1y_loss": (0.12, 0.30), "worst_fall": (-0.75, -0.45)},
    ("Debt Scheme", "Gilt Fund"): {"1y_loss": (0.00, 0.15), "worst_fall": (-0.25, -0.03)},
    # The two categories the contamination filters exist for. Without the
    # segregated-portfolio exclusion Credit Risk's worst fall reads -70% (a side
    # pocket nobody could buy); without the bad-NAV rule FoF Domestic reads -98%
    # (one gold fund printing 11.86 -> 0.19 -> 12.00 in four days). Both bounds
    # are set so that either contamination returning breaks the build.
    ("Debt Scheme", "Credit Risk Fund"): {"1y_loss": (0.00, 0.20), "worst_fall": (-0.50, -0.15)},
    ("Other Scheme", "FoF Domestic"): {"1y_loss": (0.02, 0.25), "worst_fall": (-0.65, -0.25)},
}


def check(payload: dict) -> list[str]:
    """Refuse to write a table that disagrees with what we already verified."""
    problems = []
    index = {(c["category"], c["sub_category"]): c for c in payload["categories"]}

    for key, bounds in CANARY.items():
        got = index.get(key)
        if got is None:
            problems.append(f"{key} missing from the output entirely")
            continue
        one_year = got["horizons"].get("1y")
        if one_year is None:
            problems.append(f"{key} has no one-year horizon")
        else:
            low, high = bounds["1y_loss"]
            if not low <= one_year["loss_share"] <= high:
                problems.append(
                    f"{key} one-year loss share {one_year['loss_share']} outside {low}-{high}"
                )
        low, high = bounds["worst_fall"]
        fall = got.get("worst_fall")
        if fall is None or not low <= fall <= high:
            problems.append(f"{key} worst fall {fall} outside {low}-{high}")

    equity = [
        c for c in payload["categories"]
        if c["category"] == "Equity Scheme" and "5y" in c["horizons"]
    ]
    if len(equity) < 8:
        problems.append(f"only {len(equity)} equity categories reached five years")
    # The headline finding. If this inverts, something is deeply wrong and the
    # table must not be shipped as the basis for a "how long should I hold"
    # answer.
    for category in equity:
        one, five = category["horizons"].get("1y"), category["horizons"]["5y"]
        if one and five["loss_share"] > one["loss_share"]:
            problems.append(
                f"{category['sub_category']}: five years lost money more often "
                f"({five['loss_share']}) than one ({one['loss_share']})"
            )
    return problems


def main() -> int:
    payload = build()
    problems = check(payload)
    if problems:
        print("\nREFUSING TO WRITE — the table failed its own checks:\n")
        for problem in problems:
            print(f"  {problem}")
        return 1

    OUT.write_text(json.dumps(payload, indent=1))
    coverage = payload["coverage"]
    print(f"\nwrote {coverage['categories_rated']} categories to {OUT}")
    print(
        f"  {coverage['funds_read']} funds read · "
        f"{coverage['skipped_segregated']} segregated portfolios excluded · "
        f"{coverage['bad_nav_rows_dropped']} bad NAV rows dropped"
    )
    equity = [c for c in payload["categories"] if c["category"] == "Equity Scheme"]
    print(f"\n  {'category':<28}{'funds':>6}{'lost 1y':>9}{'5y':>7}{'worst yr':>10}{'worst fall':>12}")
    for category in sorted(equity, key=lambda c: -c["horizons"]["1y"]["loss_share"])[:10]:
        one = category["horizons"]["1y"]
        five = category["horizons"].get("5y")
        print(
            f"  {category['sub_category'][:27]:<28}{category['funds']:>6}"
            f"{one['loss_share']:>8.0%}{(five['loss_share'] if five else 0):>7.0%}"
            f"{one['worst']:>9.0%}{category.get('worst_fall', 0):>11.0%}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
