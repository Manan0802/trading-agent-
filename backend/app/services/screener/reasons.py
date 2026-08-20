"""Why a fund is on the screen -- and, far more often, saying nothing at all.

This is the part of the upstream method worth porting for its restraint. A
metric bullet appears under a fund only when the fund is genuinely near the top
of its own peer group on that metric:

    Top Recent Returns vs Peers : +6.2% (3M), +2.1% (1M)

Otherwise there is no bullet. Not a softer one, not "middle of the pack", not
"in line with peers". Silence. A screen that finds something flattering to say
about all 1,886 funds has said nothing about any of them.

**The rank is never printed.** Upstream once did ("#2 of 21 by 3M return") and
stopped; the stale comment above their `_SHORT_TERM_METRICS` still describes the
old behaviour while `_value_phrase` right below it does the new one. Here the
rank cannot leak even by accident, because `FundReason` has no field to put it
in and no assembled sentence contains it. `test_screener_reasons.py` asserts
both, and asserts that two funds at different ranks with the same value produce
byte-identical text -- so the rank is not merely hidden, it is unrecoverable.

Pure, in the same sense as `universe.py`: a function over plain records. No
database, no network, no clock. It is handed the whole scored universe because a
claim about one fund is a statement about every one of its peers.

UNITS: `returns_*` and `rolling_*` come out of `metrics.FundMetrics` as PERCENTS
(12.6 means 12.6%), so a `FundReason` carrying one is `unit="percent"`. The
momentum signal is a bare 0-1 number, `unit="ratio"`.

----------------------------------------------------------------------------
Two places where a faithful port and a correct one part company
----------------------------------------------------------------------------

**Ties are resolved by minimum rank, not average.** Upstream computes
`rank = 1 + count(peers strictly better)`, which is pandas' `method="min"`;
pandas' *default* `method="average"` would hand two funds tied for 5th a rank of
5.5 and silence both, because 5.5 > `_MAX_DISPLAY_RANK`. We keep minimum rank,
and not only for parity: under it `rank <= 5` means exactly "at most four peers
beat this fund", which is the claim the bullet is making. Under averaging the
same rank number means something fuzzier that is true of neither fund.

**A missing value is not a zero.** `universe.safe_float` turns None into 0.0 for
*scoring*, deliberately and upstream. For a *claim* that would be corrosive: if
half a group has no 3-year return, scoring the absent half as 0.0 makes the
present half's "top 15%" trivially reachable, and the bullet would be boasting
about beating funds that simply have no data. So a metric is ranked over its
non-null values only and `n` counts only those -- which is what upstream's
`array_agg(...) FILTER (WHERE ... IS NOT NULL)` does too.

We add one thing upstream does not. Upstream gates group size on `COUNT(*)` of
the group while ranking over the non-null subset, so a group of 5 in which only
one fund has the metric still produces a "top of its peers" bullet -- ranked #1
of 1. Here `_MIN_PCTL_PEERS` is applied to the ranked population as well: below
five funds *with a value*, the metric says nothing. It is the same rule as the
peer-group floor, applied where the ranking actually happens.

----------------------------------------------------------------------------
What is not ported, and why
----------------------------------------------------------------------------

`_BULLET_PRIORITY` keeps every upstream slot, including the ones nothing here
emits, so wiring one up later inserts it at its right place instead of
reshuffling the rest.

  * `sector_context`, `sector_context_fund` (0, 0.5) -- no sector data.
  * `nifty` (4) -- no benchmark series in the screener yet.
  * `sub_category_boom` (5) -- upstream's is a statement about *this week's*
    curated top-10 card ("3 of this week's top 10 picks"). This module has a
    universe, not a week and not a card, so the sentence would not be true.
  * `grade` (8) -- upstream fires it for "Very Good" *and* "Good", i.e. from the
    65th percentile of the peer group upward, and calls that "exceptionally
    strong stability among its peers". A bullet that praises the 65th percentile
    is the exact hedge this module exists to refuse. Slot kept; text not ported.
  * `rank` (9) -- upstream's last-resort filler, emitted when a fund qualified
    for nothing at all: "Top <vendor>-ranked fund in Small Cap Fund". It carries
    the vendor's name into a user-facing string, and it asserts a standing the
    fund just failed to earn. Silence is the correct output there, and silence
    is what this returns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.screener.metrics import FundMetrics
from app.services.screener.universe import ScoredFund

# A fund qualifies on a metric when its rank inside the peer group is in the top
# 15% -- rank <= ceil(0.15 * n).
_TOP_PCTL_FRAC = 0.15

# Below this a rank is not a ranking. Applied twice: to the peer group (which is
# what makes a thin sub-category fall back to its category) and to the count of
# funds that actually have the metric.
_MIN_PCTL_PEERS = 5

# Hard cap on standing, whatever the group size. Without it the category
# fallback -- 586 equity funds -- would let #80 of 586 call itself top-15%.
_MAX_DISPLAY_RANK = 5

# Bullets a card shows. See `_select_bullets`.
_MAX_BULLETS = 6

# Momentum bands over the fourteen-day signal, calibrated upstream against the
# older count-of-up-days rule: 0.32 was the old 6-of-14 threshold.
MOMENTUM_STRONG = 0.40
MOMENTUM_MODERATE = 0.32

# The "lone pick" bullet's window: a fund's own category's top ten by score.
_TOP_N_IN_CATEGORY = 10

# Metrics behind each narrative, in the order their phrases are joined.
_SHORT_TERM_METRICS = (("returns_3m", "3M"), ("returns_1m", "1M"))
_LONG_TERM_METRICS = (("returns_1y", "1Y"), ("returns_3y", "3Y"))
_CONSISTENCY_METRIC = "rolling_3m"

# How much record a fund needs before a bullet may cite a horizon.
#
# Upstream's `get_trailing_ret` falls back to the whole available window when a
# fund is younger than the period asked for, and then annualises it. So a fund
# 15 months old has a `returns_3y`, and it is that 15 months compounded. Groww
# Silver ETF FOF is the live example: 1.23 years of history, +125% total, and a
# "3-year return" of +148.6%.
#
# We reproduce that in the SCORE, because the score is a faithful port. We do
# not reproduce it in the CLAIM. "Higher long-run returns" about a fund with no
# long run is exactly the kind of sentence this whole module exists to refuse,
# and the fund is still free to win on its 1Y and 3M numbers, which are real.
_MIN_YEARS_FOR = {
    "returns_3y": 3.0,
    "rolling_3y": 3.0,
    "returns_1y": 1.0,
    "rolling_1y": 1.0,
    "returns_6m": 0.5,
    "rolling_6m": 0.5,
}

# Order bullets are selected and shown in (lower first). Every upstream slot is
# here, including the five nothing emits -- see the module docstring.
_BULLET_PRIORITY = {
    "sector_context": 0,        # not emitted: no sector data
    "sector_context_fund": 0.5,  # not emitted: no sector data
    "short_term": 1,
    "long_term": 2,
    "consistency": 3,
    "nifty": 4,                 # not emitted: no benchmark wired in
    "sub_category_boom": 5,     # not emitted: needs a weekly curated top-N
    "momentum": 6,
    "outperforming_peers": 7,
    "grade": 8,                 # not emitted: praises the 65th percentile
    "rank": 9,                  # not emitted: a filler claim, deliberately
}

# The highlighted section title above each bullet.
_BULLET_LABELS = {
    "short_term": "Recent Performance",
    "long_term": "Long Term Performance",
    "consistency": "Consistent Performance",
    "momentum": "Momentum",
    "outperforming_peers": "Peer Standing",
}

# Percentile buckets, in points: top 5 / 10 / 15 / 20 / 25%.
_PCTL_STEP = 5
_TOP_PCTL_MAX = 25


@dataclass(frozen=True)
class FundReason:
    """One bullet.

    There is no rank field and there will not be one. A template that wanted to
    print "#2 of 21" would have to add the field first, and adding it fails
    `test_the_rank_never_appears_in_the_output`.
    """

    kind: str
    label: str
    value: float
    unit: str          # "percent" | "ratio"
    peer_group: str
    text: str


def bucket_pct(pos: int, n: int) -> int:
    """A position among n peers as a percentile, rounded UP to the next 5.

    Rounding up is what keeps the sentence true. #1 of 17 is 5.9%, which becomes
    "top 10%" -- true -- rather than "top 5%", which is false, because the top 5%
    of 17 funds is less than one fund. Rounding down or to nearest would make
    every claim a little more flattering than the data supports.
    """
    return max(_PCTL_STEP, _PCTL_STEP * math.ceil((100 * pos / n) / _PCTL_STEP))


def peer_standing(rank: int | None, n: int | None) -> str | None:
    """'top 10%', or None when the standing is not worth a sentence.

    Nothing in this module prints this today -- the bullets show the value and
    the period, never the standing. It is ported and tested because it is the
    only rounding rule that keeps a percentile claim honest, and because the day
    a template does want to say "top 10%", the rule has to already be right.
    Upstream uses it in the per-fund breakdown copy, not in these bullets.
    """
    if not rank or not n or n <= 0:
        return None
    pct = bucket_pct(rank, n)
    return f"top {pct}%" if pct <= _TOP_PCTL_MAX else None


def _finite(value) -> float | None:
    """None, NaN and unparseable all stay None -- never 0.0. See the docstring."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _metric_rank(value: float | None, values: list[float]) -> tuple[int | None, int | None]:
    """1-based rank among peer values (higher is better), and how many carry one.

    Minimum rank on ties: `1 + the number of peers strictly better`. So the rank
    reads as "at most this many funds beat me", which is what the bullet claims.
    """
    if value is None or not values:
        return None, None
    n = len(values)
    rank = 1 + sum(1 for x in values if x > value)
    return rank, n


