"""The grounding check, tested against what the model actually wrote.

Every string in `test_the_date_false_positive_that_this_module_exists_for` is
verbatim output from gemini-3.5-flash-lite on 2026-08-27, generated from the
payload in `SOURCE`. The naive regex version of this check rejected all four,
and not one of them contained an invented number.

The adversarial cases below are the three ways a reviewer would try to slip a
fabricated figure past a grounding check, and each has its own test.
"""

import pytest

from app.services.llm.grounding import (
    Claim,
    check,
    check_all,
    check_claims,
    check_text_claims,
)

SOURCE = {
    "fund": "Parag Parikh Flexi Cap Direct",
    "ter_pct": 0.69,
    "category_median_ter_pct": 1.02,
    "category": "Flexi Cap",
    "peer_count": 44,
    "as_of": "2026-08-27",
}


# --------------------------------------------------------------------------
# The false positives -- real model output that must PASS
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        # Date written the other way round, with a trailing full stop.
        "Parag Parikh Flexi Cap Direct has a Total Expense Ratio of 0.69% as of "
        "27-08-2026, which is lower than the Flexi Cap category median of 1.02% "
        "across 44 peers.",
        # Date written the same way round as the source.
        "The Parag Parikh Flexi Cap Direct fund has a Total Expense Ratio of "
        "0.69%, which is lower than the category median of 1.02% among 44 peer "
        "funds as of 2026-08-27.",
        # "percent" spelled out rather than %.
        "The Total Expense Ratio (TER) of the Parag Parikh Flexi Cap Direct "
        "mutual fund is 0.69 percent, while the category median TER is 1.02 "
        "percent across 44 peers as of 2026-08-27.",
        "Parag Parikh Flexi Cap Direct has a TER percentage of 0.69 compared to "
        "the category median TER percentage of 1.02 out of 44 peers in the Flexi "
        "Cap category as of 2026-08-27.",
    ],
)
def test_the_date_false_positive_that_this_module_exists_for(sentence):
    """A guard that cries wolf on correct output gets switched off.

    All four of these are real, correct, fully-grounded sentences. The naive
    `re.findall(r'-?\\d[\\d,]*\\.?\\d*')` version rejected every one of them,
    because `27-08-2026` tokenises to `-2026` and the source has `2026`.
    """
    g = check(sentence, SOURCE)
    assert g.ok, g.why()


def test_indian_grouping_matches_the_ungrouped_figure():
    """`1,54,083` and `154083` are the same number, and both get written.

    `Intl.NumberFormat('en-IN')` produces the grouped form on screen while the
    payload carries the raw integer, so a strict string compare would reject
    every rupee figure the app renders.
    """
    assert check("You have ₹1,54,083 invested.", {"invested": 154083}).ok


def test_a_trailing_zero_is_the_same_number():
    assert check("The ratio is 0.690.", {"ratio": 0.69}).ok


def test_an_integer_is_not_silently_unified_with_a_decimal():
    """44 peers and 44.0% are different facts and must not match each other."""
    assert not check("It returned 44.7%.", {"peer_count": 44}).ok


# --------------------------------------------------------------------------
# The real violations -- these must FAIL
# --------------------------------------------------------------------------


def test_a_number_from_the_models_own_memory_is_caught():
    """The failure mode this whole architecture exists to prevent.

    152 is PPFAS's real holdings count, so it is the plausible kind of wrong --
    the model knows it, it happens to be true today, and it was never in the
    payload. Grounded means "was shown it", not "happens to be right".
    """
    g = check("The fund holds 152 securities and charges 0.69%.", SOURCE)
    assert not g.ok
    assert "152" in g.ungrounded


def test_arithmetic_the_model_did_itself_is_caught():
    """0.33 is arithmetically CORRECT (1.02 - 0.69) and still a violation.

    This is the subtle one. Letting it through means the next subtraction --
    which will be wrong -- looks exactly the same on screen. Arithmetic belongs
    in Python, and this test is what keeps it there.
    """
    g = check(
        "At 0.69% against a median of 1.02%, you save 0.33 percentage points a year.",
        SOURCE,
    )
    assert not g.ok
    assert "0.33" in g.ungrounded


