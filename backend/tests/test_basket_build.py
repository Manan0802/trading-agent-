"""Assembling a basket, and surfacing what the ported optimiser does quietly.

The arithmetic is tested in `test_basket_parity.py` against the real source.
This is about the three behaviours a user would otherwise never be told about,
and about a slot that cannot be filled saying so.
"""

from datetime import date, timedelta

import numpy as np
import pytest

from app.services.advisor import fund_catalogue
from app.services.screener import basket as port
from app.services.screener import basket_build, basket_slots, navstore, pipeline, serve
from app.services.screener import inputs as inputs_mod

AS_OF = date.today()


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTRADE_NAV_DB", str(tmp_path / "nav.db"))
    navstore.reset_engine()
    navstore.ensure_schema()
    yield
    navstore.reset_engine()


def seed_every_slot(rows: int = 900) -> list[str]:
    """Enough funds in every slot of both baskets to clear the pool rule."""
    codes: list[str] = []
    for slot in basket_slots.SLOT_CATEGORIES:
        codes.extend(basket_slots.codes_for_slot(slot)[:12])
    codes = list(dict.fromkeys(codes))
    with navstore.session() as s:
        for i, code in enumerate(codes):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i * 0.7)
                 for d in range(rows)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)
    return codes


def build(basket_id="MAXX", **kw):
    with navstore.session() as s:
        return basket_build.build(s, basket_id, **kw)


# ------------------------------------------------------------ the happy path


def test_both_baskets_fill_every_slot_on_a_seeded_universe():
    seed_every_slot()
    for basket_id in ("MAXX", "BALANCED"):
        result = build(basket_id)
        assert result.filled == len(result.slots), [
            (s.slot_key, s.reason) for s in result.slots if not s.scheme_code
        ]
        assert result.success


def test_the_weights_sum_to_one():
    seed_every_slot()
    total = sum(s.weight for s in build().slots if s.weight is not None)
    assert total == pytest.approx(1.0, abs=0.01)


def test_each_slot_is_filled_by_a_fund_that_belongs_in_it():
    """The point of the mapping. A gold sleeve holding a Nasdaq tracker is the
    failure `fund_universe`'s own comment warns about."""
    seed_every_slot()
    by_code = {f.code: f for f in fund_catalogue.all_funds()}
    for slot in build().slots:
        if not slot.scheme_code:
            continue
        assert slot.scheme_code in set(basket_slots.codes_for_slot(slot.slot_key))
        if slot.slot_key == "Commodity::Gold":
            assert "gold" in by_code[slot.scheme_code].name.lower()
        if slot.slot_key == "Commodity::Silver":
            assert "silver" in by_code[slot.scheme_code].name.lower()


def test_the_pick_is_the_highest_scoring_eligible_fund_in_the_slot():
    seed_every_slot()
    result = build()
    with navstore.session() as s:
        funds, _as_of = basket_build._pool_funds(s)
    by_code = {f.code: f for f in funds}
    for slot in result.slots:
        if not slot.scheme_code:
            continue
        members = set(basket_slots.codes_for_slot(slot.slot_key))
        eligible = [
            f for c, f in by_code.items()
            if c in members and port.pool_eligibility(f)[0]
        ]
        best = max(f.score for f in eligible)
        assert by_code[slot.scheme_code].score == pytest.approx(best)


# ------------------------------------------- the three quiet behaviours


def test_a_cap_the_overlay_breaches_is_reported_not_hidden():
    """Confirmed by running it: the solver held a slot at exactly 0.4000 and the
    tactical overlay returned 0.4798. It multiplies each weight by a factor
    between 0.1 and 3.0 and renormalises without re-checking the bounds."""
    seed_every_slot()
    result = build()
    breaches = [
        s for s in result.slots
        if s.weight is not None and s.weight > s.bounds_applied[1] + 1e-9
    ]
    if breaches:
        assert any("tactical overlay" in n for n in result.notes), result.notes


def test_both_the_shown_weights_and_the_in_bounds_ones_are_returned():
    """`weights` is what upstream would display; `weights_within_bounds` is what
    the solver actually agreed to. A reader who cares about the cap needs the
    second one, and it does not otherwise exist."""
    seed_every_slot()
    for slot in build().slots:
        if slot.weight is None:
            continue
        assert slot.weight_within_bounds is not None
        assert slot.weight_within_bounds <= slot.bounds_applied[1] + 1e-9


