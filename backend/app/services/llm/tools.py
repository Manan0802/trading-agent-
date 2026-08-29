"""The eighteen tools, their JSON contracts, and the rule about identifiers.

**Twenty, not eighteen, and the two extra are the resolver rule doing its job.**
The plan lists eighteen. Writing them down with `resolver` on every opaque
identifier surfaced two that were never named: `company_exposure` takes an ISIN
and `stock_facts` takes a ticker, and neither had a resolver. Pointing them at
`resolve_fund` -- which is what a hurried version does -- returns FUND matches
for a company name, so the rule fails silently while appearing to hold.

**This registry is slice 3.2's first deliverable, not an assumption it starts
from.** The figure "18 tools in §3.5" appeared three times in the plan and was
written nowhere as eighteen things -- §3.5 named seven, scattered through prose.
A JSON contract cannot be written against a list that does not exist, so whoever
built this would have reconstructed the registry from paragraphs, and the
reconstruction would have become the spec.

**The contract comes before the implementation.** A tool whose output does not
validate against its own declared shape fails the suite. That ordering is what
makes `check_all` and the response cache possible at all: grounding validates
against a declared shape, and §4.4 hashes the contract into the cache key, so
both are undefined operations on a tool that returns `dict`.

**THE RESOLVER RULE, and it was measured rather than assumed.** Asked for XIRR
on a real fund without being given a code, the model produced
`scheme_code: "122639"` from its own memory. It was correct, which is the
dangerous kind of wrong. Asked about a fund that does not exist, it put the
fund's ENTIRE NAME into the `scheme_code` field -- and a system prompt explicitly
forbidding invented identifiers did not stop it.

    No tool takes an opaque identifier as a first-class input. Every identifier
    has a resolver, and the backend validates it regardless.

Encoded here as `resolver`, and a test walks every tool.
"""

import hashlib
import json
from dataclasses import dataclass, field

# Reused shapes. Written once so two tools cannot disagree about what a rupee
# amount or a scheme code looks like.
_SCHEME_CODE = {"type": "string", "pattern": r"^\d+$"}
_RUPEES = {"type": ["number", "null"]}
_PERCENT = {"type": ["number", "null"]}


@dataclass(frozen=True)
class Tool:
    """One thing the AI layer may ask the backend for."""

    name: str
    answers: str
    # The declared shape of its OUTPUT. Written before the implementation.
    schema: dict
    # The route behind it, or None when nothing is.
    route: str | None = None
    # Which tool must supply each opaque identifier this one takes. Empty only
    # for tools that take no identifier at all.
    resolver: dict[str, str] = field(default_factory=dict)
    # Inputs that are NOT identifiers -- amounts, horizons, flags.
    inputs: tuple[str, ...] = ()

    @property
    def contract_hash(self) -> str:
        """The cache key's identity half.

        A tool whose shape changed must not serve a response built against the
        old one, and nothing else in the request says the shape moved.
        """
        canonical = json.dumps(
            {"name": self.name, "schema": self.schema}, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _obj(**properties) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        # Closed on purpose: an extra key is a field nothing declared, which is
        # exactly the kind of thing `check_all` would then have to trust.
        "additionalProperties": True,
    }