def test_the_concatenation_trick_is_caught():
    """Stitching two real numbers into a third.

    A substring-based check passes this, because "0.691.02" contains both
    "0.69" and "1.02". Comparison is on whole tokens for exactly this reason.
    """
    g = check("The blended figure is 0.691.02 for the year.", SOURCE)
    assert not g.ok


def test_an_invented_date_is_caught_separately_from_numbers():
    g = check("As of 2025-01-15 the ratio was 0.69%.", SOURCE)
    assert not g.ok
    assert g.dates_ungrounded == ("2025-1-15",)


def test_a_year_alone_is_still_a_number_and_must_be_grounded():
    """A bare year is not a date and falls through to the number check.

    Left deliberately strict: "since 2019" is a factual claim about history the
    payload did not make, and it is exactly the kind of unremarkable-looking
    sentence a reader would never think to check.
    """
    assert not check("The fund has been cheap since 2019.", SOURCE).ok


def test_the_reason_string_names_what_was_wrong():
    """A rejection that does not say which figure is unsourced cannot be acted
    on -- not by a retry prompt, and not by a person reading the log."""
    g = check("It holds 152 securities as of 2025-01-15.", SOURCE)
    assert "152" in g.why()
    assert "2025-1-15" in g.why()


def test_source_is_searched_wherever_the_model_could_see_it():
    """A number nested inside a list the model was shown is grounded.

    The payload is compared as a whole rather than walked field by field,
    because the model saw the whole thing.
    """
    src = {"holdings": [{"name": "HDFC Bank", "weight_pct": 7.55}]}
    assert check("Its largest holding is 7.55% of the fund.", src).ok


def test_text_with_no_numbers_is_trivially_grounded():
    assert check("This fund is cheaper than most of its peers.", SOURCE).ok


# --------------------------------------------------------------------------
# Prose dates -- the false positive the unit tests above did NOT catch
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "As of August 27, 2026, the fund charges a total expense ratio of 0.69 percent.",
        "As of 27 August 2026, the fund charges 0.69 percent.",
        "As of Aug 27, 2026 the ratio was 0.69%.",
        "On 27th August 2026 it stood at 0.69%.",
    ],
)
def test_a_date_written_in_prose_is_still_a_date(sentence):
    """Found by running the model, not by writing tests.

    The first version of this module passed all its own unit tests and then
    rejected four of five real generations, because every test I had written
    used `2026-08-27` or `27-08-2026` -- the forms I thought of. Asked for two
    plain sentences, the model wrote "August 27, 2026", and 27 and 2026 became
    ungrounded numbers.

    The lesson is the one this repo keeps relearning: build the fixture from the
    real mechanism, not from the mechanism you assume.
    """
    assert check(sentence, SOURCE).ok, check(sentence, SOURCE).why()


def test_a_prose_date_that_was_never_in_the_source_is_still_caught():
    """Widening the date parser must not turn it into a way to smuggle numbers."""
    g = check("As of January 15, 2025 the ratio was 0.69%.", SOURCE)
    assert not g.ok
    assert g.dates_ungrounded == ("2025-1-15",)


def test_a_year_the_source_already_stated_is_grounded_on_its_own():
    """Measured live: one generation in six writes the year without the date.

    The source says `2026-08-27`, so 2026 is a figure the model was shown. This
    is the difference between a strict guard and a guard nobody keeps switched
    on -- and it does not weaken the check, because
    `test_a_year_alone_is_still_a_number_and_must_be_grounded` still holds for a
    year that appears nowhere in the source.
    """
    assert check("As of 2026 the fund charges 0.69%.", SOURCE).ok
    assert not check("The fund has been cheap since 2019.", SOURCE).ok


# --------------------------------------------------------------------------
# Found by attacking this module, not by testing it
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence,word",
    [
        ("The fund saves you thirty three basis points a year.", "thirty"),
        ("It is about two thirds of the median.", "thirds"),
        ("The fund manages fifteen thousand crore.", "crore"),
    ],
)
def test_a_number_spelled_as_a_word_is_reported(sentence, word):
    """A digit-based check cannot see "thirty three basis points".

    Found by writing attacks against this module rather than tests for it. The
    fix is not to parse English numerals -- that gets "a quarter of" wrong --
    but to report them, and to tell the model in the prompt to use digits.
    """
    g = check(sentence, SOURCE)
    assert not g.ok
    assert word in g.spelled_out
    assert "spelled as words" in g.why()