def test_a_rewritten_cap_is_reported_beside_what_was_asked_for():
    """Four commodity slots asked for at 15% each come back allowed 25.02%. The
    limit is not a limit, and nothing upstream says so."""
    asked = [(0.0, 0.15)] * 4
    applied = [tuple(map(float, b)) for b in port.feasible_bounds(asked)]
    assert applied[0][1] > 0.15, "the rewrite has stopped happening; recheck the note"
    assert applied[0][1] == pytest.approx(0.2502, abs=1e-3)


def test_the_strategy_setting_does_not_change_the_answer():
    """Pinned because it is surprising and because a screen offering the choice
    has to say so. The loss floor is an additive constant in the objective while
    the constraint is violated, and the softmin makes it essentially always
    violated."""
    seed_every_slot()
    weights = {}
    for strategy in ("conservative", "balanced", "aggressive"):
        weights[strategy] = [
            s.weight for s in build(strategy=strategy).slots if s.weight is not None
        ]
    base = weights["balanced"]
    for strategy, got in weights.items():
        assert got == pytest.approx(base, abs=1e-4), (
            f"{strategy} differs from balanced -- if this now fails, the loss "
            "floor has started binding and the disclosure needs revisiting"
        )


def test_the_regime_setting_does_not_change_the_answer_either():
    seed_every_slot()
    base = [s.weight for s in build(regime="neutral").slots if s.weight is not None]
    for regime in ("bullish", "bearish"):
        got = [s.weight for s in build(regime=regime).slots if s.weight is not None]
        assert got == pytest.approx(base, abs=1e-4)


# ------------------------------------------------------- when it cannot


def test_a_slot_with_no_scored_fund_says_which_and_why():
    """A silent gap and an empty market look identical. Only one of them is
    worth a user's attention."""
    codes = basket_slots.codes_for_slot("Debt Scheme::Liquid Fund")[:12]
    with navstore.session() as s:
        for i, code in enumerate(codes):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i)
                 for d in range(900)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)

    result = build("BALANCED")
    empty = [s for s in result.slots if not s.scheme_code]
    assert empty, "the fixture filled every slot; it was meant to fill one"
    for slot in empty:
        assert slot.reason and len(slot.reason) > 15
        assert slot.weight is None

    # And the one slot that DID fill still names its fund. An earlier version
    # reported every slot as empty whenever the basket failed, which tells the
    # reader a different and wronger story than "one filled, one is not enough".
    found = [s for s in result.slots if s.scheme_code]
    assert found, "the seeded slot should still report the fund it found"
    assert all(s.weight is None for s in found), "a failed basket allocates nothing"
    assert all(s.reason for s in found), "and says why it was not allocated"


def test_a_basket_that_cannot_reach_two_slots_fails_rather_than_pretending():
    """`MIN_BASKET_SIZE` is 2. One fund is not a basket, and allocating 100% to
    it while calling it a portfolio would be worse than saying no."""
    codes = basket_slots.codes_for_slot("Commodity::Gold")[:10]
    with navstore.session() as s:
        for i, code in enumerate(codes):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i)
                 for d in range(900)],
            )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)

    result = build("MAXX")
    assert result.success is False
    assert result.filled < port.MIN_BASKET_SIZE
    assert any("at least" in n for n in result.notes)


def test_an_unbuilt_store_refuses_rather_than_returning_an_empty_basket():
    with navstore.session() as s:
        with pytest.raises(serve.NoCompletedRun):
            basket_build.build(s, "MAXX")


def test_an_unknown_basket_raises():
    seed_every_slot()
    with navstore.session() as s:
        with pytest.raises(ValueError, match="unknown basket"):
            basket_build.build(s, "NOT_A_BASKET")


# --------------------------------------------------------- the caveats


def test_the_two_mega_bucket_slots_carry_their_caveat_into_the_result():
    """A basket filling its index sleeve from 364 funds tracking different
    indices is making a sector bet whether or not anyone intended to."""
    seed_every_slot()
    slots = {s.slot_key: s for s in build().slots}
    assert slots["Equity Index Fund"].caveat
    assert slots["Sectoral/ Thematic"].caveat
    assert slots["Commodity::Gold"].caveat is None


def test_the_pool_size_behind_each_slot_is_reported():
    """"Best index fund" out of two is a different claim from out of ninety."""
    seed_every_slot()
    for slot in build().slots:
        if slot.scheme_code:
            assert slot.pool_size > 0


