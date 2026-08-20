"""Building an actual basket: pick a fund per slot, then allocate across them.

Three modules, one job each. `basket.py` is the ported arithmetic and speaks
upstream's slot vocabulary. `basket_slots.py` translates that vocabulary into
traa's fund categories. This assembles them: read the latest scored run, fill
each slot, pull the NAV history, run the optimiser, and report what happened --
including the parts of what happened that upstream never surfaces.

**Three behaviours of the ported optimiser are disclosed rather than fixed**,
because the method is a faithful port and the decision was to reproduce it and
say so. All three were confirmed by running it, not read off the source:

1. Per-slot caps are rewritten when they cannot sum to 1. Four commodity slots
   asked for at 15% each come back allowed 25.02%. `bounds_applied` reports what
   the solver was actually given, beside what was asked for.
2. The strategy and regime settings do not move the answer. The loss floor is an
   additive constant in the objective while the constraint is violated, and it
   essentially always is, because the softmin is up to ten percentage points
   more pessimistic than the worst month that actually happened. Nine
   strategy x regime combinations agreed to 2.1e-15 on a realistic book.
3. The returned weights can exceed the caps the solver respected, because the
   tactical overlay multiplies and renormalises without re-checking. Both sets
   are returned: `weights` is what upstream would show, `weights_within_bounds`
   is the solver's own answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.services.advisor import fund_catalogue
from app.services.screener import basket as port
from app.services.screener import basket_slots, metrics, navstore, serve

# Enough history for the covariance to mean something and for the 30-row loss
# window to be a window rather than the whole series repeated. Two years of
# trading days, matching the pool's own 210-row floor with room over it.
RETURNS_DAYS = 500

# A fund has to share at least this much of the window with the others to join
# the covariance. Below it, keeping the fund would cost every date the others do
# have; dropping it costs one slot. Measured against the alternative: with a
# bare dropna(), one fund whose history sits in a different period empties the
# frame and the entire basket fails.
MIN_DATE_OVERLAP = 0.6

# Upstream's default. Kept because changing it would change every allocation.
DEFAULT_OBJECTIVE = "bachatt"
DEFAULT_STRATEGY = "balanced"
DEFAULT_REGIME = "neutral"


@dataclass(frozen=True)
class SlotFill:
    slot_key: str
    label: str
    scheme_code: str | None
    name: str | None
    category: str | None
    score: float | None
    weight: float | None
    weight_within_bounds: float | None
    bounds_asked: tuple[float, float]
    bounds_applied: tuple[float, float]
    pool_size: int
    caveat: str | None
    reason: str | None = None


@dataclass(frozen=True)
class BasketResult:
    basket_id: str
    name: str
    strategy: str
    regime: str
    slots: list[SlotFill]
    success: bool
    as_of: date | None
    notes: list[str] = field(default_factory=list)

    @property
    def filled(self) -> int:
        """Sleeves that found a fund. Not the same as sleeves holding money."""
        return sum(1 for s in self.slots if s.scheme_code)

    @property
    def allocated(self) -> int:
        """Sleeves that actually got weight.

        MAXX fills all five and gives one of them 0.0% -- the optimiser picked
        Zerodha Gold ETF FoF, scored it, and then allocated it nothing. Reporting
        only `filled` says "5 of 5 sleeves filled" over a table with an empty
        sleeve in it, which is true and misleading at once.
        """
        return sum(1 for s in self.slots if (s.weight or 0.0) > 0.0)


def _pool_funds(session) -> tuple[list[port.PoolFund], date | None]:
    """Every scored fund from the latest accepted run, as the pool rule needs it."""
    run_id = navstore.latest_run_id(session)
    if run_id is None:
        raise serve.NoCompletedRun(navstore.store_stats(session))
    header = serve.latest_run(session)

    rows = session.execute(
        navstore.text(
            "SELECT s.code, s.category, s.sub_category, s.score, s.peer_size,"
            "       i.nav_fresh, i.nav_rows "
            "FROM screener_score s "
            "LEFT JOIN screener_input i ON i.run_id = s.run_id AND i.code = s.code "
            "WHERE s.run_id = :r"
        ),
        {"r": run_id},
    ).all()
    return (
        [
            port.PoolFund(
                code=r[0], category=r[1], sub_category=r[2],
                score=float(r[3] or 0.0), peer_size=r[4],
                nav_fresh=bool(r[5]), nav_rows=int(r[6] or 0),
            )
            for r in rows
        ],
        header["as_of"],
    )


def _returns(session, codes: list[str], as_of: date) -> pd.DataFrame:
    """Daily log returns for the chosen funds, on their common dates.

    An inner join on date, not an outer one. A fund missing a day would
    otherwise contribute a NaN that propagates through the covariance and makes
    every pairing with it undefined -- and `np.cov` would not complain, it would
    return NaN weights that the solver turns into an arbitrary corner.
    """
    start = date.fromordinal(as_of.toordinal() - RETURNS_DAYS)
    series = {}
    for code in codes:
        navs = navstore.nav_window(session, code, start=start, end=as_of)
        if len(navs) < 2:
            continue
        series[code] = metrics.nav_to_log_returns(navs)
    if not series:
        return pd.DataFrame()
    frame = pd.DataFrame(series)

    # Drop thin columns BEFORE dropping rows. A single fund whose history sits
    # in a different period makes every row contain a NaN, so a bare `dropna()`
    # empties the frame and the whole basket fails because of one stray. Dropping
    # the column that causes it costs that slot and saves the basket.
    coverage = frame.notna().mean()
    keep = [c for c in frame.columns if coverage[c] >= MIN_DATE_OVERLAP]
    if keep:
        frame = frame[keep]
    return frame.dropna()


def build(
    session,
    basket_id: str,
    *,
    strategy: str | None = None,
    regime: str = DEFAULT_REGIME,
    objective: str = DEFAULT_OBJECTIVE,
) -> BasketResult:
    """Fill a basket's slots and allocate across them."""
    definition = port.get_basket(basket_id)
    if definition is None:
        raise ValueError(f"unknown basket {basket_id!r}")
    strategy = strategy or definition.get("strategy") or DEFAULT_STRATEGY

    funds, as_of = _pool_funds(session)
    by_code = {f.code: f for f in funds}
    catalogue = {f.code: f for f in fund_catalogue.all_funds()}
    notes: list[str] = []

    # One pick per slot. Membership comes from the traa mapping, eligibility
    # from the ported rule -- kept apart so an empty slot can say which of the
    # two emptied it.
    picks: list[tuple[str, port.PoolFund | None, int, str | None]] = []
    for slot_key in definition["slots"]:
        try:
            member_codes = set(basket_slots.codes_for_slot(slot_key))
        except basket_slots.UnmappedSlot as exc:
            picks.append((slot_key, None, 0, str(exc)))
            continue
        candidates = [by_code[c] for c in member_codes if c in by_code]
        eligible = [f for f in candidates if port.pool_eligibility(f)[0]]
        eligible.sort(key=lambda f: (-f.score, f.code))
        if not eligible:
            why = (
                f"no fund in this slot is currently rankable "
                f"({len(candidates)} scored, none clearing the pool rule)"
                if candidates
                else "no scored fund matched this slot"
            )
            picks.append((slot_key, None, len(candidates), why))
            continue
        picks.append((slot_key, eligible[0], len(eligible), None))

    chosen = [(slot, fund) for slot, fund, _n, _why in picks if fund is not None]
    if len(chosen) < port.MIN_BASKET_SIZE:
        notes.append(
            f"only {len(chosen)} slot(s) could be filled; a basket needs at least "
            f"{port.MIN_BASKET_SIZE}"
        )
        return BasketResult(
            basket_id=basket_id, name=definition.get("name", basket_id),
            strategy=strategy, regime=regime, as_of=as_of, success=False,
            notes=notes,
            # A slot that DID find a fund still reports it, with no weight.
            # An earlier version hardcoded every scheme_code to None here, so a
            # basket that failed for being too small told the reader that none
            # of its slots had filled -- which is a different and wronger story
            # than "one filled, and one is not a basket".
            slots=[
                SlotFill(
                    slot_key=slot,
                    label=basket_slots.label_for_slot(slot),
                    scheme_code=fund.code if fund else None,
                    name=getattr(catalogue.get(fund.code), "name", None) if fund else None,
                    category=fund.category if fund else None,
                    score=fund.score if fund else None,
                    weight=None, weight_within_bounds=None,
                    bounds_asked=port.weight_bounds_for_slot(slot),
                    bounds_applied=port.weight_bounds_for_slot(slot),
                    pool_size=n, caveat=basket_slots.caveat_for_slot(slot),
                    reason=why if fund is None else "not allocated: the basket is too small",
                )
                for slot, fund, n, why in picks
            ],
        )

    codes = [f.code for _slot, f in chosen]
    returns = _returns(session, codes, as_of)
    usable = [c for c in codes if c in returns.columns]
    if len(usable) < port.MIN_BASKET_SIZE or returns.empty:
        notes.append("not enough overlapping NAV history to allocate across these funds")
        success = False
        weights = raw = [None] * len(chosen)
        applied = [port.weight_bounds_for_slot(s) for s, _f in chosen]
    else:
        returns = returns[usable]
        chosen = [(s, f) for s, f in chosen if f.code in usable]
        asked = [port.weight_bounds_for_slot(s) for s, _f in chosen]
        applied = [tuple(map(float, b)) for b in port.feasible_bounds(asked)]
        if applied != [tuple(map(float, b)) for b in asked]:
            notes.append(
                "the per-slot caps could not sum to 1, so the optimiser rescaled "
                "them: "
                + ", ".join(
                    f"{basket_slots.label_for_slot(s)} asked {a[1]:.0%} "
                    f"allowed {p[1]:.0%}"
                    for (s, _f), a, p in zip(chosen, asked, applied)
                    if abs(a[1] - p[1]) > 1e-9
                )
            )
        scores = {f.code: f.score for _s, f in chosen}
        weights, success, raw = port.optimize_portfolio(
            returns, asked, strategy, regime, objective, scores=scores, return_raw=True
        )
        weights, raw = list(np.asarray(weights)), list(np.asarray(raw))
        # Rounded the same way the field is before it is formatted. Otherwise
        # the note reads "15.9%" off the raw float while the table one line
        # below reads "16.0%" off `round(w, 4)` -- the same number printed two
        # ways, which is exactly the kind of small disagreement that makes a
        # reader stop trusting both.
        breached = [
            f"{basket_slots.label_for_slot(s)} {round(float(w), 4):.1%} "
            f"against a {p[1]:.0%} cap"
            for (s, _f), w, p in zip(chosen, weights, applied)
            if w > p[1] + 1e-9
        ]
        if breached:
            notes.append(
                "the tactical overlay pushed a slot past the cap the optimiser "
                "respected: " + ", ".join(breached)
            )
        if not success:
            # Worth saying out loud, because the failure makes the page look
            # BETTER. On the all-attempts-failed path the ported optimiser
            # returns clipped equal weights and never reaches the tactical
            # overlay -- so no cap is breached, no note appears, and a run that
            # did not converge is indistinguishable from a clean one except that
            # it looks tidier.
            notes.append(
                "the optimiser did not converge, so these are fallback weights "
                "rather than an optimised allocation, and the usual momentum "
                "adjustment was skipped"
            )

    filled = {s: (f, w, r) for (s, f), w, r in zip(chosen, weights, raw)}
    bounds_by_slot = {s: b for (s, _f), b in zip(chosen, applied)}

    slots = []
    for slot_key, fund, pool_size, why in picks:
        got = filled.get(slot_key)
        meta = catalogue.get(fund.code) if fund else None
        slots.append(
            SlotFill(
                slot_key=slot_key,
                label=basket_slots.label_for_slot(slot_key),
                scheme_code=fund.code if fund else None,
                name=getattr(meta, "name", None),
                category=fund.category if fund else None,
                score=fund.score if fund else None,
                weight=None if got is None or got[1] is None else round(float(got[1]), 4),
                weight_within_bounds=(
                    None if got is None or got[2] is None else round(float(got[2]), 4)
                ),
                bounds_asked=port.weight_bounds_for_slot(slot_key),
                bounds_applied=bounds_by_slot.get(
                    slot_key, port.weight_bounds_for_slot(slot_key)
                ),
                pool_size=pool_size,
                caveat=basket_slots.caveat_for_slot(slot_key),
                reason=why if fund is None else None,
            )
        )

    return BasketResult(
        basket_id=basket_id, name=definition.get("name", basket_id),
        strategy=strategy, regime=regime, slots=slots,
        success=bool(success), as_of=as_of, notes=notes,
    )