def test_ordinary_english_is_not_mistaken_for_a_smuggled_number():
    """The false-positive rate is the thing that gets a guard switched off.

    "one of your funds" and "a third fund" are English, not arithmetic, so
    "one" and "a" are deliberately not in the word list.
    """
    assert check("This is one of the cheapest funds in its category.", SOURCE).ok


# --------------------------------------------------------------------------
# check_claims -- the attack set membership structurally cannot see
# --------------------------------------------------------------------------

CLAIM_SOURCE = {
    "ter_pct": 0.69,
    "peer_count": 44,
    "return_1y": -0.59,
    "holdings": [{"name": "HDFC Bank", "weight_pct": 7.55}],
}


def test_a_grounded_number_reused_as_a_different_quantity_is_caught():
    """THE attack. `peer_count` is 44. "It returned 44% since launch" is
    fabricated, and `check()` passes it because 44 really is in the payload.

    Only naming the field catches this, which is why the model is required to
    return a source path for every figure it uses.
    """
    assert check("It has returned 44% since launch.", CLAIM_SOURCE).ok, (
        "set membership is expected to miss this -- that is why check_claims exists"
    )
    g = check_claims([Claim("44", "return_1y")], CLAIM_SOURCE)
    assert not g.ok
    assert "return_1y" in g.why() and "-0.59" in g.why()


def test_a_claim_naming_a_field_that_does_not_exist_is_caught():
    """Covers the model inventing both the number and somewhere to put it."""
    g = check_claims([Claim("12.5", "alpha")], CLAIM_SOURCE)
    assert not g.ok
    assert "not in the source" in g.why()


def test_a_claim_with_the_right_field_but_the_wrong_value_is_caught():
    g = check_claims([Claim("0.96", "ter_pct")], CLAIM_SOURCE)
    assert not g.ok
    assert "0.69" in g.why()


def test_a_claim_can_name_a_nested_path():
    """Payloads are nested -- holdings, peers, stats -- so a flat field list
    would force the model to cite the top-level object and prove nothing.

    A list path now also has to say who the row is about; see
    `test_a_number_from_a_list_must_name_its_subject`.
    """
    assert check_claims(
        [Claim("7.55", "holdings.0.weight_pct", "holdings.0.name", "HDFC Bank")],
        CLAIM_SOURCE,
    ).ok


def test_honest_claims_pass():
    assert check_claims(
        [Claim("0.69", "ter_pct"), Claim("44", "peer_count")], CLAIM_SOURCE
    ).ok


def test_the_two_checks_are_complementary_by_design():
    """Neither alone is sufficient, and the failure they each miss is different.

    `check()` needs no cooperation from the model and catches a number that
    appears nowhere. `check_claims()` needs the model to name its sources and
    catches a number that appears in the wrong place. Shipping one without the
    other leaves a live hole.
    """
    invented = "The fund holds 152 securities."
    assert not check(invented, CLAIM_SOURCE).ok          # caught by set membership
    borrowed = [Claim("44", "return_1y")]
    assert check("It returned 44%.", CLAIM_SOURCE).ok    # missed by set membership
    assert not check_claims(borrowed, CLAIM_SOURCE).ok   # caught by field check


# --------------------------------------------------------------------------
# Found by an adversarial review, 2026-08-27. Each reproduced before the fix.
# --------------------------------------------------------------------------


def test_a_loss_never_narrates_as_a_gain():
    """THE one output a financial narrator must never produce.

    The sign had been excluded from the number pattern deliberately, under a
    comment claiming "a fall of 12%" and "-12%" describe the same fact. They do
    when Python writes the surrounding words. They do not when the model does --
    and the live PPFAS payload carries `stat_1y: -0.59`, a fund that is down.
    """
    src = {"return_1y": -0.59}
    assert not check("The fund returned 0.59% over the last year.", src).ok
    assert not check_claims([Claim("0.59", "return_1y")], src).ok
    assert check("The fund fell -0.59% over the last year.", src).ok


def test_a_year_cannot_be_spent_as_a_rupee_amount():
    """The year relaxation was justified with "This does NOT open a hole."

    It did. With `as_of: 2026-08-27` in the payload, a bare 2026 was grounded
    anywhere -- and a ~Rs 2,000 annual fee is exactly what this app narrates.
    A temporal cue is now required, which keeps the case the relaxation exists
    for and refuses the rest.
    """
    src = {"as_of": "2026-08-27", "ter_pct": 0.69}
    assert not check("You pay ₹2,026 a year in fees.", src).ok
    assert not check("The fund has 2026 holdings.", src).ok
    assert check("As of 2026 the TER is 0.69%.", src).ok


