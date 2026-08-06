"""Turn the factor research into something the app can show.

The strongest measurements in this project live in a document nobody opens.
This builds them into `app/data/factor_evidence.json`, which the API serves and
the Research page renders.

Source: IIMA's Indian Fama-French-Momentum library -- survivorship-bias
adjusted, monthly, from October 1993. Built independently by academics with no
stake in this app being right, which is exactly why it is worth showing.

Committed rather than fetched at request time. The file updates monthly and a
thirty-two-year regression is not something to run on a page load. Re-run this
script to refresh; the date it was built is carried in the output so a stale
file cannot pass for a fresh one.

    python scripts/build_factor_evidence.py
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
import pandas as pd  # noqa: E402

_SOURCE = (
    "https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/DATA/"
    "2025-12_FourFactors_and_Market_Returns_Monthly_SurvivorshipBiasAdjusted.csv"
)
_OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "factor_evidence.json"

# What each column is, in words a reader can check rather than take on trust.
_FACTORS = {
    "WML": (
        "Momentum",
        "Past winners minus past losers. Buy what has been going up.",
    ),
    "HML": (
        "Value",
        "Cheap minus expensive, on book-to-market. Buy what looks cheap.",
    ),
    "SMB": (
        "Size",
        "Small companies minus large ones. Buy the smaller half.",
    ),
    "MF": (
        "The market itself",
        "What the whole market returned above the risk-free rate.",
    ),
}

# Episodes worth calling out by name, and the windows matter more than the
# names do.
#
# The first version of this used 2007-01 to 2009-12 for "the 2008 crash". That
# window contains the 2007 rally and the 2009 recovery, so the market came out
# at +12.7% and every factor washed to nothing -- and it was written up as
# "momentum pays nothing in a crash", which is the opposite of the truth.
#
# Peak to trough, and the rebound separately, because they are where the two
# halves of the risk live: momentum holds up while the market falls and then
# loses violently when it turns, since the losers it has stepped away from
# bounce hardest.
_EPISODES = [
    ("2008 crash", "2008-01", "2009-03"),
    ("2009 rebound", "2009-04", "2009-12"),
    ("COVID crash", "2020-01", "2020-04"),
    ("COVID rebound", "2020-04", "2020-12"),
    ("Last 8 years", "2018-01", "2025-12"),
]


def _stats(series: pd.Series, min_months: int = 24) -> dict | None:
    clean = series.dropna()
    if len(clean) < min_months:
        return None
    mean = float(clean.mean())
    spread = float(clean.std())
    if spread == 0:
        return None
    return {
        "annual_return": round(mean * 12, 2),
        # Fama-MacBeth on monthly observations, which do not overlap.
        "t_stat": round(mean / (spread / len(clean) ** 0.5), 2),
        "months": int(len(clean)),
        # Below about 2, the column is consistent with luck. Said here rather
        # than left for the reader to remember.
        "significant": abs(mean / (spread / len(clean) ** 0.5)) >= 2.0,
    }


def main() -> int:
    print(f"fetching {_SOURCE.rsplit('/', 1)[-1]} ...")
    response = httpx.get(_SOURCE, timeout=90, follow_redirects=True)
    response.raise_for_status()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    raw = Path(_OUT.parent / "_iima_raw.csv")
    raw.write_bytes(response.content)

    frame = pd.read_csv(raw)
    frame["Date"] = pd.to_datetime(frame["Date"])
    for column in ("SMB", "HML", "WML", "MF", "RF"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    raw.unlink(missing_ok=True)

    factors = []
    for code, (name, plain) in _FACTORS.items():
        overall = _stats(frame[code])
        if overall is None:
            continue
        episodes = []
        for label, start, end in _EPISODES:
            window = frame[(frame.Date >= start) & (frame.Date <= end)][code]
            # A crash is three to fifteen months. The floor that protects the
            # headline figure would discard exactly the windows that matter,
            # so these are allowed to be short -- and their t is reported so a
            # short window cannot pass as a strong one.
            measured = _stats(window, min_months=3)
            if measured:
                episodes.append({"label": label, **measured})
        factors.append(
            {
                "code": code,
                "name": name,
                "plain": plain,
                **overall,
                "episodes": episodes,
            }
        )

    # A cumulative line for momentum: the shape is the argument. It earns
    # steadily and then goes flat for years at a time, and no table conveys
    # that as directly as the curve does.
    monthly = frame[["Date", "WML"]].dropna()
    growth = (1 + monthly["WML"] / 100).cumprod()
    curve = [
        {"date": d.strftime("%Y-%m"), "value": round(float(v), 3)}
        for d, v in zip(monthly["Date"], growth)
        # Yearly points: 386 monthly points draw the same line and send four
        # times the data.
        if d.month == 12
    ]

    payload = {
        "built_on": date.today().isoformat(),
        "source": {
            "name": "IIMA Indian Fama-French-Momentum library",
            "url": _SOURCE,
            "note": (
                "Survivorship-bias adjusted, monthly, from October 1993. Built "
                "independently of this app."
            ),
        },
        "period": {
            "from": frame.Date.min().strftime("%Y-%m"),
            "to": frame.Date.max().strftime("%Y-%m"),
            "months": int(len(frame)),
        },
        "factors": factors,
        "momentum_curve": curve,
    }
    _OUT.write_text(json.dumps(payload, indent=2))

    print(f"\nwrote {_OUT.relative_to(Path.cwd()) if _OUT.is_relative_to(Path.cwd()) else _OUT}")
    print(f"  {payload['period']['from']} to {payload['period']['to']}, "
          f"{payload['period']['months']} months\n")
    for factor in factors:
        mark = "significant" if factor["significant"] else "not significant"
        print(f"  {factor['name']:<20} {factor['annual_return']:>+7.1f}%/yr  "
              f"t={factor['t_stat']:>+6.2f}  {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