def _is_top_rank(rank: int | None, n: int | None) -> bool:
    """Top 15% of the group AND no worse than #5. Ported verbatim.

    The two clauses are not redundant, but on this universe they mostly agree:
    ceil(0.15 * 33) is 5, so below 34 peers the percentile is the binding
    clause and the absolute cap only starts doing work in the twenty
    sub-categories bigger than that.
    """
    if not rank or not n:
        return False
    cutoff = max(1, math.ceil(_TOP_PCTL_FRAC * n))
    return rank <= cutoff and rank <= _MAX_DISPLAY_RANK


def _qualifies(value: float | None, values: list[float]) -> bool:
    """Whether this fund may say anything at all about this metric."""
    if value is None or len(values) < _MIN_PCTL_PEERS:
        return False
    rank, n = _metric_rank(value, values)
    return _is_top_rank(rank, n)


def _value_phrase(value: float | None, values: list[float], label: str) -> str | None:
    """'+6.2% (3M)' when the fund leads its peers on this metric, else None."""
    if not _qualifies(value, values):
        return None
    return f"{float(value):+.1f}% ({label})"


def _reason(kind: str, value: float, unit: str, peer_group: str, text: str) -> FundReason:
    return FundReason(
        kind=kind,
        label=_BULLET_LABELS[kind],
        value=value,
        unit=unit,
        peer_group=peer_group,
        text=text,
    )


