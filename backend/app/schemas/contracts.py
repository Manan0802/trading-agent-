"""Declared shapes for the two endpoints that answer correctly and describe nothing.

§3.2's first task, and a prerequisite of it rather than work beside it. Of 50
routes, 12 declare no `response_model`; ten of those are DELETEs, auth redirects
and internal calculators. Two are **tools the AI layer is specified to call**:

    POST /advisor/tax-saving   the regime lever, the largest rupee figure in the app
    GET  /research/evidence    thirty-two years of Indian factor returns, and
                               what §1.4's base rates rest on

A tool with no declared shape cannot be grounded and cannot be cached. §3.2
says the JSON shape is what `check_all` validates against, and §4.4 hashes
`tool_json` into the cache key -- so both of those are undefined operations on
an endpoint whose response is `dict`. The models are written BEFORE any tool
wraps them, which is the order §3.2's acceptance actually demands.

They describe what the engines already return. Nothing here changes a number;
if a field below disagrees with the engine, the model is wrong and the test
that serialises a real response says so.
"""

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------- tax saving


class RegimeVerdictOut(BaseModel):
    """Which regime is cheaper for this person, and by how much."""

    recommended: str
    new_regime_tax: float
    old_regime_tax: float
    saving: float
    # Deductions at which the old regime would catch up. The number that turns
    # "the new regime is cheaper" into something a person can act on, because it
    # says how far away the other answer is.
    #
    # None is a REAL answer, not a missing one: below the new regime's threshold
    # the tax is zero, and no amount of deductions can make the old regime
    # cheaper than nothing. Declaring this required — which a model written from
    # one example does — makes the endpoint 500 for exactly the people who owe
    # no tax.
    breakeven_deductions: float | None
    rationale: str

    model_config = ConfigDict(from_attributes=True)


class TaxActionOut(BaseModel):
    """One deduction, and whether it is available under the regime being used.

    `applicable` is not decoration. Under the new regime most of these are worth
    nothing, and an action list that showed only the usable ones would leave a
    reader wondering what happened to 80C. It is shown, at zero, with the reason.
    """

    name: str
    section: str
    # None, not 0. The employer-NPS action is a percentage of BASIC salary, and
    # somebody who did not tell us their basic has no amount here — which is a
    # different fact from "you can claim nothing", and it is the one the note
    # explains. Declaring this required 500'd the endpoint for every caller who
    # omitted `basic_salary`, which is the default on the app's own form.
    amount: float | None
    tax_saved: float
    applicable: bool
    note: str

    model_config = ConfigDict(from_attributes=True)


class TaxSavingOut(BaseModel):
    regime: RegimeVerdictOut
    # The regime the actions below are priced under -- always the recommended
    # one. Pricing 80C against the old regime while recommending the new one
    # produces a saving nobody can collect.
    evaluated_under: str
    actions: list[TaxActionOut]
    total_potential_tax_saving: float

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------- factor evidence


class EvidenceSourceOut(BaseModel):
    name: str
    url: str
    note: str

    model_config = ConfigDict(from_attributes=True)


class EvidencePeriodOut(BaseModel):
    # `from` is a Python keyword, so the field is `from_` and the alias carries
    # the real name. FastAPI serialises response models by alias, so the JSON
    # the frontend already reads is unchanged — which is the point: declaring a
    # shape must not quietly rename a field the screen is keyed on.
    from_: str = Field(alias="from")
    to: str
    months: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FactorEpisodeOut(BaseModel):
    """One factor's behaviour inside a named regime — a crash, a rebound.

    The episodes are the honest half. Momentum's full-period t-stat is 3.11;
    across the 2009 rebound the same factor returned -53.5% annualised. A figure
    without its episodes reads as a promise.
    """

    label: str
    annual_return: float
    t_stat: float
    months: int
    significant: bool

    model_config = ConfigDict(from_attributes=True)


class FactorOut(BaseModel):
    code: str
    name: str
    # Written for someone who has never met the word "factor".
    plain: str
    annual_return: float
    t_stat: float
    months: int
    # At the 5% level. Carried as a field rather than recomputed on the screen,
    # so the threshold lives in one place.
    significant: bool
    episodes: list[FactorEpisodeOut] = []

    model_config = ConfigDict(from_attributes=True)


class FactorEvidenceOut(BaseModel):
    """What has been shown to work over 32 years, and what has not.

    `built_on` travels with it so a stale file cannot pass for a fresh one.
    """

    built_on: str
    source: EvidenceSourceOut
    period: EvidencePeriodOut
    factors: list[FactorOut]
    momentum_curve: list[dict]

    model_config = ConfigDict(from_attributes=True)
