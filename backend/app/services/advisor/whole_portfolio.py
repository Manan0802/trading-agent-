"""Allocation advice for the whole balance sheet, not just the money we can see.

A salaried Indian's largest fixed-income holding is usually EPF, and it is
invisible to an app that only tracks mutual funds. Someone with ₹8 lakh in EPF
and ₹4 lakh in equity has a 67% debt portfolio; telling them to route 25% of
every new rupee into a debt fund keeps them permanently under-weight equity,
and the EPF balance grows every month, so the gap widens rather than closes.

So the target mix is applied to everything the user owns, and the monthly
investment is then split to close the gap. Nothing here ever suggests selling:
EPF and PPF cannot be redeemed on demand, so an over-weight class simply gets
nothing until the rest catches up.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

AssetClass = Literal["equity", "debt", "gold"]

# Matched with word boundaries: a bare "fd" substring would otherwise fire on
# any word containing those letters.
_CLASSIFIERS: list[tuple[str, AssetClass]] = [
    (r"\bepf\b|\bemployees?\s+provident\b", "debt"),
    (r"\bppf\b|\bpublic\s+provident\b", "debt"),
    (r"\bsukanya\b", "debt"),
    (r"\bnsc\b|\bnational\s+savings\b", "debt"),
    (r"\bkisan\s+vikas\b|\bkvp\b", "debt"),
    (r"\bfixed\s+deposit\b|\brecurring\s+deposit\b|\bfd\b|\brd\b", "debt"),
    # Gold is tested before bonds so a Sovereign Gold Bond lands in gold, which
    # is what it actually gives you exposure to.
    (r"\bgold\b|\bsgb\b", "gold"),
    (r"\bbond\b|\bdebenture\b", "debt"),
    (r"\besop\b|\brsu\b|\bshares?\b|\bstock\b|\bequity\b", "equity"),
]

# Above this share of the portfolio a single holding is worth naming out loud.
_CONCENTRATION_THRESHOLD = 0.30
# Below this gap an over-weight class is not worth commenting on.
_OVERWEIGHT_GAP_PP = 10.0


@dataclass(frozen=True)
class ExternalAsset:
    name: str
    amount: float
    asset_class: AssetClass


@dataclass(frozen=True)
class NewMoneyPlan:
    allocation: dict[str, float]
    current_mix: dict[str, float]
    target_mix: dict[str, float]
    insights: list[str] = field(default_factory=list)


def classify_asset(name: str) -> AssetClass | None:
    """Best-effort mapping from an instrument name to an asset class.

    Returns None rather than defaulting, because silently filing an unknown
    instrument as equity or debt would distort the whole plan.
    """
    text = (name or "").lower()
    for pattern, asset_class in _CLASSIFIERS:
        if re.search(pattern, text):
            return asset_class
    return None


def _current_mix(existing: dict[str, float]) -> dict[str, float]:
    total = sum(existing.values())
    if total <= 0:
        return {c: 0.0 for c in ("equity", "debt", "gold")}
    return {
        c: round(existing.get(c, 0.0) / total * 100, 4)
        for c in ("equity", "debt", "gold")
    }


def _build_insights(
    existing: dict[str, float],
    current: dict[str, float],
    target: dict[str, float],
    allocation: dict[str, float],
    assets: list[ExternalAsset],
) -> list[str]:
    insights: list[str] = []
    total = sum(existing.values())

    for asset_class in ("equity", "debt", "gold"):
        gap = current[asset_class] - target.get(asset_class, 0)
        if gap < _OVERWEIGHT_GAP_PP or allocation.get(asset_class, 0) > 0:
            continue
        names = [a.name for a in assets if a.asset_class == asset_class]
        joined = (
            " and ".join([", ".join(names[:-1]), names[-1]])
            if len(names) > 1
            else "".join(names)
        )
        holdings = f", mostly {joined}" if joined else ""
        insights.append(
            f"Your {asset_class} is already {current[asset_class]:.0f}% of "
            f"everything you own{holdings}, against a {target[asset_class]:.0f}% "
            f"target. New money skips {asset_class} entirely until the rest "
            "catches up. Nothing needs to be sold."
        )

    for asset in assets:
        # Only equity: single-company risk is the concern here, and a large EPF
        # or PPF balance is a diversified government-backed scheme, not a
        # concentrated bet. Its size is already covered by the over-weight note.
        if (
            asset.asset_class == "equity"
            and total > 0
            and asset.amount / total > _CONCENTRATION_THRESHOLD
        ):
            insights.append(
                f"{asset.name} alone is {asset.amount / total:.0%} of your "
                "portfolio. If this is employer stock, your salary and your "
                "savings ride on the same single company, the two fail "
                "together, which is exactly when you can least afford it."
            )

    return insights


def plan_new_money(
    target: dict[str, float],
    existing: dict[str, float],
    monthly: float,
    assets: list[ExternalAsset] | None = None,
) -> NewMoneyPlan:
    """Split `monthly` so the whole portfolio moves toward `target`.

    `existing` is rupee balances per asset class, including anything held
    outside the app. `assets` is the optional itemised breakdown, used only to
    name holdings in the insights.
    """
    classes = ("equity", "debt", "gold")
    existing = {c: float(existing.get(c, 0.0)) for c in classes}
    current = _current_mix(existing)

    if monthly <= 0:
        return NewMoneyPlan(
            allocation={c: 0.0 for c in classes},
            current_mix=current,
            target_mix=dict(target),
            insights=[],
        )

    total_after = sum(existing.values()) + monthly
    # Shortfall against where each class should sit once this month is invested.
    # Clipped at zero because over-weight classes cannot be sold down here, so
    # the shortfalls sum to more than the month and are scaled back to fit.
    need = {
        c: max(0.0, target.get(c, 0) / 100 * total_after - existing[c]) for c in classes
    }
    total_need = sum(need.values())

    allocation = {c: round(need[c] * monthly / total_need) for c in classes}
    # Rounding must not lose or invent rupees; the residual lands on the
    # largest slice, where it is proportionally invisible.
    residual = monthly - sum(allocation.values())
    if residual:
        largest = max(allocation, key=lambda c: allocation[c])
        allocation[largest] += residual

    return NewMoneyPlan(
        allocation=allocation,
        current_mix=current,
        target_mix=dict(target),
        insights=_build_insights(
            existing, current, target, allocation, assets or []
        ),
    )