def _select_bullets(reasons: list[FundReason], limit: int = _MAX_BULLETS) -> list[FundReason]:
    """Up to `limit` bullets, one per kind, in priority order."""
    out: list[FundReason] = []
    seen: set[str] = set()
    for r in sorted(reasons, key=lambda r: _BULLET_PRIORITY.get(r.kind, 99)):
        if r.kind in seen:
            continue
        seen.add(r.kind)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def _metric_of(
    fund: ScoredFund, metrics: dict[str, FundMetrics], name: str
) -> float | None:
    record = metrics.get(fund.code)
    if record is None:
        return None
    return _finite(getattr(record, name, None))


def _has_lived_through(fund: ScoredFund, metrics: dict, name: str) -> bool:
    """Whether the fund is old enough for a claim about this horizon to be true.

    Unknown history is treated as insufficient. A missing `history_years` means
    we cannot show the claim is honest, and the rule everywhere else in this
    module is that silence is the default.
    """
    needed = _MIN_YEARS_FOR.get(name)
    if needed is None:
        return True
    record = metrics.get(fund.code)
    years = getattr(record, "history_years", None) if record else None
    return years is not None and float(years) >= needed


def _display_group(fund: ScoredFund) -> str:
    """What to call this fund's segment when the sentence is not a peer claim."""
    return fund.sub_category or fund.category or "peers"