# ═══════════════════════════════════════════════════════════════════
# Written after a sabotage pass: five mutations walked through the tests
# above. Identical synthetic funds gave the tactical overlay nothing to
# tilt, so the breach test passed vacuously; nothing asserted the
# rewritten-cap note, the pool rule, or the date join at all.
# ═══════════════════════════════════════════════════════════════════


def seed_differentiated(rows: int = 900) -> None:
    """Funds that differ, so the tactical overlay has something to act on.

    The overlay scales each weight by momentum and drawdown over the last
    fortnight. Feed it a dozen identical linear ramps and every fund gets the
    same factor, renormalising changes nothing, and a test looking for a cap
    breach finds none — which is what happened.
    """
    import math

    codes: list[str] = []
    for slot in basket_slots.SLOT_CATEGORIES:
        codes.extend(basket_slots.codes_for_slot(slot)[:12])
    codes = list(dict.fromkeys(codes))

    with navstore.session() as s:
        for i, code in enumerate(codes):
            drift = 0.0002 + (i % 7) * 0.00035
            # A late acceleration on some funds and a late slump on others, so
            # the fortnight the overlay reads is genuinely different per fund.
            navs = []
            level = 100.0
            for d in range(rows):
                day = date(2026, 8, 19) - timedelta(days=rows - 1 - d)
                kick = 0.0
                if d > rows - 15:
                    kick = 0.004 if i % 3 == 0 else (-0.003 if i % 3 == 1 else 0.0)
                level *= math.exp(drift + kick)
                navs.append((day, round(level, 4)))
            navstore.insert_navs(s, code, navs)
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)


def test_a_cap_breach_is_named_in_the_notes(monkeypatch):
    """Tests the reporting, not the optimiser.

    Whether the overlay breaches depends on the data: it does on the real
    universe (0.4798 against a 0.40 cap) and not on a synthetic one, because
    identical funds all get the same tilt factor and renormalising is then a
    no-op. `test_basket_parity.py` proves the breach happens; this proves that
    when it does, the reader is told. A sabotage removing the note walked
    straight through the version of this test that waited for a real breach.
    """
    seed_every_slot()
    real = port.optimize_portfolio

    def breaching(returns, bounds, *a, **kw):
        adjusted, ok, raw = real(returns, bounds, *a, **{**kw, "return_raw": True})
        adjusted = list(np.asarray(adjusted, dtype=float))
        adjusted[0] = bounds[0][1] + 0.05          # push slot 0 past its cap
        return (adjusted, ok, raw) if kw.get("return_raw") else (adjusted, ok)

    monkeypatch.setattr(port, "optimize_portfolio", breaching)
    result = build("MAXX")
    assert any("tactical overlay" in n for n in result.notes), result.notes
    assert any("cap" in n for n in result.notes)


def test_the_in_bounds_weights_are_carried_through_separately(monkeypatch):
    """`weights` is what upstream would show; `weights_within_bounds` is what the
    solver agreed to. If the second were a copy of the first it would be
    worthless, and dropping it must fail something."""
    seed_every_slot()
    real = port.optimize_portfolio

    def diverging(returns, bounds, *a, **kw):
        adjusted, ok, raw = real(returns, bounds, *a, **{**kw, "return_raw": True})
        adjusted = [float(w) * 0.5 + 0.01 for w in np.asarray(adjusted, dtype=float)]
        return (adjusted, ok, raw) if kw.get("return_raw") else (adjusted, ok)

    monkeypatch.setattr(port, "optimize_portfolio", diverging)
    pairs = [
        (s.weight, s.weight_within_bounds)
        for s in build("MAXX").slots
        if s.weight is not None
    ]
    assert pairs
    assert all(b is not None for _w, b in pairs), "the in-bounds weights were dropped"
    assert any(abs(w - b) > 1e-6 for w, b in pairs), (
        "every shown weight equals its in-bounds weight, so the two are the same field"
    )


def test_a_rewritten_cap_is_named_in_the_notes(monkeypatch):
    """Four slots capped at 15% cannot sum to 1, so the optimiser quietly
    rescales them to 25.02% — and the caller's limit stops being a limit. No
    real basket triggers it, so it is forced here."""
    seed_every_slot()
    monkeypatch.setattr(port, "weight_bounds_for_slot", lambda _slot: (0.0, 0.15))
    result = build("MAXX")
    assert any("rescaled" in n for n in result.notes), result.notes
    assert any(s.bounds_applied[1] > s.bounds_asked[1] + 1e-9 for s in result.slots)


