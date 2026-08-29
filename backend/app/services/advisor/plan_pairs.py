"""Which direct plan is the same fund as this regular plan.

The badge §11.7 calls the largest single number this app will ever show is
`Regular plan — Direct saves ₹X/yr`, and it could not fire for anyone. The
catalogue holds **zero** regular plans, deliberately: it is the recommendation
universe, and recommending a regular plan is recommending a worse version of
the same portfolio. So a person who holds one types a scheme code the app has
never heard of, and the one number that would have told them what the
distributor commission costs never appears.

The numbers were never the problem. `expense_ratios.json` carries both plans'
TERs for 1,385 funds, because AMFI files both on one row. What was missing was
the edge from what the user types to what the table is keyed on.

It is built from rows `build_fund_catalogue.py` already fetches and throws
away. mfapi's `/mf` returns every scheme, both plans as separate rows; the
catalogue filters to direct+growth and discards the rest. Keeping the regular
side and joining on the same normalised name `build_expense_ratios.py` already
uses pairs **3,762 of 4,136 regular plans, 91%**.

Not an `NSDLSchemeCode` stem. AMFI's TER row carries both plans' figures inside
one row, so there is no separate regular code there to join from -- a first
version of this proposed exactly that and was wrong.
"""

import json
from functools import lru_cache
from pathlib import Path

_PAIRS = Path(__file__).resolve().parent.parent.parent / "data" / "plan_pairs.json"


@lru_cache(maxsize=1)
def _regular_to_direct() -> dict[str, str]:
    try:
        return json.loads(_PAIRS.read_text())
    except (OSError, ValueError):
        # Built by a script and may not exist yet. Every caller then behaves as
        # it did before this file: a regular code simply does not resolve, and
        # the badge does not fire. Silent absence, never a wrong pairing.
        return {}


@lru_cache(maxsize=1)
def _direct_to_regular() -> dict[str, str]:
    return {direct: regular for regular, direct in _regular_to_direct().items()}


def direct_twin(scheme_code: str) -> str | None:
    """The direct plan of the same fund, or None if this is not a regular plan."""
    return _regular_to_direct().get(str(scheme_code))


def regular_twin(scheme_code: str) -> str | None:
    """The regular plan of the same fund, or None if it has none we know of.

    Needed the other way round to price what a holder of the DIRECT plan is
    already saving, which is the same sentence read from the other side.
    """
    return _direct_to_regular().get(str(scheme_code))


def is_regular_plan(scheme_code: str) -> bool:
    return str(scheme_code) in _regular_to_direct()


def pair_count() -> int:
    return len(_regular_to_direct())