def _category_top_n(
    scored: list[ScoredFund],
    metrics: dict[str, FundMetrics],
    n: int = _TOP_N_IN_CATEGORY,
) -> dict[str | None, tuple[frozenset[str], dict[str | None, int]]]:
    """Each category's top-n by score, and how its sub-categories are spread there.

    Ordered by score, then by 1-month return, then by code -- upstream's own
    tie-break for the same list, and total, so the tenth slot is never decided
    by dict ordering.
    """
    by_category: dict[str | None, list[ScoredFund]] = {}
    for fund in scored:
        by_category.setdefault(fund.category, []).append(fund)

    out: dict[str | None, tuple[frozenset[str], dict[str | None, int]]] = {}
    for category, members in by_category.items():
        ranked = sorted(
            members,
            key=lambda f: (
                -f.score,
                -(_metric_of(f, metrics, "returns_1m") or float("-inf")),
                f.code,
            ),
        )[:n]
        counts: dict[str | None, int] = {}
        for fund in ranked:
            counts[fund.sub_category] = counts.get(fund.sub_category, 0) + 1
        out[category] = (frozenset(f.code for f in ranked), counts)
    return out


def reasons_for_universe(
    scored: list[ScoredFund],
    metrics: dict[str, FundMetrics],
) -> dict[str, list[FundReason]]:
    """Every fund's bullets, keyed by scheme code.

    Every code in `scored` appears in the mapping. Most of them map to an empty
    list, and that is the intended output -- a fund with nothing true to say
    about it says nothing, and the caller can tell the difference between "no
    bullets" and "fund not considered".
    """
    sub_members: dict[tuple, list[ScoredFund]] = {}
    cat_members: dict[str | None, list[ScoredFund]] = {}
    for fund in scored:
        if fund.sub_category:
            sub_members.setdefault((fund.category, fund.sub_category), []).append(fund)
        cat_members.setdefault(fund.category, []).append(fund)

    cache: dict[tuple, dict[str, list[float]]] = {}

    def values_for(key: tuple, members: list[ScoredFund], name: str) -> list[float]:
        group = cache.setdefault(key, {})
        if name not in group:
            group[name] = [
                v for f in members
                if (v := _metric_of(f, metrics, name)) is not None
            ]
        return group[name]

    def resolve(fund: ScoredFund) -> tuple[tuple | None, list[ScoredFund], str]:
        """The fund's peer group: its sub-category if that holds enough funds,
        else its category, else nothing at all."""
        if fund.sub_category:
            members = sub_members.get((fund.category, fund.sub_category))
            if members and len(members) >= _MIN_PCTL_PEERS:
                key = ("sub", fund.category, fund.sub_category)
                return key, members, (fund.sub_category or fund.category or "peers")
        members = cat_members.get(fund.category) if fund.category else None
        if members and len(members) >= _MIN_PCTL_PEERS:
            return ("cat", fund.category), members, (fund.category or "peers")
        return None, [], ""

    top_n = _category_top_n(scored, metrics)
    sub_sizes = {key: len(members) for key, members in sub_members.items()}

    out: dict[str, list[FundReason]] = {}
    for fund in scored:
        out[fund.code] = _select_bullets(
            _reasons_for_fund(fund, metrics, resolve, values_for, top_n, sub_sizes)
        )
    return out


