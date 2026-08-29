"""The tool registry, its contracts, and the identifier rule that was measured.

§3.2's first deliverable, and the plan is explicit about why it has to exist
before anything else: *"the JSON shape is written BEFORE any of them"*, and a
JSON contract cannot be written against a list that does not exist. The figure
"18 tools in §3.5" appeared three times in the plan and was written nowhere as
eighteen things — §3.5 named seven, scattered through prose bullets.
"""

import json

import pytest
from jsonschema import Draft7Validator, ValidationError, validate

from app.services.llm.tools import BY_NAME, REGISTRY, Tool, cache_key


def test_the_registry_is_enumerated_rather_than_reconstructed_from_prose():
    """Twenty, not eighteen — and the two extra are the resolver rule working.

    `company_exposure` takes an ISIN and `stock_facts` takes a ticker, and
    neither had a resolver in the plan's list. Pointing them at `resolve_fund`
    returns FUND matches for a company name, so the rule would fail silently
    while appearing to hold.
    """
    assert len(REGISTRY) == 20
    assert len(BY_NAME) == 20, "two tools share a name"
    for planned in (
        "resolve_fund", "fund_facts", "fund_analysis", "holdings", "overlap",
        "cost_review", "levers", "benchmark", "portfolio_history", "base_rates",
        "tax_regime", "category_coverage", "top_funds", "stock_facts",
        "fund_ter_history", "look_through", "company_exposure", "switch_cost",
    ):
        assert planned in BY_NAME, f"{planned} is in the plan and not the registry"
    assert {"resolve_stock", "resolve_company"} <= set(BY_NAME)


class TestEveryToolDeclaresAShape:
    @pytest.mark.parametrize("tool", REGISTRY, ids=lambda t: t.name)
    def test_the_schema_is_valid_json_schema(self, tool: Tool):
        """A malformed schema validates nothing and raises nowhere."""
        Draft7Validator.check_schema(tool.schema)

    @pytest.mark.parametrize("tool", REGISTRY, ids=lambda t: t.name)
    def test_it_declares_what_it_answers_in_words(self, tool: Tool):
        assert len(tool.answers) > 10, f"{tool.name} says nothing about itself"

    @pytest.mark.parametrize("tool", REGISTRY, ids=lambda t: t.name)
    def test_every_declared_field_is_required(self, tool: Tool):
        """An optional field is one a caller may quietly stop sending, and
        `check_all` would then have nothing to validate against."""
        assert set(tool.schema["required"]) == set(tool.schema["properties"])


class TestTheResolverRule:
    """Measured, not assumed.

    Asked for XIRR on a real fund without a code, the model produced
    `scheme_code: "122639"` from memory. It was CORRECT, which is the dangerous
    kind of wrong. Asked about a fund that does not exist, it put the fund's
    entire name in the scheme_code field — and a system prompt forbidding
    invented identifiers did not stop it.
    """

    @pytest.mark.parametrize("tool", REGISTRY, ids=lambda t: t.name)
    def test_every_resolver_named_actually_exists(self, tool: Tool):
        for field, resolver in tool.resolver.items():
            assert resolver in BY_NAME, (
                f"{tool.name}.{field} resolves through {resolver!r}, which is "
                "not a tool — so the identifier arrives unvalidated"
            )

    def test_an_identifier_never_resolves_through_the_wrong_namespace(self):
        """A ticker pointed at the fund search returns fund matches for a
        company name: the rule failing while appearing to hold."""
        assert BY_NAME["stock_facts"].resolver == {"ticker": "resolve_stock"}
        assert BY_NAME["company_exposure"].resolver == {"isin": "resolve_company"}

    @pytest.mark.parametrize("tool", REGISTRY, ids=lambda t: t.name)
    def test_no_tool_takes_a_bare_identifier_as_a_plain_input(self, tool: Tool):
        """`inputs` is for amounts, horizons and flags. An identifier there is
        one the model may invent."""
        for name in tool.inputs:
            assert not name.endswith(("_code", "isin", "ticker")), (
                f"{tool.name} takes {name!r} as a plain input; it needs a resolver"
            )

    def test_the_resolvers_themselves_take_a_query_not_a_code(self):
        for name in ("resolve_fund", "resolve_stock", "resolve_company"):
            assert BY_NAME[name].inputs == ("query",)
            assert BY_NAME[name].resolver == {}, "a resolver that needs a resolver"


class TestAToolThatBreaksItsContractFailsTheSuite:
    def test_a_conforming_payload_validates(self):
        tool = BY_NAME["look_through"]
        validate(
            {
                "companies": [],
                "covered_value": 0.0,
                "unopened_value": 0.0,
                "unopened": [],
                "covered_share": 0.0,
                "summary": "nothing yet",
            },
            tool.schema,
        )

    def test_a_payload_missing_the_honesty_number_is_rejected(self):
        """`covered_share` is what stops a partial look-through reading as a
        complete one, so dropping it must fail loudly."""
        tool = BY_NAME["look_through"]
        with pytest.raises(ValidationError):
            validate(
                {
                    "companies": [],
                    "covered_value": 0.0,
                    "unopened_value": 0.0,
                    "unopened": [],
                    "summary": "nothing yet",
                },
                tool.schema,
            )

    def test_a_scheme_code_that_is_not_a_code_is_rejected(self):
        """The exact failure the resolver rule exists for: the model put a
        fund's whole NAME into the scheme_code field."""
        tool = BY_NAME["fund_facts"]
        with pytest.raises(ValidationError):
            validate(
                {
                    "scheme_code": "Parag Parikh Flexi Cap Fund",
                    "name": "Parag Parikh Flexi Cap Fund",
                    "category": "Equity",
                    "direct_ter": 0.63,
                },
                tool.schema,
            )

    def test_the_live_look_through_payload_matches_its_declared_shape(self):
        """The contract against the real engine, not against a fixture."""
        from app.services.portfolio.look_through import look_through

        result = look_through([])
        payload = {
            "companies": [],
            "covered_value": result.covered_value,
            "unopened_value": result.unopened_value,
            "unopened": list(result.unopened),
            "covered_share": result.covered_share,
            "summary": "",
        }
        validate(payload, BY_NAME["look_through"].schema)


class TestTheCacheKeyHashesTheContract:
    def test_the_same_arguments_give_the_same_key(self):
        assert cache_key("fund_facts", {"scheme_code": "122639"}) == cache_key(
            "fund_facts", {"scheme_code": "122639"}
        )

    def test_different_arguments_give_different_keys(self):
        assert cache_key("fund_facts", {"scheme_code": "122639"}) != cache_key(
            "fund_facts", {"scheme_code": "118955"}
        )

    def test_a_changed_shape_changes_the_key(self):
        """Hashing only the arguments serves a response built against the old
        contract after the shape moves, and nothing in the request says so."""
        tool = BY_NAME["fund_facts"]
        before = tool.contract_hash
        moved = Tool(
            name=tool.name,
            answers=tool.answers,
            schema={**tool.schema, "properties": {**tool.schema["properties"], "aum": {"type": "number"}}},
        )
        assert moved.contract_hash != before

    def test_the_key_names_the_tool_so_two_cannot_collide(self):
        key = cache_key("fund_facts", {"scheme_code": "122639"})
        assert key.startswith("fund_facts:")


def test_the_registry_is_serialisable_so_it_can_be_sent_to_a_model():
    """A registry that cannot be handed to the model is a registry the model
    cannot route against."""
    payload = [
        {"name": t.name, "answers": t.answers, "schema": t.schema, "inputs": list(t.inputs)}
        for t in REGISTRY
    ]
    assert json.loads(json.dumps(payload))