def test_a_fund_that_fails_the_pool_rule_is_not_picked():
    """The rule is peer_size >= 8, NAV-fresh, and >= 210 rows. Skipping it lets a
    fund with ten months less history than its rivals be called the best of its
    slot on a score built from a shorter record.

    The earlier version of this test asserted over a fixture in which every fund
    was eligible, so it proved nothing and a sabotage removing the rule passed.
    """
    slot = "Debt Scheme::Liquid Fund"
    members = basket_slots.codes_for_slot(slot)[:12]
    short_code = members[0]

    with navstore.session() as s:
        for i, code in enumerate(members):
            if code == short_code:
                # 200 NAVs spread over four years, not 200 consecutive days.
                # With daily NAVs anything under 210 rows also spans under a
                # year, so `universe.is_scoreable` refuses it first on roll1y
                # and the 210-row rule never gets a turn -- which is why an
                # earlier version of this test skipped instead of running.
                # Sparse publishing separates the two gates.
                # Steeper GROWTH, not a higher level. An earlier version added
                # 40 to the NAV, which changes nothing at all -- the score is
                # built from returns, so the fund was never top of its slot and
                # the eligibility sabotage had nothing to walk past.
                navstore.insert_navs(
                    s, code,
                    [(date(2026, 8, 19) - timedelta(days=7 * d), 100.0 * (1.004 ** (200 - d)))
                     for d in range(200)],
                )
            else:
                navstore.insert_navs(
                    s, code,
                    [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i * 0.5)
                     for d in range(900)],
                )
            navstore.record_source(s, code, backfilled_at="x")
        for other in basket_slots.codes_for_slot("Commodity::Gold")[:12]:
            navstore.insert_navs(
                s, other,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.03)
                 for d in range(900)],
            )
            navstore.record_source(s, other, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)

    with navstore.session() as s:
        funds, _ = basket_build._pool_funds(s)
    by_code = {f.code: f for f in funds}
    if short_code not in by_code:
        pytest.skip("the short fund was refused earlier than the pool rule")
    assert port.pool_eligibility(by_code[short_code])[0] is False, (
        f"{short_code} has {by_code[short_code].nav_rows} rows and was still eligible"
    )

    picked = {s.scheme_code for s in build("BALANCED").slots if s.scheme_code}
    assert short_code not in picked, (
        "a fund with 150 NAV rows filled a slot, under a rule requiring 210"
    )


def test_a_fund_with_no_overlapping_history_cannot_poison_the_others():
    """The returns frame is an inner join on date. An outer join leaves a NaN
    that propagates through the covariance, and `np.cov` does not complain — it
    returns NaN weights the solver turns into an arbitrary corner."""
    seed_every_slot()
    # One fund whose history sits entirely in a different decade.
    stray = basket_slots.codes_for_slot("Commodity::Gold")[0]
    with navstore.session() as s:
        frame = basket_build._returns(
            s, [stray] + basket_slots.codes_for_slot("Debt Scheme::Liquid Fund")[:3], AS_OF
        )
    assert not frame.isna().any().any(), "a NaN survived into the returns frame"

    result = build("MAXX")
    for slot in result.slots:
        if slot.weight is not None:
            assert slot.weight == slot.weight, f"{slot.slot_key} weight is NaN"


def test_the_short_fund_would_have_won_its_slot_if_the_rule_were_skipped():
    """Makes the previous test's negative meaningful.

    Asserting "the ineligible fund was not picked" proves nothing if it would
    not have been picked anyway. This asserts it outscores every rival, so its
    absence is the rule working rather than the score.
    """
    slot = "Debt Scheme::Liquid Fund"
    members = basket_slots.codes_for_slot(slot)[:12]
    short_code = members[0]
    with navstore.session() as s:
        for i, code in enumerate(members):
            if code == short_code:
                navstore.insert_navs(
                    s, code,
                    [(date(2026, 8, 19) - timedelta(days=7 * d), 100.0 * (1.004 ** (200 - d)))
                     for d in range(200)],
                )
            else:
                navstore.insert_navs(
                    s, code,
                    [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i * 0.5)
                     for d in range(900)],
                )
            navstore.record_source(s, code, backfilled_at="x")
    pipeline.run_nightly(as_of=AS_OF, refresh_feed=False)

    with navstore.session() as s:
        funds, _ = basket_build._pool_funds(s)
    by_code = {f.code: f for f in funds}
    if short_code not in by_code:
        pytest.skip("the short fund was refused before the pool rule saw it")
    rivals = [by_code[c] for c in members[1:] if c in by_code]
    assert rivals
    assert by_code[short_code].score > max(f.score for f in rivals), (
        "the short fund does not outscore its slot, so its exclusion proves nothing"
    )