def test_identifiers_and_clock_times_are_not_facts():
    """`repr(source)` made every digit inside an ISIN and a timestamp grounded.

    `T18:30:00.000Z` is on every v5 holdings row, so 18, 30 and 0 were grounded
    on every holdings narration ever produced. The date half is kept; the clock
    is not, and identifier-valued keys contribute nothing.
    """
    src = {"isin": "INF879O01027", "portfolio_date": "2026-07-30T18:30:00.000Z",
           "scheme_code": "122639", "ter_pct": 0.69}
    assert not check("The fund holds 879 securities.", src).ok
    assert not check("It returned 30% last year.", src).ok
    assert not check("The fund holds 18 stocks.", src).ok
    assert check("Its TER is 0.69%.", src).ok
    assert check("The portfolio is as of 2026-07-30.", src).ok, "the date half survives"


def test_a_number_from_a_list_must_name_its_subject():
    """A path proves the number. It never proved who the number was about.

    "Reliance Industries is 7.55% of the fund" cited `holdings.0.weight_pct`
    and passed both checks -- and holdings.0 is HDFC Bank. Every look-through
    sentence in the product is this shape.
    """
    src = {"holdings": [{"name": "HDFC Bank Ltd", "weight_pct": 7.55}]}
    assert not check_claims([Claim("7.55", "holdings.0.weight_pct")], src).ok
    wrong = Claim("7.55", "holdings.0.weight_pct", "holdings.0.name", "Reliance Industries")
    assert not check_claims([wrong], src).ok
    right = Claim("7.55", "holdings.0.weight_pct", "holdings.0.name", "HDFC Bank Ltd")
    assert check_claims([right], src).ok


def test_two_paths_that_mean_the_same_thing_are_not_ambiguous():
    """This test asserted the OPPOSITE, and its own example was the false positive.

    `stats.0.stat_1y` and `return_stats.0.return1y` are both -0.59 because they
    are the SAME FACT written twice -- Groww ships the one-year return under two
    names. Citing either is honest, and rejecting it is not caution.

    Measured across 39 live Groww scheme payloads, the original rule rejected
    230,067 of 240,404 citable figures (95%) and every single collision was
    same-meaning. A guard that rejects 95% of correct output and catches nothing
    does not get tightened, it gets switched off.
    """
    src = {"stats": {"stat_1y": -0.59}, "return_stats": {"return1y": -0.59}}
    assert check_claims([Claim("-0.59", "stats.stat_1y")], src).ok


def test_two_paths_that_mean_different_things_still_are():
    """The case the relaxed rule must keep, because the prose cannot settle it.

    A peer count of 44 and a holdings count of 44 are different facts wearing
    the same digits, and a sentence honest enough to satisfy one predicate would
    satisfy the other. This is the collision worth rejecting.
    """
    src = {"peer_count": 44, "aum": 44}
    g = check_claims([Claim("44", "peer_count")], src)
    assert not g.ok
    assert "mean different things" in g.why()


def test_an_integer_field_cannot_licence_a_decimal_claim():
    """`_numbers` keeps 44 and 44.0 apart because a peer count and a percentage
    are different facts. Comparing through it again would have undone that."""
    src = {"peer_count": 44}
    assert not check_claims([Claim("44.0", "peer_count")], src).ok
    assert check_claims([Claim("44", "peer_count")], src).ok


def test_a_figure_quoted_out_of_a_prose_field_is_citable():
    """Set equality rejected every number inside a sentence-valued field.

    `exit_load` is prose -- "Exit load of 2% if redeemed within 365 days" -- and
    the cost badge has to cite the 2. Rejecting it is the false-positive failure
    this module keeps relearning, so the relation is containment.
    """
    src = {"exit_load": "Exit load of 2% if redeemed within 365 days"}
    assert check_claims([Claim("2", "exit_load", quote="2% if redeemed")], src).ok