def _reasons_for_fund(fund, metrics, resolve, values_for, top_n, sub_sizes) -> list[FundReason]:
    reasons: list[FundReason] = []
    key, members, group = resolve(fund)

    if key is not None:
        def peers(name: str) -> list[float]:
            return values_for(key, members, name)

        def qualifying(pairs):
            """(value, phrase) for each metric the fund genuinely leads on.

            A horizon the fund has not lived through is skipped, however good
            the number looks -- see `_MIN_YEARS_FOR`.
            """
            out = []
            for name, label in pairs:
                if not _has_lived_through(fund, metrics, name):
                    continue
                value = _metric_of(fund, metrics, name)
                phrase = _value_phrase(value, peers(name), label)
                if phrase:
                    out.append((value, phrase))
            return out

        # Recent returns the fund leads its peers on. No momentum fallback --
        # momentum has its own bullet and would otherwise be counted twice.
        won = qualifying(_SHORT_TERM_METRICS)
        if won:
            reasons.append(_reason(
                "short_term", float(won[0][0]), "percent", group,
                "Top Recent Returns vs Peers : " + ", ".join(p for _v, p in won),
            ))

        won = qualifying(_LONG_TERM_METRICS)
        if won:
            reasons.append(_reason(
                "long_term", float(won[0][0]), "percent", group,
                "Higher long-run returns vs Peers : " + ", ".join(p for _v, p in won),
            ))

        rolling = _metric_of(fund, metrics, _CONSISTENCY_METRIC)
        if _qualifies(rolling, peers(_CONSISTENCY_METRIC)):
            reasons.append(_reason(
                "consistency", float(rolling), "percent", group,
                f"Highly Reliable : {float(rolling):+.1f}% (3M rolling) "
                "consistently over the periods",
            ))

    # Momentum is the fund's own two-week signal, not a peer comparison, so a
    # thin peer group does not silence it. It is described, never numbered: a
    # 0-1 score means nothing to a reader, and rendering it would invite the
    # question "0.41 out of what?".
    momentum = _finite(fund.momentum)
    if momentum is not None and momentum >= MOMENTUM_MODERATE:
        text = (
            "Strong accelerated growth over the last two weeks"
            if momentum >= MOMENTUM_STRONG
            else "Accelerated growth over the last two weeks"
        )
        reasons.append(_reason("momentum", momentum, "ratio", _display_group(fund), text))

    # "Lone top-10 pick" only when it is literally true: the fund is in its
    # category's top ten AND no other fund of its sub-category is. A fund that
    # merely ranks well says nothing here -- upstream had this bug and fixed it.
    #
    # The peer floor applies here too, and upstream does not apply it. "While
    # most peers rank lower" needs peers: a sub-category with one fund in it is
    # trivially the only one of its kind anywhere, so upstream's version fires
    # on a universe of a single fund. Requiring five sub-category peers also
    # makes the window mean something -- with ten or fewer funds in the
    # category every fund is in the top ten, and five peers can then never be
    # one.
    ids, counts = top_n.get(fund.category, (frozenset(), {}))
    if (fund.code in ids
            and counts.get(fund.sub_category, 0) == 1
            and sub_sizes.get((fund.category, fund.sub_category), 0) >= _MIN_PCTL_PEERS):
        segment = fund.sub_category or "its segment"
        reasons.append(_reason(
            "outperforming_peers", float(fund.score), "ratio", segment,
            f"Outperforming peers in {segment} — lone top-{_TOP_N_IN_CATEGORY} "
            "pick while most peers rank lower",
        ))

    return reasons