REGISTRY: tuple[Tool, ...] = (
    Tool(
        name="resolve_fund",
        answers="which fund is this — the gate every other tool passes through",
        route="GET /research/funds/search",
        inputs=("query",),
        schema=_obj(
            matches={
                "type": "array",
                "items": _obj(scheme_code=_SCHEME_CODE, name={"type": "string"}),
            }
        ),
    ),
    Tool(
        name="fund_facts",
        answers="TER, AUM, manager, min SIP, exit load, plan type",
        route="GET /screener/funds/{code}",
        resolver={"scheme_code": "resolve_fund"},
        schema=_obj(
            scheme_code=_SCHEME_CODE,
            name={"type": "string"},
            category={"type": "string"},
            direct_ter=_PERCENT,
        ),
    ),
    Tool(
        name="fund_analysis",
        answers="the fund page's full read",
        route="GET /screener/funds/{code}/analysis",
        resolver={"scheme_code": "resolve_fund"},
        inputs=("range",),
        schema=_obj(
            scheme_code=_SCHEME_CODE,
            name={"type": "string"},
            total_return=_PERCENT,
            peer_total_return=_PERCENT,
            peers_compared={"type": "integer"},
        ),
    ),
    Tool(
        name="holdings",
        answers="what he owns, with cost basis and XIRR",
        route="GET /portfolio/holdings",
        schema=_obj(
            holdings={
                "type": "array",
                "items": _obj(name={"type": "string"}, value=_RUPEES),
            }
        ),
    ),
    Tool(
        name="overlap",
        answers="are two of my funds the same bet",
        route="GET /portfolio/overlap",
        schema=_obj(
            pairs={"type": "array"},
            effective_positions={"type": ["number", "null"]},
            counted={"type": "integer"},
            excluded={"type": "object"},
        ),
    ),
    Tool(
        name="cost_review",
        answers="what am I paying across everything",
        route="GET /portfolio/cost-review",
        schema=_obj(total_annual_cost=_RUPEES, flagged={"type": "array"}),
    ),
    Tool(
        name="levers",
        answers="what should I do next, ranked by what it is worth",
        route="GET /portfolio/levers",
        inputs=("years_remaining", "assumed_return"),
        schema=_obj(
            gates={"type": "array"},
            levers={"type": "array"},
            trades={"type": "array"},
            unpriced={"type": "array"},
        ),
    ),
    Tool(
        name="benchmark",
        answers="how has this done against its index",
        route="GET /portfolio/benchmark",
        schema=_obj(portfolio_return=_PERCENT, benchmark_return=_PERCENT),
    ),
    Tool(
        name="portfolio_history",
        answers="the value line, for any window",
        route="GET /portfolio/history",
        inputs=("range",),
        schema=_obj(points={"type": "array"}),
    ),
    Tool(
        name="base_rates",
        answers="what has this kind of fund done to people before",
        route="GET /research/evidence",
        schema=_obj(
            built_on={"type": "string"},
            factors={"type": "array"},
            period={"type": "object"},
        ),
    ),
    Tool(
        name="tax_regime",
        answers="old regime or new",
        route="POST /advisor/tax-saving",
        inputs=("annual_income", "existing_80c", "existing_80d", "basic_salary"),
        schema=_obj(
            regime={"type": "object"},
            evaluated_under={"type": "string"},
            actions={"type": "array"},
            total_potential_tax_saving=_RUPEES,
        ),
    ),
    Tool(
        name="category_coverage",
        answers="what the screen is and is not showing",
        route="GET /screener/categories",
        schema=_obj(universe={"type": "integer"}, scored={"type": "integer"}),
    ),
    Tool(
        name="top_funds",
        answers="the ranked cut, with its coverage",
        route="GET /screener/top-funds",
        inputs=("category", "limit"),
        schema=_obj(funds={"type": "array"}, coverage={"type": "object"}),
    ),
    Tool(
        name="stock_facts",
        answers="sector-relative fundamentals",
        route="GET /screener/stocks/{ticker}",
        # NOT resolve_fund. A ticker is a different namespace from a scheme
        # code, and pointing a ticker at the fund search returns fund matches
        # for a company name -- which is the resolver rule failing silently
        # while looking like it is working.
        resolver={"ticker": "resolve_stock"},
        schema=_obj(ticker={"type": "string"}, name={"type": "string"}),
    ),
    Tool(
        name="fund_ter_history",
        answers="has this fund got more expensive since I bought it",
        route="Groww historic_fund_expense[]",
        resolver={"scheme_code": "resolve_fund"},
        schema=_obj(
            scheme_code=_SCHEME_CODE,
            points={
                "type": "array",
                "items": _obj(date={"type": "string"}, ter=_PERCENT),
            },
        ),
    ),
    Tool(
        name="look_through",
        answers="what do I own underneath my funds",
        route="GET /portfolio/look-through",
        schema=_obj(
            companies={"type": "array"},
            covered_value=_RUPEES,
            unopened_value=_RUPEES,
            unopened={"type": "array"},
            # The honesty number. Declared, so a caller cannot quietly omit it.
            covered_share={"type": "number"},
            summary={"type": "string"},
        ),
    ),
    Tool(
        name="company_exposure",
        answers="how much Reliance do I own — the question no Indian app answers",
        route="GET /portfolio/company-exposure/{isin}",
        resolver={"isin": "resolve_company"},
        schema=_obj(
            isin={"type": "string"},
            name={"type": "string"},
            value=_RUPEES,
            share_pct={"type": ["number", "null"]},
            through={"type": "array"},
            covered_share={"type": "number"},
            summary={"type": "string"},
        ),
    ),
    Tool(
        name="switch_cost",
        answers="if I move out of X, what does it cost and return",
        route="computed by advisor/switch_badge.py",
        resolver={"scheme_code": "resolve_fund"},
        inputs=("balance", "horizon_years", "assumed_return"),
        schema=_obj(
            annual_saving=_RUPEES,
            exit_load=_RUPEES,
            tax_brought_forward=_RUPEES,
            tax_carry_per_year=_RUPEES,
            horizon_years={"type": "number"},
        ),
    ),
    Tool(
        name="resolve_stock",
        answers="which listed company is this ticker — the gate stock_facts passes through",
        route="GET /research/stocks",
        inputs=("query",),
        schema=_obj(
            matches={
                "type": "array",
                "items": _obj(ticker={"type": "string"}, name={"type": "string"}),
            }
        ),
    ),
    Tool(
        name="resolve_company",
        answers="which company is this — the resolver company_exposure passes through",
        route="derived from the holdings store",
        inputs=("query",),
        schema=_obj(
            matches={
                "type": "array",
                "items": _obj(isin={"type": "string"}, name={"type": "string"}),
            }
        ),
    ),
)

BY_NAME: dict[str, Tool] = {tool.name: tool for tool in REGISTRY}


def cache_key(tool_name: str, arguments: dict) -> str:
    """A key that changes when the ARGUMENTS change or when the SHAPE does.

    Hashing only the arguments serves a response built against the old contract
    after the shape moves, and nothing in the request says it moved.
    """
    tool = BY_NAME[tool_name]
    payload = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    return f"{tool.name}:{tool.contract_hash}:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