def test_a_prose_field_will_not_licence_a_bare_digit():
    """This test used to assert the OPPOSITE, and that was the hole.

    Containment fixed a real false positive and opened a real hole in the same
    line: it let every digit inside a prose field float free of the clause that
    conditioned it. The live payload is worse than the fixture --

        "Exit Load for units in excess of 10% of the investment, 1% will be
         charged for redemption within 3 months"

    -- so `Claim("1", "exit_load")` licensed "switching costs you 1% of your
    money", which drops the 10% allowance AND the 3-month window and inverts
    the advice. The quote is the fix: it has to be a literal substring, so the
    condition cannot be left behind.
    """
    src = {"exit_load": "Exit Load for units in excess of 10% of the investment,"
                        "1% will be charged for redemption within 3 months"}
    assert not check_claims([Claim("1", "exit_load")], src).ok
    assert not check_claims([Claim("1", "exit_load", quote="1% flat")], src).ok
    assert check_claims(
        [Claim("1", "exit_load", quote="1% will be charged for redemption")], src
    ).ok
    # A figure that is not in the field at all still fails for the older reason,
    # so the quote rule adds a check rather than replacing one.
    assert not check_claims(
        [Claim("9", "exit_load", quote="1% will be charged")], src).ok


# ---------------------------------------------------------------------------
# The four holes this module shipped with, each pinned by the case that found it
#
# All four were WRITTEN DOWN in the plan as known and unfixed, which is worth
# saying plainly: a documented hole is still a hole. Narration reaches the user
# as advice about their own money, and a guard that is 90% closed is the one
# people stop reading the output of.
# ---------------------------------------------------------------------------


def test_an_honest_entity_claim_does_not_licence_a_dishonest_sentence():
    """The deepest of the four, because every check passed.

    `check_claims` compared the claim to the PAYLOAD -- name matches row, number
    matches row -- and never once looked at the sentence. So a model could cite
    `holdings.0.name = "HDFC Bank Ltd"` entirely correctly and write "Reliance
    Industries is 7.55% of the fund". Set membership: pass. Field match: pass.
    Entity match: pass. And the fund does not hold Reliance at that weight.

    The subject now has to appear in the prose too.
    """
    src = {"holdings": [{"name": "HDFC Bank Ltd", "weight_pct": 7.55}]}
    claims = [Claim("7.55", "holdings.0.weight_pct", "holdings.0.name", "HDFC Bank Ltd")]
    assert not check_all("Reliance Industries is 7.55% of the fund's weight.", claims, src).ok
    assert check_all("HDFC Bank is 7.55% of the fund's weight.", claims, src).ok


def test_the_subject_may_be_named_in_the_previous_sentence():
    """The false-positive half, which matters as much as the hole.

    "HDFC Bank is the largest holding. It is 7.55% of the portfolio." is correct
    prose and the second sentence names nobody. Demanding the subject in the
    same sentence would reject it, and a check that rejects correct output is
    a check someone switches off -- this module's oldest recurring failure.
    """
    src = {"holdings": [{"name": "HDFC Bank Ltd", "weight_pct": 7.55}]}
    claims = [Claim("7.55", "holdings.0.weight_pct", "holdings.0.name", "HDFC Bank Ltd")]
    assert check_all(
        "HDFC Bank is the largest holding. It is 7.55% of the portfolio.", claims, src).ok


def test_two_rows_named_in_one_sentence_is_ambiguous():
    """If both names are present the reader cannot tell which the figure is for."""
    src = {"holdings": [{"name": "HDFC Bank Ltd", "weight_pct": 7.55},
                        {"name": "Reliance Industries Ltd", "weight_pct": 5.10}]}
    claims = [Claim("7.55", "holdings.0.weight_pct", "holdings.0.name", "HDFC Bank Ltd")]
    assert not check_all(
        "HDFC Bank and Reliance Industries together hold 7.55% weight.", claims, src).ok


def test_an_honest_citation_cannot_be_used_to_say_something_else():
    """The attack that survives a truthful claim list.

    Payload says `peer_count: 44`. The model cites `peer_count` -- honestly, the
    number really is there -- and writes "the fund returned 44% over the last
    year". Nothing in the claim is false. The SENTENCE is false, and it is the
    sentence the user reads.
    """
    src = {"peer_count": 44, "ter_pct": 0.69}
    assert not check_all("The fund returned 44% over the last year.",
                         [Claim("44", "peer_count")], src).ok
    assert check_all("It is compared against 44 peers.",
                     [Claim("44", "peer_count")], src).ok


