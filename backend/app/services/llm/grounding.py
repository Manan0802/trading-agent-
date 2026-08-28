"""Every number the model writes must already exist in what it was shown.

WHY THIS IS THE WHOLE GUARDRAIL
-------------------------------
FinanceBench measures the same model at 9% correct closed-book and 85% correct
when handed the source document. The difference is entirely grounding. So the
design is: Python computes every number, the model only writes sentences about
numbers it was given, and this module is what makes "only" enforceable rather
than aspirational.

It is deliberately a *comparison*, not a judgement. No model grades another.
Given the tool JSON and the generated sentence, the check is closed-form and
anyone can rerun it.

THREE CHECKS, AND NONE OF THEM IS SUFFICIENT ALONE
---------------------------------------------------
    check(text, source)              a figure that appears nowhere in the payload
    check_claims(claims, source)     a figure that appears in the WRONG field
    check_text_claims(text, claims)  a figure the model used and did not declare

The second needs the model to name its sources; the first and third do not.
Ship fewer than three and there is a live hole. `check_all` runs them together
and is what callers should use.

WHAT THIS FILE HAS BEEN WRONG ABOUT, TWICE
-------------------------------------------
Both were found by running it rather than by testing it, and both are recorded
because the pattern matters more than the bugs.

**Round one -- the date false positive.** The obvious implementation is a bare
`\\d[\\d,]*\\.?\\d*` over both sides. Against gemini-3.5-flash-lite it rejected
four of five *correct* sentences: source `2026-08-27` tokenises to `2026, -08,
-27`; output `27-08-2026.` tokenises to `27, -08, -2026.`. Then the fix passed
all its own unit tests and still rejected four of five live generations, because
the model writes `August 27, 2026` in prose and every test used ISO. A guard
with a 17% false-positive rate is a guard someone switches off, and then nothing
is guarded.

**Round two -- an adversarial review, and it was worse.** Four holes, all
reproduced before being fixed:

    "The fund returned 0.59%"   against  {"return_1y": -0.59}      -> PASSED
    "You pay Rs 2,026 a year"   against  {"as_of": "2026-08-27"}   -> PASSED
    "The fund holds 879 stocks" against  {"isin": "INF879O01027"}  -> PASSED
    "It returned 30% last year" against  {"portfolio_date": "...T18:30:00Z"} -> PASSED

The first is the one that matters. **A loss narrated as a gain** is the single
output a financial narrator must never produce, and the sign had been excluded
from the number pattern on purpose, with a comment claiming "a fall of 12%" and
"-12%" describe the same fact. They do when Python writes the surrounding
words. They do not when the model does.

The other three share a cause: the payload was flattened with `repr()`, so every
digit inside an ISIN, a scheme code and a timestamp became a grounded fact. A v5
holdings payload stamps every row `T18:30:00.000Z`, which grounded 18, 30 and 0
on every holdings narration ever produced.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|september|october|"
    "november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_MONTH_INDEX = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_NUMERIC_DATES = (
    re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b"),   # 2026-08-27
    re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b"),   # 27-08-2026
)

# Prose dates. The model was asked for prose, so it writes prose: "August 27,
# 2026" and "27 August 2026" are both natural, and both were rejected by the
# version of this file whose unit tests all passed.
_PROSE_DATES = (
    re.compile(rf"\b({_MONTH_NAMES})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I),
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_NAMES})\.?,?\s+(\d{{4}})\b", re.I),
)

_DATE_PATTERNS = _NUMERIC_DATES + _PROSE_DATES

# A bare year is grounded only inside a temporal phrase.
#
# The previous version grounded any year appearing in a source date, under a
# comment asserting "This does NOT open a hole." It did: with `as_of:
# "2026-08-27"` in the payload, **"You pay Rs 2,026 a year in fees"** passed --
# and a ~Rs 2,000 annual fee is exactly what this app narrates. Requiring a
# temporal cue keeps "as of 2026", which is why the relaxation exists, and
# refuses "Rs 2,026" and "2026 holdings".
_TEMPORAL_YEAR = re.compile(
    r"\b(?:as of|in|since|during|by|until|till|from|through|after|before)\s+(\d{4})\b",
    re.I,
)

# --------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------

# The sign is part of the token. It has to be: without it a loss narrates as a
# gain and every check approves. Dates are stripped before this runs, so the
# hyphen in `27-08-2026` is already gone and cannot be read as a minus. The
# lookbehind stops the `2` in `1-2` being read as negative two.
_NUMBER = re.compile(r"(?<![\d.])(-?)(\d[\d,]*(?:\.\d+)?)")

_TRAILING = ".,;:!?)%"

# Unicode minus, en-dash and figure-dash all render as a minus and none of them
# is ASCII. The plan document itself writes "-0.052" with U+2212, so it is the
# form actually in use, and until this existed a LOSS narrated with a real minus
# sign parsed as a POSITIVE number -- the exact bug the sign was added to catch,
# arriving through a character the pattern had never seen.
_DASHES = str.maketrans({"\u2212": "-", "\u2013": "-", "\u2012": "-", "\u2010": "-"})

# Numbers spelled out. Narration must use digits, because a digit is the only
# form this can check -- "thirty three basis points" is invisible to a regex
# over \d. Parsing English numerals would get "a quarter of" wrong, so these are
# reported instead, and the prompt tells the model to use digits.
#
# "one" and "a"/"an" are excluded on purpose: "one of your funds" is English,
# not smuggled arithmetic, and flagging it would put the false-positive rate
# back where it started.
_NUMBER_WORDS = frozenset("""
two three four five six seven eight nine ten eleven twelve thirteen fourteen
fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty
seventy eighty ninety hundred thousand million billion lakh lakhs crore crores
half quarter third quarters thirds
""".split())

_WORD = re.compile(r"[A-Za-z]+")

# --------------------------------------------------------------------------
# Which parts of a payload are facts, and which are addresses
# --------------------------------------------------------------------------

# Identifier fields. Their digits are addresses, not quantities, and treating
# them as facts is how `isin: "INF879O01027"` grounded "the fund holds 879
# securities". Matched as a substring of the lowercased key, so `scheme_code`,
# `direct_scheme_code` and `rta_scheme_code` are all covered by one entry.
_IDENTIFIER_KEYS = (
    "isin", "code", "id", "slug", "ticker", "symbol", "url",
    "token", "arn", "pan", "folio",
)

# A timestamp's clock is never a fact about money. `T18:30:00.000Z` appears on
# every v5 holdings row, so 18, 30 and 0 were grounded on every holdings
# narration. The DATE half is kept -- that is a real fact.
_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ]\d{2}:\d{2}")


_KEY_TOKENS = re.compile(r"[A-Za-z]+")


def _singular(tok: str) -> str:
    """`isins` -> `isin`.

    Plurals re-opened the ISIN hole the moment matching moved from substring to
    whole-word: `identifiers.isins` stopped being an identifier, so every digit
    inside an ISIN became a grounded fact again. The fix for one bug reinstated
    another, which is why both now have a test.
    """
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss") else tok


def _is_identifier(key: str) -> bool:
    """Whole-word match on the key's parts, never a substring.

    Substring matching was wrong and a test caught it: `portfolio_date` contains
    "folio", so the whole disclosure date was discarded as an identifier and
    then reported as an ungrounded date the moment the model quoted it back.
    A guard that throws away real facts is the same failure as one that lets
    fake ones through, arriving from the other side.
    """
    return any(_singular(tok.lower()) in _IDENTIFIER_KEYS
               for tok in _KEY_TOKENS.findall(key))


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Grounding:
    ok: bool
    ungrounded: tuple[str, ...] = ()
    dates_ungrounded: tuple[str, ...] = ()
    spelled_out: tuple[str, ...] = ()
    undeclared: tuple[str, ...] = ()
    misused: tuple[str, ...] = ()
    unruled: tuple[str, ...] = ()

    def why(self) -> str:
        bits = []
        if self.ungrounded:
            bits.append(f"numbers not in the source: {', '.join(self.ungrounded)}")
        if self.dates_ungrounded:
            bits.append(f"dates not in the source: {', '.join(self.dates_ungrounded)}")
        if self.spelled_out:
            bits.append(
                "numbers spelled as words, which cannot be checked: "
                f"{', '.join(self.spelled_out)}"
            )
        if self.undeclared:
            bits.append(f"figures used but not declared: {', '.join(self.undeclared)}")
        if self.misused:
            bits.append(f"figures used to say something else: {', '.join(self.misused)}")
        return "; ".join(bits) or "grounded"

    def merge(self, other: "Grounding") -> "Grounding":
        return Grounding(
            ok=self.ok and other.ok,
            ungrounded=self.ungrounded + other.ungrounded,
            dates_ungrounded=self.dates_ungrounded + other.dates_ungrounded,
            spelled_out=self.spelled_out + other.spelled_out,
            undeclared=self.undeclared + other.undeclared,
            misused=self.misused + other.misused,
            unruled=self.unruled + other.unruled,
        )


@dataclass(frozen=True)
class Claim:
    """One figure the model used, the field it came from, and who it is about.

    THE ENTITY HALF IS NOT OPTIONAL FOR LIST DATA, and leaving it out was a real
    hole. A path validates a *number*; it never binds the *subject*:

        source : {"holdings": [{"name": "HDFC Bank Ltd", "weight_pct": 7.55}]}
        text   : "Reliance Industries is 7.55% of the fund."
        claim  : Claim("7.55", "holdings.0.weight_pct")
        -> both checks passed, and Reliance is not held.

    Every look-through sentence in this product is that shape, so a claim can
    also say *"and the row I took it from is called X"*, which is compared
    against the payload.

    Optional, because a scalar payload (`ter_pct`) has no entity to bind and
    demanding one there would be noise. `check_claims` requires it whenever the
    cited path runs through a list.
    """

    value: str
    field: str
    entity_field: str | None = None
    entity_value: str | None = None
    quote: str | None = None
    """For a prose-valued field, the phrase the figure was taken from.

    Containment fixed a false positive and opened a hole. `exit_load` reads
    "Exit Load for units in excess of 10% of the investment, 1% will be charged
    for redemption within 3 months": its digits -- 10, 1, 3 -- float free, so
    `Claim("1", "exit_load")` licensed *"switching costs you 1% of your money"*,
    which drops both conditions and inverts the advice. The quote must be a
    literal substring of the field, so the condition travels with the number."""


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------


def _dates(text: str) -> set[tuple[int, int, int]]:
    """Canonical (y, m, d), so writing order and spelling stop mattering."""
    out: set[tuple[int, int, int]] = set()
    for a, b, c in _NUMERIC_DATES[0].findall(text):
        out.add((int(a), int(b), int(c)))
    for a, b, c in _NUMERIC_DATES[1].findall(text):
        out.add((int(c), int(b), int(a)))
    for mon, day, year in _PROSE_DATES[0].findall(text):
        out.add((int(year), _MONTH_INDEX[mon[:3].lower()], int(day)))
    for day, mon, year in _PROSE_DATES[1].findall(text):
        out.add((int(year), _MONTH_INDEX[mon[:3].lower()], int(day)))
    return out


def _strip_dates(text: str) -> str:
    for pat in _DATE_PATTERNS:
        text = pat.sub(" ", text)
    return text


def _normalise(sign: str, digits: str) -> str:
    """`1,54,083` -> `154083`; `0.690` -> `0.69`; `-0.59` keeps its sign.

    Commas go, because Indian grouping means the same figure is routinely
    written both ways. Trailing zeros after a decimal point go so `0.690`
    matches `0.69`, but an integer is never turned into a float -- `44` stays
    `44`, so a peer count and a percentage cannot silently unify.
    """
    tok = digits.strip(_TRAILING).replace(",", "")
    if not tok:
        return ""
    if "." in tok:
        tok = tok.rstrip("0").rstrip(".")
    if not tok:
        return ""
    return f"-{tok}" if sign and set(tok) != {"0", "."} else tok


def _numbers(text: str) -> set[str]:
    src = _strip_dates(text.translate(_DASHES))
    out = {_normalise(sign, digits) for sign, digits in _NUMBER.findall(src)}
    out.discard("")
    return out


def _walk(obj: object, key: str = "") -> tuple[set[str], set[tuple[int, int, int]]]:
    """Numbers and dates that are genuinely facts in the payload.

    Walks rather than `repr()`-ing, because `repr()` grounds every digit inside
    an ISIN, a scheme code and a timestamp. Identifier-valued keys contribute
    nothing, and a timestamp contributes only its date.
    """
    nums: set[str] = set()
    dates: set[tuple[int, int, int]] = set()

    if isinstance(obj, dict):
        for k, v in obj.items():
            if _is_identifier(str(k)):
                continue
            n, d = _walk(v, str(k))
            nums |= n
            dates |= d
        return nums, dates

    if isinstance(obj, (list, tuple)):
        for v in obj:
            n, d = _walk(v, key)
            nums |= n
            dates |= d
        return nums, dates

    if obj is None or isinstance(obj, bool):
        return nums, dates

    if isinstance(obj, (int, float)):
        if isinstance(obj, float) and not math.isfinite(obj):
            return nums, dates
        nums |= _numbers(repr(obj))
        return nums, dates

    text = str(obj)
    m = _TIMESTAMP.match(text)
    if m:                       # keep the date, drop the clock
        text = m.group(1)
    dates |= _dates(text)
    nums |= _numbers(text)
    return nums, dates


def _flatten(obj: object, prefix: str = "") -> dict[str, str]:
    """Every leaf keyed by a dotted path, for `check_claims`.

    Identifiers are kept here, unlike in `_walk`: a claim naming `isin` is
    self-evidently not a numeric claim, and excluding the key would report it as
    "not in the source", which is a different and more confusing error.
    """
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}.{i}" if prefix else str(i)))
    elif obj is not None and not isinstance(obj, bool):
        out[prefix] = str(obj)
    return out


# --------------------------------------------------------------------------
# What a field is ALLOWED to be used to say
# --------------------------------------------------------------------------

# `check_claims` proves a figure sits at the path cited. It cannot prove the
# SENTENCE is about that path, and the gap is the whole attack: the payload says
# `peer_count: 44`, the model honestly cites `peer_count`, and writes "the fund
# returned 44% over the last year". Every check passes and the claim is invented.
#
# The payload is ours, so what each field MEANS is ours to state. A claim whose
# leaf key matches a rule must appear in a sentence carrying one of that rule's
# words. Stems, not words, so "returned"/"returns"/"return" are one entry.
#
# HONEST LIMIT: a field with no rule is not checked. That does not close the
# hole, it BOUNDS it -- from "any field can say anything" to "any field nobody
# wrote a rule for". Unruled cited fields are reported in `Grounding.unruled`
# so the gap is counted rather than assumed empty.
_PREDICATES: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (frozenset({"ter", "expense_ratio", "expense", "ter_pct"}),
     frozenset({"ter", "expense", "cost", "charg", "fee", "pay"})),
    (frozenset({"peer_count", "peers", "category_count"}),
     frozenset({"peer", "categor", "compar", "other fund", "rank", "out of"})),
    (frozenset({"return_1y", "return_3y", "return_5y", "return1y", "return3y",
                "return5y", "stat_1y", "stat_3y", "stat_5y", "cagr", "xirr"}),
     frozenset({"return", "gain", "grew", "grow", "gave", "deliver", "cagr",
                "xirr", "rose", "fell", "lost", "annuali", "up ", "down "})),
    (frozenset({"weight_pct", "weight", "holding_pct", "allocation"}),
     frozenset({"weight", "hold", "allocat", "position", "portfolio",
                "of the fund", "of your", "stake"})),
    (frozenset({"aum", "aum_cr", "fund_size", "corpus"}),
     frozenset({"aum", "size", "asset", "corpus", "manages", "managing"})),
    (frozenset({"exit_load", "exit_load_pct"}),
     frozenset({"exit", "load", "redeem", "redempt", "switch", "withdraw",
                "sell", "leav"})),
    (frozenset({"min_investment", "min_sip", "minimum_investment"}),
     frozenset({"minimum", "min ", "least", "start", "smallest"})),
    (frozenset({"nav", "nav_value"}),
     frozenset({"nav", "unit price", "per unit"})),
)

_PREDICATE_INDEX = {k: words for keys, words in _PREDICATES for k in keys}

# Sentence split. The lookbehind requires whitespace AFTER the stop, so `0.69%`
# and `27.08.2026` are never split -- a decimal point has a digit after it, not
# a space, and splitting inside a number would hand every clause the wrong
# figures and make this check worse than useless.
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

_ENTITY_NOISE = frozenset({
    "ltd", "limited", "inc", "plc", "co", "corp", "corporation", "the", "and",
    "of", "india", "fund", "direct", "regular", "growth", "plan", "scheme",
})


def _sentences(text: str) -> list[str]:
    return [p for p in _SENTENCE.split(text) if p.strip()]


def _sentence_of(text: str, value: str) -> tuple[str, str]:
    """The sentence asserting `value`, and the one before it.

    The previous sentence is returned because a model legitimately writes
    "HDFC Bank is the largest holding. It is 7.55% of the fund" -- the entity is
    named once and then pronouned. Demanding the name in the same sentence would
    reject correct prose, and a check that rejects correct prose gets switched
    off, which is how the guard becomes decoration.
    """
    parts = _sentences(text)
    want = _numbers(value)
    for i, p in enumerate(parts):
        if want and want <= _numbers(p):
            return p, (parts[i - 1] if i else "")
    return text, ""


def _entity_tokens(name: str) -> list[str]:
    toks = [t.lower() for t in _WORD.findall(name)]
    keep = [t for t in toks if t not in _ENTITY_NOISE and len(t) > 1]
    return keep or toks


def _names_entity(text: str, name: str) -> bool:
    """First distinctive token present, and at least half of the rest.

    Exact substring is wrong in both directions: "HDFC Bank Ltd" is written
    "HDFC Bank", and requiring every token would reject that. Requiring only ONE
    token would let "Nippon India Large Cap" satisfy a claim about "Nippon India
    Small Cap", which is a different fund with a different answer.
    """
    toks = _entity_tokens(name)
    if not toks:
        return False
    low = text.lower()
    if toks[0] not in low:
        return False
    hit = sum(1 for t in toks if t in low)
    return hit * 2 >= len(toks)


# --------------------------------------------------------------------------
# The three checks
# --------------------------------------------------------------------------


def check(generated: str, source: object) -> Grounding:
    """Does every figure in `generated` appear somewhere in `source`?

    The coarse net. Needs no cooperation from the model, and catches a number
    that appears nowhere at all. Blind to a number that appears in the wrong
    field -- that is `check_claims`.
    """
    src_nums, src_dates = _walk(source)
    gen_dates = _dates(generated)

    # A year the payload stated, written on its own, in a temporal phrase, is
    # exempt -- about one generation in six writes "as of 2026" rather than the
    # full date. `_used_numbers` owns that rule so every check applies it.
    gen_nums = _used_numbers(generated, source)

    bad_nums = tuple(sorted(gen_nums - src_nums, key=lambda s: (len(s), s)))
    bad_dates = tuple(
        "-".join(str(p) for p in d) for d in sorted(gen_dates - src_dates)
    )
    words = _spelled_out(generated, source)
    return Grounding(
        ok=not bad_nums and not bad_dates and not words,
        ungrounded=bad_nums,
        dates_ungrounded=bad_dates,
        spelled_out=words,
    )


def _echoed_strings(source: object) -> list[str]:
    """String values in the payload long enough to be quoted back verbatim.

    A user names a goal "Edge fifty crore" and the narration repeats it. Those
    number words are the USER'S, echoed correctly -- not the model spelling out
    arithmetic to dodge a digit check. Measured on 757 real generations from
    this app's own database: every single spelled-out-number flag was of this
    kind, and none was smuggled arithmetic.

    Length 4 is the floor because a two- or three-character value ("50", "abc")
    matches far too much prose to be evidence of a quote.
    """
    out: list[str] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)
        elif isinstance(obj, str) and len(obj.strip()) >= 4:
            out.append(obj.strip().lower())

    walk(source)
    return out


def _spelled_out(text: str, source: object) -> tuple[str, ...]:
    """Number words the MODEL wrote, excluding any it quoted from the payload.

    Without the exemption this fires on 6% of real generations and every one is
    a false positive -- which is the rate at which a guard stops being read.
    """
    echoed = _echoed_strings(source)
    found = set()
    for m in _WORD.finditer(text):
        w = m.group(0).lower()
        if w not in _NUMBER_WORDS:
            continue
        lo, hi = m.start(), m.end()
        if any(e in text.lower() and
               (i := text.lower().find(e)) <= lo and hi <= i + len(e)
               for e in echoed):
            continue
        found.add(w)
    return tuple(sorted(found))


def _temporal_years(text: str) -> set[str]:
    return set(_TEMPORAL_YEAR.findall(text))


def _used_numbers(text: str, source: object | None) -> set[str]:
    """The figures a passage asserts, with the temporal-year exemption applied.

    ONE helper, called by every check that reads free text. When `check` applied
    the exemption and `check_text_claims` did not, the correct sentence "As of
    2026 the TER is 0.69%" passed one and failed the other, so `check_all`
    rejected roughly one generation in six for writing a date the payload had
    stated. The two fixes broke each other, which is worse than either bug
    alone: each looked right in its own tests and only the combination failed.
    """
    used = _numbers(text)
    if source is None:
        return used
    _, src_dates = _walk(source)
    return used - (_temporal_years(text) & {str(y) for y, _, _ in src_dates})


def check_claims(claims: list[Claim], source: object) -> Grounding:
    """Does each figure match the field it names?

    THE ATTACK THIS EXISTS FOR. The payload says `peer_count: 44`; the sentence
    says "returned 44% since launch". Set membership passes -- 44 really is in
    the source -- and the claim is invented. Only naming the field catches it.
    """
    flat = _flatten(source)
    by_value: dict[str, list[str]] = {}
    for path, val in flat.items():
        for num in _numbers(val):
            by_value.setdefault(num, []).append(path)

    bad: list[str] = []
    for c in claims:
        actual = flat.get(c.field)
        if actual is None:
            bad.append(f"{c.value} (claimed from '{c.field}', which is not in the source)")
            continue

        # Containment, not set equality. `exit_load` is a sentence -- "Exit load
        # of 2% if redeemed within 365 days" -- and the cost badge needs to cite
        # the 2. Equality rejected every figure quoted out of a prose field,
        # which is the "guard someone switches off" failure again.
        claimed = _numbers(c.value)
        if not claimed or not claimed <= _numbers(actual):
            bad.append(f"{c.value} (claimed from '{c.field}', which is {actual})")
            continue

        # An integer field cannot licence a decimal claim. `_numbers` keeps 44
        # and 44.0 apart on purpose -- a peer count and a percentage are
        # different facts -- and comparing through it again would undo that.
        if ("." in c.value) != ("." in actual) and _numbers(actual) == claimed:
            bad.append(
                f"{c.value} (claimed from '{c.field}', which is {actual} -- "
                "an integer and a decimal are different facts)"
            )
            continue

        # A figure lifted out of a sentence has to bring the sentence with it.
        # Containment let `exit_load`'s three digits float free of the two
        # conditions attached to them; the quote pins the figure back to its
        # clause. Only prose fields need one, so a plain numeric field is
        # unaffected and no existing caller has to change.
        if len(_numbers(actual)) > 1 or len(actual) > 40:
            if not c.quote:
                bad.append(
                    f"{c.value} (from the prose field '{c.field}' with no quote; "
                    "a digit pulled out of a sentence loses its conditions)")
                continue
            if c.quote not in actual:
                bad.append(f"{c.value} (quote {c.quote!r} is not in '{c.field}')")
                continue
            if not claimed <= _numbers(c.quote):
                bad.append(f"{c.value} (not inside its own quote {c.quote!r})")
                continue

        # A collision only matters if the colliding paths MEAN different things.
        #
        # The first version of this rule rejected any value reachable from more
        # than one path. Measured across 39 live Groww scheme payloads that is
        # 230,067 of 240,404 citable figures -- 95% -- and of every collision,
        # ZERO were between fields with different meanings. `stats.0.stat_1y`
        # and `return_stats.0.return1y` are both -0.59 because they are the same
        # fact written twice, and citing either is honest.
        #
        # So the rule was rejecting almost everything and catching nothing: the
        # exact "guard that gets switched off" shape this module has hit before.
        # What it was really guarding against -- citing one path while meaning
        # another -- is now caught by the predicate check in `check_text_claims`,
        # which reads the sentence. This keeps only the case that check cannot
        # see: two paths that would licence genuinely different claims.
        paths = by_value.get(next(iter(claimed)), [])
        if len(paths) > 1 and c.field in paths:
            rules = {_PREDICATE_INDEX.get(p.split(".")[-1].lower()) for p in paths}
            rules.discard(None)
            if len(rules) > 1:
                bad.append(
                    f"{c.value} (reachable from {len(paths)} paths that mean "
                    f"different things -- {', '.join(sorted(paths)[:3])})"
                )
                continue

        # And who is it about? Required whenever the path runs through a list,
        # because that is exactly where the subject is chosen by the model.
        through_list = any(part.isdigit() for part in c.field.split("."))
        if through_list and c.entity_field is None:
            bad.append(
                f"{c.value} (cited from a list at '{c.field}' with no entity -- "
                "a path proves the number, not who it is about)"
            )
            continue
        if c.entity_field is not None:
            got = flat.get(c.entity_field)
            if got is None:
                bad.append(f"{c.value} (entity field '{c.entity_field}' is not in the source)")
            elif c.entity_value is not None and got.strip().lower() != c.entity_value.strip().lower():
                bad.append(
                    f"{c.value} (claimed to be about '{c.entity_value}', but "
                    f"'{c.entity_field}' is '{got}')"
                )
    return Grounding(ok=not bad, ungrounded=tuple(bad))


def _siblings(flat: dict[str, str], entity_field: str | None) -> list[str]:
    """Every other row's name, for the same list and the same attribute.

    `holdings.0.name` -> the values at `holdings.1.name`, `holdings.2.name`...
    These are the names a sentence could plausibly be about instead, and they
    are the only wrong subjects worth naming explicitly.
    """
    if not entity_field:
        return []
    parts = entity_field.split(".")
    idx = next((i for i in reversed(range(len(parts))) if parts[i].isdigit()), None)
    if idx is None:
        return []
    out = []
    for path, val in flat.items():
        p = path.split(".")
        if len(p) == len(parts) and p[idx].isdigit() and p[idx] != parts[idx]:
            if [x for i, x in enumerate(p) if i != idx] == \
               [x for i, x in enumerate(parts) if i != idx]:
                out.append(val)
    return out


def check_text_claims(
    generated: str, claims: list[Claim], source: object | None = None
) -> Grounding:
    """Did the model declare every figure it used -- and does the PROSE match?

    Three questions, because declaring a figure is not the same as using it
    honestly.

    1. COMPLETENESS. Without this, `check_claims` is only as complete as the
       model chooses to be: write five numbers, declare the one you can justify,
       pass. The adversary supplies the list, so the list is checked against the
       text rather than trusted.

    2. WHAT THE FIGURE IS USED TO SAY. `check_claims` proves 44 sits at
       `peer_count`. It cannot see that the sentence reads "the fund returned
       44%". `_PREDICATES` states what each field may be used to assert, and the
       sentence carrying the figure must carry one of those words.

    3. WHO THE SENTENCE IS ABOUT. The entity check in `check_claims` compares
       the claim to the PAYLOAD and never to the TEXT, so a claim could name
       "HDFC Bank Ltd" perfectly correctly while the sentence said "Reliance
       Industries is 7.55% of the fund" -- and every check passed. The name now
       has to appear in the sentence, or the one before it, and no other row
       from the same list may be named alongside it.

    `source` is optional only so the completeness check stays usable alone; 2
    and 3 need the payload and are skipped without it, which `check_all` never
    does.
    """
    declared = {n for c in claims for n in _numbers(c.value)}
    used = _used_numbers(generated, source)
    undeclared = tuple(sorted(used - declared, key=lambda s: (len(s), s)))

    flat = _flatten(source) if source is not None else {}
    misused: list[str] = []
    unruled: list[str] = []

    for c in claims:
        here, before = _sentence_of(generated, c.value)
        low = here.lower()

        allowed = _PREDICATE_INDEX.get(c.field.split(".")[-1].lower())
        if allowed is None:
            unruled.append(f"{c.value} from '{c.field}'")
        elif not any(w in low for w in allowed):
            misused.append(
                f"{c.value} (cited from '{c.field}', but {here.strip()!r} says "
                f"none of: {', '.join(sorted(allowed)[:5])})")

        name = c.entity_value or (flat.get(c.entity_field) if c.entity_field else None)
        if not name:
            continue
        if not _names_entity(f"{before} {here}", name):
            misused.append(
                f"{c.value} (claimed to be about '{name}', which "
                f"{here.strip()!r} does not name)")
            continue
        for other in _siblings(flat, c.entity_field):
            if other.strip().lower() != name.strip().lower() and _names_entity(here, other):
                misused.append(
                    f"{c.value} (about '{name}', but {here.strip()!r} also "
                    f"names '{other}' -- the reader cannot tell which)")
                break

    return Grounding(
        ok=not undeclared and not misused,
        undeclared=undeclared,
        misused=tuple(misused),
        unruled=tuple(unruled),
    )


def check_all(generated: str, claims: list[Claim], source: object) -> Grounding:
    """All three, which is the only combination without a live hole.

    This is what callers should use. Running fewer is a decision to leave one of
    the three documented failure modes unguarded.
    """
    return (
        check(generated, source)
        .merge(check_claims(claims, source))
        .merge(check_text_claims(generated, claims, source))
    )
