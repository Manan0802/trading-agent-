"""How much of a portfolio is actually in equity.

Not what a risk profile *recommends* — `asset_allocator.get_allocation` already
answers that. This is what the person is holding right now, which is the input
the equity-share trade needs and the one thing about a portfolio that decides
more of the outcome than every fund choice in it put together.

## Why it refuses rather than guesses

A holding whose category we cannot resolve is returned as unclassified, and the
share is withheld entirely once too much of the money is unclassified. Splitting
the difference — assuming the unknown part matches the known part — would
produce a number that looks like a measurement and is a guess, and the trade
built on it tells someone to move real money.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.advisor import fund_catalogue

# Above this share of unclassified money, no answer is given. A tenth is enough
# slack for one small odd holding without letting the figure become fiction.
MAX_UNCLASSIFIED = 0.10

# AMFI scheme types that are equity risk in substance. `Solution Oriented`
# covers retirement and children's funds, which are equity-heavy by mandate.
_EQUITY_SCHEME_TYPES = ("Equity Scheme", "Solution Oriented Scheme")

# Sub-categories inside other scheme types that still carry equity risk. An
# aggressive hybrid is 65-80% equity by SEBI definition, and an index fund
# tracking the Nifty is equity however AMFI files it.
_EQUITY_SUB_CATEGORIES = (
    "aggressive hybrid",
    "equity savings",
    "balanced hybrid",
    "index fund",
    "arbitrage",
)

# Gold, silver and overseas funds are not Indian equity but they are not the
# safe half either. Counted as equity risk, because the question this feeds is
# "how much of your money can fall a long way", not "which asset class is it".
_RISK_SUB_CATEGORIES = ("fof overseas", "fof domestic")


@dataclass(frozen=True)
class Mix:
    equity_value: float
    other_value: float
    unclassified_value: float
    unclassified_names: tuple[str, ...]

    @property
    def total(self) -> float:
        return self.equity_value + self.other_value + self.unclassified_value

    @property
    def unclassified_share(self) -> float:
        return self.unclassified_value / self.total if self.total > 0 else 0.0

    @property
    def equity_share(self) -> float | None:
        """0 to 1, or None when too much of the money could not be classified."""
        if self.total <= 0:
            return None
        if self.unclassified_share > MAX_UNCLASSIFIED:
            return None
        classified = self.equity_value + self.other_value
        if classified <= 0:
            return None
        return round(self.equity_value / classified, 4)


def _is_equity(asset_type: str, category: str | None) -> bool | None:
    """True for equity risk, False for the safe half, None when unknown."""
    if asset_type == "STOCK":
        return True
    if not category:
        return None
    lowered = category.lower()
    if any(word in lowered for word in _EQUITY_SUB_CATEGORIES):
        return True
    if any(word in lowered for word in _RISK_SUB_CATEGORIES):
        return True
    top = category.split(" - ", 1)[0].strip()
    if top in _EQUITY_SCHEME_TYPES:
        return True
    if top in ("Debt Scheme", "Hybrid Scheme", "Other Scheme"):
        return False
    return None


def _catalogue_category(identifier: str) -> str | None:
    for fund in fund_catalogue.all_funds():
        if fund.code == identifier:
            return fund.category
    return None


def classify(holdings) -> Mix:
    """Split priced holdings into equity risk, the safe half, and unknown.

    Each holding needs `asset_type`, `identifier`, `name` and a current value.
    The stored `category` is free text a user typed at creation ("Flexi Cap"),
    so the catalogue is consulted first and the stored string is only a
    fallback.
    """
    equity = other = unknown = 0.0
    unknown_names: list[str] = []
    for holding in holdings:
        value = float(getattr(holding, "current_value", 0) or 0)
        if value <= 0:
            continue
        asset_type = getattr(holding, "asset_type", "MF")
        category = (
            _catalogue_category(getattr(holding, "identifier", ""))
            if asset_type == "MF"
            else None
        ) or getattr(holding, "category", None)
        verdict = _is_equity(asset_type, category)
        if verdict is True:
            equity += value
        elif verdict is False:
            other += value
        else:
            unknown += value
            unknown_names.append(getattr(holding, "name", "unnamed holding"))
    return Mix(equity, other, unknown, tuple(unknown_names))


# ---------------------------------------------------------------------------


def monthly_contribution(transactions, as_of, months: int = 12) -> float:
    """What this person has actually been putting in each month.

    Derived rather than asked for. Every caller of the levers engine had to
    supply `monthly_sip` and the decision screen passed a hardcoded zero, which
    silently removed the single largest lever on it — the one worth ₹25 lakh to
    the reference user.

    Buys only, over the last `months` months, divided by that many months. Sells
    are not netted off: the question is "what are you adding", and someone who
    bought ₹20,000 and sold ₹20,000 of something else is still adding ₹20,000 a
    month. Averaging over the window rather than taking the last month means a
    missed instalment or a lump sum does not swing it.
    """
    cutoff = date(as_of.year - (months // 12), as_of.month, 1) if months >= 12 else as_of
    total = 0.0
    for txn in transactions:
        if getattr(txn, "txn_type", "") != "BUY":
            continue
        when = getattr(txn, "txn_date", None)
        if when is None or when < cutoff or when > as_of:
            continue
        units = float(getattr(txn, "units", 0) or 0)
        price = float(getattr(txn, "price", 0) or 0)
        total += units * price
    return round(total / months, 2) if total > 0 else 0.0