def test_a_field_with_no_rule_is_reported_rather_than_assumed_safe():
    """The bound is honest about where it stops.

    `_PREDICATES` is a maintained list, so it cannot cover every field, and
    pretending otherwise would be the same self-certification this repo has
    caught its own tooling doing four times. An unruled field passes and is
    NAMED, so the gap is counted instead of invisible.
    """
    g = check_all("The scheme has 17 something-or-others.",
                  [Claim("17", "unruled_field")], {"unruled_field": 17})
    assert g.ok
    assert g.unruled == ("17 from 'unruled_field'",)


def test_the_temporal_year_rule_is_applied_by_every_check_not_just_one():
    """Two correct fixes that broke each other, which unit tests could not see.

    `check` exempted a payload year written in a temporal phrase; the year fix
    landed there and nowhere else, so `check_text_claims` still counted 2026 as
    an undeclared figure. Each function's own tests passed. `check_all` -- the
    only combination callers are told to use -- rejected roughly one generation
    in six for correctly writing the date it was given.
    """
    src = {"ter_pct": 0.69, "as_of": "2026-08-27"}
    claims = [Claim("0.69", "ter_pct")]
    assert check("As of 2026 the TER is 0.69%.", src).ok
    assert check_text_claims("As of 2026 the TER is 0.69%.", claims, src).ok
    assert check_all("As of 2026 the TER is 0.69%, which you pay every year.", claims, src).ok


def test_a_minus_sign_that_is_not_ascii_is_still_a_minus_sign():
    """The sign was added so a loss could not narrate as a gain. Then U+2212.

    The plan document itself writes "-0.052" with a Unicode minus, so it is the
    character actually in use, and a real typographic minus made the loss parse
    as positive -- reinstating the exact bug the sign existed to prevent, via a
    character the pattern had never been shown.
    """
    for dash in ("−", "–", "‒", "‐"):
        assert not check(f"The fund fell {dash}0.59%.", {"return_1y": 0.59}).ok
        assert check(f"The fund fell {dash}0.59%.", {"return_1y": -0.59}).ok


def test_a_plural_identifier_key_is_still_an_identifier():
    """The whole-word fix for `portfolio_date` silently reopened the ISIN hole.

    Substring matching discarded `portfolio_date` as an identifier because it
    contains "folio". Moving to whole-word tokens fixed that and stopped
    matching `isins`, so every digit inside an ISIN became a grounded fact
    again -- "the fund holds 879 securities" from `INF879O01027`.
    """
    assert not check("The fund holds 879 securities.",
                     {"identifiers": {"isins": "INF879O01027"}}).ok
    assert check("Disclosed as of 27 August 2026.",
                 {"portfolio_date": "2026-08-27"}).ok


def test_a_number_word_inside_the_users_own_text_is_not_smuggled_arithmetic():
    """Found by running this module against 757 real generations, not by thinking.

    The shipped app's `goals` table holds 757 LLM explanations, every one written
    before this module existed. Checked against their own source rows:

        ungrounded figures        0
        spelled-out number words  46 generations  (crore, fifty, hundred)

    **Zero hallucinated numbers in 757 real texts.** And all 46 flags were the
    same false positive: the words sit inside the user's own goal name --
    "Edge fifty crore", "Edge a hundred years out" -- which the narration quotes
    back correctly. That is the user's phrasing echoed, not the model spelling
    out arithmetic to dodge a digit check.

    6% of real output is exactly the rate at which a guard stops being read.
    """
    src = {"goal_name": "Edge fifty crore", "target_amount": 500000000.0, "years": 10}
    assert check("Your goal 'Edge fifty crore' needs 10 more years.", src).ok

    # The exemption is the quote, not the word. Outside it, nothing changes.
    bad = check("Your goal 'Edge fifty crore' returned twenty percent.", src)
    assert not bad.ok
    assert bad.spelled_out == ("twenty",)


def test_the_exemption_needs_a_real_quote_not_a_shared_word():
    """A short source value must not licence every number word in the text.

    `"50"` or `"a"` appears inside ordinary prose constantly; treating that as a
    quotation would switch the check off entirely rather than narrow it.
    """
    assert not check("It doubled fifty times.", {"code": "50", "x": 2}).ok