def test_a_fund_whose_history_does_not_overlap_is_dropped_not_propagated():
    """One stray fund must cost its own slot, not the whole basket.

    `pd.DataFrame` outer-joins on the index, so a fund publishing in a different
    period puts a NaN in every row. A bare `dropna()` then empties the frame and
    every slot fails; leaving the NaN in is worse still, because `np.cov` does
    not complain and the solver turns NaN weights into an arbitrary corner.
    """
    good = basket_slots.codes_for_slot("Debt Scheme::Liquid Fund")[:4]
    stray = basket_slots.codes_for_slot("Commodity::Gold")[0]
    with navstore.session() as s:
        for i, code in enumerate(good):
            navstore.insert_navs(
                s, code,
                [(date(2026, 8, 19) - timedelta(days=d), 100.0 + d * 0.04 + i)
                 for d in range(900)],
            )
            navstore.record_source(s, code, backfilled_at="x")
        # Inside the 500-day window, but covering only its oldest quarter.
        # An earlier version put this fund a decade back, which meant
        # `_returns` skipped it before the frame was built and both sabotages
        # of the join walked straight through. It has to be present and thin,
        # not absent.
        oldest = AS_OF - timedelta(days=basket_build.RETURNS_DAYS - 10)
        navstore.insert_navs(
            s, stray,
            [(oldest + timedelta(days=d), 100.0 + d * 0.04) for d in range(110)],
        )
        navstore.record_source(s, stray, backfilled_at="x")

    with navstore.session() as s:
        frame = basket_build._returns(s, good + [stray], AS_OF)

    assert not frame.empty, (
        "one stray fund emptied the whole frame -- the thin column has to go "
        "before the rows do"
    )
    assert not frame.isna().any().any(), "a NaN survived into the returns frame"
    assert stray not in frame.columns, "the non-overlapping fund was kept"
    assert set(frame.columns) == set(good)


def test_a_fund_with_scattered_gaps_is_kept_but_its_missing_days_are_dropped():
    """The other half of the join, and the half the coverage filter cannot do.

    A fund that publishes on 85% of the window clears the overlap threshold and
    should be kept — it is a real fund with a real history. But the days it
    skipped still leave a NaN in those rows, and a NaN reaching the covariance
    makes every pairing with that fund undefined. `np.cov` does not complain; it
    returns NaN weights and the solver turns them into an arbitrary corner.

    Dropping the thin *columns* does not remove these, because this column is
    not thin. Only dropping the affected *rows* does.
    """
    good = basket_slots.codes_for_slot("Debt Scheme::Liquid Fund")[:4]
    gappy = basket_slots.codes_for_slot("Commodity::Gold")[0]
    window = basket_build.RETURNS_DAYS

    with navstore.session() as s:
        for i, code in enumerate(good):
            navstore.insert_navs(
                s, code,
                [(AS_OF - timedelta(days=d), 100.0 + d * 0.04 + i) for d in range(window - 5)],
            )
            navstore.record_source(s, code, backfilled_at="x")
        # Same window, same length, but skipping roughly every seventh day.
        navstore.insert_navs(
            s, gappy,
            [(AS_OF - timedelta(days=d), 100.0 + d * 0.05)
             for d in range(window - 5) if d % 7 != 3],
        )
        navstore.record_source(s, gappy, backfilled_at="x")

    with navstore.session() as s:
        frame = basket_build._returns(s, good + [gappy], AS_OF)

    assert gappy in frame.columns, (
        "a fund publishing on most of the window was dropped as thin; the "
        "overlap threshold is too strict"
    )
    assert not frame.isna().any().any(), (
        "a NaN survived into the returns frame, and np.cov will not complain "
        "about it"
    )
    assert len(frame) > 100, "dropping the gappy days should not empty the frame"
