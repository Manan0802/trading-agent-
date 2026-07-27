"""Turning a fund's NAV history into the evidence the scorer ranks on.

One place where a NAV series becomes rolling windows, volatility, drawdown and
cost, so the scorer never touches raw prices and the same evidence can be
rebuilt as of any past date for an honest backtest.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.services.advisor.fund_score import FundEvidence, WindowEvidence
from app.services.advisor.rolling_returns import (
    neutralise_nav_artefacts,
    rolling_return_stats,
)
from app.services.marketdata.mutual_fund import NavPoint

_EXPENSE_TABLE = (
    Path(__file__).resolve().parent.parent.parent / "data" / "expense_ratios.json"
)

# The windows the scorer asks for. 3y is required; 1y supports it.
WINDOWS = {"1y": 365, "3y": 1095, "5y": 1825}

_TRADING_DAYS = 252


@lru_cache(maxsize=1)
def expense_ratios() -> dict[str, dict]:
    """Scheme code -> {direct_ter, regular_ter, as_of}, as percentages."""
    try:
        return json.loads(_EXPENSE_TABLE.read_text())
    except (OSError, ValueError):
        # The table is built by a script and may not exist yet. Cost then drops
        # out of the score for every fund equally, which is honest.
        return {}


@dataclass(frozen=True)
class RiskShape:
    volatility: float | None
    max_drawdown: float | None


def _risk(navs: list[NavPoint]) -> RiskShape:
    if len(navs) < _TRADING_DAYS // 4:
        return RiskShape(None, None)

    values = np.array([p.nav for p in navs], dtype=float)
    daily = values[1:] / values[:-1] - 1.0
    volatility = float(daily.std() * np.sqrt(_TRADING_DAYS)) if daily.size else None

    peak = np.maximum.accumulate(values)
    drawdown = float((values / peak - 1.0).min())

    return RiskShape(volatility=volatility, max_drawdown=drawdown)


def build_evidence(
    scheme_code: str,
    scheme_name: str,
    category: str,
    navs: list[NavPoint],
) -> FundEvidence | None:
    """Everything the scorer needs about one fund, or None if it has no NAV."""
    if not navs:
        return None

    clean, _ = neutralise_nav_artefacts(navs)

    windows: dict[str, WindowEvidence] = {}
    for label, days in WINDOWS.items():
        stats = rolling_return_stats(clean, days)
        if stats is None:
            continue
        windows[label] = WindowEvidence(
            mean=stats.mean,
            worst=stats.worst,
            share_positive=stats.share_positive,
            count=stats.count,
        )

    shape = _risk(clean)
    span_years = (clean[-1].date - clean[0].date).days / 365.25
    fees = expense_ratios().get(scheme_code) or {}

    def _as_fraction(value) -> float | None:
        # Stored as a percentage by the build script; the scorer works in
        # fractions so a 0.75% TER and a 0.0075 return are the same units.
        return None if value in (None, "") else float(value) / 100.0

    return FundEvidence(
        scheme_code=scheme_code,
        scheme_name=scheme_name,
        category=category,
        windows=windows,
        volatility=shape.volatility,
        max_drawdown=shape.max_drawdown,
        direct_ter=_as_fraction(fees.get("direct_ter")),
        regular_ter=_as_fraction(fees.get("regular_ter")),
        history_years=span_years,
    )


def commission_drag(evidence: FundEvidence) -> float | None:
    """Annual cost of holding the regular plan instead of the direct one.

    Published by AMFI for both plans of the same scheme, so this is a measured
    fee difference, not an estimate.
    """
    if evidence.direct_ter is None or evidence.regular_ter is None:
        return None
    gap = evidence.regular_ter - evidence.direct_ter
    return gap if gap > 0 else None
