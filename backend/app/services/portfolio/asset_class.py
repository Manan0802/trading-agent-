"""Which slice of the pie each holding belongs in: equity, overseas, debt, gold.

Not `advisor/asset_mix.py`. That module answers "how much of your money can
fall a long way", and so deliberately counts gold and overseas funds as equity
risk. This answers "what is it", for an allocation chart, where gold that is
drawn as equity is simply the wrong colour.

The official AMFI category is the input, never the text somebody typed when
they added the holding. The traps are all in how AMFI files things rather than
in the funds:

- An index fund is "Other Scheme - Index Funds" whether it tracks the Nifty or
  state government bonds.
- A US fund can be filed as an Indian "Equity Scheme - Sectoral/ Thematic".
- A gold fund of funds is "Other Scheme - FoF Domestic".

So inside those buckets the scheme's own name decides. Outside them the scheme
type is trusted, because the name of a flexi cap fund says nothing its category
does not.

It refuses rather than guesses. A holding it cannot read goes in its own
"Unclassified" slice: filing it as equity would move real money from one side of
the chart to the other and look exactly like a measurement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from app.services.advisor import fund_catalogue
from app.services.advisor.plan_pairs import direct_twin

AssetClass = Literal["equity", "international", "debt", "gold", "hybrid", "other"]


@dataclass(frozen=True)
class Placement:
    asset_class: AssetClass
    # The label inside that class: "Flexi Cap", "Corporate Bond", "Stocks".
    category: str


UNCLASSIFIED = Placement("other", "Unclassified")

_OVERSEAS = re.compile(
    r"nasdaq|s&p\s*500|\bus\b|u\.s\.|\bglobal\b|international|\bworld\b|overseas"
    r"|emerging\s+market|developed\s+market|\bchina\b|\bjapan\b|taiwan|hang\s+seng"
    r"|\beurope|\bfang",
    re.I,
)
_GOLD = re.compile(r"\bgold\b", re.I)
_SILVER = re.compile(r"\bsilver\b", re.I)
# Government and corporate bond trackers that AMFI files beside the equity ones.
_DEBT_NAME = re.compile(
    r"\bgilt\b|g-?sec|\bsdl\b|\bbond\b|\bpsu\b|t-?bill|treasury|crisil\s+ibx"
    r"|\bdebt\b|target\s+maturity|\bliquid\b|money\s+market|overnight",
    re.I,
)

_EQUITY_TYPES = ("Equity Scheme", "Solution Oriented Scheme")
_DEBT_TYPES = ("Debt Scheme", "Income/Debt Oriented Schemes")
_HYBRID_TYPES = ("Hybrid Scheme", "Life Cycle Funds")
# Where the scheme type does not say what the fund holds, so the name must.
_AMBIGUOUS_TYPES = ("Other Scheme", "Exchange Traded Funds (ETFs)")

# AMFI's longest sub-category, shortened for a chart label.
_LABELS = {
    "Dynamic Asset Allocation or Balanced Advantage": "Balanced Advantage",
    "Sectoral/ Thematic": "Sectoral / Thematic",
    "Index Funds": "Index Fund",
}


def _label(sub: str) -> str:
    sub = sub.strip()
    if sub in _LABELS:
        return _LABELS[sub]
    return re.sub(r"\s+Funds?$", "", sub).strip() or sub


def from_category(asset_type: str, name: str, amfi_category: str | None) -> Placement:
    """Place a holding from its official AMFI category and its scheme name."""
    if asset_type == "STOCK":
        return Placement("equity", "Stocks")
    if not amfi_category or " - " not in amfi_category:
        return UNCLASSIFIED

    top, sub = (part.strip() for part in amfi_category.split(" - ", 1))
    sub_lower = sub.lower()

    # Precious metals first: a Gold ETF and a gold FoF are gold wherever filed.
    if _SILVER.search(name) or "silver" in sub_lower:
        return Placement("gold", "Silver")
    if _GOLD.search(name) or "gold" in sub_lower:
        return Placement("gold", "Gold")

    # Overseas before Indian equity: a US fund filed as "Sectoral/ Thematic" is
    # still US stocks.
    if "overseas" in sub_lower or (
        top in (*_EQUITY_TYPES, *_AMBIGUOUS_TYPES) and _OVERSEAS.search(name)
    ):
        return Placement("international", "International")

    if top in _AMBIGUOUS_TYPES:
        if "debt" in sub_lower or _DEBT_NAME.search(name):
            return Placement("debt", "Debt index")
        if "index" in sub_lower or "etf" in sub_lower:
            return Placement("equity", "Index Fund")
        # A domestic fund of funds that is not gold: could hold anything.
        return Placement("other", "Fund of funds")

    if top in _EQUITY_TYPES:
        return Placement("equity", _label(sub))
    if top in _DEBT_TYPES:
        return Placement("debt", _label(sub))
    if top in _HYBRID_TYPES:
        return Placement("hybrid", _label(sub))
    return UNCLASSIFIED


@lru_cache(maxsize=1)
def _categories() -> dict[str, str]:
    return {fund.code: fund.category for fund in fund_catalogue.all_funds()}


def classify(asset_type: str, identifier: str, name: str) -> Placement:
    """Place one holding, reading its AMFI category from the catalogue.

    The catalogue holds direct plans only, so a regular plan is read through its
    direct twin -- the same portfolio, and therefore the same category. The
    category the user typed is deliberately not an input: "Flexi Cap" typed
    against a debt fund's code would otherwise draw that fund as equity.
    """
    if asset_type == "STOCK":
        return Placement("equity", "Stocks")
    code = str(identifier)
    amfi = _categories().get(code)
    if amfi is None:
        twin = direct_twin(code)
        amfi = _categories().get(twin) if twin else None
    return from_category(asset_type, name, amfi)
