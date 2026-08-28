# Phase 1, redesigned

**Status: plan, not built. Written 2026-08-27.**

Manan, on the Phase 1 that exists today: *"i will say it is just 1 percent of
what i want"*. This is the answer to that, and it is written to be attacked —
every number in it was measured today or is marked as not verified.

---


**Contents.** 5,426 lines, 20 sections. Read §0 for scope, §7 for the build order, §9.1 for what is still open. §18 is the review log and is at the back on purpose.

- [The whole thing in one page](#the-whole-thing-in-one-page) · 56 lines
- [0. What this document is, and what it is not](#0-what-this-document-is-and-what-it-is-not) · 163 lines
- [1. The five findings the whole design rests on](#1-the-five-findings-the-whole-design-rests-on) · 436 lines
- [2. The data layer](#2-the-data-layer) · 424 lines
- [3. The product](#3-the-product) · 574 lines
- [4. The AI layer](#4-the-ai-layer) · 293 lines
- [5. What this app will not do, and why](#5-what-this-app-will-not-do-and-why) · 34 lines
- [6. The debt-fund defect, stated honestly](#6-the-debt-fund-defect-stated-honestly) · 28 lines
- [7. Build order](#7-build-order) · 318 lines
- [8. Regulation — the short version](#8-regulation--the-short-version) · 363 lines
- [9. Open, and honest about it](#9-open-and-honest-about-it) · 118 lines
- [10. Tax — verified, and the answer splits in two](#10-tax--verified-and-the-answer-splits-in-two) · 164 lines
- [11. The things a plan of this size usually leaves out](#11-the-things-a-plan-of-this-size-usually-leaves-out) · 479 lines
- [12. Reconciliation — every count in this document, in one place](#12-reconciliation--every-count-in-this-document-in-one-place) · 155 lines
- [13. The visual system](#13-the-visual-system) · 556 lines
- [14. What the rebuild must not lose](#14-what-the-rebuild-must-not-lose) · 142 lines
- [15. Navigation](#15-navigation) · 85 lines
- [16. Data model — what exists, and the seven things this plan adds](#16-data-model--what-exists-and-the-seven-things-this-plan-adds) · 396 lines
- [17. The narration contract](#17-the-narration-contract) · 281 lines
- [18. The review log](#18-the-review-log) · 325 lines

---

## The whole thing in one page

**What changes.** Not the engines — the product. Six screens organised by data
type become five organised by decision, the 32,456px screener becomes a finder,
and three things become possible that were not: the exact set of funds Manan can
actually buy, what he owns *underneath* his funds, and an AI layer that cannot
state a number it was not given.

**What the evidence says, after being measured rather than assumed.**

| | |
|---|---|
| picking funds on past return | fails — the worse quartile came out on top, 19 of 44 windows won (43%) (§1.1) |
| **cost** | works — **43 of 52 windows (83%)**, +2.1pp, rank IC +0.195 — the only column not near zero (§1.1) |
| **selling** | is where people lose. Professionals sell worse than *randomly* (§1.2) |
| **holding period** | decides outcomes far more than fund choice (§1.4) |
| **look-through** | two of Manan's plausible five funds would be 47% the same fund (§1.5) |

**What is new, and verified live on 2026-08-27.** 1,686 buyable Groww funds with
TER, AUM, manager tenure and full holdings; 2,632 NSE stocks with 26 years of
daily prices and delivery, one request a day; `gemini-3.1-flash-lite` with
structured output, function calling and a grounding validator that catches a
loss narrated as a gain.

**What it refuses to do,** and each refusal has a citation: no "sell the
underperformer", no concentration limit, no trailing stop, no price alerts, no
streaks, no behaviour-gap number, no order placement. §5.

**The biggest risk,** which is not any of the above: every rupee rests on
hand-typed transactions that nothing currently checks (§11.7).

**Where it stands.** Plan **five times adversarially reviewed** — two
engineering, one product/design, one build-readiness, and one checking the
document against the filesystem — for **44 findings**. The three that mattered
most were each **my own largest claim being wrong** (§17.6, §1.1, §1.3).
1,624 tests green; the exit-signal gate passes with a verified instrument.

**`grounding.py`'s four known holes were closed on 2026-08-28** (§17.6), so
nothing written *for this plan* carries a recorded unfixed defect. Three things
still do, all named rather than carried: `tax_regime.py` has **no surcharge
logic at all** and the fix needs marginal relief and the capital-gains cap, not
a rate table (§10); debt funds are still ranked on equity metrics (§6); and the
irrecoverable look-through store **has no backup** until slice 2.3 writes one
(§16.4).

**Is it ready to build?** Yes, in the sense that is testable: every step in §7
names what to build, where it goes, and a criterion that can fail. **No, in the
sense that cannot be tested from a document** — **one hundred forty-seven review passes**
have each found something — and pass 89 found that this sentence had itself gone
stale. It said *thirty-six*, and that *"the last four found work already done
rather than work missing"*. That was true when it was written and is not now:
passes 85-88 found a total that disagreed with its own slices, two constraints
shaping every section while recorded in none, four headings out of order with
thirteen references hanging off an unguarded list, and **two slice-1 steps whose
acceptance needed work from slices 2 and 3**. **The rate of finding has not
fallen, and a readiness verdict reporting otherwise is the one claim here that
flatters the document.** What remains is named, scoped, and carries the test that
closes it.

**The full review log — every pass, its method, and what it found — is §18.**
It is at the back on purpose: this section is for someone about to build, and
the audit trail is for someone deciding whether to trust it.


## 0. What this document is, and what it is not

It is **not** a feature list. Every section below either cites a measurement in
this repo, a live probe run on 2026-08-27, or a paper whose abstract was
actually fetched. Where something is unverified it says so in the same sentence,
because a plan that hides its soft spots gets found out by the first reviewer
who checks one.

**Scope: advisory only.** Manan, 2026-08-27: *"buss tumara goal advisory tak ka
hai"* — get the advice right first, trading is a later phase. Nothing in this
document places an order, sizes a trade, or times a market. Where a data source
would enable trading (live order book, F&O chains, intraday), it is catalogued
in `docs/groww-endpoints.md` and deliberately left unused.

**Why only Groww-buyable funds.** Manan: *"groww is the platform we use to
invest"*. Every universe figure in this document — the 1,686, §11.2's *union of
buyable and held* — follows from that one sentence, and **pass 86 found the
sentence itself was recorded nowhere**, only its consequences. That matters in
one specific way: a later reader seeing a filter that drops 3,271 of AMFI's
4,957 schemes would read it as an arbitrary narrowing and could reasonably
"fix" it. It is not a narrowing. **A fund he cannot buy is not advice, it is
trivia**, and widening the universe would make every ranking in the app less
useful, not more.

**Who reviews this, and why the document reads the way it does.** It is written
to be checked by other engines — Codex, Cursor, Antigravity — against the
standard Manan set: *"koi itna sa bhi minute to inute flaw bhi ni hoi"*. That
is the reason for the things a reader might otherwise find excessive: every
number carrying where it was measured, §12's list of figures whose inputs were
**not** retained, §9.2 keeping closed items rather than deleting them, and §18's
log of every pass from the fifth on — eighty-two entries, including the ones
that found my own claims wrong.
**A plan that only records its wins cannot be audited**, and this one expects to
be. This too was unrecorded until pass 86 — the standard was shaping every
section while appearing in none of them.

**What it extends, and what it leaves alone.** `NexTrade_PRD_v1.md` specifies a
goal calculator: give it a target, a horizon and an assumed rate of return, and
it solves for the monthly SIP, splits it across equity/debt/gold, and has an
LLM explain the result in Hinglish. **That works and it has shipped** — 600
users, 757 goals, each carrying a generated explanation.

**This document does not redesign it. It builds a second thing on top of it.**
The PRD's advisor never looks up a fund: across its 2,330 lines, AMFI appears 0
times, `mfapi` 0, bhavcopy 0, Groww twice in passing. A calculator does not need
market data. Everything here that does — the 1,686-fund universe, the NAV store,
the cost verdict, the look-through, the base rates, the exit signal — **is new
scope**, and §7's estimate is the price of that scope, not of a rebuild.

```
what the PRD's advisor answers   "you need ₹32,447 a month for five years,
                                  50% equity / 40% debt / 10% gold"
what this one adds               which funds you can actually buy, what each
                                  costs, what they hold underneath, which two
                                  of yours are one bet, and what this kind of
                                  fund has done to people before
```

Reading it as "the PRD, rebuilt" gets the cost and the risk wrong in the same
direction: it makes §2 look like plumbing that already existed, and §1's
research look like background rather than the thing that justifies the
extension at all.

Three things are settled and are not reopened here:

- The app **never places an order.** Manan executes on Groww himself.
- The portfolio is **entered manually** for now (CAS import later, his call).
- The engines stay; the **product shell and every screen are rebuilt.**

Two more, added on pass 72 because they were assumed rather than stated:

- **How many people use it is not settled**, and §8's entire regulatory reading
  turns on it. The PRD says *"personal use + 4-5 close friends/family"* while
  bounding it with *"not a multi-user public SaaS"*; §8 argues from one. See
  §8.-1.
- **`/ask` is an expansion beyond the PRD**, whose LLM only ever explains a
  computation that just ran. The whole grounding apparatus exists because of
  that one choice. See §17.5a.

---

### 0.1 🔴 What this document never opened — pass 59

Before §1, an admission that changes how to read it. Fifty-eight passes went
into checking this plan against the code, the databases, the deployment, the
git history, the memory and the statutes. **Nobody checked it against the
documents sitting in its own folder.**

```
NexTrade_PRD_v1.md      2,330 lines   the complete PRD -- executive summary,
                                      personas, architecture, Part A advisor,
                                      Part B trading agent, tech stack, data
                                      sources, database schema
SECURITY.md                44 lines   and §8.1/§8.2 audited credentials without it
DEPLOY.md                 238 lines
START_HERE.md             162 lines

docs/what-actually-predicts-returns.md      285 lines   cited 0 times here
docs/does-the-score-work.md                 118          0
docs/do-factors-work-here.md                199          0
docs/does-the-stock-score-work.md             -          0
docs/why-there-is-no-fund-manager-screen.md  48          0
docs/bachatt-teardown.md                      -          0
```

**§1 of this document is titled "The five findings the whole design rests on",
and it is about what predicts returns and whether the score works. Five files
with those exact questions as titles sit in the same directory and are cited
nowhere.** `what-actually-predicts-returns.md` opens by answering a direct
objection from Manan, dated 2026-07-30, *"not by argument, but by the same
harness that has already failed our own scoring engine once."*

**This is the same failure this document has now recorded six times, at its
largest scale.** `fund_ter_history` (§16.6), `/portfolio/overlap` (§9.2), §14's
rules as response contracts, the frontend harnesses (§13.11), `check.sh`'s nine
gates (§13.12) — every one was work assumed to be needed and already done. The
pattern was always *"read the plan, not the repo"*. **Its final form is a
redesign that never opened the requirements it was redesigning.**

**What this does not mean.** §1's measurements were made here, from the NAV
store, and re-derived under review; they do not become wrong because a
neighbouring file asks the same question. **What it means is that this plan
cannot claim to be the project's considered position until the two are
reconciled** — and where they disagree, the older document was written closer to
the evidence.

**First task of slice 0, ahead of the marker gate:** read all four root
documents and the six research files, and record in §12 for each one whether it
agrees with this plan, supersedes it, or is superseded. Nothing else in this
document is trustworthy in the way it claims to be until that is done.

### 0.2 🔴 This is not a redesign of the PRD's advisor. It is a different product. — pass 71

The clearest thing to come out of reading `NexTrade_PRD_v1.md`, and it should
have been in §0 from the start.

**The PRD's advisor never touches a fund.** Its SIP engine takes
`annual_return_rate` as a **parameter** — an assumed number — and solves a
formula:

```python
def calculate_required_sip(target_amount, years, annual_return_rate,
                           current_savings=0.0, inflation_rate=0.06)
```

It looks up nothing. Counted across 2,330 lines: **AMFI 0 mentions, mfapi 0,
bhavcopy 0, Groww 2 in passing.** Its only data sources are `yfinance` and
Angel One SmartAPI, both for stocks and ETFs — Part B, the trading half. **For
the advisor half the PRD specifies no market data at all**, because a
calculator does not need any.

**So the two products answer different questions:**

```
PRD's advisor      "you need ₹32,447 a month for five years,
                    split 50% equity / 40% debt / 10% gold"
this plan          "here are the 1,686 funds you can actually buy, what each
                    costs, what they hold underneath, which two of yours are
                    the same bet, and what this kind of fund has done to
                    people before"
```

**This plan is not a redesign of that. It is an extension of it into a
different category of product** — from a goal calculator with an LLM explainer
into a fund-selection and portfolio-analysis tool. §2's entire data layer, §1's
five findings, the look-through, the cost verdict and the exit signal are all
**new scope**, not improvements to something specified.

**What that changes, and it is not a criticism of either document:**

- **§1's findings only matter to a product that chooses funds.** "Selection
  does not predict, cost does" is advice about picking; the PRD's advisor never
  picks. The research was necessary *because* of the extension, and reads as
  foundational only from inside it.
- **The 34-session estimate covers work the PRD never scoped.** §7's cost is
  the cost of the extension. That is worth stating where the estimate is given.
- **And the PRD's advisor is not hypothetical — it shipped.** 600 users, 757
  goals, each with an LLM explanation (§17.5a). The calculator works. **This
  plan builds on a working product and says so nowhere.**

> **§0 says what this document is and is not, and it never said this.** A
> reader — Manan included — would reasonably take "Phase 1 redesign" to mean
> the thing in the PRD, rebuilt. It is not. **It is a second product on the
> same rails**, and the honest framing changes what "done" means for it.

### 0.3 The last two root documents, and one of them is badly wrong — pass 74

**`START_HERE.md` — the file that says "read this first" — describes a project
that has not been built.**

```
Last updated: 2026-06-29
Phase: research + planning complete, ready to build Phase 1 (no app code yet)
```

Since that line was written: **158 commits, 1,603 tests, 49 API endpoints, 88
schemas, 7 migrations, a 5.2M-row NAV store, 49 `.tsx` files.** Its own opening
is *"If you know nothing about this project, this file + the PRD + the research
doc = full understanding… written so a total beginner (or a fresh AI agent) can
get up to speed in 15 minutes."*

**A fresh reader following that instruction is told there is no app.** This is
the §11.4 failure in its most consequential position — not a stale number in a
table, but the front door telling everyone who walks through it that the
building is empty. **And it is the cheapest to fix of anything in §9.1**: one
status line.

**It also confirms two things independently, which is worth more than either
document alone:**

- *"Built for **Manan + 4-5 friends/family**."* Second statement of the user
  count, in the onboarding document, matching the PRD (§8.-1). §8 still argues
  from one.
- *"Budget tiny (**~₹0–800/month**)."* A third figure — the PRD said ₹500–2000
  — and this one **includes zero**, so it is compatible with the free-tier
  constraint rather than superseded by it.

🟢 **`DEPLOY.md` resolves the tense question §8.0 left open.** It describes the
no-card route as one that *"**ends on a public HTTPS URL** at ₹0/month with no
payment method anywhere."* So `SECURITY.md`'s *"not publicly deployed"* is a
statement about **now** — confirmed by an empty `gh release list` — and public
is the **intended end state**, stated in a third document. §8.2's credential
argument is dated rather than hypothetical, and §8.-1's user-count question
becomes live at the same moment.

## 1. The five findings the whole design rests on

### 1.1 What past returns do and do not say — measured five times, three of them wrong

**The three prior measurements, quoted from `app/data/track_record.json`**, the
committed scoreboard §3.6 puts on screen (measured 2026-08-22, median of 3 runs):

| ranked on | top quartile | bottom quartile | spread | windows won | rank IC |
|---|---|---|---|---|---|
| **past 3y return** | 19.4% | 20.2% | **−0.9pp** | **19 of 44 (43%)** | −0.025 |
| NAV level | 20.1% | 19.8% | +0.4pp | 25 of 44 (57%) | +0.014 |
| blend | 19.7% | 18.9% | +0.8pp | 30 of 44 (68%) | +0.105 |
| **cost** | 20.6% | 18.4% | **+2.1pp** | **36 of 44 (82%)** | **+0.195** |
| cost alone, 52 windows | — | — | +2.1pp | **43 of 52 (83%)** | — |
| the shipped score | — | — | +1.6pp | 33 of 54 (61%) | — |

🟢 **The `blend` row is the strongest line in this table and this document
never read it. `docs/what-actually-predicts-returns.md` did — pass 60.**

That file, written 2026-07-30 and cited nowhere here until now, ran the same
harness and drew the conclusion this section left on the floor:

> *"Blending them halves the signal. `blend` is a 50/50 mix of the past-return
> rank and the cost rank. IC drops from +0.184 to +0.091… Adding 'but returns
> matter' to the ranking does not merely fail to help — **it destroys half of
> the only signal that works.** Past return is not neutral information being
> ignored. It is noise, and mixing noise into a signal degrades it. This is the
> quantitative justification for `past_return` carrying weight **0%** rather
> than a small positive weight."*

**That is a different and better argument than "past return does not predict".**
It answers the objection a reasonable person actually makes — *surely a little
weight on returns cannot hurt* — and the answer is that it does hurt, measurably,
by half. The row was sitting in the table above with no sentence attached to it.

**The two documents' numbers differ in every cell and agree in every direction**,
which is what §12's `why_ranges` predicts: the validators fetch from mfapi at 24
threads and the sample moves with which fetches succeed.

```
                 2026-07-30 (research doc)      2026-08-22 (this table)
past_3y     -1.0%  20/44  IC -0.033         -0.9pp  19/44  IC -0.025
cost        +1.9%  34/44  IC +0.184         +2.1pp  36/44  IC +0.195
nav_level   +0.3%  20/44  IC +0.020         +0.4pp  25/44  IC +0.014
blend       +0.7%  28/44  IC +0.091         +0.8pp  30/44  IC +0.105
```

**Neither supersedes the other.** They are two runs of one harness, and the
agreement across them is better evidence than either alone — which is a thing
this section could only say after opening the file next to it.

⚠️ **And that file settles something else this document never checked.**
`nav_level` was ranked *as a signal* to test the most common misconception in
Indian retail investing — that a ₹10 NAV is cheaper than a ₹1,000 one. Rank IC
**+0.020**, which is zero. *"This also kills the NFO pitch. A new scheme at ₹10
is not cheap; it is a fund with no record, sold on the one number that does not
matter."* §5's refusal list should carry that, and does not.

🔴🟢 **The correction this section has carried since pass 2 was itself half
wrong, and pass 61 found out by opening the file next door.**

*What this section said:* an earlier draft printed "60 windows", "50% hit rate",
"top +17.2% vs bottom +19.4%" — and those *"came from a vault note, not from
the file"*, a stale record of the kind §11.4 forbids.

*What is actually true:* **every one of those figures is in
`docs/does-the-score-work.md`, committed 2026-07-27, and they are correct.**

```
Result 1   10 categories x 6 windows = 60 windows, median hit rate 50%
Result 2   54 category-windows
           top quartile by our score    +17.2%
           category median              +18.1%
           bottom quartile by our score +19.4%
           top beat bottom in 25 of 54 = 46%
```

**They measure a different thing.** `validate_score.py` asks *"does the fund
SCORE pick funds that go on to do better?"* — it runs the real scorer and
measures its picks against the category median. `why_not_returns.py`, which
feeds `track_record.json` and the table above, asks *"which SIGNAL predicts the
next three years?"* — it ranks on `past_3y`, `cost`, `nav_level` and `blend` and
measures top quartile against bottom.

**Two questions, two harnesses, two window counts — 60/54 against 44.** The
earlier draft's error was putting scorer figures in a table of signal figures
without saying which was which. **The correction replaced that with a different
labelling error and invented a provenance**: it declared them a vault-note
artefact when they were a committed measurement, and this table already carries
one of them — the *"shipped score, 33 of 54"* row is Result 2's window count.

> **This is the third time the same mistake has been made about this one table,
> and the shape is identical each time: a number was explained rather than
> traced.** The original draft explained 60/50% as belonging here; the
> correction explained it as a stale note; both skipped the thirty seconds of
> `grep` that settles it. §11.4's rule is not only "regenerate the record" — it
> is **cite where each number came from**, which this section now does.

**And the older document's verdict is blunter than anything here:** *"The answer
is no, and this document exists because that needed writing down rather than
quietly not being tested."* It also states the survivorship caveat this plan
repeats: *"our catalogue is built from funds that are alive today… the true
numbers are worse than the ones above by an unknown margin."*

**§12 requires these regenerated rather than retyped, and now also requires each
row to name the script that produced it.**

Read it straight: ranking on past three-year return put the *worse* quartile on
top by 0.9pp and won 43% of windows. Ranking on cost won 82–83%.

**The fourth measurement** — does past return say when to *leave* — was written
for this plan. `backend/scripts/validate_exit_signal.py`. It has been wrong
three times, and each error is recorded because it is the reason to believe the
fourth version.

1. **Median of a quintile.** The random control came back at 59%, which is
   impossible. On small cohorts a quintile is two or three funds and their
   "median" sits above the cohort median on a right-skewed distribution.
2. **Reading rows against 0.500** while its own controls sat at 0.477–0.539.
3. **Calling that drift bias.** It is not. `prank = i/(n-1)` gives a random
   subset an expectation of exactly 0.500 at any n — simulated over 3,000 runs
   at every cohort count used here, the mean is 0.4999. The drift was **variance
   from drawing one control per cohort**; 200 draws collapses it. The tempting
   alternative was widening the band until the run went green, which would have
   turned the only instrument check in the file into decoration.
4. **Bootstrapping cohorts instead of dates.** A cohort is one (category, date)
   pair, so resampling them treated five equity categories measured on
   2013-01-01 as five independent draws of Indian equity. They are one. The
   intervals on those rows — ±0.10 to ±0.22 — were cross-category spread inside
   a single market episode wearing the clothes of uncertainty about time.

Version five clusters the bootstrap on **formation date** and refuses to print
an interval below four distinct dates:

```
OVERLAPPING  (formation dates one year apart)
 lb/fwd  dates cohorts    obs  died   ctrl  LOSE-ctrl            95% CI   WIN-ctrl            95% CI   tails
  1y/1y     12      73   2580    40  0.500     -0.028   [-0.088,+0.030]     +0.033   [-0.051,+0.102]  1.006
  3y/3y      8      35   1183    97  0.501     +0.040   [-0.032,+0.110]     -0.052   [-0.101,-0.005]  0.990
  3y/1y     10      53   1786    35  0.499     +0.000   [-0.046,+0.050]     +0.010   [-0.043,+0.059]  1.007
  1y/3y     10      53   1786   114  0.500     +0.011   [-0.014,+0.039]     +0.015   [-0.013,+0.048]  1.025
  5y/3y      6      21    729    84  0.503     +0.039   [-0.010,+0.093]     -0.106   [-0.132,-0.082]  0.938
  3y/5y      6      21    729   113  0.501     +0.042   [-0.039,+0.110]     -0.038   [-0.088,+0.027]  1.006

NON-OVERLAPPING
  1y/1y      6      40   1413     7  0.499     -0.028   [-0.112,+0.048]     +0.030   [-0.096,+0.141]  1.001
  3y/3y      1       5    169     1  0.499     +0.001          <4 dates     +0.039          <4 dates  1.038
  3y/1y      3      17    580     0  0.499     -0.000          <4 dates     +0.020          <4 dates  1.018
  1y/3y      3      17    580     8  0.497     -0.030          <4 dates     +0.061          <4 dates  1.025
  5y/3y      1       5    159     4  0.500     -0.030          <4 dates     -0.083          <4 dates  0.888
  3y/5y      1       5    159    30  0.499     +0.104          <4 dates     -0.114          <4 dates  0.988
```

**Every control lands between 0.497 and 0.503.** The instrument is checked
against its own null before any row is read.

**What this actually says:**

- **The non-overlapping pass, which an earlier draft told you to believe, is the
  thinner one.** Four of its six rows rest on one to three formation dates and
  now print no interval at all. Spacing windows so they cannot share data also
  throws away most of the dates; the overlapping pass carries 6–12.
- **At one-year lookback, nothing survives.** 1y/1y winners +0.033
  [−0.051, +0.102] on twelve dates. This is not evidence against momentum; it is
  too weak to be evidence of anything, and `nextrade-prediction-research` tests
  a different, cross-sectional design.
- **At three- and five-year lookback, past winners subsequently underperform,
  and it survives date clustering.** 3y/3y −0.052 [−0.101, −0.005] on eight
  dates; 5y/3y −0.106 [−0.132, −0.082] on six. That is the shape De Bondt and
  Thaler describe, and it is the strongest thing in this table.
- **`tails` is an asymmetry indicator, not an error detector.** It sums to 1.000
  only under the null, so 5y/3y at 0.938 means both extremes underperformed the
  middle — a coherent non-monotonicity. An earlier draft used it to discard that
  row, which was wrong.

**🔴 And the finding that limits all of it.** The script loudly refuses
`nav.db.trimmed` and reads the untrimmed store — 4,939 schemes, 63% of them
wound up. But cohort membership comes from `fund_catalogue.json`, whose category
labels are modern SEBI names, and **dead funds carry legacy labels**:

```
nav.db                          4,939 schemes, 3,104 dead (63%)
the 10 equity categories          582 funds,      41 dead (7%)
where the other 3,063 dead sit:   Income 1,601 · IDF 792 · "1099 Days" 221 · Growth 102
```

So the survivorship defence guards the NAV source and **the category join
reintroduces the bias anyway**. 541 of the 582 funds measured are alive today.
The `died` column is printed for exactly this reason: 0 to 114 dropped per row is
implausibly little attrition for twenty years of Indian funds.

> **Every conclusion here is conditional on a fund still existing and carrying a
> post-2018 equity label.** Fixing it needs point-in-time AMFI classification,
> which we do not have. This is a stated limit, not a to-do.

**What follows for the product.**

- **No `Underperforming — consider exiting` badge.** Ranking on past return put
  the worse quartile on top (43% of windows) and the exit measurement cannot
  support a threshold. §5.1.
- **No "sell your winners" rule either**, and this is the harder refusal because
  the table's strongest column points at one. It is one measurement, on one
  store, survivorship-conditional, with two of twelve intervals excluding zero
  and no correction for testing twelve hypotheses — and §1.2 says a sell rule is
  the most expensive kind to get wrong. **Recorded as a finding, not shipped as
  a feature.**
- **Cost stays the ranking signal**, at 82–83% of windows and rank IC +0.195,
  which is the only column in the table that is not close to zero.

### 1.2 Selling is where people lose. This is the strongest verified finding.

**Akepanidtaworn, Di Mascio, Imas & Schmidt (2023), *Journal of Finance* 78(6),
DOI `10.1111/jofi.13271`** — abstract fetched and read today. Institutional
managers, portfolios averaging $573m: *"evidence of skill in buying, selling
decisions underperform substantially, even relative to random-selling
strategies"*, driven by *"a systematic, costly heuristic process for selling but
not for buying"*.

Professionals, with teams and data, sell **worse than randomly**.

**Consequence:** the app gets a sell layer, and its job is the opposite of what
that phrase usually means. It exists to stop a heuristic sell, not to prompt
one. Every exit prompt must be mechanical and pre-committed, never reactive to
a price move.

*(The "~80bps/yr" figure in earlier notes is not in the abstract and was not
verified. Direction verified, magnitude not — do not put a number on screen.)*

### 1.3 Engagement mechanics increase trading, and trading costs money

Direction supported by Barber & Odean's turnover result (most-traded quintile
11.4%/yr against 16.4% for the average household and 17.9% for the market).

The FCA randomised trading-app experiment — push notifications +11%, gamification
+12%, worst among younger and less literate users — **could not be re-verified
today.** Occasional Paper 62 turned out to be a different paper; OP 63/64/65 are
404; the FCA search returns 403; WebSearch and firecrawl budgets are exhausted.
**The direction stands on Barber & Odean. The 11%/12% figures are not to be
quoted until the paper is found.**

**Consequence, which survives either way:** no price alerts, no streaks, no
confetti, no daily P&L on the home screen. Daily P&L lives one tap away.

### 1.4 How long you hold decides the outcome. Which fund you pick does not.

From 5,183,632 NAV rows, 3,992 funds, 2006–2026 ([[traa-base-rates]]):

```
Small Cap:  one year  20.3% of windows lost money
            five years 1.8%
            ten years  0.0%
            worst fall −57.4% = ₹4,59,280 on ₹8,00,000, ~9 months to recover
```

Every equity category runs 16–22% losing years and 0–2% losing five-year
stretches. That effect is larger and more certain than anything fund selection
produces, and it is on no other Indian app.

### 1.5 The genuinely new capability: look-through. Proven today, not asserted.

Five funds, five different AMCs, five different categories — the largest fund in
each. Real ISIN-level holdings from Groww's v5 endpoint:

```
Large Cap   vs ELSS         29 common names   46.8% overlap
Flexi Cap   vs Large Cap    31 common names   34.4%
Flexi Cap   vs ELSS         23 common names   28.0%

₹1,00,000 split equally  →  ₹90,945 actually reaches equity
HDFC Bank   ₹4,704  (5.2% of all equity)  held via 4 of the 5 funds
ICICI Bank  ₹4,418  (4.9%)                held via 3
```

Two sentences no Indian app currently says: *"your Large Cap fund and your ELSS
are 47% the same fund"*, and *"you put ₹1,00,000 into equity funds and ₹90,945
reached equity"*.

Until today this was impossible at scale — we could read seven AMCs' XLS files,
so holdings overlap covered a fraction of the universe. It now covers all of it
(measured: 40/40 funds across 20 AMCs returned full holdings).

🔴 **But this does not replace correlation, and an earlier draft of this plan
quietly implied it did.** The decision recorded on 2026-07-30 is *"correlation
first, then real holdings — both"*, and its reasoning still holds: **holdings
overlap can say two funds are different when they are the same bet.** The
recorded example is the argument:

```
SBI Small Cap  vs  PPFAS Flexi Cap    corr 0.78   holdings  0.7%
     → almost no shared names, and one market. Holdings alone calls this
       "diversified", which is the wrong answer.

Axis Large Cap vs  ICICI Large Cap      —         holdings 57.1%
     → the same shares, twice. Only the holdings number can say this.
```

They answer different questions and the product needs both:

| | answers |
|---|---|
| **correlation**, monthly returns | *"do these two move as one thing?"* — the question a diversification claim is actually about. Monthly, not daily: on daily returns two Indian equity funds correlate near 1.0 and the number says nothing. |
| **holdings overlap**, ISIN-level | *"am I buying the same companies twice?"* — which correlation cannot localise to a name, and which is what makes the finding actionable. |

So the `Same bet as another fund you hold` badge fires on **either**, and names
which. A pair that is high on both is the strongest case in the product; a pair
high on only one is the more interesting sentence, because it says something the
user could not have worked out.

---

### 1.5b What the stock score's own test says, and the sentence this plan is missing — pass 65

`docs/does-the-stock-score-work.md`, 115 lines, cited nowhere here until now.
§3.5 quotes its headline — *"won on NIFTY 500, lost on NIFTY 50"* — and drops
everything that makes it usable.

**The magnitude, and the conclusion §3.5 leaves off:**

```
universe     years   spread    mean IC
NIFTY 500      2     +10.6%    not yet measured
NIFTY 50       2      -5.0%     -0.084
```

> *"On the large caps the top quartile LOST to the bottom in both years, and the
> rank correlation is slightly negative — the score orders them faintly
> backwards. … **a result that reverses sign when you change the index is not a
> signal.** The likeliest reading of the NIFTY 500 number is a size effect."*

**And two attacks before that one**, each removing a flattering number:
scoring on the fiscal year end used figures *"nobody had until August"* and was
worth **4.5 percentage points a year** of lookahead; the six-month lag then left
**two observations**, and *"a score with no skill lands two the same way a
quarter of the time."*

🔴 **The limitation this plan does not carry anywhere, and should:**

> *"**Two of the score's five weighted inputs are never exercised.**
> `dividend_yield` is passed as `None` and `promoter_history` as empty for every
> observation … the promoter-stake adjustment — which the model's own docstring
> calls **the cheapest read on India's dominant equity risk** — has never been
> tested at all. **Whatever this concludes is a claim about 87 of the score's
> 100 points.**"*

Every statement this plan makes about the stock score is a statement about 87%
of it. **§3.5's refusal line needs that number**, because "the score has not
been shown to predict" and "13 points of the score have never been measured at
all" are different admissions and only the first is currently made.

🔴 **And it corrects a survivorship claim of the same shape this plan makes.**
That document's earlier version said survivorship *flatters the bottom quartile
and therefore understates the spread* — a signed direction. It withdrew it:

> *"That is only one channel. India's characteristic blow-ups — Yes Bank, DHFL,
> IL&FS, Reliance Capital — read as respectable on P/E, ROE and earnings growth
> until the governance or leverage failure that a score with no debt or auditor
> signal cannot see. Every such name scored well and then collapsed, and every
> one is now missing from the top quartile's average. **The net direction is
> genuinely unsigned, and the earlier claim was too confident.**"*

§1.1 says its own measurement is *"survivorship-conditional"* and leaves the
direction open, which is right. **§12 should state the reason in those terms**,
because "conditional" reads as a hedge and *"the net direction is genuinely
unsigned, and here is the mechanism that makes it unsigned"* is an argument.

⚠️ **And a fifth instance of this project's recurring failure, in a script.**

> *"The script now refuses to print a conclusion below five years — because the
> version of it written an hour earlier **declared success on those two**, which
> is the exact self-flattery this app exists to prevent, **produced by the
> app**."*

`check.sh` that could not fail, `why_ranges` that could not be wrong, the
path-ambiguity rule that rejected everything, a test of mine that asserted
against `None`, and now a validator that declared victory on two observations.
**Five, in one codebase, each found a different way.**

### 1.6 The control practice this plan uses and never credited — pass 64

`docs/do-factors-work-here.md`, rewritten 2026-08-06 and cited nowhere here
until now, is where the discipline §1 leans on was established — and it earned
it the expensive way.

**Its controls caught a finding that was not there.** The first version
benchmarked each factor's top quartile against `^NSEI`:

> ```
> random   vs index +4.2%   t = +4.13
> ```
>
> *"A random quartile beating the index by 4.2%, with a t-statistic that would
> read as overwhelming significance. That is not an edge — it is mid caps
> outrunning large caps across the sample, because the universe was NIFTY 500
> and the benchmark was NIFTY 50. **Measuring a factor against a different
> universe measures the universe.** … Without the controls that +4.2% would
> have been reported as a finding."*

**That is the same failure §1.1's own control caught**, one project earlier: a
random draw reading as signal until the comparison was made honest. This
document ran a **seeded shuffle that must score zero** and a **`reversal`
control that must mirror momentum**, and only read the other rows once
`random` fell to +0.0%, t = +0.07. §1 uses a random control and credits nobody
for the practice; it came from here.

**Its method table is a standard §1 partly meets and should state:**

```
non-overlapping windows   §1.1 does this, after review forced it
benchmark = the universe  "the alternative an investor actually has is the
                           same set of stocks, not a different index"
costs charged, not assumed 0.5% a side, a full round trip per rebalance
rank IC, not just quartiles §1.1 reports IC
both indices, separately   "the stock score won on NIFTY 500 and lost on
                           NIFTY 50, INVISIBLY, until they were split"
price history only         no fundamentals, no filing lag, no currency
```

That fifth line already appears in §3.5's refusal table — *"the stock score's
own measured record (won on NIFTY 500, lost on NIFTY 50)"* — **quoted without
its source, and without the part that matters: it was invisible until split.**

**On momentum, it agrees with §9.1 and sharpens it.** Momentum is real
(quarterly t = +2.99 over 60 non-overlapping windows) and **not harvestable at
quarterly turnover** — the 2.1% edge becomes −1.9% after 4% of trading. Annually
it nets +7.2% but only reaches t = +1.60. *"Neither run alone would justify
anything. Together they say: the effect is real, and it is only harvestable at
low turnover."*

⚠️ **And one row needs reading carefully rather than quoted.** `low_vol` is
negative at both horizons (t = −2.67, −2.56). **That is not a contradiction of
the fund score's volatility weight**, and this section says so explicitly to
stop a future reader making that leap: *"It is a risk-adjusted claim and this
sample is a bull market, so this is the factor behaving as documented rather
than failing. It is not a way to make more money here."* The fund score uses
volatility to describe **risk**, not to predict **return**. Different claim.


### 1.7 The evidence is executable, and §1 cited two of eight — found on pass 116

§1 is 435 lines of findings and names `why_not_returns.py` and
`validate_score.py`. **Six more validators exist in `backend/scripts`, 1,769
lines between them, and none is cited anywhere in this document.** Each asks its
question the same way — rank on the decision date using only what was knowable
then, measure forward returns — and each prints a result a reviewer can re-run.

```
validate_cost_ranking.py       93  "Does ranking by expense ratio predict better
                                    than ranking by past record?"
validate_lifetime_ranking.py   63  Manan's hypothesis: score on the WHOLE lifetime
validate_stock_score.py       492  "Does the stock score predict anything?"
validate_factors.py           469  "Do momentum and low volatility actually pay
                                    on the stocks we can buy?"
measure_score_edge.py         201  "Does the ported fund score rank funds better
                                    than a coin?"
build_base_rates.py           350  how often each category has lost money since 2006
```

**`validate_cost_ranking.py` is the one that matters most, because it is §1.1's
pivot in code.** Its docstring states the reasoning this whole plan rests on:
*"The composite score does not predict. Cost is the one input with replicated
predictive power in the literature, so before rebuilding the product around it,
it gets the same test the score just failed."* It prints the cheapest quartile's
median forward return against the dearest, the annual gap, and **how many windows
cheap beat dear**. §1 asserts that finding; this runs it.

**Two things this changes.** A reviewer told to check §1 currently has prose and
two scripts; there are eight, and the most load-bearing one was missing.
**And `validate_lifetime_ranking.py` records something no section here does** —
that Manan proposed scoring funds on their whole lifetime record, and that it was
*tested rather than dismissed*: *"The 3-year test failed. Lifetime is a different
claim — a longer record, more market cycles, arguably a truer picture of the
manager. Worth testing rather than dismissing."* **That is the project's own
standard applied to its owner's idea, and it belongs in the record.**

⚠️ **Not run here.** These are listed because they exist and are uncited, not
because pass 116 executed them — each needs the NAV store and several minutes,
and §12's rule is that a figure without a retained input is not evidence. What
this section now says is *where the evidence lives*, not what it says.
### 1.8 The claim the product rests on, reproduced — pass 148

§1.7 listed the validators and said plainly that pass 116 had **not run them**.
Pass 148 ran the one that matters, a different way: not by calling
`validate_cost_ranking.py` — it fetches every NAV from `mfapi` and that is
thousands of requests — but by re-implementing its method against the **local
store**, 5.19M rows already on disk. Rank each equity category by direct TER,
take the cheapest and dearest quartiles, measure the forward three-year return
from six decision dates a year apart, 2018 to 2023.

```
                        this run          §1.1 states
category-windows        52                52
cheapest quartile       +21.4% / yr       —
category median         +19.8% / yr       —
dearest quartile        +19.3% / yr       —
cheap minus dear        +2.1 pp           +2.1 pp
cheap beat dear in      43 of 52  (83%)   43 of 52  (83%)
```

**The window count, the spread and the win count all land exactly**, from a
separate implementation reading a different source than the original script.
**§1.1's pivot — cost predicts where past record does not — is now reproduced in
this review rather than cited from it.**

⚠️ **Four things this does not settle, stated because the number is persuasive.**
**Lookahead — tested on pass 149, and the assumption is measurably false.**
Both runs rank on **today's** TER filing at a decision date up to eight years
earlier, on the script's own reasoning that cost *"is known on the decision date
and does not move much, so there is no lookahead in using today's filing."*
§16.6 said Groww ships eleven years of daily TER; **all 39 cached payloads carry
`historic_fund_expense`, median span 10.8 years, median 1,091 rows** — and PPFAS
returns **1,166 rows over 12.8 years**, reproducing §16.6's figure exactly. So
the assumption is checkable, and it does not hold:

```
decision date   n    rank correlation    median rank move   median TER change
                     with 2026-08        of n funds
2018-07-01      24        +0.34               6 of 24           −0.29 pp
2020-07-01      27        +0.47               6 of 27           −0.10 pp
2023-07-01      32        +0.56               5 of 32           +0.15 pp
```

**At the earliest decision date, today's cost ranking agrees with the ranking
that actually applied only +0.34, and the median fund had moved six places out
of twenty-four.** Cost is stable *as a number* — the median TER moved 0.1-0.3pp
— but **not stable as a rank**, and rank is what the quartile method uses.

🔴 **Pass 150 ran both ways on the same funds, and the sign flips.** Twenty-one
of the cached funds have **both** a TER history and enough local NAV. Same six
decision dates, same three-year hold, same quartile split — the only thing that
changes is which TER does the ranking:

```
ranking signal                      cheap − dear      cheap won
today's TER      (as §1.1 does)        +4.2 %           6 of 6
the TER filed that day                 −2.7 %           2 of 6
```

⚠️ **This is not a refutation and must not be read as one.** **n = 21 funds,
~16 per window, quartiles of four, six overlapping windows** — against §1.1's 52
category-windows across ten categories. Four funds' mean forward return is a very
noisy statistic, the cache is not a random sample of anything, and the slug-to-
scheme-code match that built this set is my own and matched 21 of 39. **A sign
flip on this sample is weak evidence about the true effect.**

**What it does establish is the thing that matters:** the lookahead is **not
harmless**. The script assumes ranking on today's filing changes nothing; here it
changes the sign. **So §1.1's +2.1pp is untested against its own method**, and the
question is now empirical rather than rhetorical. **The proper run is affordable**
— `historic_fund_expense` on the 1,686 buyable funds, one request each, the same
pull slice 2.1 already owns — and until it happens, §1.1 should say that its
headline rests on an assumption a 21-fund check did not support.

**What this does and does not mean.** It does not refute +2.1pp: a fund that was
cheap then is still more likely than not to be cheap now, and the effect may well
survive. **It means the measurement has not been run the honest way** — ranking
each decision date on the TER filed *at that date* — and that until it is, §1.1's
headline carries an advantage it did not earn. **The data to do it properly is
already on disk for 39 funds and one request per fund for the rest.** ⚠️ My own
sample is 24-32 equity funds from one cache; a rank correlation on that many is
noisy, and the direction is what it establishes, not the coefficient. **Survivorship:** the catalogue holds
funds that still publish, so every figure here is a survivor's figure.
**Independence:** six dates a year apart with three-year holds overlap heavily,
so 52 windows are nowhere near 52 observations and *83%* is not a binomial on 52.
**Provenance:** this is my re-implementation, not the committed script — it
agrees with it, which is evidence, and it is not the same as running it.


## 2. The data layer

Everything below was fetched on 2026-08-27. Full detail in
[[traa-groww-data-layer]], [[traa-nse-archive]], `docs/groww-endpoints.md`,
`docs/zerodha-endpoints.md`.

### 2.1 Funds

| Layer | Source | Why this one |
|---|---|---|
| **Spine** | AMFI `NAVAll.txt` / `NAVOpen.txt` | Public, documented, ToS-clean. 8-column header verified today; the retiring `Original_NAVAll.txt` is not used, so tomorrow's format change breaks nothing. |
| **Universe** | Groww `st_filter` → **1,686** buyable direct-growth codes | It is the platform Manan actually buys on. Carries TER, AUM, fund manager, min SIP/lumpsum, exit load, sub-category. |
| **Per-fund** | Groww `v5/scheme/search/{search_id}` | ISIN, benchmark, **holdings as named objects with `stock_search_id`**, manager tenure dates, **1,166 rows of daily TER history**, exit-load history, `stats` (fund vs category vs rank), and `return_stats` (sharpe/beta/stddev). |
| **Cross-check** | Zerodha `api.kite.trade/mf/instruments` → 1,658 | Independent, ToS-clean, ISIN-keyed. Two sources 28 apart is the universe validation. |
| **NAV history** | local `nav.db`, 5.19M rows | Already built. |

**The rule that governs all of it:** Groww's `/v1/api/*` is `Disallow:` in their
robots.txt. No auth is required; that is not permission. So Groww is an
**enrichment layer the app degrades without** — AMFI stays the spine, and the
screener must still produce a ranking with Groww unreachable. `groww.py` raises
a dedicated `GrowwUnavailable` for exactly this reason.

**And "degrades gracefully" has to be specified, not asserted.** Two things in
this plan depend on Groww and are load-bearing: cost (§1.1's only measured
signal, 55% of the fund score) and the active/passive split that makes cost
rankings meaningful at all (§2.3). With Groww unreachable, *both* are affected,
so the degraded state is a design question, not a shrug:

| with Groww down | what happens |
|---|---|
| cost source | AMFI alone — which `groww.py`'s own docstring records as the join that **lost PPFAS**, because AMFI keys on a code the NAV feed does not carry. Labelled `cost unverified — one source only`, which is a **different string** from the two-source gate's `cost sources disagree`; an earlier draft used one label for both causes and the user could not tell which had happened |
| cost ranking | still runs, every fund marked **"cost from one source"** rather than silently ranked as if verified |
| active/passive | last good Groww pull, with its age shown; if there is none, categories that are >50% passive are **not ranked at all** and say why |
| the screen | states the degraded state at the top of the list, not in a footnote |

**The test that makes this real:** a screener run with `groww.py` forced to raise
must still return a ranking, and must contain PPFAS. That single assertion
catches both the crash path and the known AMFI join hole.

### 2.2 Stocks — this is the part that changes most

| Layer | Source | Numbers |
|---|---|---|
| **Universe + daily prices + delivery** | NSE `sec_bhavdata_full_DDMMYYYY.csv` | **2,632** main-board names (was 751), one request per day for the entire market |
| **History** | NSE legacy `cm{DD}{MON}{YYYY}bhav.csv.zip` + `MTO_*.DAT` | back to **2000**; backfill measured at **~5 minutes / 6,500 files / ~9.3M rows**. Arithmetic re-checked on pass 23 and coherent — 6,500/26yr = **250 files a year** against ~250 NSE trading days, 9.3M/6,500 = **1,431 rows a day** against ~2,000 listed equities, 5min/6,500 = 46ms a file which at 24 threads is ~1.1s of work each. ⚠️ **Not re-verified end to end**: that needs 6,500 live downloads, and this session's network budget is spent. Coherent is not the same as reproduced |
| **Corporate actions** | NSE `corporates-corporateActions` | split/bonus/dividend with ex-dates — bhavcopy prices are unadjusted |
| **Fundamentals, live price, shareholding** | Groww `stocks_data/v1/company/...` | consolidated **and** standalone financials, live LTP, order book, `fundsInvested` |
| **Index membership** | NSE `allIndices` + niftyindices CSVs | an attribute, never a universe filter |

This retires yfinance for prices. It removes the ~1000-request rate limit, the
rolling-5-year statement window that forced `stock_score_ledger.csv` to exist,
and the absence of delivery history. Survivorship becomes correct by
construction: a delisted stock is in the old files and not the new ones.

**The trap, and it is bigger than we had recorded.** `traa-gotchas` says four
non-EQ series publish numeric delivery. Measured today: **eight** do — SM, ST,
GS, GB **plus BZ, IV, RR, E1, SZ**, 605 rows, with government bonds printing
100.00% delivery. The old blocklist would let five new series through.
**`SERIES == 'EQ'` allowlist, nothing else.** Third time this repo has learned
that a blocklist cannot be finished.

Also: our committed universe contains `DUMMYTRVN` — an NSE dummy scrip, not a
company. Another reason the universe comes from the exchange's own daily file
rather than an index list.

### 2.3 Three data-quality rules, each measured not assumed

**Cost.** Groww has 31 of 1,677 direct TERs above 2.25%, and 13 index funds
above 1.00% (worst **8.66%**, on a passive index FoF).

🔴 **But "SEBI's 2.25% ceiling" is not a ceiling, and pass 16 measured that in
this repo's own data.** `app/data/expense_ratios.json` — AMFI's published TERs,
2,793 values:

```
min 0.02   median 0.88   p95 2.48   max 3.46
above 2.25%:  241 of 2,793  (8.6%)
density 2.36 - 2.50:  4, 5, 6, 3, 8, 4, 8, 2, 6, 5, 3, 4, 4, 5
```

**There is no edge at 2.25%.** The distribution runs smoothly through it and on
to 3.46. A real regulatory ceiling leaves a cliff in the data; this leaves
nothing. So whatever 2.25% is, the published TERs of Indian mutual funds are not
bounded by it.

**The likely reason, stated as inference rather than fact:** SEBI's TER limit is
**slab-based on AUM and varies by scheme type**, with the highest slab applying
to the smallest equity schemes and lower slabs above it, plus permitted add-ons
for B-30 inflows. Under that structure 2.25% is the *top* of one slab, not a
universal cap — and a regular plan carrying distributor commission sits higher
again, which is most of the 8.6% above.

**What that does to the gate in §2.3, and it cuts both ways:**

- The direct-only figure (31 of 1,677, **1.8%**) is still the meaningful one and
  still worth flagging — a *direct* plan above 2.25% is genuinely anomalous,
  because direct plans exclude the commission that lifts the rest.
- But a flat 2.25% test **under-detects by construction.** A ₹10,000 crore fund
  whose own slab is far below 2.25% passes at 2.0%, and that is a worse deal
  than several of the funds the gate does catch. **The gate finds the loudest
  errors and misses the expensive ones.**
- The Groww universe already carries `aum_crore` (§16.2), so a slab-aware test
  is implementable with data the plan already collects. **What is missing is the
  slab table itself.**

⚠️ **Not resolved, and the reason is a tool limit rather than a judgement.**
The slab table lives in the SEBI (Mutual Funds) Regulations. WebSearch was
exhausted at 200/200 this session and Firecrawl returned `402`, so SEBI's
document paths could only be guessed; three attempts returned 404 and one
returned the wrong section. **The figures 2.25% and 1.00% appear nowhere in this
repo's code — only in this document — so they have no source here either.**

**Slice 1.2's acceptance changes accordingly:** the cost gate is not "flag above
2.25%". It is **flag above this fund's own slab**, and until the slab table is
sourced the gate ships as *"unusually high for a direct plan"* with the number
shown and no claim of a breach — which is the §14 rule that a contested
magnitude gets no number at all, applied to our own threshold.
AMFI has 12 of 1,408 above ceiling. Both are nonetheless mostly right, and the
two figures below are the same measurement on two denominators — an earlier
draft printed them as if they contradicted each other:

```
all 1,686 Groww buyable funds   1,233 have both sources   71 disagree >0.10pp   94.2% agree

✅ **Partially reproduced on pass 24, and the reproduction is worth more than
the confirmation.** Of §12's six non-retained figures this is the only one with
enough retained input to test: 39 cached Groww payloads against the committed
`expense_ratios.json`.

```
32 of 39 joined      31 of 32 agree within 0.10pp = 97%      (claim: 94.2%)
the one disagreement: ICICI Pru Large & Mid Cap  groww 1.34  amfi 1.17
```

97% on a 39-fund equity sample against 94.2% over 1,233 is consistent, so the
claim stands. **Two things the plan never wrote down came out of doing it:**

🔴 **1. The join key, which is not the obvious one.** `expense_ratios.json` is a
dict keyed by **AMFI scheme code** (`103490`, `111549`), each value carrying
`amfi_name`, `direct_ter`, `regular_ter`. Groww payloads carry `scheme_code` and
`direct_scheme_code`. The join is code-to-code — and **joining by name returns
exactly zero matches**, measured, because the two sources spell every fund
differently (`"Abakkus Small Cap Fund Direct Growth"` against
`"QUANTUM VALUE FUND"`-style AMFI capitalisation). A builder reaching for the
name field, which is the field a human would reach for, gets an empty result and
no error.

🟡 **2. Coverage is ~82% here against the 73% the claim implies** (32/39 versus
1,233/1,686). Both are small enough that the gap is sampling, but it means the
**7 funds that did not join are the interesting ones** — the ones whose Groww
`scheme_code` is absent from AMFI's expense file entirely. Those are the funds a
cost gate silently has no second source for, and §14's rule is that missing cost
is **neutral, never dropped**.

**Slice 2.1 acceptance gains the key:** the TER cross-check joins on
`scheme_code`, records the unjoined count as a first-class number, and **fails if
it ever tries to join on name.**
of those, the 1,430 SCORED      1,158 have both sources   56 disagree >0.10pp   95.2% agree
```

The second row is the one the screener acts on.

> Carry both sources. Require agreement within 0.10pp. Where they disagree —
> **56 of the 1,158 scored funds that carry both** — **do not rank that fund on
> cost, and say why on screen.** Plus a plausibility gate: any direct TER above 2.25%, or index-fund
> TER above 1.00%, is suspect even if both sources agree.

**Category.** Groww's detail endpoint carries `category_info.sub_type`. Sampled
60 funds: **0 agreed** with the universe endpoint, 51 disagreed. It labels
essentially every equity fund `Contra` and every debt fund `Gilt`. Using it
would collapse 1,686 funds into two peer groups and look entirely normal.
But the detail endpoint is being condemned on the wrong field: **the same
payload carries a correct top-level `sub_category`**, verified across the five
cached funds (Axis ELSS → `ELSS`, HDFC Mid Cap → `Mid Cap`, PPFAS → `Flexi Cap`,
while `category_info.sub_type` says `Contra` for all five).

> `category_info.sub_type` is never read. Category is taken from the universe
> endpoint's `sub_category` and **cross-checked against the detail endpoint's
> top-level `sub_category` on every fund we pull anyway** — the same two-source
> agreement rule applied to cost, for the same reason. Leaving category
> single-source while §2.3 demands two sources for TER would be inconsistent,
> and this section has just argued that a category error poisons the cost
> ranking.

**Active vs passive.** Groww's `sub_category` classifies an index fund by the
cap it *tracks*, so **86 of the 123 funds in "Large Cap" are index trackers —
70%**. Rank that peer group on cost and an index fund wins every time, which is
not a comparison: being cheap is a passive fund's design, not its merit. Cost
carries 55% of our score, so this single grouping error poisons the strongest
signal we have.

Groww's `index` boolean has **zero false positives** (375 of 375 correct) but
**65 false negatives**, and they are one coherent class: **ETF fund-of-funds** —
`Gold ETF FoF`, `BSE 500 ETF FOF`, `BHARAT Bond ETF FOF`. The proof is that
filtering on `index == False` and asking for the cheapest "active" Large Cap
returns *"Mirae Asset Diversified Equity Allocator **Passive** FoF"*.

> `is_passive = index == True OR name matches index|nifty|sensex|\bbse\b|etf`.

OR-ing an unmeasured regex onto a perfect flag can only *add* false positives,
and a false positive here deletes a genuinely active fund from its peer group —
the same error in the other direction. So the regex was measured in both:

```
flag = True   375 funds   regex also matches 375   (100%, no disagreement)
flag = False 1,311 funds  regex matches       67   ← what OR-ing adds
```

All 67 inspected: 20 Gold ETF FoF, 15 Silver ETF FoF, 13 thematic ETF FoF, and
the rest index FoFs — the two that do not contain the literal word "index" or
"etf" are `Nifty Next 50 Junior BeES FoF` and `Nifty 100 ESG Sector Leaders FoF`,
both fund-of-funds over index ETFs.

🔴 **"Zero false positives" was wrong, and it is the same bug this document
already catalogues in another module.** Pass 17 ran the regex over all 4,957
schemes in `fund_catalogue.json`. Six names match on a **substring inside a
longer word**, and three of those are genuine misclassifications:

```
DWS  Inflation INDEXED Bond Fund      <- actively managed. "Index" inside "Indexed"
HDFC Inflation INDEXED Bond Fund      <- same
SBI  INFLATION INDEXED BOND FUND      <- same
US Treasury 1-3 Year Bond ETFs FoF    <- correctly passive. "ETF" inside "ETFs"
US Treasury 3-10 Year Bond ETFs FoF   <- correctly passive
Developed Market Ex US ETFs FoF       <- correctly passive
```

An inflation-indexed bond fund tracks an index for its **coupon**, not its
portfolio. It is actively managed, and §2.3's own rule then excludes it from
ranking wherever its category is majority-passive and forbids comparing it to
active funds — **so three real active debt funds vanish from their own peer group
over a spelling.**

**This is exactly the failure `grounding.py` hit and this plan already records**
(§17.6: `portfolio_date` contains "folio", so a real date was discarded as an
identifier). The lesson was learned in one module and asserted away in another.

**And the obvious fix is wrong**, which is why the tested one is written here
rather than the intent. Adding plain word boundaries **loses the three correct
ETFs catches**, because the plural is inside the boundary:

```
plan's regex     452 passive
naive \b version 446   loses all three "ETFs Fund Of Funds"
tested fix       449   removes exactly the 3 inflation-indexed, adds nothing

\bindex\b|\bnifty\b|\bsensex\b|\bbse\b|\betfs?\b
```

🔴 **And on pass 25 the regex turned out to be the ONLY signal, not one of two.**
§2.3 defines `is_passive = index == True OR name matches …`. Measured across all
39 cached scheme payloads: **the `index` key is present in 0 of 39.** It lives on
the `st_filter` universe listing — which is where "375 of 375 correct" was
measured — and **not on the scheme detail endpoint at all.** So wherever the app
reads a scheme, the first clause contributes nothing and classification rests
entirely on a name regex that pass 17 showed has three false positives. A
two-signal design that silently becomes one-signal depending on which endpoint
you are holding is worse than a one-signal design, because nobody is watching
the signal they think is redundant.

✅ **The mechanism §2.3 describes is real, and confirmed.** Groww does file an
index fund under the cap it tracks:

```
sub_category = "Large Cap"   ICICI Prudential Nifty 50 Index Direct Plan Growth
sub_category = "Large Cap"   SBI Nifty Next 50 Index Fund Direct Growth
sub_category = "Large Cap"   UTI Nifty Next 50 Index Fund Direct Growth
```

The *count* (86 of 123) still needs the universe pull. The *premise* does not —
it is established.

🟢 **And a better signal was sitting in the payload the whole time: `benchmark`.**
Nothing in this plan mentions it. Token overlap between a fund's name and its
benchmark, stopwords removed:

```
passive (n=3)    1.00  1.00  1.00                       min 1.00
active  (n=36)   mean 0.05, max 0.33 (Invesco Smallcap / BSE 250 SmallCap)
                                                        SEPARABLE, cleanly
```

A passive fund's name **contains its entire benchmark** — `UTI Nifty Next 50
Index Fund` against `NIFTY Next 50 TRI`. An active fund's name and benchmark
share almost nothing: `Abakkus Small Cap Fund` against `NIFTY Smallcap 250 TRI`
scores 0.00.

**This is structural rather than orthographic, which is exactly why it fixes
pass 17's false positives at the root.** `Inflation Indexed Bond Fund` carries a
gilt or bond benchmark its name does not contain, so it scores near zero and is
classified **active** — correctly, and without anyone maintaining a list of
words that look like "index" but are not.

⚠️ **Three passive funds is three points.** The separation is total and the gap
is wide (1.00 against 0.33), but slice 2.1 confirms it on the full universe
before it replaces anything. **Proposed there: `is_passive` becomes
name↔benchmark overlap, with the name regex kept as a second opinion and any
disagreement between them counted rather than silently resolved** — which is the
two-source discipline §2.3 already applies to TER, and which the `index` boolean
was supposed to provide and does not.

✅ **The same pass also produced a much stronger validation than the one it
replaced.** Cross-checked against AMFI's own scheme classification — a second,
independent source already sitting in this repo:

```
4,957 schemes   ·   agreement 98.4%   ·   AMFI-passive that the regex misses: 0
```

**Zero false negatives against an authority** is a far better claim than "zero
false positives" by inspection, and it is the two-source discipline §2.3 already
applies to TER, applied here for the first time. The 79 where the regex says
passive and AMFI's category does not are mostly the regex being *right* — a
`Nifty 50 Index Fund` filed under ELSS is a tax bucket, not a strategy — which
is itself the argument for keeping name evidence alongside the category. Active and passive
are never peers, in ranking or in overlap.

Also: a few funds carry an **empty `sub_category`**. Reject them before forming
a peer group, or a peer group named `""` quietly appears.

**Rating.** `groww_rating` is a bare digit with no scale anywhere on Groww's
page. Their own `<meta description>` says "2/10" while their JSON-LD says
`bestRating: 5`, on the same page. PPFAS carries `groww_rating: 5` while Groww's
own hidden `analysis` array lists a CONS of *"consistently lower annualised
returns than category average for 1Y, 3Y and 5Y"*. **Store it, never show it as
a rating.**

### 2.3a The gap list this plan has been closing without citing — pass 73

`docs/bachatt-teardown.md`, 701 lines, cited nowhere here. Its middle section
is a fourteen-row table headed *"Behind — and it is not close"*, comparing this
app against the reference implementation. **Several rows are things §2 closed
and reported as discoveries.**

**Closed by the Groww layer, and the teardown is where the gap was named:**

```
5  minimum investment   them: per fund, per frequency, from the AMC, with a
                        swap/drop/redistribute repair loop
                        us:   "flat ₹500 constant"     -> Groww gives min_sip
                                                          and min_lumpsum
6  expense ratio        them: synced per fund
                        us:   "not integrated"          -> §2.3's two-source
                                                          cross-check
7  AUM / fund size      them: synced per fund
                        us:   "nothing"                 -> aum_crore, and §2.3's
                                                          slab-aware cost gate
                                                          depends on it
```

**Still open, and this plan does not mention any of them:**

```
2   normalisation    "pure percentile rank. #1 by 0.1pp scores the same as #1
                     by 8pp" -- theirs is hybrid rank+magnitude
3   return windows   theirs 8 (1m/3m/6m/1y trailing + rolling, 3y); ours 3
4   risk tiers       theirs a 6-tier cross-category score, "built because
                     SEBI's is flat"; ours none
8   market regime    Nifty DMA + P/E + VIX with crash phases; ours nothing.
                     Zero mentions in this document.
14  diversification  max 2 per sub-category, dominance detection, AMC spread;
                     §3.2's overlap is adjacent and is not this
```

**Row 2 is the sharpest and the cheapest.** A percentile rank makes *"first by
0.1pp"* and *"first by 8pp"* the same fact, and §14's own rule is that a value
which moves with an assumption is a range. **A rank that discards magnitude is
that failure in the scoring engine**, and this plan spent no words on it.

🟢 **And its "do not copy" list independently reached §1.1's conclusion, earlier.**

> *"**Expense ratio is synced but not scored.** TER is the most replicated
> predictor of future fund returns that exists. They have the column and do not
> use it. We should."*

That was written before `why_not_returns.py` measured cost at IC +0.184. **Two
routes to the same answer — one from the literature, one from this repo's own
NAV history — and §1.1 cites only the second.**

It also flags what §1.6 later measured: *"27% of the final score is a 14-day
signal… our own research found short-horizon momentum does not survive Indian
transaction costs."* `momentum.py` uses a 250-day lookback with a 21-day skip,
so this app does not make that mistake — **but nothing in this plan says that
was a deliberate avoidance rather than a coincidence.**

### 2.3b Two Groww return fields, decoded — and they are two different facts

Carried as an open item since the data layer was written: `sip_return3y` and
`sipReturn3y` disagree (43.44 against 27.43 on SBI Gold), v5 ships separate
`sip_return` and `simple_return` objects, and the mapping was **inferred from
magnitudes**. Pass 47 measured it against `.navstore/nav.db`, which had the
answer the whole time:

```
                          Groww     NAV-derived
Aditya Birla Large & Mid  47.29        45.83     simple_return.return3y
Axis ELSS                 45.16        44.04       = CUMULATIVE 3y return
HSBC Midcap              102.39       100.76       12 of 12 match

                          Groww     simulated
Aditya Birla Large & Mid   9.75         10.14    sip_return.return3y
Axis ELSS                  7.85          7.48      = monthly-SIP XIRR
DSP Large Cap              5.65          5.50      9 of 9, max gap 0.58pp
```

**These are not two versions of one number, they are two different questions**,
and the gap between them is the point: the same fund is *"up 47% over three
years"* and *"earned you 9.7% a year"*, both true, and the second is the one
that describes what actually happened to somebody paying in monthly. Showing
either alone implies the other.

**So both go on the fund page, labelled, never one standing for both** — which
is §14's rule that a value moving with an assumption is a range, applied to an
assumption most apps do not admit they are making. The disagreeing legacy pair
stays unread.

### 2.3c The manager data this project had concluded does not exist — pass 63

`docs/why-there-is-no-fund-manager-screen.md`, written 2026-08-21 and cited
nowhere here until now, closes a surface on a flat finding:

> *"**There is no free source for who manages an Indian mutual fund.** Checked
> again on 2026-08-21: `api.mfapi.in` — 200, and the response has **no manager
> field at all**; `amfiindia.com` fund-manager details page — **404**;
> `api.kuvera.in` — 200, and the body is **2 bytes**. The reference
> implementation does have manager data. It comes from **60 local `.xls` files**
> … That is not a feed."*

**Six days later the Groww layer closed it, and neither document knew about the
other.** Measured on the cache:

```
39 of 39 payloads carry manager data
  fund_manager          "Sanjay Doshi"
  fund_manager_details[] date_from 2026-03-22, funds_managed[] with 4 schemes
```

Tenure and the manager's other schemes — the two things a manager screen needs
beyond a name — arrive in the same request as everything else. **This plan
supersedes that document on the data question**, and §16.2's `fund_managers`
table is the right shape for it.

🔴 **But that document supersedes this plan on the question that decides whether
to build it, and this plan never asks it:**

> *"This project has measured fund **selection** three times and found it weak:
> 50%, 38%, and most recently 68% over 235 category-years with **three of seven
> years at or below chance**. Cost predicted at 87%. **Manager identity is a
> narrower claim than fund selection and would have to clear a higher bar than
> either.**"*

**§3.4 puts manager tenure on the fund page and offers no evidence it earns the
space.** The data being available is not the same as the answer mattering, and
this project has already measured the broader claim three times and found it
weak. **The refusal in that file was never a data refusal — it was an evidence
refusal, and only the data half has changed.**

**So §3.4's manager line needs one of two things**: a measurement that manager
identity predicts anything, or the same treatment §5 gives every other
unearned surface — shown as a fact about the fund, never as a reason to buy it.
The second is cheap and honest; the first is Phase 2 work. **What is not
available is quietly shipping it because the field is now in the payload.**

> That file's last line is the standard this plan should meet on it:
> *"A screen full of `—` would have been worse than no screen."* The failure
> mode has changed — the screen would now be full — and the question it was
> protecting against has not been answered.

### 2.4 What is honestly still missing

- **SEBI Potential Risk Class, YTM and modified duration** for debt funds. Not
  in Groww (probed for "potential risk", "risk class", "macaulay", "interest
  rate risk" — none present), and 0 of 913 holdings across 14 debt funds carried
  a credit rating. These live only in per-AMC PDF factsheets. **So the open
  defect "debt funds are ranked on equity metrics" cannot be fully closed from
  any free API**, and §6 says what we do instead.
- **G-Sec 10-year yield** — every free route tested was blocked or JS-only.
- **CPI** — needs an own data.gov.in key.
- **Demerger adjustment** — no ratio exists in the corporate-action text.

---
### 2.5 The cost data has a hole the shape of an integer — passes 118-123

**This is the largest single defect this review found, and it sits under the one
thing the product was rebuilt around.** It was assembled over six passes and is
kept here rather than inside a §9.1 cell, where it had grown to 7,700 characters
and stopped being readable.

Cost is this app's method: `validate_cost_ranking.py` is the study that pivoted the product away from past returns, and §1.1 rests on it. **Measured on pass 118 against funds that published a NAV since 2026-08-01:** 1,701 catalogue funds are live, 353 have no row in `expense_ratios.json`, and the gap is not scattered — **23 fund houses are at zero, covering 297 funds**. `Groww Mutual Fund` **37 · 0**, `Union` 31·0, `Mahindra Manulife` 27·0, `PGIM India` 25·0, `Bajaj Finserv` 21·0, `WhiteOak` 21·0, `ITI` 20·0, `Jio BlackRock` 14·0, `Zerodha` 12·0, `Samco` 11·0, `Trust` 10·0, `360 ONE` 9·0. **Every one is an AMC that registered recently**, which points at one line: `build_expense_ratios.py` walks AMFI's AMC ids as `range(1, _MAX_MF_ID + 1)` with **`_MAX_MF_ID = 55`** hardcoded — so an AMC numbered above the ceiling is never fetched.

🔴 **Proven on pass 120 by probing AMFI directly — the endpoint the builder already calls in a loop.** `MF_ID` 56 to 86 return TER rows for **at least 24 fund houses**, every one of them above the ceiling: `58` PGIM India · `61` Union · `62` 360 ONE · **`63` Groww** · `64` Parag Parikh · `67` Shriram · `69` Mahindra Manulife · `70` ITI · `71` WhiteOak · `72` TRUSTMF · `73` NJ · `74` Samco · `75` Bajaj Finserv · `76` Helios · **`77` Zerodha** · `78` Old Bridge · `79` UNIFI · `80` Angel One · `81` Capitalmind · **`82` JioBlackRock** · `83` The Wealth Company · `84` Choice · `85` Abakkus · `86` AlphaGrep. **The ceiling is the cause, not a hypothesis about it.**

🔴 **And the probe found a house pass 118 missed, because the catalogue spells it differently: `PPFAS Mutual Fund` — all seven live schemes, zero TER, including `Parag Parikh Flexi Cap Fund` (code **122639**), among the most widely held funds in India and the one this very document uses as its example URL (`/screener/fund/122639`).** So the app ships a detail page for it and cannot state its expense ratio. **The fix is one line** — raise the ceiling, or better, walk until N consecutive ids come back empty, since 56, 57, 59, 60, 65, 66 and 68 are gaps inside a live range and a fixed number will go stale again. **The builder's own docstring asserts the opposite of what is happening** — *"what does not resolve is mostly ETFs and closed-ended schemes that are not in our universe anyway"* — and it already carries a fix for an earlier version of exactly this failure (*"stopping at the first productive month left whole fund houses uncovered"*). **Consequence:** a fund with no TER cannot be cost-ranked, so the method the product was rebuilt around silently does not reach 297 live funds — including every fund from the AMC of the platform Manan invests through. `tests/test_ter_coverage.py` pins all three facts.

🟢 **Pass 119 swept the whole backend for this class — a hardcoded number that bounds an iteration or a slice — and `_MAX_MF_ID` is the only one that loses data.** Twelve exist. Nine are display caps or retry counts with their reason in a comment beside them (`SIMILAR_SHOWN` 6, `DOMINANCE_TOP_N` 10, `_FAILING_LINES_SHOWN` 3, `_MAX_ATTEMPTS` 3 twice, `_ANNOUNCEMENT_LIMIT` 12, `MAX_GAPS_VERIFIED` 12, `_MAX_PAGES` 12, `_MAX_LOOKBACK_DAYS` 6). `_MAX_RANKED = 120` caps a **stock** ranking and its docstring is explicit that the response reports matched-against-priced *"so a partial ranking never presents itself as the whole market"*.

⚠️ **One near-miss worth stating:** `UNSCORABLE_SHOWN = 200` slices `coverage.unscorable[:limit]` with no field saying the list is partial — the *count* survives, because `universe` and `scored` are both returned, but the type does not carry what `_MAX_RANKED` carries. **And the sweep's first regex missed `_MAX_MF_ID` itself** — it required the bound word after the first letter — which is why it was re-run rather than trusted.

🔴 **Pass 121 followed it into the scorer, and the harm is sharper than a missing number.** `fund_score._pillar_inputs` scores a fund with no TER as **`_NEUTRAL = 0.5`** — median cost — and **`cost` is the only pillar that substitutes anything; `share`, `worst`, `vol` and `dd` all keep `None`.** That substitution is deliberate and well-argued in a comment beside it: *"Cost is the majority of the score and the only pillar with measured predictive power, so a fund AMFI files no TER for is scored neutral on it rather than having the pillar dropped. Dropping it would rank that fund purely on inputs we know do not predict, and let it climb above funds we can actually measure."* **The reasoning is right. Its premise is now false.** **AMFI does file for these funds** — pass 120 read their filings at `MF_ID` 63, 64, 77 and 82. So a mitigation written for genuinely unfiled schemes is currently absorbing **297 funds where the filing exists and our builder never fetched it**, and it absorbs them *invisibly*: 0.5 is indistinguishable from a measurement, so §14's *`n/a` when unmeasured, never `0`* never fires. **`Parag Parikh Flexi Cap` is scored as an average-cost fund** on a screen whose whole argument is cost. **Fixing `_MAX_MF_ID` fixes the scoring too** — and the neutral fallback should stay, for the funds AMFI really does not file.

🟢 **Pass 122 measured how much of this actually reaches a ranking.** Of **1,612** live funds in the 37 browsable categories, **333 have no AMFI TER, and 151 of those are old enough to be scored** — so **9% of the ranked universe carries a fabricated median cost**. It is not spread evenly, and it is worst where cost is nearly the whole decision: **`Debt Scheme - Liquid Fund` 13 of 37 scored funds · `Equity Scheme - ELSS` 10 of 37 · `Equity Scheme - Flexi Cap Fund` 10 of 35 · `Debt Scheme - Overnight Fund` 9 of 34**. A liquid fund returns 6-7% and its TER spans roughly 0.10-0.35%, so **cost is most of what separates one from another** — and a third of that category is ranked without it.

⚠️ **What pass 122 could NOT establish: the direction.** Whether these funds are cheaper or dearer than the median they are given decides whether the app under- or over-recommends them, and **two attempts to measure it were both wrong**: AMFI returns **one row per scheme per day**, so a first pass read one fund thirty times as thirty funds; and comparing one hybrid scheme against a whole-table median mixes categories that are not comparable.

🟢 **Pass 123 measured it properly, after finding why the first attempt failed: the builder sends `Month=MM-YYYY`, and the probe had sent `2026-07`.** With the builder's own call, `MF_ID=63` returns **1,200 rows**, which by itself proves the ceiling is the only thing between this app and Groww's filings. Deduped to distinct open-ended schemes: **Groww 40 · Zerodha 21 · JioBlackRock 14 · Parag Parikh 7 — 82 schemes, all fully available.** Comparing their direct TER against the funds we do have, **within category**, on the three categories where AMFI's `SchemeCat_Desc` joins ours: `Other Scheme - Index Funds` **+0.01pp** (n=7 vs 306), `Index Funds - Equity Funds` **−0.08pp** (n=6 vs 8), `Other Scheme - FoF Domestic` **+0.08pp** (n=3 vs 99). **No systematic direction, on samples too small to settle it** — so the neutral substitution is not a one-way bias across the group. **That does not rescue it for an individual fund**, which is the only unit a user compares: a real TER is replaced by the category median, and two funds that genuinely differ on the one axis this product trusts are shown as identical on it. (The repeated-row shape does confirm the builder's own design — it keys on the normalised scheme name and keeps the newest `TER_Date`, which is exactly the dedupe this data needs.)


**The fix, specified — pass 131.** The ceiling is not merely too low; a fixed
number is the wrong shape, because AMFI assigns ids as AMCs register and any
constant goes stale the same way this one did. Probed today:

```
live AMC ids          1 … 86        86 is the highest that returns data
empty inside range    56 57 · 59 60 · 65 66 · 68     largest interior gap: 2
empty above 86        87 … 110      24 consecutive, checked
current ceiling       55            misses 31 ids and at least 24 fund houses
```

**So the rule that survives the next registration is: walk until eight
consecutive ids return nothing.** Eight is four times the largest gap ever
observed inside the live range, and today it would stop at 94 — nine wasted
requests per month against a run that already makes hundreds. A raised constant
would work this year and fail silently the year an AMC registers above it,
which is exactly the failure being fixed.

⚠️ **Two things must go with it.** The builder's docstring claims what does not
resolve is *"mostly ETFs and closed-ended schemes that are not in our universe
anyway"* — that sentence is false while 297 live open-ended funds are missing,
and it is what made the gap invisible to eleven passes. And the run should
**report its coverage**: houses found, schemes matched, and schemes in the
catalogue with no TER, so the next hole announces itself instead of waiting to
be measured.

## 3. The product

Today there are six screens organised by data type — Portfolio, Goals,
Research, Screener, You, Decide — one of which renders 1,700 funds as a
**32,456px** table. The reorganisation is by **decision**, not by data type.

### 3.0 Getting the portfolio in — the screen the plan did not have

🟢 **The screen exists, and pass 107 found it by opening the four components this
section never names.** `Portfolio.tsx` has an `EmptyState()` that renders
`StartHere.tsx` (141 lines), and that file's own comment is this section's
argument, reached independently:

> *"A new account landed on an empty holdings table and a button saying 'add a
> fund'. That is the most work for the least money. Somebody earning ₹24 lakh who
> has drifted onto the old tax regime is leaving ₹2.45 lakh a year on the table,
> and answering that takes two fields — but the page led with the task that takes
> an afternoon. So the order here is the order the levers list uses."*

**So the undesigned-empty-state half of this section is shipped**: the first
three actions are ordered by what each is worth, the two-field tax question
leads instead of the afternoon-long import, and the tax step reprices itself in
rupees once income exists. **This is the sixth time a section here has argued
for something the repo already did** — after `fund_ter_history`,
`/portfolio/overlap`, §14's response contracts, §3.2's table, and §3.3's
pagination.

**What is genuinely still open in this section is the typing, and only that.**
Measured off the components: `AddHoldingDialog` is 3 fields and a submit
(Type · Name via `FundPicker` · NSE ticker), `AddTransactionDialog` is 4 and a
submit (Type · Date · Units · price or amount) — so **≈4.6 interactions per
fund, which is where the *23 with five funds* figure comes from and it holds.**
Closing it needs the two things this section proposes that do *not* exist:
**CAS import** (`casparser`, still not installed — pass 95) and **the SIP
entered as a rule that expands to lots**. The missing-instalment problem is real
and untouched either way.


A product review put this first, and it is right: **§11.7 calls manual entry the
biggest risk and then treats it as a data-quality problem. It is the primary
interface, and it was undesigned.**

Walk it as it stood. To see anything, Manan must find each fund in a 1,686-row
list, decide Direct or Regular himself (the app cannot infer it — code 118955 is
Direct despite its name), and type a FIFO lot per purchase. **A three-year SIP is
36 rows.** Two SIPs and four lumpsums is roughly 80 rows of typing before the
first pixel of value.

And the check §11.7 proposes cannot catch the error that will actually happen.
Rebuilding implied NAV catches a *wrong* date. It cannot catch a **missing**
instalment. So within two weeks of ordinary Groww activity, XIRR is quietly
wrong in an app whose entire pitch is numbers you can trust — and one caught
error inverts that pitch permanently.

**So the order changes.**

1. **CAS import moves into slice 1.1** (§7), ahead of the universe work. The consolidated CAMS/KFintech statement
   arrives by email as one PDF and carries every folio and every transaction;
   ⚠️ **`casparser` is not installed and is not in `requirements.txt`** — checked
   on pass 21 by importing it (`ModuleNotFoundError`). It appears in this
   document and nowhere else in the repo. That does not make the choice wrong,
   but slice 1.1 is priced at 2 sessions as though the library were present, and
   CAS files are password-protected PDFs in several formats needing a PDF
   backend. **Read "if he wants it" as a genuine sub-project, not a switch.**

   `casparser` (222★, MIT) parses CAMS, KFintech, NSDL and CDSL. One upload
   replaces eighty rows of typing and removes the missing-instalment failure
   entirely. It was filed under "his call, later" — it is the thing that makes
   the other 1,531 rankable funds worth ranking.
2. **If CAS is genuinely off the table, manual entry gets designed rather than
   assumed:**
   - **A SIP is entered as a rule, not as instalments** — fund, amount, day of
     month, start, end — and expands to lots. Thirty-six rows become five fields.
   - **Plan type is a two-option chip he confirms**, resolved from the scheme
     code and shown, never silently inferred. §11.7 calls this the largest
     single number the app will ever show him.
   - **"Last reconciled" is per holding, on the row**, not one global date.
3. **Groww reconciliation (§11.7 check 3) is the acceptance test for step 0**,
   not a nice-to-have — it is what turns entered data into checked data.

Until a portfolio exists, `Today` shows one thing: the shortest path to one true
statement about his money. In practice that is the tax-regime answer, which
needs only his income and is the largest verified number in the app.

### 3.1 `Today` — the home screen

🟢 **Measured against `Portfolio.tsx` on pass 102 — the levers row is done, the
teaching moment is not.** `Levers.tsx` is 92 lines and already carries all three
things a row is specified to have: **the rupee value, how we know, and when to
look again.** The page already renders the total and `portfolio_xirr`.

🔴 **What is genuinely absent is the one thing this section argues hardest for:
today's move next to its own base rate.** Neither appears on this page — the two
`today` matches in the file are comments, one of them recording a *different*
fix (the live price was fetched, used for every figure, and never shown; it is
shown now, with its date). **But `BaseRatePanel.tsx` already exists** and renders
on `FundAnalysis` and `Decide`. So the strongest asset in the product, by §1.4's
own account, is built and merely absent from the screen that needs it: **this is
composition, not construction.**

🔴 **And a risk this section creates by how it is written.** It opens *"Replaces
the current Portfolio landing"* without saying what the current landing does.
That page already carries three honesty states nothing here mentions:
**`misnamed_as`** — the holding that names one fund and analyses another, the
defect `nextrade-name-vs-code` exists for — **`stale_days`** (*"Priced from a NAV
of …, which is N days behind your other funds. This value is not current."*), and
**`price_error`** (*"Live price unavailable, so this is left out of the
returns"*). **A replacement written from this section alone would drop all
three**, and each is the kind of warning §14 exists to protect. They belong in
slice 4's acceptance as things that must survive, in the same way
`AllocationPie` is named as a thing that must go.

🟢 **Pass 103 swept every page for the rest of this class, and there is no
fourth.** Twenty files carry an honesty or absence state; the ones a rewrite
could silently drop — `misnamed_as`, `stale_days`, `price_error`, `unscorable`
— are now all named in this document. The same sweep **found pass 90's finding
to be false**: `Research.tsx` does disclose its excluded funds, and that row is
corrected in §9.1 rather than softened. `rankable` and `nav_points_available`
run the other way — named here, computed by the API, rendered nowhere — which
belongs to the eighteen-field item, not this one.


Replaces the current Portfolio landing. Order is by how much money each row is
worth, which is the levers engine's existing job.

```
┌ Your money                                    ₹2,47,827   XIRR +9.4%      ┐
│  Inter Tight 2.75rem/500, brand colour — NOT sentiment-coloured.           │
│                                                                            │
│  The second figure is XIRR, not lifetime gain. Lifetime gain grows with     │
│  every deposit and therefore always flatters; it was the largest number on  │
│  an earlier draft of this screen and it is the least decision-relevant one  │
│  in the app. If a rupee gain is shown at all it carries its period.         │
│                                                                            │
│  Today's move IS here — small, low contrast, and next to its own base rate: │
│      "−1.4% today · days this bad or worse: 31% of days for this mix"       │
│                                                                            │
│  An earlier draft hid it entirely on §1.3's evidence. That evidence is      │
│  about trading VOLUME, not about seeing a number, and hiding it does not    │
│  stop him seeing it — Groww is on the same phone and leads with exactly     │
│  this figure, next to order buttons. Withholding it forfeits the app's best │
│  teaching moment and hands the session to a broker. §1.4's base rates are   │
│  the strongest asset in the product and this is precisely when they matter. │
└───────────────────────────────────────────────────────────────────────────┘

┌ Do these — ranked by what each is worth over your horizon ────────────────┐
│  Every row: what to do · what it is worth in rupees · how we know ·        │
│  when to look at this again. Already built (`advisor/levers.py`).          │
│  A trade is never sorted among them. A gate is not a lever.                │
│  "Pick the best-performing fund — ₹0" stays, because the zero is the       │
│  finding.                                                                  │
└───────────────────────────────────────────────────────────────────────────┘

┌ Running out ──────────────────────────────────────────────────────────────┐
│  Dated, bounded, and different every month by construction:                │
│    "₹1,25,000 of tax-free gain unused · 7 months left · worth ~₹15,600"     │
│    "80C: ₹40,000 unused"      "SIP debits ₹15,000 on the 5th"               │
│                                                                            │
│  This module replaces "What changed since you last looked", which a         │
│  product review correctly called empty by design: three of its four        │
│  triggers are rare and the fourth ("a holdings disclosure updated") means   │
│  nothing to a user. Its one real trigger — a cheaper fund appeared — belongs│
│  in the levers list, where it is already priced.                           │
│                                                                            │
│  Indian retail investing has a hard calendar: 31 March, ITR season, SIP     │
│  debit dates, goal dates. Gain harvesting is annual and use-it-or-lose-it,  │
│  worth roughly ₹15,600 a year, and it appeared on no screen in an earlier   │
│  draft. These are arithmetic on data already held, and they are the only    │
│  honest reason to reopen the app in month two.                             │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.2 `Holdings` — with the look-through underneath

Two tabs over the same money.

**Your funds** — columns in the order they are worth reading:

```
name (pinned)  ·  badge  ·  value  ·  XIRR
```

The **badge is second**, not fifth. It is the only column that says do-something,
and behind a pinned name column at laptop width the fifth column may be off
screen entirely. **Gain/loss moves into the expansion** — it is the column that
duplicates Groww, and by §1.3's own logic it is the one that should not lead.

Default sort is by the badge's rupee value, so the row worth acting on is at the
top. Grouping is off by default and available by category or by goal.

🟢 **Whether this is a table at all was settled in code, and pass 100 looked.** `Portfolio.tsx` — the file the surface map puts behind this surface — already renders `TableRow`/`TableCell`/`TableBody` from the shared `ui/table` component, and composes zero `Card`s. **The question below was open in this document and closed in the repo**, which is the same shape as `fund_ter_history` (pass 26) and `/portfolio/overlap` (pass 33). Measured against that file, this section's genuinely new work is **six interactions, not a screen**: tabs, a pinned name column, the badge column, sort by badge value, row expansion, and grouping — none of which exists. **What already exists is more than the prose assumes:** XIRR renders at lines 70 and 157, and the page already composes `CostReview`, `FundOverlap`, `Levers`, `PortfolioChart`, `Announcements` and `StartHere` — the machinery §3.1 and §3.2 both discuss as though it were ahead. The original note is kept below because the reasoning in it is still the right reasoning; only its premise moved.

⚠️ **The original note, retained.** "A table, not cards" was
inherited from the screener problem, where 1,700 rows made it obvious. Here
there are perhaps twelve rows each carrying a one-line reason, which is a
different shape, and the decision is deferred to §13's density call rather than
assumed here.

The verdict vocabulary is deliberately not Buy/Sell:

**One column, one grammar, and a number wherever there is one.** An earlier
draft had seven badges in six different grammatical shapes — an adjective, a
claim, a relation, a metaphor, a past-tense verb, an event — which a reader has
to *read* rather than scan, in a column that gets under a second of attention.

| badge | fires on | why it earns the column |
|---|---|---|
| **`₹5,000/yr cheaper elsewhere`** | a cheaper **active** fund in the same sub-category, net of switching cost | cost is the only measured signal, 43 of 52 windows. The rupee goes **in the badge**, not in the expansion |
| **`Cheaper option won't pay back`** | same test, breakeven beyond the horizon | a different verdict, so a different badge — not the same one with softer text |
| **`Regular plan — Direct saves ₹X/yr`** | plan type resolved from the scheme code | mechanical, certain, typically 0.6–1.2pp/yr. **This was missing entirely** and §11.7 calls plan type the largest single number the app will ever show him |
| **`41% the same as <fund>`** | ISIN overlap above the fixed threshold, same disclosure month | states the relation *and* its size |
| **`Drifted from <category>`** | holdings no longer match the category label | names what it drifted from, so the word means something |
| **`Too new to rank`** | under a year of NAV history | Value Research's `Unrated` pattern |

**No `Fine` badge.** It was the default, so it would have filled most rows with
zero information. **Blank is the default**; ink appears only where something
fired.

**Two things left the column.** `Manager changed since you bought` moves to the
fund page and the `Running out` feed — it is an observation with no action
(§5.6), and a verdict column is not where observations belong. `Concentrated
through the back door` moves to the look-through view as a plain fact with its
number — **`Reliance: 8% of your equity`** — because §5.2 refuses to treat
concentration as a risk trigger, and a badge whose own plan says it recommends
nothing is spending the most expensive attention in the product on a shrug. The
old label also editorialised: "back door" implies wrongdoing that §5.2 says the
evidence does not support.

**Precedence, because the most likely portfolio fires three at once.** An
expensive, overlapping large-cap trips cost, overlap and drift together. One
primary badge, ranked **by rupees at stake** — the levers engine already does
exactly this ranking and is reused — with a `+2` affordance and the full set in
the expanded row.

🔴 **The cost badge inherits §2.3's rule and must restate it.** "A cheaper fund
in the same sub-category" is incomplete: 70% of Groww's "Large Cap" are index
trackers, so without the active/passive split every active fund gets told it is
expensive against a Nifty tracker. **Active compares to active.** §2.3's error
re-entering through the front door is exactly how a rule that was fixed once
comes back.

There is no badge for "underperforming". §1.1 is why, and the screen says so.

**Two of the seven are deliberately inert, and the screen says that too.**
`Concentrated through the back door` reports a look-through fact and recommends
nothing, because §5.2's evidence runs against concentration limits as a risk
trigger. `Manager changed since you bought` is a flag with no action, because
§5.6 found no confirmable literature either way. A vocabulary that replaces
Buy/Sell has to be honest that two of its entries are observations rather than
verdicts — otherwise the reader discovers it four sections later and stops
trusting the other five.

#### The overlap threshold is measured, not chosen

The first draft of this plan said "≥30%". That was a number I picked. Measured
instead, across 595 comparable pairs (35 equity funds, 7 categories, all sharing
the 2026-07-30 disclosure date):

```
all pairs        median 12.3%   p75 22.9%   p90 32.4%   max 99.8%
same category    median 20.4%   p90 36.4%
cross category   median 11.4%   p90 31.0%
```

30% is unremarkable inside a category and near the p90 across categories, so one
constant would have been simultaneously too loud and too quiet.

**But a percentile is the wrong form too, and for a worse reason: it guarantees
a fixed alarm rate forever.** Fire above the p90 and 10% of pairs always fire,
whether or not any duplication is real — a five-fund portfolio has ten pairs, so
roughly one permanent alarm by construction. The sample is also thin: 595 pairs
across ~28 category-pair cells is ~21 observations per cell, so each "p90" is
essentially the second-highest of twenty-one, and it would move on every rebuild
with no change to the user's holdings.

> **A fixed threshold, calibrated once from the measured distribution, and
> different for the two cases:** `same category ≥ 40%`, `cross category ≥ 30%` —
> both above their measured p90 (36.4% and 31.0%) so the base rate is under 10%
> and falls as the sample grows, rather than being pinned at 10% forever.
> Recalibrate only deliberately, with the old and new numbers both recorded, and
> require **n ≥ 50 per cell** before trusting any future recalibration.
> Hysteresis on top: once fired, the badge clears only below threshold − 5pp, so
> it cannot flicker on a rebuild.

Note the boundary reads correctly this way round: two Large Caps at 35% stay
silent (same-category overlap is normally 20%) while a Large Cap / Mid Cap pair
at 32% fires (cross-category is normally 11%). A single constant inverts that.

And the highest pair in the sample — **99.8%, 50 common names, SBI vs UTI Large
Cap** — is not a finding at all. Both are Nifty index funds. Which is why active
and passive are never compared (§2.3): without that rule the loudest thing this
feature would ever say is a false alarm.

#### The cost badge is not actionable on its own, and this is the fix

`Costs more than it needs to` is the app's strongest signal — cost is the one
thing measured to work, 43 of 52 windows. But as a badge it is **incomplete to
the point of being misleading**, because switching funds is not free:

```
sell the expensive fund   →  capital gains tax
                             LTCG 12.5% above ₹1.25L/yr if held >12 months
                             STCG 20% if held ≤12 months
                          →  exit load, if inside the window
                             (Groww gives this as text per fund, and as a
                              dated history in v5's historic_exit_loads)
buy the cheaper fund      →  the TER difference, per year, on the balance
```

An app that says *"this fund costs 1.0pp more than a peer"* and stops has told
the user half a fact.

**And the obvious way to complete it is also wrong.** A first draft of this
section charged the full capital-gains bill against the switch — ₹9,375 on a
₹2,00,000 unrealised long-term gain — and concluded "two-year payback". That
treats deferred tax as a sunk cost, and it is not one:

- **Exit load is a true cost.** The money leaves and never comes back. Groww
  supplies it per fund, and `historic_exit_loads` in v5 gives the dated history.
- **Capital-gains tax on a switch is mostly a *deferral*.** The cost basis
  resets, so the same gain is not taxed twice — sell A today and the tax you pay
  is tax you would have paid on exit anyway. The real cost is only the **return
  forgone on money paid early**, over the remaining horizon.
- **And the first ₹1.25 lakh of the gain costs nothing at all.** The exemption
  is annual and use-it-or-lose-it; realising into it is the gain-harvesting move
  this repo already records as worth ~₹15,600/yr. Charging it as a cost is
  charging for something the user should be doing regardless.

Charging the gross bill **overstates the cost of switching**, which pushes the
badge toward `Leave it` — in the one place §1.1 says the app has a real,
measured signal. That is the expensive direction to be wrong in.

So the badge carries **four numbers**, and the tax line is a deferral, labelled:

```
  saves            ₹5,000 a year at today's balance   (1.0pp on ₹5,00,000)
  exit load        ₹0        real cost, gone           (past the load window)
  tax brought
   forward         ₹9,375    NOT a cost — the basis resets. ₹1,25,000 of the
                             ₹2,00,000 gain is exempt this year anyway; the
                             cost is the return forgone on ₹9,375, ~₹1,125
                             a year at your assumed 12%
  breakeven        under a year on the real cost  ·  your horizon is 12
```

All of it is arithmetic on data we hold — `portfolio/fifo.py` supplies the lot
ledger, the LTCG constants are verified current (§10), Groww supplies the exit
load. **Nothing here is a prediction.**

⚠️ Two constraints the arithmetic must respect. The ₹1.25 lakh exemption is
**annual and shared across all equity gains**, so it cannot be spent per-holding
— the engine allocates it across the year's realised gains or every row
overstates its saving. And §10 now **confirms** against the Income Tax
Department's portal that the exemption is a **Section 112A** provision covering
equity shares and equity-oriented funds only — gold, debt-oriented and
international funds sit under Section 112, which has no such threshold. So this
arithmetic runs for equity, and does so on a sourced rule rather than a cautious
guess.

And when the breakeven exceeds the horizon, the badge must say **`Leave it`** —
an app that recommends a switch which does not pay back inside the user's own
horizon is doing the thing §1.2 says destroys returns.

⚠️ The ₹1.25L exemption is **annual and shared across all equity gains**, so it
cannot be applied per-holding. The engine has to allocate it across the whole
year's realised gains or the saving is overstated on every row — the same class
of error as the original tax lever showing every user the full regime gap.

**Your companies** — the look-through. (Named "Your funds" / "Your companies"
because "As you hold it" and "What you actually own" are near-synonyms to
anyone who is not a professional.)

🔴 **And the flagship number needs a reference class, which an earlier draft
omitted.** *"₹1,00,000 into equity funds; ₹90,945 reached equity"* has no
denominator — in a plan that mandates reference-class-before-specific-case
(§3.3, Kahneman and Lovallo) and whose §13.5 bans "a progress bar with no
denominator". Around 9% cash is ordinary; without saying so the number reads as
either an indictment or as nothing. It ships as:

> *"₹90,945 of your ₹1,00,000 reached equity. Funds hold cash for redemptions;
> 5–10% is normal."*

Same for concentration. The company table caps at ten and carries a calibrating
comparison the data already supports:

> *"Your top 10 are 42% of your equity. The Nifty 50's top 10 are 57%."*

That turns a fact into a bearing, which is what a non-professional needs from
it. A sorted horizontal stacked bar
(not a pie — real weights should be comparable, not guessed from angles), then a
table of companies with the rupee amount, the share of total equity, and which
of your funds hold each. Plus the line nobody else prints: *"₹1,00,000 into
equity funds; ₹90,945 reached equity."*

### 3.3 `Find` — a finder, not a dump

🟢 **Measured against `Screener.tsx` on pass 101, and most of this section already
ships.** The surface map puts `Find` behind that file — 2,012 lines, the largest
in the app. What it already does: **category-first selection** (52 references),
**a stated reason per fund** (26), **facets** (36), **sorting** (70), a real
table, and **coverage including `unscorable`** (51) — the last being the very
thing pass 90 found `Research.tsx` throwing away, done correctly here.

🔴 **And the volume problem this section proposes solving was solved already, a
different way.** §3.3 asks for virtualisation behind *"a deliberate click"*, and
slice 4.2's acceptance is *"1,686 rows scroll without dropping frames"*. The
file paginates at `PAGE_SIZE = 100`, and the comment above it says why:

> *"1,689 rows across 21 columns is forty thousand nodes; the page stops
> responding and the accessibility walk times out. A hundred at a time is the
> whole reason this view is usable."*

**So the acceptance criterion presumes a design this codebase deliberately
rejected, for a reason it wrote down** — and the a11y timeout in that comment is
the same `a11y.mjs` §13.11 counts as a real gate. Two consequences. **The open
item about `@tanstack/react-virtual` and `@tanstack/react-table` not being
installed changes question**: not *"when do we install them"* but *"do we need
them at all"*, and the answer costs two dependencies and a rewrite of the one
view that already works. **And what is genuinely left in this section is two
things, not a screen:** overlap-at-the-moment-of-choosing, which §3.3 itself
calls the largest missed move and which is **absent from the file** — and a
compare tray, also absent (its single `compare` match is a tooltip about
valuation peers). The *"32,456px table"* this section opens by deleting is
already deleted.


The 32,456px table is deleted. Replaced by:

- **Category first.** Pick a sub-category, get the ≤8 cheapest with a stated
  reason, and a sentence saying #1 and #5 are the same decision.
- 🔥 **Overlap against what he already owns, at the moment of choosing.** This
  is the single largest missed move in an earlier draft: look-through sat on
  Holdings, where §5.2 refuses to make concentration actionable, so the plan's
  most distinctive capability was inert by construction. **§1.2's evidence is
  about selling. It says nothing against declining a redundant buy.** So the
  money-relevant moment is here — he opens a Flexi Cap and the row says:

  > *"41% the same as the Large Cap you already hold — of ₹50,000, about
  > ₹29,500 would be new exposure."*

  Forward-looking, evidence-safe, costs nothing, and changes a real decision.
  Find had no connection whatsoever to his holdings before this.
- **The full universe behind a deliberate click**, and when opened it is
  virtualised (`@tanstack/react-virtual` 3.14 + `@tanstack/react-table` 9.2 —
  versions checked live today, ⚠️ **and neither is in `package.json`** — pass 29
  checked. "Versions checked live" confirmed they exist on npm; nobody checked
  whether they exist *here*. The frontend has **26 dependencies and no
  virtualisation library and no table library at all**. Same shape as
  `casparser` in §3.0: a named, versioned dependency priced into an estimate and
  not present. Slice 4.2 is 3 sessions and its acceptance is "1,686 rows scroll
  without dropping frames" — that starts with two installs and a first
  integration, not with styling), sticky header, name column pinned with
  TanStack's inset-shadow recipe, faceted filter chips, density toggle.
- **A compare tray** — select 2–4, get the same metric rows side by side.
- **Base rates on the category, before the list.** Reference class first, then
  the specific case (Kahneman & Lovallo; the UK Green Book mandates the same
  ordering).

### 3.3b Is look-through worth building? Measured, not assumed — pass 135

§3.3 calls overlap-at-the-moment-of-choosing *"the single largest missed move"*,
and §9.1 listed *whether it is worth building at all* among the three things only
Manan's real portfolio could settle. **It is answerable now.** The 39 cached
Groww payloads give 39 funds with fifteen or more named holdings, and every pair
of them can be compared by weight on shared company names:

```
741 pairs        median weight-overlap  11.8%      mean 15.1%
                 above 10%   426 pairs   57%
                 above 20%   213 pairs   29%
                 above 40%    25 pairs    3%

the extremes, which are the argument
  99.8%   50 names   UTI Nifty Next 50 Index   /  SBI Nifty Next 50 Index
  68.6%   38 names   DSP Large Cap             /  ICICI Prudential Large Cap
  65.1%   40 names   ICICI Prudential Nifty    /  ICICI Prudential Large Cap
```

**So the answer is yes, and it does not depend on what he owns.** Nearly a third
of arbitrary pairs already share a fifth of their weight; two funds tracking the
same index are **the same fund twice**, and the third line is one house's active
and passive products at two-thirds identical. **A portfolio has to be unusually
lucky to avoid this**, which is the opposite of the assumption that made it a
blocked question.

⚠️ **What this measurement is not.** 39 funds, all equity, matched on
**company name** rather than ISIN — the real path parses ISIN out of AMC
disclosure spreadsheets (`fund_holdings.py`), and Groww's own payload carries no
ISIN at all, which is why the cache cannot be used for the production join.
Name-matching will merge two listings of one company and miss a renamed one, so
these figures are a **shape**, not the numbers a screen would print. The shape is
enough to settle *whether to build it*; slice 2.3's pull settles the rest.

### 3.4 Fund page and Company page

🟢 **Measured on pass 108, and this is the first §3 section that comes back
genuinely additive.** `FundAnalysis.tsx` (751 lines, `/screener/fund/:code`) and
`StockAnalysis.tsx` (611, `/screener/stock/:ticker`) both ship. What is already
there: **fund vs category rank** (11 references), the **NAV chart** (18), **base
rates** (4) — and on the company page, **sector** (19) and its own chart (13).
What this section asks for and is genuinely absent: **TER as a time series**,
**manager tenure**, and **holdings with sector on the fund page**.

⚠️ **Two precisions.** The horizons here are **1y and 3y, not 1y/3y/5y** — the
first two render (lines 421, 569-576, 633) and **5y does not exist**, so asking
for three is asking for one more. And `StockAnalysis.tsx` carries none of the
fund-side items, which is correct, but it is also **one of the six pages this
document never names** — the page that renders the very score §3.5 and §1.5b
argue about.

**All seven §3 sections have now been measured against what they land on, and
the split is not random — it is exactly where the app already exists.**

```
§3.0  the on-ramp screen      SHIPPED     StartHere.tsx makes the same argument
§3.1  Today                   PART        Levers.tsx complete; BaseRatePanel exists elsewhere
§3.2  Holdings                SHIPPED     already a table; the deferred decision was taken
§3.3  Find                    MOSTLY      pagination already solves the volume problem
§3.4  Fund and Company page   ADDITIVE    TER series, manager tenure, sector holdings absent
§3.5  Ask                     NEW         no chat surface, no /ask route, no tool registry
§3.6  Why                     NEW         no /why route; the word appears only in prose
```

**Four of the seven found work already done. The other three are the three that
map to nothing** — `Ask` and `Why` have no page at all, and §3.4 adds to pages
that exist. **So the over-estimate is concentrated precisely where the repo
already had something**, which is what a plan written without opening the repo
would look like, and it is the opposite of how §7's 34 sessions were framed.
**Pass 108 stated this as "four out of five" from a sample that had not yet
measured `Ask` or `Why`; four of seven is the honest figure and the sharper
one.**


Keep the Groww information architecture already matched in
[[traa-detail-pages]], and add what Groww has but does not show:

- **TER as a time series** — and the real shape, not Groww's label for it.
  PPFAS returns **1,166 rows, 1,138 distinct dates**, 2013-10 to 2026-08:

  ```
  2013:  3    2014-2021: 12 a year  (MONTHLY)
  2022: 38    2023: 130    2024: 336    2025: 325    2026: 237
  ```

  The payload's `frequency` field says `"Daily"`. It is monthly for the first
  eight years and daily only from 2024 — a genuinely daily series over that span
  would be ~3,343 rows. This was the one place an earlier draft repeated a Groww
  self-description as measured fact, inside a section built on distrusting
  Groww's numbers. **The feature survives at a twelfth of the advertised
  resolution:** "has this fund got more expensive?" is still answerable back to
  2013, and the pre-2022 tail renders as steps rather than a line, because a
  line implies daily observation that does not exist. Dedupe by date first —
  fourteen dates repeat, `2022-02-28` three times.
- **Fund vs category vs rank** from `stats`, at 1y/3y/5y.
- **Manager tenure**, with the date the current manager started marked on the
  NAV chart — so "whose record is this?" is visible rather than argued.
- **Holdings with sector**, and the overlap against everything else you own.
- Every ratio against its own sector median, with `lower_is_better` known per
  ratio — already built.

### 3.5 `Ask` — the chat, and the exact list of what it can do

Architecture in §4. It answers from tools or it declines, and it holds no
opinion the deterministic engine does not already hold. What makes that
enforceable rather than aspirational is that **the tool registry is the whole
capability surface** — if a question cannot be answered by composing these, the
answer is "I cannot compute that", not prose.

**The registry.** Every one is a pure function over data we hold; none calls a
model; none writes anything.

```
resolve_fund(name)              -> scheme_code + the exact fund it matched
resolve_stock(name)             -> symbol + ISIN
                                   ^ nothing else takes an identifier as a
                                     first-class input (§4.3)

holdings()                      -> what you own, units, value, XIRR per holding
holding_history(scheme_code)    -> your transactions in one holding
portfolio_xirr()                -> money-weighted return, whole portfolio
benchmark_compare(index)        -> the same money, same dates, in the index

fund_facts(scheme_code)         -> TER (both sources, and whether they agree),
                                   AUM, manager + tenure, benchmark, exit load
fund_cost_rank(sub_category)    -> the cheapest N in a peer group, active or
                                   passive stated separately (§2.3)
fund_ter_history(scheme_code)   -> the series, with its real resolution (§3.4)
base_rates(sub_category)        -> losing-window shares by horizon, worst fall,
                                   recovery time, in rupees on your amount

overlap(code_a, code_b)         -> BOTH: monthly-return correlation, and
                                   ISIN-level holdings overlap (same disclosure
                                   month or it refuses). Never one alone.
look_through()                  -> every company you own through funds, weighted
company_exposure(symbol)        -> which of your funds hold it, and how much

tax_regime(income, deductions)  -> both regimes, the bill, and where it flips
switch_cost(scheme_code, to)    -> exit load, tax brought forward, breakeven
levers()                        -> the ranked list `Today` already shows
track_record()                  -> what this app has measured about itself
```

**What it answers well**, because these are lookups and arithmetic:

- *"What am I actually paying across everything?"*
- *"Which of my funds are the same bet?"* → `overlap` over every holding pair,
  reporting correlation and shared names separately because they disagree in
  informative ways
- *"How much Reliance do I own?"* → `company_exposure`, the question no Indian
  app answers
- *"If I move out of X into the cheapest in its category, what does that cost
  me today and when does it pay back?"* → `switch_cost`
- *"Has this fund got more expensive since I bought it?"* → `fund_ter_history`
- *"What has this kind of fund done to people before?"* → `base_rates`
- *"Old regime or new?"* → `tax_regime`

**What it refuses, and the refusal is specific rather than a disclaimer:**

| asked | answer |
|---|---|
| "Which fund will do best next year?" | Names the measurement. §1.1, with the number, and offers the cost ranking instead. |
| "Should I sell X, it's down 12%?" | Refuses the premise. Cites §1.2 — professionals sell worse than randomly — and offers the mechanical checks on X instead. |
| "What will the market do?" | No tool returns a forecast, so there is nothing to narrate. |
| "Is this a good stock?" | Sector-relative facts, and the stock score's own measured record — **+10.6% on NIFTY 500, −5.0% on NIFTY 50, mean IC −0.084**, over two years each. *"A result that reverses sign when you change the index is not a signal."* **And the answer says out loud that 13 of the score's 100 points have never been tested at all**: `dividend_yield` is passed as `None` and `promoter_history` as empty in every observation, so the promoter-stake adjustment — the model's own docstring calls it the cheapest read on India's dominant equity risk — has no measurement behind it. No verdict. |
| Anything about a fund not in the universe | `resolve_fund` returns not-found and the chain stops there (§4.3, tested). |
| "How much should I put in?" | Position sizing is not computed anywhere. Univest refuses this too and says so; so do we. |

**The registry is a menu, so the screen shows it.** An earlier draft rendered
all of this as a blank input, which means the refusals above are discoverable
only by asking and being told no — the most expensive way to learn a boundary,
and after two refusals a person stops asking. Combined with "no proactive
messages", the screen had no affordances at all.

So `Ask` opens with **six chips generated from the registry against his actual
holdings** — *"How much Reliance do I own?"*, *"What am I paying across
everything?"*, *"If I move out of X, when does it pay back?"* — and the refusal
list is **published on the screen as a list**, not sprung at runtime. A menu is
not a proactive message and does not touch §1.3's evidence.

**Two interface rules that follow from the evidence, not from taste.**

Every answer shows **the tool calls it made**, collapsed. Not for transparency
theatre — because §4.3's whole architecture is that the numbers came from
somewhere checkable, and hiding the provenance throws that away for nothing.

And the chat has **no proactive messages, ever**. No "your portfolio moved", no
daily summary, no nudge. §1.3: engagement mechanics increase trading, and
trading is where returns go. It speaks when spoken to.

### 3.5b The tool registry, enumerated

Pass 31 found that this document says *"the 18 tools in §3.5"* in three places
while §3.5 names seven in prose and enumerates none — and slice 3.2's first act
is *"the JSON shape is written before any of them"*, which cannot be done
against a list that does not exist. **Written on pass 46 rather than left to
whoever opened §3.5 that morning.**

Status column: **live** = an endpoint answers this today (pass 32); **untyped**
= it answers but declares no response model, so it cannot be grounded or cached
until it does (pass 35); **new** = nothing behind it.

| # | tool | answers | backing route | status |
|---|---|---|---|---|
| 1 | `resolve_fund` | "which fund is this?" — the gate every other tool passes through | `GET /research/funds/search` | **live** |
| 2 | `fund_facts` | TER, AUM, manager, min SIP, exit load, plan type | `GET /screener/funds/{code}` (`ScreenedFundOut`, 34 fields) | **live** |
| 3 | `fund_analysis` | the fund page's full read | `GET /screener/funds/{code}/analysis` (27 fields) | **live** |
| 4 | `holdings` | what he owns, with cost basis and XIRR | `GET /portfolio/holdings` + `GET /portfolio` | **live** |
| 5 | `overlap` | "are two of my funds the same bet?" | `GET /portfolio/overlap` — `common_weight`, `shared_securities`, `holdings_as_of` | **live** |
| 6 | `cost_review` | "what am I paying across everything?" | `GET /portfolio/cost-review` | **live** |
| 7 | `levers` | "what should I do next, ranked by what it is worth" | `GET /portfolio/levers` (`LeversOut`, 12 fields) | **live** |
| 8 | `benchmark` | "how has this done against its index?" | `GET /portfolio/benchmark` | **live** |
| 9 | `portfolio_history` | the value line, for any window | `GET /portfolio/history` | **live** |
| 10 | `base_rates` | "what has this kind of fund done to people before?" | `GET /research/evidence` | 🔴 **untyped** |
| 11 | `tax_regime` | "old regime or new?" | `POST /advisor/tax-saving` | 🔴 **untyped** |
| 12 | `category_coverage` | what the screen is and is not showing | `GET /screener/categories` (`ScreenerCoverageOut`) | **live** |
| 13 | `top_funds` | the ranked cut, with its coverage | `GET /screener/top-funds` | **live** |
| 14 | `stock_facts` | sector-relative fundamentals | `GET /screener/stocks/{ticker}` | **live** |
| 15 | `fund_ter_history` | "has this fund got more expensive since I bought it?" | Groww `historic_fund_expense[]` — **11 years daily** (§16.6) | **live**, a field read |
| 16 | `look_through` | "what do I own *underneath* my funds?" | — | **new** |
| 17 | `company_exposure` | "how much Reliance do I own?" — §3.5 calls this the question no Indian app answers | — | **new** |
| 18 | `switch_cost` | "if I move out of X, what does it cost and return?" | `/portfolio/cost-review` is adjacent, not the same | **new** |

**Eighteen, and the count now means something.** Twelve are live, two are live
but untyped, three are genuinely new, one is a field Groww already returns.

**So slice 3.2 is not "write eighteen tools".** It is: **type two endpoints,
wrap fifteen, and build three.** The three that are new — `look_through`,
`company_exposure`, `switch_cost` — are also the three most distinctive things
in this product, which is the right place for the effort to land.

⚠️ **This registry is a proposal, not a measurement.** Rows 1-15 are anchored to
routes verified on pass 32; the *tool names* and the split of work between them
are a design choice made here and open to revision. What is no longer open is
whether the list exists.

### 3.6 `Why` — the app's own scoreboard, and where the honesty lives

Already exists as `app/data/track_record.json`. Promoted to a real screen,
because [[traa-competitors]] found that **no Indian app publishes an audited
record of its own engine** — not Tickertape, not ET Money, not MarketsMojo, not
Zerodha's Nudge. It costs nothing but nerve.

**But a wall of unlabelled percentages is not a scoreboard.** 43%, 57%, 68%,
82%, 83%, 61% — of what, against what baseline, on what question? A
non-professional reads 83% as the headline and 43% as a typo. And §1.1's actual
exit finding is not a percentage at all and has nowhere to sit in a list of
them.

So one repeated card, identical shape, sorted by how much money the question
touches:

```
   what we claimed        "ranking funds on past 3-year return picks better ones"
   how we tested it        44 three-year windows, top quartile vs bottom
   how often it was right  19 of 44  (43%)
   a coin flip would give  22 of 44  (50%)
   what we do about it     we do not rank on past return, and there is no
                           "underperforming" badge
```

**Honesty gets a home, and stops being chrome on every other screen.** A product
review counted roughly ten permanent "here is what we don't know" surfaces
against four affirmative capabilities — a ₹0 lever kept on the home screen
forever, two inert badges, unmeasured axes, `cost from one source`, four
universe counts, collapsed tool calls, a provenance line. Past some density,
rigour stops reading as rigour: a user told more often what the app cannot do
concludes, correctly, that it mostly cannot.

> **`Why` owns the epistemics** — §5's refusals (which are the app's positioning
> and appeared nowhere in the product), the unmeasured axes, the counts. Every
> other screen carries **at most one** epistemic statement, and it must be
> attached to a number the user is looking at. The ₹0 lever becomes a one-time
> dismissible card and then lives here. **"38 unexplained" never appears in the
> product** — it is a note to a reviewer, and §12 is where it belongs.

🔴 **And the record he actually cares about is missing.** The app never asks
whether he acted on a lever, so it can never measure whether its own advice
helped. For a product whose differentiator is publishing unflattering
measurements of itself, not measuring the one outcome the user owns is the
largest hole in the honesty claim. **One dismissible "did you do this?" on an
executed lever** closes it — and it also stops the levers list recommending
something he did three months ago.

---

## 4. The AI layer

Manan asked for "inline verdict + chat". The architecture question — agentic or
generative — is settled by evidence, not taste.

```
FinanceBench            same model: 9% correct closed-book, 85% given the source
FinSheet-Bench 2026     89.1% on lookup, 19.6% on aggregation, 37.5% on sorting
PAL ablation            GSM8K 72.0% → 23.2% when the model runs its own code
Vals AI Finance Agent   best frontier model 64% on entry-level analyst tasks
```

### 4.1 The shape

```
React ──────────────► FastAPI
                        │
        ┌───────────────┴────────────────┐
        │                                │
   Deterministic core              Narration / Ask
   (pure Python, no LLM)           (the only place Gemini exists)
                                    1. Gemini picks tools from a fixed
   scoring · XIRR · tax ·              allow-list
   ranking · sorting ·              2. BACKEND executes them
   dates · look-through ·           3. tool JSON → Gemini
   overlap · base rates             4. Gemini writes sentences ONLY
        │                              about that JSON
        └──── exposed as typed ───►  5. grounding.check() — every number
             tool functions             must appear in the source
                                     6. fail → retry once → template
                                        fallback. Never ship ungrounded.
```

**Model:** `gemini-3.1-flash-lite`, pinned by Manan on 2026-08-27, in
`backend/.env` as `GEMINI_MODEL`. One model, so there is one set of measured
behaviours rather than a fleet with different quirks.

🔴 **And none of this exists in the app yet — the plan should not read as though
it does.** `services/llm/client.py` is **26 lines calling Groq's
`llama-3.3-70b-versatile`** through LangChain, and `config.py` declares exactly
one LLM key, `groq_api_key`. `GEMINI_API_KEY` and `GEMINI_MODEL` sit in `.env`
**unread**; `grep -rin gemini app/` returns two hits and both are comments.

Everything verified above was verified in a probe that left no code behind.
Slice 3.3 is therefore a real piece of work — client, `Settings` fields, the
tool-call loop, retry and cache — and it is budgeted as one.

🔴 **"The 18 tools in §3.5" — §3.5 names seven, and there is no registry.**
Counted on pass 31. Every function-shaped name in that section:

```
resolve_fund   overlap   company_exposure   switch_cost
fund_ter_history   base_rates   tax_regime               = 7
```

They appear scattered through prose bullets — *"Which of my funds are the same
bet?" → `overlap` over every holding pair* — and **§3.5 contains no enumerated
list.** The figure 18 appears in three places in this document and is written
nowhere as eighteen things.

That matters because **slice 3.2 is three sessions and its first act is "the JSON
shape is written BEFORE any of them."** A JSON contract cannot be written against
a list that does not exist. Whoever builds it would reconstruct the registry from
prose, and the reconstruction would be the spec — decided by whoever happened to
read §3.5 that morning, which is exactly what a written registry prevents.

**§3.5 must carry the enumerated list, and it is slice 3.2's first deliverable
rather than an assumption it starts from.** The seven above are the confirmed
members; the remaining eleven have to be named or the count corrected.

🔴 **And pass 32 found the reason that list was never hard to write: this
document names ZERO of the 49 API endpoints that already exist.**

```
advisor.py    14      portfolio.py  12      research.py   10
screener.py   10      auth.py        2      alerts.py      1     = 49
named anywhere in this plan:                                       0
```

Mapped against §3.5's seven tools, **four already have a working endpoint**:

```
resolve_fund      GET  /api/v1/research/funds/search        exists
overlap           GET  /api/v1/portfolio/overlap            exists
base_rates        GET  /api/v1/research/evidence            exists
tax_regime        POST /api/v1/advisor/tax-saving           exists
fund_ter_history       Groww historic_fund_expense[]        exists (pass 26)
switch_cost       GET  /api/v1/portfolio/cost-review        ADJACENT, not the same
company_exposure                                            nothing at all
```

§4 already says *"the capability exists for roughly eight"* — and **roughly**
was doing all the work. Nobody had checked which. `/portfolio/overlap` is
§1.5's whole look-through finding, live behind an HTTP route, while §16.2 plans
the store underneath it as new.

**What this changes.** Slice 3.2's tools are mostly **thin wrappers over routes
that answer already**, which makes three sessions look generous rather than
tight — but the same fact makes slice 4's screens riskier, because they will
call these endpoints and **this plan has never looked at one response shape.**
`company_exposure` is the genuine hole, and §3.5 calls it *"the question no
Indian app answers"*, so it is also the most distinctive thing here.

**Slice 3.2's first deliverable becomes two lists, not one:** the enumerated
tool registry, and each tool's backing endpoint or the note that it has none.

🟢 **Pass 33 then read the first response shape, and §1.5's headline finding is
already half-shipped — with its measurement discipline already in the schema.**
`OverlapPairOut` in `schemas/portfolio.py`:

```python
common_weight: float | None       # "Share of net assets in the same securities,
                                  #  matched on ISIN. None means unmeasured --
                                  #  the UI must not render it as zero."
shared_securities: int | None
holdings_as_of: date | None       # "AMCs file up to ten days after month end,
                                  #  so this can lag by five weeks."
```

That is §1.5's *"29 common names, 46.8% overlap"* — **the number, the count, and
the as-of date, behind `GET /api/v1/portfolio/overlap`, today.** §14's rule that
*unmeasured is "n/a", never 0%* is not a thing to enforce in the rebuild; it is
already written into the field's own comment. `OverlapOut` carries `excluded` as
a name→reason map for the same reason.

**What is genuinely absent is the other half of the same headline.** Nothing
computes *"₹1,00,000 into equity funds; ₹90,945 reached equity"* — grep finds no
cash-drag calculation anywhere. And pass 26 established the input exists:
`holdings[].nature_name` is literally `"CASH"` on repo lines, so this is one
aggregation over a field already fetched, not an engine.

> **The plan's single most-quoted finding splits cleanly in two, and it had
> never been split: the overlap half is built and disciplined, the cash-drag
> half is unbuilt and cheap.** Planning it as one undifferentiated block is how
> the built half gets rebuilt and the unbuilt half gets assumed.

**Pass 35 then mapped all 49 at once, and it sharpens pass 32's good news into
something more useful than either finding alone.**

```
49 endpoints · 34 declare a response_model · 88 schema classes · 12 untyped

ScreenedFundOut     34 fields      FundAnalysisOut   27 fields
StockPageOut        27 fields      ScreenerCoverageOut 11 fields
```

A **34-field fund contract** and a **27-field analysis contract** already exist,
while §3.4 designs the fund page as new work.

🔴 **But two of the four tools pass 32 called "already served" sit behind
endpoints with no response model at all:**

```
tax_regime   -> POST /api/v1/advisor/tax-saving     UNTYPED
base_rates   -> GET  /api/v1/research/evidence      UNTYPED
```

Both **answer correctly and describe nothing.** That matters more here than it
would in most codebases, because §3.2's stated first act is *"the JSON shape is
what `check_all` validates and what the cache key hashes, so it is written
before any of them"* — and §4.4 hashes `tool_json` into the cache key. **A tool
whose backing endpoint has no declared shape cannot be grounded or cached**, and
`base_rates` carries §1.4, one of the five findings the design rests on.

The other ten untyped routes are the advisor POST calculators
(`calculate-sip`, `risk-score`, `asset-allocation`, `whole-portfolio`), two
DELETEs and the two auth redirects — the last four legitimately return nothing.

**So slice 3.2's real first task is not writing tool functions.** It is **giving
response models to endpoints that already answer**, which is smaller than
writing eighteen tools and is a different job from the one the slice describes.

**Of the tools §3.5 does name, zero exist.** The capability exists for roughly eight
of them (`portfolio/returns.py`, `portfolio/benchmark.py`, `screener/base_rates.py`,
`screener/fund_facts.py`, `advisor/tax_regime.py`, `advisor/track_record.py`,
`portfolio/fifo.py`, `advisor/fund_overlap.py`), but each still needs a pure
function with a **stable JSON contract** — because that JSON is what
`check_all` validates against and what the cache key hashes. Five are genuinely
new engines: `look_through`, `company_exposure`, `switch_cost`,
`fund_ter_history`, `fund_cost_rank`. **The registry in §3.5 is a specification,
not an inventory**, and slice 3.2 writes the contracts before writing the
functions.

Verified on that exact model today: plain calls, structured output with `enum`
and `ARRAY`, function calling, and the resolver pattern. Grounding validator:
**6/6 correct sentences accepted, 3/3 arithmetic violations caught.**

### 4.2 Where the LLM is allowed, and where it is banned

| | LLM? |
|---|---|
| scoring, ranking, sorting, counting | **never** — FinSheet-Bench: sorting 37.5%, counting 41.7% |
| XIRR, tax, SIP projections, rupee amounts | **never** |
| date and period arithmetic | **never** |
| the buy/hold/exit verdict itself | **never decides** — a threshold on engine output |
| explaining a verdict | yes, narrates validated JSON |
| free-text questions about the portfolio | yes, as a tool router |
| general education ("what is an expense ratio") | yes, still scope-guarded |

### 4.3 Two guardrails that were tested, not assumed

**The resolver rule.** Asked for XIRR on a real fund without giving a code, the
model produced `scheme_code: "122639"` from its own memory. It was correct,
which is the dangerous kind of wrong. Asked about a fund that does not exist, it
put the fund's **entire name** into the `scheme_code` field — and a system prompt
explicitly forbidding invented identifiers **did not stop it**, because
`mode: ANY` forces a call.

The fix, verified on both models: expose `resolve_fund(name) → scheme_code` and
declare that every code must come from it. Both real and fake fund names then
routed to the resolver, and the fake one dies honestly at the backend.

> **No tool takes an opaque identifier as a first-class input. Every identifier
> has a resolver, and the backend validates it regardless.**

**The grounding rule.** `app/services/llm/grounding.py`, **50 tests**. Every
number in generated text must appear in the tool JSON it was shown, must sit at
the field it cites, must be used to say what that field means, and must be about
the entity the sentence names. The four holes an adversarial review found here
are **now closed** (§17.6), along with two more that closing them exposed.

The interesting part is what it took to make it usable. The obvious regex
rejected **four of five correct sentences** — not on invented numbers, on the
date: source `2026-08-27` tokenises to `2026, -08, -27`; output `27-08-2026.`
tokenises to `27, -08, -2026.`. Then the fixed version passed all its unit tests
and still rejected four of five *live* generations, because the model writes
`August 27, 2026` in prose and every test I had written used ISO format.

> A guard with a 17% false-positive rate is a guard someone switches off, and
> then nothing is guarded. Both fixes are pinned by tests built from the real
> model output, not from the format I assumed.

It still catches what matters: a number from memory (`152 holdings`), arithmetic
the model did itself (`0.33` = 1.02 − 0.69, correct and still a violation), and
the concatenation trick (`0.691.02`).

### 4.4 Rate limits and caching

```
gemini-3.5-flash-lite (old key)   429 at request #16 in 14.9s   → ~15 RPM
gemini-3.1-flash-lite (new key)   40/40 in 41.1s, no wall
gemini-3.1-flash-lite (28 Aug)    60/60 in 4.8s at 12 concurrent, no wall
```

Two variables changed at once between the first two rows (model and key), so the
difference cannot be attributed. The third row is a harder push on the pinned
model: sixty concurrent requests in under five seconds, no 429, which is an
instantaneous rate around **50× the 15 RPM this design assumes**.

🔴 **And the reason that number cannot be trusted anyway, checked 2026-08-28:
Google no longer publishes free-tier RPM, TPM or RPD for any model.** The rate
limits page now says only that limits *"depend on a variety of factors (such as
your usage tier)"*, are viewable in AI Studio, and *"will automatically update"*
as account status changes. There is no documented constant to design against —
which reframes the two rows above. They are not evidence of a limit; they are
two samples of one account's state on two days, and the account's state is the
thing that moves.

**RPD was deliberately not measured.** Bounding it requires exhausting it, and
exhausting it costs Manan a day of his own app. It is left unknown on purpose,
and the design below is what makes that acceptable.

Both escape hatches are closed on the free tier and were tested:
`batchGenerateContent` → `400 FAILED_PRECONDITION`; `cachedContents` →
`limit=0`.

**So: cache in our own store, keyed on the hash of the tool JSON.** If a fund's
score has not changed, its explanation is not regenerated. Narration is
generated for what is on screen, not for all 1,686 funds. Design sized for
15 RPM and left there even though the measured headroom is 50× that.

Given that Google publishes no number, **sizing for the lowest limit ever
observed is not conservatism, it is the only defensible choice** — and it turns
the unknown RPD into a non-issue rather than a risk, because §4.4's own sizing
(~50 calls on a heavy day, §17.5) sits far below any plausible daily cap.

Three consequences, all of which belong in the build:

1. **No rate limit is hard-coded as a fact.** A 429 is a normal response, not an
   error path: the request retries with the `retryDelay` the API returns, and the
   surface falls back to the template narration §17 already requires. The app has
   to be correct with the AI layer entirely absent, so a quota wall degrades it
   rather than breaking it.
2. **The limit is checked where it actually lives.** `aistudio.google.com/rate-limit`
   shows this account's real numbers over the last 28 days. That is the only
   source of truth, and it is Manan's to read — no code should assert otherwise.
3. **A limit that "automatically updates" can move down as well as up.** The two
   keys measured here differed by more than an order of magnitude on the same
   free tier, which is the clearest evidence available that this is account
   state, not a product constant.

---

## 5. What this app will not do, and why

Each of these is a feature a reviewer will ask for. Each has a reason.

1. **No "sell the underperformer".** Ranking on past three-year return put the
   *worse* quartile on top by 0.9pp and won 19 of 44 windows; the dedicated exit
   measurement cannot support a threshold, and is survivorship-conditional
   besides. **And no "sell the winner" either**, even though §1.1's table
   contains the strongest column pointing that way — one measurement, two of
   twelve intervals excluding zero, no multiple-testing correction, and §1.2
   says a sell rule is the most expensive kind to get wrong.
2. **No concentration *limit* as a risk trigger.** The evidence runs the other
   way — Kacperczyk/Sialm/Zheng (2005) and Cremers & Petajisto (2009) both find
   concentrated, high-Active-Share funds outperform. We surface *look-through*
   concentration as a fact about what you own, never as "this fund is too
   concentrated, exit".
3. **No trailing stops.** Kaminski & Lo (2014) is real but tested on index
   futures, not long-horizon retail fund holdings.
4. **No price alerts, streaks, confetti, or daily P&L on the home screen.** §1.3.
5. **No AUM-bloat threshold.** The direction is supported by two top-journal
   papers eleven years apart; no verified numeric threshold exists in either
   abstract. Ships as a qualitative flag or not at all.
6. **No manager-change action.** Four attempts to locate the Khorana literature
   failed. This is a research gap, not evidence of no effect — so it is a flag
   the user reads, never a trigger.
7. **No behaviour-gap number.** Morningstar says −1.2pp; Fulkerson et al. (FAJ
   2026) found three methodology errors reducing it to 0.03%; DALBAR's ~6pp
   compares a lump sum to a DCA investor. No figure goes on screen.
8. **No `groww_rating` shown as a rating.** §2.3.
9. **The app never places an order.** A 64%-accuracy layer does not get order
   capability. This is arithmetic, not philosophy.

---

## 6. The debt-fund defect, stated honestly

`nextrade-code-defects` records it: debt funds are ranked on Sortino and CAGR,
which are equity metrics.

🔴 **Pass 112 opened both scorers, and there are two — which this section never
says, and they do not agree.**

```
advisor/fund_score.py   235 ln  score_peer_group_v2 -> category_ranking -> /fund-rankings
                                volatility 2 · drawdown 2 · COST 4 · sortino 0 · cagr 0
screener/scoring.py     318 ln  score_universe      -> universe/inputs  -> /screener
                                sortino 5 · volatility 7 · drawdown 24 · COST 0 · cagr 0
```

**Three corrections follow, and none of them rescues the conclusion.** *Sortino*
is real but only on the **screener** path; the advisor path scores volatility and
drawdown instead. **`cagr` appears in neither scorer** — that half of the
sentence is wrong. And the two paths **disagree about cost**: the advisor scorer
already weighs TER four times, the screener scorer **not once** — so §6's own fix
(*"rank debt on cost and category-fit only"*) is already half-built on one path
and absent on the other, and this section did not know which one it was talking
about.

🟢 **And pass 113 has to correct pass 112's framing of that, because the
divergence is deliberate, reasoned, and already guarded.** `scripts/consistency.py`
— which runs third in `check.sh` — carries a section headed **"A DISAGREEMENT
THAT MUST STAY ONE"**:

> *"Research and the screener rank the SAME funds in DIFFERENT orders, on
> purpose. Research scores on cost, which is the thing this project measured as
> predictive; the screener scores on trailing record, which is the
> industry-standard method it is a port of. The same fund can be first on one and
> twenty-second on the other. Nobody should ever 'fix' that. What must agree is
> the SET of funds."*

So the two scorers are **§1.1's own finding, built**: cost on the surface this
project trusts, trailing record on the surface it ports. Pass 112 read that as an
oversight; it is the opposite. **What §6 still gets wrong stands** — *cagr* is in
neither scorer, *Sortino* is only in one, and neither branches on asset class —
but the cost asymmetry is a design, not a defect.

⚠️ **One real gap inside a solid gate.** The check computes `missing = theirs -
ours` only. Research is a subset by construction (browsable categories, ≥5 funds,
3y history), so that is the direction that can expose a bug — but the comment
promises symmetry (*"a bug in whichever is smaller"*) that the code does not
implement, and if the screener ever loses funds research has, nothing here says
so.

**The defect stands and is bigger than stated:** neither scorer branches on asset
class at all. `fund_score.py` contains no `debt`, no `credit`, no `duration`, no
`YTM` in 235 lines. Measured against the browsable universe, that is **460 debt
funds across 16 categories — 24% of everything a user can browse** — ranked by
how much their NAV wobbled, which for credit risk is the one number that stays
calm until the day it does not.
 Debt risk is a left-tail credit event plus duration
exposure, and neither is visible in trailing NAV — Franklin Templeton's schemes
looked smooth until the day they gated.

The recorded fix needs TER, the SEBI Potential Risk Class cell, and duration-fit.
**Probed today: Groww has none of PRC, YTM or modified duration, and 0 of 913
debt holdings carried a credit rating.** These exist only in per-AMC PDF
factsheets. There is no free API.

So Phase 1 does the honest thing rather than the impressive one:

- Rank debt on **cost and category-fit only** — both of which we have.
- Show **duration-fit against the stated horizon** where the category implies it
  (a category name carries a duration band even when the fund's own number does
  not).
- **Say on the screen that the credit-risk dimension is not measured**, and name
  what would be needed. An unmeasured axis silently scored as neutral is exactly
  the Bachatt delivery-% bug — 9% of their stock score returning a constant 0.5
  forever because its source 403s.
- **Never recommend a credit-risk fund.** SPIVA's finding that 98.5% of Indian
  bond funds trail over ten years makes low-cost, high-quality, duration-matched
  the only defensible recommendation.

---

## 7. Build order

**An earlier version of this section put every screen in step 10.** Nineteen
sessions of pytest-verified plumbing, then six sessions containing
virtualisation, two Holdings tabs, `Today`, `Why`, a sidebar, a trail, a command
palette and sixteen new components — and the first user-visible improvement as
the final act. A build-readiness review named that as the thing most likely to
make this fail, and it was right for a reason worse than morale: **every schema,
badge and harness decision would surface in week nine instead of week one.**

So the order is now a **vertical slice first**, then widening. The scope is
unchanged; the sequence is not.

Effort is in **sessions** — a focused stretch ending with the gate green — and
each figure now includes the verification tax, which the earlier table priced at
zero. A step that adds a reconciliation, an on-screen reason string, a marker
JSON and a sabotage test is not the same size as the feature inside it.

### Slice 0 — the instrument that keeps this honest  ·  3 sessions

Before any feature, because everything after it cites numbers.

- **Marker gate (§11.4b).** Each script writes a small JSON; the document holds
  markers; `check.sh` fails when a marker disagrees with its JSON. Without this,
  §12 goes stale the way §1.1 did — four times, inside one afternoon.
- **Commit what exists — re-counted on pass 139, and it is larger than files.**
  **12,423 lines of this project exist in exactly one place.** Three parts:

  ```
  untracked, no history at all   22 files   11,384 lines
      .md   3 files  7,505      phase-1-redesign.md 6,399 · groww-endpoints.md 907
      .py  19 files  3,879      grounding.py 793 · test_grounding.py 620 · 17 more
  modified, uncommitted          12 files      246 lines
  committed, not on origin/main   8 files      793 lines   incl. nightly.yml
  ```

  **The largest single file is this document.** The bullet used to count Python
  and say *"1,019 lines and 61 tests"*; it is now nineteen Python files and
  **1,623 tests**, and the docs are twice the code. **And `origin/main` is two
  commits behind**, so the deployment workflow that §16.5 rests on has never
  reached the remote — see the §9.1 row for that. **One `git checkout` is still
  the phrase, and it now costs more than the code.**
- 🔴 **The waking state** (§13.5's eleventh), moved here from slice 4.1 on
  pass 42. The first thing any user meets is a ~60-second cold start, and it was
  scheduled roughly twenty sessions after the first usable screen — so every
  test session in slices 1-3 would open with an unexplained frozen skeleton,
  which is also the thing most likely to be misread as a bug in freshly written
  code. It needs none of slice 4's design system: a timeout, a >2s threshold and
  one line of copy, against an API that already deploys and already sleeps.
  **Acceptance:** with the API stopped, the waking state appears within 2s and
  the error state by 90s — against a stopped server, not a mocked delay.
- **Fix step 9's gate now, not at step 9.** `validate_exit_signal.py` fails if
  any row prints an interval on fewer than four distinct formation dates — a
  condition the data can actually violate, unlike the control band, which with
  200 draws sits at 0.500 ± 0.008 and can never fire.

*Done when:* `check.sh` goes red if a number in the plan is edited to disagree
with its source JSON.

### Slice 1 — one holding, end to end  ·  6 sessions

The first thing Manan can look at, and it arrives in week two.

| | | sessions |
|---|---|---|
| **1.1** | **Schema and one holding in.** `holdings` gains `plan_type`, `goal_id`, `last_reconciled_at`, and the `amfi_code ↔ search_id ↔ isin` triple. **CAS import** (`casparser`) if he wants it, otherwise a SIP entered as a *rule* that expands to lots (§3.0). **Plus a real user record with a known id (§16.4):** the db holds **600 fixture users and 396 populated `user_id`s**, so a query that loses its scope returns plausible data rather than nothing. Acceptance: a test that passes with the fixtures present and fails if any surface drops its `user_id` scope. | 2 |
| **1.2** | **Its cost, from both sources.** Groww TER + the committed `expense_ratios.json` (1,408 AMFI entries with both plans, already built), the 0.10pp agreement gate, the plausibility ceiling, and the **active/passive split** so an index fund is not its peer. 🔴 **Acceptance, corrected on pass 88 — the previous one could not be met in this slice.** It read *"the disagreement count from §2.3 re-prints (71 of 1,233 above 0.10pp)"*. That compares Groww TER against AMFI across **1,233 funds**, and `backend/.growwcache/` holds **39**; the bulk pull that produces the rest is **slice 2.1**, six sessions later. Worse, *94.2% TER agreement* is **already listed as slice 2.1's own acceptance**, so slice 1 was duplicating a universe-wide criterion it had no data for. **This slice is one holding end to end, and its acceptance is now about that holding:** both sources agree within 0.10pp for **the held fund**, or the disagreement is shown rather than averaged away; a fund with **one** source shows `n/a`, never `0` — §14's rule, and the failure that once put three unpriced funds in a Large Cap top five; a fund above the SEBI ceiling is **flagged, not silently ranked**. | 1 |
| **1.3** | **Surcharge and marginal relief** in `tax_regime.py`. Not deferred, because the cost badge's tax term needs it and it is the one place the app's largest number is currently wrong above ₹50L. **Acceptance:** at each of the four thresholds (₹50L, ₹1cr, ₹2cr, ₹5cr) the total tax on **one rupee above** exceeds the tax below by **at most one rupee**. That is the definition of marginal relief and it is a test that cannot be argued with. Separately, a case where the capital-gains cap binds — high salary, equity redemption — asserted on its own, because it is the number this app actually shows | 1 |
| **1.4** | **The cost badge, all four numbers** — saving, exit load, tax brought forward as a *deferral*, breakeven against the horizon — on a real Holdings row, with §13's real tokens. **Acceptance:** the badge fits **34 characters** (§7.5's corrected cap); every figure in it passes `check_all` against **the payload that produced it** — `check_all(generated, claims, source)` takes `source: object`, so it runs against whatever shape slice 1 has; §3.2 later standardises that payload as tool JSON, and pass 88 corrected this line because it previously named the tool JSON and so could not be satisfied until eight sessions later. **A consequence worth stating: this makes slice 1.4 `grounding.py`'s first caller**, which is the thing §9.1 records as missing and slice 3.1 was priced to do; and the tax term reads as a **deferral**, asserted as a string, because §14 says a tax brought forward is not a saving and this is the one badge that could imply otherwise | 2 |

*Done when:* one real holding renders one badge whose four numbers he can check
by hand — and the harnesses (§7.6) are already pointed at the new route.

**Why this order.** It forces the schema decisions (§16), the badge-width
contradiction (§7.5), the plan-type problem and the harness rewrite into week
one, where they cost a session each instead of a rewrite.

### Slice 2 — widen the universe  ·  6 sessions

| | | sessions |
|---|---|---|
| **2.1** | Groww universe ingestion → `groww_universe.json`; screener filters to the **union of buyable and held** (§11.2). **Acceptance is not "it ingested" but "it re-prints §2's four figures"** — 1,686 buyable, 94.2% TER agreement, 86 of 123 Large Cap passive, 0 of 913 debt holdings rated — with the raw pull retained and any figure that moved corrected in this document. None of the four is reproducible today (§12). 🔴 **The pull must include the `st_filter` listing, not only scheme detail** — that is where the `index` boolean lives (0 of 39 cached scheme payloads carry it), so without it `is_passive` stays a one-signal design wearing two, and that open item cannot close here | 2 |
| **2.2** | NAV backfill for the codes with no local history. 🔴 **The figure "101" could not be reproduced (pass 23).** Measured against `fund_catalogue.json` (4,957 codes) only **18** lack any row in `nav_history`, which covers 4,939 codes. 101 must have been counted against the **Groww buyable universe**, and `groww_universe.json` is one of the four §12 figures whose inputs were not retained — so the number cannot be checked and **this step's size is unknown, not 1 session**. **Acceptance:** after the run, the count of held codes with no local NAV history is **0**, and the run prints the starting count so the figure enters the record. Any code that failed writes `nav_source.last_error` and is **counted in the report** — 5 rows carry one today, so the field works and is simply not surfaced | 1 |
| **2.3** | Holdings store + look-through + overlap. **`.holdings/` is now gitignored (§16.4), so git is not its backup** — this step also writes the monthly `sqlite3 .dump \| gzip` into `data/holdings-dumps/`. **Acceptance:** **delete `.holdings/`, restore from the newest committed dump, get the same store** (§16.4) — a backup nobody has restored from is not a backup. **And the sample this store builds decides §16.2's sizing:** the 39 payloads behind *78.3 holdings/fund* are all equity, so **this step pulls debt funds too** and re-prints the total. Equity alone spans 51–107 per fund; across 1,686 the honest range is **48,894 – 428,244 rows**, and the plan currently states one number in it | 2 |
| **2.4** | NSE bhavcopy store and corporate actions. **Acceptance (corrected on pass 21, the previous one pointed the wrong way):** `trim_nav_store.py` must **EXCLUDE** `stock_daily` and `corporate_actions` from the published copy. It calls `con.backup()` — a whole-file snapshot — then one `DELETE FROM nav_history`, so today it would **copy 9.3M rows of stock history straight into the 23.9 MB asset the app downloads at every cold start** (§16.3, reproduced by running it). The test is that the gzipped output stays within sight of 23.9 MB after the archive lands. Plus: one named historical split produces a series **continuous across its ex-date**, and a demerger is marked unadjustable rather than adjusted | 1 |

**Four of slice 2's nine open items close in 2.1, and they are the same
item.** *1,792 vs 1,741*, *"101 codes" is 18 or unverifiable*, *§2's four figures
cannot be reproduced*, and *`is_passive`'s two signals are one* are one problem
wearing four hats: **a number was measured against a population this repo did
not keep.** They do not need four pieces of work, they need one pull that
retains what it counted — which is why 2.1's acceptance is a re-print and not an
ingest, and why the `st_filter` line above was added.

**The other five do not close here, and two are not slice 2 at all.** The
storage sizing is exact arithmetic on an equity-only sample, and the sample it
needs is the **holdings cache — 2.3's, not 2.1's**, so it moves with the store.
The 2.25% TER figure needs SEBI's actual AUM-slab schedule, which no pull from
Groww contains. §16's wrong machine is a rewrite of this document. And the
backup is a script that does not exist. **Sequencing consequence: 2.1 is worth
more than its 2 sessions suggest, and 2.3 quietly owns a sizing question whose
answer spans 48,894 – 428,244 rows.**

⚠️ **2.4's 26-year backfill is 5 minutes of wall clock and a session of
guardrails** — the `SERIES=='EQ'` allowlist with a test per excluded series, the
`DUMMY*` exclusion, and teaching `trim_nav_store.py` about the new tables so it
does not silently delete them.

⚠️ **The `Drifted` badge cannot be tested until a second disclosure month
exists.** That is 30 days of calendar inside 2.3, not effort. Build it against a
synthetic second month and mark it unverified until the real one lands.

### Slice 3 — the AI layer  ·  8 sessions

| | | sessions |
|---|---|---|
| **3.1** | ~~Fix `grounding.py`'s four holes~~ — **done, 2026-08-28** (§17.6): all four closed plus two found while closing them, 38 tests → 50, ambiguity rejection 95.7% → 0.2% re-measured on 39 live payloads. What remains here is **wiring it to a caller**, which is the real slice-3 work: the module still has none **Acceptance:** **no narration reaches any surface without `check_all`.** Proven by removing the check in a test and asserting a fabricated figure *does* reach the screen — the guard has to be shown failing, or nobody knows it runs | 1 |
| **3.2** | **The 18 tool functions** and their **JSON contracts**. Of the 18 in §3.5, **none exist today**; roughly eight are wrappers over existing engines and **four** — `look_through`, `company_exposure`, `switch_cost`, `fund_cost_rank` — are new. 🟢 **`fund_ter_history` came off this list on pass 26: Groww already ships it.** The JSON shape is what `check_all` validates and what the cache key hashes, so it is written **before** any of them. 🔴 **Acceptance, added on pass 88 — this was the only one of the sixteen steps with none, and it is the largest at four sessions.** Three things, each a test: every tool declares a JSON schema **before** its implementation, and a tool whose real output does not validate against its own declared schema **fails the suite**; `check_all` rejects a figure that is absent from the tool output it claims to come from, **proven by removing the figure from the payload and asserting the narration is refused**; and the cache key hashes the contract, so changing a tool's shape cannot serve a stale entry — the failure §17.x already records once, where a key omitted its period | 4 |
| **3.3** | **A Gemini client.** There is none. `services/llm/client.py` is 26 lines of Groq, and `Settings` declares only `groq_api_key` — `GEMINI_API_KEY` sits in `.env` unread. Client, `Settings` fields, tool-call loop, retry, cache **Acceptance:** a **forced 429** is retried using the API's own `retryDelay`, and when retries are exhausted the surface falls back to template narration **with the app still correct**. Tested by injecting the 429, not by waiting for one — §4.4 establishes there is no published limit to design against, so this path is the design | 2 |
| **3.4** | `/ask`, the refusal set, the adversarial suite **Acceptance:** **every refusal in §5 has a test that the answer is refused**, and the adversarial suite from §4.3 passes. A refusal set with no test is a paragraph | 1 |

**The claims decision, taken here rather than discovered:** the model returns
`(value, entity_name)` pairs and **the backend resolves them to paths**. Asking
the model to emit `holdings.0.weight_pct` is asking it to index into a list —
the exact task FinSheet-Bench measures at 19.6%, and §4.2 bans everywhere else.

### Slice 4 — the rest of the surfaces  ·  11 sessions

🔴 **First, the map this slice could not be started without — built on pass 99.**
Slice 4 is written in surface names and the repo is written in page files, and
until now nothing connected them. Read off `App.tsx`'s route table and what each
page actually renders:

```
plan surface   route                     page file          lines   evidence
Today          /  -> /portfolio          Portfolio.tsx        358   renders levers, cost review, overlap
Holdings       /portfolio                Portfolio.tsx        358   same file — see below
Find           /screener                 Screener.tsx       2,012   the finder; largest page in the app
Why            —                         does not exist         —   track record renders inside 3 pages
Ask            —                         does not exist         —   no chat surface

named nowhere in this document, but shipped and routed  (six, re-counted pass 105):
               /screener/stock/:ticker   StockAnalysis.tsx    611   shows the §3.5 stock verdict
               /profile                  Profile.tsx          208   where §14's tax-regime lever must live
               /goals                    Goals.tsx            210   the goal list
               /goals/new                GoalNew.tsx          202   part of §3.0's 23-step on-ramp
               /login                    Login.tsx            136   the first screen, and §13.5's cold start
               /auth/callback            AuthCallback.tsx      20
also routed, and named elsewhere in this document:
               /decide Decide.tsx 428 · /research Research.tsx 1,036 ·
               /goals/:id GoalDetail.tsx 144 · /screener/fund/:code FundAnalysis.tsx 751
```

**And one level down, the same gap — added on pass 106.** Of 18 top-level
components, **8 are never named in this document, and all 8 are live**:

```
FactorEvidence         250   Research.tsx          factor evidence — §1's own subject
AddTransactionDialog   163   Portfolio.tsx         the on-ramp
AddHoldingDialog       159   Portfolio, StartHere  the on-ramp
MomentumScreen         147   Research.tsx          momentum — §1.1's strongest claim
StockScoreBreakdown    141   StockAnalysis.tsx     the stock score §3.5 discusses
FundPicker             135   AddHoldingDialog      the on-ramp
ThemeToggle             80   App.tsx, main.tsx     §13's two themes
ChartLegend             34   FundAnalysis, Stock…  chart furniture
                     1,109 lines, none of it dead
```

🔴 **The sharpest of these is §3.0.** That section is 48 lines arguing about how
hard it is to get a portfolio in — and it names **none** of the four components
that *are* the on-ramp: `AddHoldingDialog`, `AddTransactionDialog`, `FundPicker`,
and `StartHere`, the last being the empty-state guide `Portfolio.tsx` already
renders. **A section about a flow that does not name the flow's own code cannot
be used to change it**, and the 23-step count it is famous for was made without
opening them.

**Two more land the same way.** `MomentumScreen` renders on `Research` while §1.1
argues momentum from a t-statistic and never mentions that a screen for it
already exists; `StockScoreBreakdown` renders the score whose 13 untested points
§3.5 admits to. **In both cases the analysis is in this document and the surface
is in the repo, and neither knows about the other.**

**All four slice-4 steps, measured — added on pass 110.**

```
4.1  navigation shell   2 sess   nav exists but is a HORIZONTAL TOP NAV, not a sidebar
                                 deep links work (useParams in 4 pages) · back handled
                                 ABSENT: the trail, and ⌘K
4.2  Find               4 sess   category-first, reasons, facets, sorting, coverage all ship
                                 ABSENT: overlap-at-choosing, compare tray
                                 DISPUTED: virtualisation — pagination already solves it
4.3  Today and Why      2 sess   Today is a rewrite of Portfolio.tsx; Why is a NEW page
                                 priced as one step; it is two different jobs
4.4  §13.6's devices    3 sess   zero of eight exist — genuinely new (pass 95 confirmed)
```

**So 4.4 is the only step whose price is untouched by what already exists.** 4.1
is a reshape plus two new pieces rather than a build; 4.2 is two features on a
page that already does the rest; 4.3 is one rewrite and one new page counted as
one. **The 11 sessions were set before any of this was looked at.**

⚠️ **Two of these five readings were wrong on the first grep and are recorded
so the method is visible**: `<nav>` matched and looked like the sidebar the step
asks for — it is a horizontal top nav — and *trail* matched **"trailing
returns"** on the screener, not a breadcrumb. **Every count in this document
that came from a pattern match and not from opening the file has now been
wrong at least once**, which is why passes 103-110 re-open the file each time.

**Three things this map settles that the prose did not.**

**`Today` and `Holdings` are the same file.** §3.1 and §3.2 describe them as two
surfaces; `Portfolio.tsx` renders levers, the cost review, overlap *and* the
holdings list, and `/` redirects to it. **Splitting one page into two is a real
decision and slice 4 never states it** — nor which of the two keeps the route.

**Two of the five surfaces do not exist at all.** `Why` and `Ask` are new pages,
not rewrites. `Why`'s content is currently scattered: the track record renders
inside `Decide`, `Screener` and `Research`. So 4.3 (*"`Today` and `Why`"*, 2
sessions) is one rewrite plus one new page, and they were priced as one step.

**`Decide.tsx` has no surface in this plan at all** — 428 lines, routed at
`/decide`, rendering levers and holdings, and the plan neither renames nor
retires it. That is the largest unmapped thing here, and it is a question for
Manan rather than an omission to fix silently: **does `Decide` become `Today`,
or does it go?**


| | | sessions |
|---|---|---|
| **4.1** | Navigation shell — sidebar, trail, `⌘K`, real URLs **Acceptance:** every surface is reachable from every other without the browser back button; **deep links resolve on a cold load**; and browser back does what it says. The `/screener/fund/:schemeCode` → `/fund/:code` move keeps the old path working | 2 |
| **4.2** | `Find` — virtualised, faceted, compare tray, **overlap against what he already owns** **Acceptance:** 1,686 rows scroll without dropping frames on Manan's own machine; and overlap against his holdings shows **`n/a` when unmeasured, never `0%`** — §14, because 0% reads as perfectly diversified, the opposite of "we could not tell" | 4 |
| **4.3** | `Today` and `Why` **Acceptance:** **every figure on `Today` appears in `Why` with its source named.** That is §14's coverage rule applied to the app's own front page | 2 |
| **4.4** | **§13.6's devices — all eight, because zero exist (pass 30).** The slice used to say "the remaining… dot grid, bullet, underwater, slope, fan", which implied three were done; the other three — **rebased line, sorted stacked bar, and sparkline** — were unpriced, and §3.2 puts a sparkline in every `Find` row. `lib/chart.ts` gives real groundwork (UTC dates, axis ticks, padded domains, tooltip style) but no rebasing function. **Acceptance:** each device renders its **empty and loading states**, not a blank box (§13's ten states exist because loading and template-fallback were missing entirely); **and `AllocationPie.tsx` is DELETED, not deprecated** — it is a shipped recharts donut on `GoalDetail`, and §13.6 says never a pie, so leaving it means the app shows allocation two ways on two screens | 3 |

🟢 **Which half of this estimate to trust — settled on pass 111 by measuring
every slice's own claims against the repo.**

```
slice 1  1.1 six columns it adds       ALL ABSENT   holdings has 6 columns, none of them
         1.3 "no surcharge logic"      CORRECT      198 lines, no surcharge, no CG cap
                                                    (its "marginal" is "marginal RATE",
                                                     in a slab comment — not relief)
         1.2 / 1.4                     corrected on pass 88, for depending on later slices
slice 2  its nine open items           EXACT        0 of 39 · 18 · 78.3 all reproduced (pass 96)
slice 3  3.1 grounding has no caller   CORRECT      zero non-test imports
         3.2 "none of the 18 exist"    CORRECT      0 of 8 sampled tool functions defined
         3.3 "26 lines of Groq"        EXACT        26 lines; no gemini key in Settings
         3.4 no /ask                   CORRECT      no route, no chat surface
slice 4  every step                    OVER         passes 99-110: only 4.4 is untouched
```

**So the over-estimate is not spread across the plan — it is confined to the
screens.** Slices 1, 2 and 3 describe what is missing accurately, item by item;
slice 4 and §3 are where a plan written without opening the repo priced shipped
work as new. **That is a usable answer to a question §7 could not previously
settle: the money, data and AI estimates can be read as written; the 11 sessions
for the surfaces cannot.**

🔴 **Before the table: the unit is undefined and the number was priced against
an assumption the last fifteen passes disproved.** Pass 40 checked it, which no
earlier pass had.

**"Session" is defined nowhere in this document.** It carries every estimate
here and cannot be converted into a day, an hour or a sitting. Manan will plan
around it.

**And against this repo's own history it is very large:**

```
the ENTIRE app so far    158 commits · 20 active days · 56 calendar days
                         49 endpoints · 92 schemas · 7 migrations
                         1,624 tests · a 5.2M-row NAV store · 49 .tsx files
                         median 2,758 lines changed per active day

this plan estimated      31 sessions  =  155% of all of that
re-priced on pass 41     33 sessions  (see the table below)
the slice headers now sum to    34 sessions  (3 · 6 · 6 · 8 · 11 — pass 85)
```

**That number was set before passes 26-35, and they changed its basis.** Those
passes found, repeatedly, that work priced here as new already exists:
`fund_ter_history` is a Groww field; `/portfolio/overlap` already returns
`common_weight` and `shared_securities`; §14's rules are **24 enforced response
contracts**; `ScreenedFundOut` has 34 fields while the fund page is planned as
new; four of seven tools have live endpoints. **Nobody re-priced afterwards.**

**Two things follow, and they point opposite ways.** The estimate is probably
**too high** for slices 2-4, because much of that ground is already covered. It
may be **too low** for slice 3.2, which pass 35 showed is not "write eighteen
tools" but "give response models to twelve untyped endpoints and enumerate a
registry that does not exist" — a different and less predictable job.

**The honest fix is not a new number.** It is to say that **31 is an estimate
made against a greenfield reading of a codebase that turned out not to be
greenfield**, and that slice 1 — six sessions, one holding end to end — is the
measurement that re-prices everything after it. That is what a first slice is
for, and it is the only estimate here with evidence under it.

🔴 **And one step moved, the first thing anybody sees.** Pass 42 traced the
primary journey end to end — the one review dimension this project's own
`gstack-plan-eng-review` skill asks for (*"trace data flow, map the full user
journey"*) and that forty-one passes never applied. Reading sections cannot
catch what only a sequence shows:

```
what the user meets first                 was built in     session
1  cold open, backend asleep, ~60s        slice 4.1        24-33
3-8 holdings, cost, overlap, levers       slice 1           4-9
9  ask the AI                             slice 3          16-23
```

**The first thing every user meets shipped second-to-last.** §13.5 establishes
the cold start as the *modal* experience — Render free sleeps after 15 minutes,
this app is opened a few times a week — and the state that explains it sat
twenty sessions after the first usable screen.

**The cost falls on Manan-the-builder more than Manan-the-user.** Every test
session across slices 1, 2 and 3 would open with a frozen skeleton and no
explanation, and a 60-second unexplained hang is the single most likely thing to
be misread as a bug in code written that morning.

**Moved to slice 0** (2 → 3 sessions). It needs none of slice 4's design system
— a timeout, a threshold, one line of copy, against an API that already deploys
and already sleeps.

**The re-price, done on pass 41 rather than left as a note.** Every step below
that passes 26-35 touched, with the evidence and the direction it moves:

```
step  was  now  why
2.3    3    2   /portfolio/overlap already returns common_weight and
                shared_securities with the None-not-zero rule in its own
                comment (p33). The store beneath it is the new part; the
                overlap arithmetic and its discipline are not.
3.1    1    1   unchanged in size, but its content changed entirely: the
                holes are closed, and a 757-generation corpus was found to
                validate against (p27). It is wiring, not writing.
3.2    3    4   NOT "write 18 tools". Four of seven have live endpoints
                (p32); twelve endpoints have NO response model, two of them
                behind tools the AI layer must ground (p35); and the
                registry §3.5 is supposed to contain does not exist (p31).
                Typing an API you did not design is slower than wrapping one
                you did.
4.2    3    4   `@tanstack/react-virtual` and `react-table` are not
                installed (p29). Two installs, a first integration and a
                first render come before any of the styling this step
                describes.
4.4    2    3   zero of eight devices exist where the step priced five, and
                sparkline was unpriced entirely (p30). Plus deleting
                AllocationPie and moving GoalDetail onto the bar.

                        net  +2 sessions, and a redistribution
```

**The total barely moves; where the work sits moves a lot.** Slice 2 gets
cheaper because the look-through half is built. Slices 3 and 4 get dearer
because "wrap the existing tools" is really "type an API nobody typed" and
"add the remaining devices" is really "build all eight".

**That is the useful correction, not the number.** An estimate that is 2
sessions light overall while being 3 sessions wrong in each direction is worse
than one that is 2 sessions light evenly, because the schedule breaks in the
middle rather than at the end.

**Total: 34 sessions** — slice 0 three, then 6 · 6 · 8 · 11 — against the 31 this
table carried before pass 41 and the 25 an earlier draft carried. The difference is the verification tax and the harness rewrite, both
of which were previously unpriced.

> This line read **32** until 2026-08-28, and it was wrong for one day because
> slice 3.1 dropped from 2 sessions to 1 when `grounding.py`'s holes were closed
> ahead of the build, and the total was not re-added. **Found by summing the
> table rather than reading them** — which is the only way a total is ever
> checked, and the reason a seventh review pass was worth running at all.

### 7.5 Contradictions this review found in §3.2 and §13, resolved here

- **The badge cap was wrong.** §13.4 said 26 characters, and five of six
  specified badges exceed it — middle-ellipsis would eat either the rupee figure
  or the fund name, which is the identifying half. **The cap is 34 characters,
  the truncation is on the *counterparty name only*** (`41% the same as HDFC
  Flexi…`), and the money badge is never truncated because §3.2's whole point is
  that the rupee goes in the badge.
- **`--loss-subtle` was used and never defined.** `oklch(.96 .025 27)` light,
  `oklch(.28 .045 25)` dark.
- **A fund with no TER from either source** — 9 of 1,686 — gets a fifth badge
  kind, `cost not published`, dashed ring. Blank means zero and a dash means
  not-measured; neither is this.
- **Sort with no rupee value.** Badge-value descending, then unbadged rows in
  their previous order, stable across refetches. Three of five badge kinds carry
  no rupee and blank is the default, so most rows fall through — the sort must be
  stable or the table reshuffles on every poll.
- **Precedence is a new function.** §3.2 said "the levers engine already does
  this ranking and is reused". It does not — `levers.py` produces
  portfolio-level `Lever` objects, not per-holding ranks. New code, in 1.4.
- 🟢 **Plan type: this bullet was wrong, and wrong in the pessimistic
  direction.** It read *"plan type cannot be resolved from data —
  `plan_identity.classify()` is a name regex, which §11.7 forbids"*. Checked
  2026-08-28 by reading the module instead of its name.

  **§11.7 forbids reading plan type from the name the USER typed. It says
  nothing about the name AMFI publishes**, and `plan_identity.py` exists
  precisely to draw that line — its own docstring opens *"The name a user types
  is not evidence… the code is authoritative and we already fetch its real
  name; the typed string is a label."* It was written after a real bug: someone
  typed "HDFC Flexi Cap Fund - Regular Plan" against code 118955, which AMFI
  publishes as **Direct**, and was shown a lever worth over a lakh to fix
  nothing. `classify()` is a regex, but it runs on `official_name` from
  `get_scheme_meta(code)`. "No plan *column*" is true and beside the point: the
  published *name* is the field, and it carries the word.

  **Measured: 4,957 of 4,957 schemes in `fund_catalogue.json` resolve — 100%.**
  With the honest caveat that **the catalogue is direct-only** (all 4,957 come
  back `direct`), so this proves the direct side and nothing about regular
  plans. The regular side **cannot be measured locally**: `nav_source` has no
  name column and `NAVAll.txt` was not retained — the same non-retention
  problem as §12's four figures.

  **What actually changes.** The §3.0 chip becomes a **pre-filled confirmation
  with an authoritative default**, not a required input — which is a materially
  better first-run and removes a step from 1.1 rather than adding one. The real
  residual is narrower and already handled: **schemes predating the 2013
  direct/regular split have no plan in their name**, and `classify()` returns
  `None` for them by design rather than guessing. Those are the holdings the
  chip must actually ask about.

  **Slice 1.1 acceptance:** print the resolve rate over Manan's own holdings,
  and ask only where it returns `None`.
- **The Nifty-50 top-10 reference line may be unbuildable** — it needs index
  *weights*, and §2.2 established membership only. If free weights cannot be
  found, the comparison is dropped rather than estimated.

### 7.6 The harnesses have to be rewritten, and it is not free

`frontend/scripts/sweep.mjs` hard-codes thirteen routes — `/portfolio`,
`/research`, `/decide`, `/screener`, `/screener/fund/122639`,
`/screener/stock/HDFCBANK.NS` and the rest — and `mobile.mjs` and `a11y.mjs`
share the list. §15 renames every one of them.

So *"harnesses green"* as a done-when is circular: the harness is part of the
change. **The route list becomes a single shared module updated in slice 1**,
before any renaming, so the safety net is never off during the largest work.

### 7.7 Counts as fixtures, not as assertions

`1,686 / 1,531 / 1,158 / 56 / 31 / 13 / 2,632` are snapshots of a live
third-party feed taken on one afternoon. A test asserting `== 1686` goes red
because an NFO listed, which is not a defect. And step 2's `1,158` is computed on
the 1,430-scored set, which 2.2 raises to 1,531 — **the earlier ordering
invalidated its own done-when one step later.**

Every count-based check is therefore two things: an **exact assertion against a
committed fixture payload**, and a **live check that prints the delta and fails
only outside a band**.

### The verification that has to exist

- **Write `test_screener_survives_groww_being_down` first.** A screener run with
  `groww.py` forced to raise must still return a ranking and must contain PPFAS.
  It catches both the crash path and the known AMFI join hole, and it is the
  highest value-per-line assertion in this document.
- **Grounding fidelity, stated as a distribution rather than a 100%:** of N
  generations, X passed first attempt, Y after retry, Z fell back to template.
  A floor on X, a ceiling on Z. A 100% on the union is satisfied by falling back
  every time, which measures nothing.
- **Tool-call enforcement:** every `/ask` answer referencing user data has ≥1
  tool call before its text.
- **Adversarial set as properties, not string matches:** no numeric token absent
  from the tool trace; for a nonexistent fund, `resolve_fund` returned not-found
  and nothing downstream ran; for a forecast request, zero future-dated numerals.
  Fixed seed and temperature for the gate run.
- **Sabotage:** plant a defect, confirm a test goes red. Two escaped last time
  and both were weak tests, not weak code.

## 8. Regulation — the short version

🔴 **Read §8.-1 first. The PRD says this app has 4-5 users, and everything
below assumes one.**

### 8.-3 The rebalancer, and a weekly job with nothing to run it — pass 69

Second instance of pass 68's pattern, and a third finding underneath it.

**1. The 5pp absolute band is specified.** PRD §5.6:

```python
drift_threshold: float = 5.0  # 5% absolute drift
```

`advisor/rebalancer.py` implements that line for line, comment included. So the
second of the three defects `nextrade-code-defects` carries as outstanding is
also **a faithful build of the requirement**. Two of three. The critique stands
— a 5pp band means a 5% gold sleeve must **double** before it triggers while the
same 5pp is an 8% relative move on a 60% equity sleeve — but the fix is a
**specification change**, and this document should say so where it says the band
is wrong.

**2. The PRD schedules it, and nothing runs it.** *"Check runs every Sunday via
scheduled job"*, alerting over WhatsApp. Measured:

```
run_rebalancing_check   called by tests/test_scheduler.py, and by nothing else
.github/workflows/nightly.yml   invokes nav_refresh_job() and nightly_job()
```

**The weekly rebalance check was collateral damage of the free deployment.**
Commit `8a5e4d2` removed the in-process APScheduler — that removal is what made
a no-card host possible (§16.5) — and the nightly jobs moved to GitHub Actions.
**The Sunday job did not move with them.** No workflow runs it, no route calls
it, and the only thing that has executed it since is a unit test.

**3. So §9.1's requirement is already met, for a reason it did not know.**
This plan says Phase 1 is advisory and *"the rebuild must not surface this
rebalancer"*. **Nothing surfaces it today** — not by design, but because its
scheduler was deleted for an unrelated reason. That is a weaker guarantee than
it reads: **anyone re-adding a scheduler restores a weekly alert built on a band
this document has already called wrong**, and nothing would flag it.

**Slice 0 gains a line, and it is one line:** the rebalancer's absolute band
carries a comment saying it is unfixed and unscheduled, so the next person to
wire a scheduler reads that before it fires.

### 8.-2 The risk questionnaire's defect is in the PRD, not the code — pass 68

`nextrade-code-defects` carries as outstanding: *"the risk questionnaire
collapses risk ability and willingness into one score."* Reading the PRD's Part
A settles where that came from. **It is specified.**

```python
RISK_QUESTIONS  # PRD §5.4
  "If your investment drops 30% tomorrow, what would you do?"   WILLINGNESS
  "What is your investment experience?"                          WILLINGNESS
  "How stable is your income?"                                   ABILITY
  "Do you have existing financial liabilities?"                  ABILITY

def calculate_risk_score(answers): return round(sum(answers) / len(answers))
```

`asset_allocator.py` implements that line for line. **The defect is a faithful
build of the requirement**, which makes fixing it a departure from the PRD
rather than a bug fix — a different decision, and one that should be recorded
as such rather than slipped in.

**What the average does, run on the PRD's own four questions:**

```
freelance income, heavy loans, buys the dip     [10, 9, 2, 1]  -> 6  moderate
stable govt job, no loans, would sell everything [1, 3, 8, 10]  -> 6  moderate
balanced on all four                             [6, 6, 6, 6]  -> 6  moderate
```

**Three investors with nothing in common get the same allocation.** Averaging
lets high willingness pay for absent ability, which is exactly the wrong
direction: the person who **cannot** absorb a drawdown is told they can, and
the recommendation that follows puts more equity in front of the one household
least able to hold it through a fall.

**Ability is a ceiling, not a term in a mean.** The correction is `min(ability,
willingness)` — or, better, willingness sets the profile and ability caps the
equity share — so a stable-income, no-loans investor who panics is still moved
down, and a confident freelancer with heavy loans is not moved up.

**This is §1.3's finding at the point of entry.** That section's whole argument
is that the cost of holding through a fall is real and is why equity share is a
gate rather than a lever. A questionnaire that hands a moderate allocation to
somebody with unstable income and heavy loans is the same mistake made before
the user has seen a single number.

**Slice 1.1 owns it, and its acceptance is the table above**: the three answer
sets must not produce one profile.

### 8.-1 The user count this section argues from is not the one the PRD states — pass 66

`NexTrade_PRD_v1.md`, 2,330 lines at the repo root, opened for the first time
on pass 66. Its executive summary table:

```
Users                    Personal use + 4-5 close friends/family
Timeline                 1-2 months to working MVP
Budget                   ₹500-2000/month infra
Starting Capital (real)  ₹10-15k (only after paper trading proves system)
```

**This section's whole argument runs off the first cell and gets it wrong.**
§8 says a single person using this alone is *"categorically outside SEBI's
Investment Adviser definition"* and treats sharing with a few friends as a
hypothetical: *"Sharing it free with a few friends is a genuine grey zone."*

**The PRD does not describe that as a hypothetical. It is the stated user
base.** So the case §8 files under "if it is ever shared" is the case the
product was specified for, and the safe case it argues from — one person, alone
— is not what was asked for. **The grey zone is the design, not a risk to it.**

**That does not change the legal reading, and it changes which reading applies.**
§8's own findings stand: no enforcement action found without a fee or a
monetisation funnel; low practical risk; no client-count exemption anywhere in
the regulations. **What changes is that this is now the live question rather
than the contingency**, and three things follow that §8 leaves as "if":

- **The sell-side language review is not deferred.** §8 says *"if it is ever
  shared, the sell-side language and the 'holding out' surface are what need
  review"*. On the PRD's user base that review is due before the first friend
  gets a link, not after.
- **§8.2's credential argument dates differently.** It was filed as live-on-
  deployment; with other people's accounts it is live on the first shared
  login, and `isolation.py`'s 31 checks stop being belt-and-braces.
- **DPDP applies the moment the app stores another person's data**, which §8
  already says — and the PRD says that moment is planned, not possible.

⚠️ **One PRD line is superseded and should be marked, not reconciled.**
*"Budget ₹500-2000/month infra"* is overtaken by Manan's later instruction that
this run free with no credit card, which is what commit `8a5e4d2` and §16.5 are
built on. **A budget line and a no-card constraint cannot both hold, and the
newer instruction wins.** The user-count line has no such retraction.

**Slice 0 gains the question this plan should have asked in §0: how many people
will use it?**

🟢 **Pass 132 read §8.1 and §8.2 against that sentence, and the sentence
overstates its own section.** It said *every regulatory sentence in §8, and the
whole of §8.1-§8.2, resolves differently at one than at five*. They do not.

- **§8.1 does not turn on the count.** Its finding is that the OAuth scopes are
  identity-only, so a leaked token buys a name and an email address. That is
  true of one token or five.
- **§8.2 says the opposite of the sentence, in its own words:** *"Single-user is
  not a property of this app; it is a property of the login screen."* The
  deployment is public either way, so the login screen is the boundary
  regardless of how many people stand behind it. **That section exists
  precisely to retire client count as the mechanism.**
- **The legal reading is unchanged**, which §8.-1 itself establishes two
  paragraphs above: no enforcement action without a fee or a monetisation
  funnel, low practical risk, and no client-count exemption anywhere in the
  regulations.

**What the answer actually decides is timing, not direction** — and the three
consequences listed above say so if read as written: the sell-side language
review is *due sooner*, §8.2's credential argument *dates* differently, and DPDP
applies at a *planned* moment rather than a possible one. **So this is a
scheduling input, not a blocker on the design**, and the PRD's own non-goals
("*Multi-user public SaaS (Phase 1 is personal)*") point the other way from its
executive summary, which is a contradiction inside the PRD rather than inside
this plan.

⚠️ **And the paragraph above overstated the PRD, which pass 67 found by reading
twenty lines further.** Its non-goals list says:

> *"❌ **Multi-user public SaaS (Phase 1 is personal)**"*
> *"❌ Robo-advisor with SEBI RIA license (out of scope legally)"*

**Those are compatible with "4-5 close friends/family" and they change the
tone.** The PRD's exclusion is aimed at *public SaaS*, not at a user count —
four friends is still personal in that sense. So the document does not
contradict §8 as flatly as stated above; it sets a ceiling (never public, never
registered) while naming a number above one.

**What survives the correction is the part that mattered:** §8 argues from
*one*, the PRD plans for *several*, and the difference decides whether the
sell-side language review is due before the first shared link or after. **The
ceiling being explicit makes that easier, not moot** — "not a public SaaS" is
not the same claim as "outside the Investment Adviser definition", and only the
second one §8 actually makes.

🟢 **And the PRD leaves this plan a gap rather than a conflict, which is worth
recording.** Its §2.3 is titled *"Core Philosophy (Non-Negotiable)"* and every
line of it is about trading:

> *"100 trades → 45 losses, 55 profits = acceptable… This is a **probability
> game**, not a prediction game. Risk management is more important than signal
> quality. Paper trading MUST prove the system before real money goes in."*

**That is Part B, which Manan scoped out of Phase 1.** So the PRD states no
non-negotiables at all for the advisor half — **§14 is not competing with an
older list, it is the first one.** Where §14 and the PRD both speak, they agree
in spirit: the PRD's *"probability game, not a prediction game"* is the trading
form of §1's finding that selection does not predict and cost does.

Researched today; full detail in the session record.

- **A single person building and using this for themselves is categorically
  outside SEBI's Investment Adviser definition** — no other person receives
  advice, no consideration, no "business". Safe.
- **Sharing it free with a few friends is a genuine grey zone.** Every
  enforcement action found involved a fee or a monetisation funnel; none involved
  genuinely free advice to a handful of contacts. Low practical risk, not a
  guaranteed legal position — there is no client-count exemption anywhere in the
  regulations.
- **Publishing it publicly is where real risk starts**, via the "holding out"
  limb — which does not require consideration — and the post-2023 behavioural
  test that treats specific buy/sell calls as regulated advice "irrespective of
  how it is labelled".
- **SEBI's AI/ML guidelines are a consultation paper (20 June 2025), not a
  binding circular**, and their trigger is being a SEBI-registered entity, not
  using AI. Two claimed circulars found in secondary sources could not be
  located and are treated as fabricated. **Re-checked 2026-08-28** against
  SEBI's own 2026 circular listing, because a June-2025 consultation paper is
  exactly the kind of claim that goes stale in fourteen months: no AI or ML
  circular appears for 2026. The most recent entries are cyber incident
  reporting and IT resilience, both of which trigger on *being a registered
  entity*. Still a consultation paper.
- **DPDP Act 2023**: rules notified 14 Nov 2025, but the substantive
  obligations — notice, consent, breach reporting, security safeguards —
  commence **14 May 2027**. They apply the moment the app stores another
  person's data, independent of SEBI.

### 8.0 `SECURITY.md` exists, and §8.1/§8.2 were written without it — pass 62

Forty-four lines at the repo root, named nowhere in this document until now,
and it already answers most of what §8.1 and §8.2 went on to "find":

- **The JWT secret check** — §8.2 reported it as a discovery. `SECURITY.md`
  records it as a deliberate control, with the reason: *"A comment saying
  'change in production' is not a control; the check is in `Settings`, the only
  place the value is ever built."*
- **Account isolation** — §13.12 found `isolation.py` in the gate.
  `SECURITY.md` calls it *"the one that matters most here: **31 checks** that no
  account can reach another's data and that nothing answers without a session"*,
  and adds what neither §8 nor §13.12 knew: every id route answers **404 rather
  than 403** to a stranger, *"so the existence of another user's goal is not
  confirmable."*
- **Input and secrets** — every body a Pydantic model with bounds, every query
  through SQLAlchemy with no string-built SQL, `.env` never in the history.

**Three accepted risks this plan never mentioned, each with its reasoning:**

1. **The token lives in `localStorage`.** An httpOnly cookie survives an XSS
   where this does not. Moving it needs CSRF protection, cookie-domain handling
   and an OAuth-callback rewrite — *"a Phase 2 change rather than a Phase 1
   patch"*. Mitigation today: the app renders no user-supplied HTML and uses no
   `dangerouslySetInnerHTML`, so there is no injection path.
2. **`react-router` 7.18.2 carries a CSRF advisory.** It applies to RSC mode and
   server actions; this is a plain Vite SPA with `BrowserRouter` and neither.
   No patched release exists. Re-check on upgrade.
3. **No rate limiting** — *"a single-user personal app that is not publicly
   deployed."*

🔴 **The third is stale, and checking it settled something bigger.**
`backend/app/middleware/rate_limit.py` exists, is wired in `main.py`
(`app.add_middleware(RateLimitMiddleware)`), and has its own test file. It is
tiered by what an abuser would gain rather than flat: *"a login endpoint is not
rate limited to protect the server at all — it is rate limited because it is
where passwords get guessed."* **The risk was accepted and then closed, and the
document was not updated.**

🟢 **And its other half resolves a contradiction §8.2 walked into.** §8.2 argued
the safety case rests on a login screen *because the deployment is public*,
citing `deploy/FREE-NO-CARD.md`. `SECURITY.md` says the app **is not publicly
deployed**. Checked: **`gh release list` is empty**, so the `nav-store` release
asset the whole deployment depends on has never been published. **The app is not
deployed; `FREE-NO-CARD.md` describes the route, not the state.**

**That does not retire §8.2 — it dates it.** Every credential argument there
becomes live on the day the first release asset is published, and the two
documents will contradict each other from that moment unless one is updated.
**Slice 0 gains a line: publishing the store also updates `SECURITY.md`'s
deployment sentence, or the security record starts lying on the day the app
starts existing.**

### 8.1 🔴 "Single-user is the safe state" is true for SEBI and false for credentials

Pass 28 read the auth path, which §8 never did. Google OAuth **is wired and
live** (`app/auth/google.py`, `routers/auth.py`), and three things follow that
this section had no view of:

**1. The scopes are identity-only, and that is the good news — say it first.**
`httpx_oauth`'s `BASE_SCOPES`, confirmed by importing them:
`userinfo.profile` and `userinfo.email`. No Drive, no Gmail, no Calendar. A
leaked token buys the holder Manan's name and email address, nothing else.

**2. But the app deliberately asks for a long-lived refresh token it never
uses.** `routers/auth.py` passes
`extras_params={"prompt": "consent", "access_type": "offline"}`. `access_type=
offline` is precisely the flag that makes Google mint a **refresh token**, and
`prompt=consent` forces re-consent to guarantee one. The login flow needs a
one-time identity check — it reads `get_id_email(token["access_token"])` and is
done. **Nothing in this app ever refreshes anything.** `fastapi-users`'
`SQLAlchemyBaseOAuthAccountTable` then stores `access_token` and `refresh_token`
in **plaintext columns**, and §16.5 established that in production that table
lives in **Turso** — a third party. So the app asks a provider for a durable
credential it has no use for, and puts it unencrypted on someone else's server.
**Dropping `access_type=offline` removes the asset entirely**, which is a better
fix than encrypting it.

**3. The auth path logs a failed token exchange's full response body.**
`logger.error(f"Google token exchange failed: {body}")`, and the success path
logs `code_prefix={code[:12]}`. An authorization code is single-use and
short-lived so the prefix is minor, but on a free tier those logs go to the
host's dashboard, and "log the whole error body from a token endpoint" is a
habit that stops being minor the first time the endpoint echoes something back.

> **The framing this corrects:** §8 concludes that single-user is the safe
> state, and for **SEBI exposure** that is right — no other person receives
> advice. It does not carry over to credentials. **One user's own refresh token
> sitting in plaintext on a third-party host is exactly as exposed as a thousand
> would be.** Client count is the wrong axis for this risk, and §8 had only that
> axis.

**Slice 0 takes item 2** — a one-line removal — **and slice 4.1 takes item 3**
alongside the cold-start work, since both live in the same request path.

### 8.2 The safety case depends on auth, and this section never said so

Pass 43 counted the on-ramp, which is what `gstack-plan-devex-review` asks —
*"how many steps between I-want-to-try and it-works?"* Step 1 is **sign in**,
and counting it forced the question this section had never asked: *why is there
auth at all in a single-user app?*

**Because the deployment is public.** `deploy/FREE-NO-CARD.md` puts the frontend
on `*.vercel.app` and the API on `*.onrender.com`. **"Single-user" is not a
property of this app; it is a property of the login screen.** §8 argues safety
from client count and never mentions the one mechanism that makes the count one.

🟢 **And the auth actually in use is well built — which corrects the emphasis of
§8.1.** Measured:

```
oauth_account      0 rows      Google OAuth has never been used
users            600 rows      600 of 600 carry a password hash
```

So §8.1 audited the path **nobody uses**, and the path everybody uses had never
been looked at. It holds up:

- **Argon2id** (`$argon2id$v=19$m=65536,t=3,p=4$…`), the current recommendation,
  not bcrypt and not a bare SHA.
- **The JWT secret is validated, not assumed.** `config.py` refuses to boot on
  the `.env.example` value and enforces a 32-character floor, with the reason in
  the error: *"so the signature is not the weak link."*
- 30-day token lifetime.

§8.1's finding stands — the app still requests an unused refresh token and logs
a token-exchange body — but it is a defect on a **dormant** path, and this
section should not leave the impression that sign-in is weak. It is not.

**The count itself, for the record:**

```
1 open the app            ~60s cold start (slice 0)
2 sign in
3 choose how to add       CAS upload | manual | SIP rule
4 search the fund         /research/funds/search
5 confirm direct/regular  now PRE-FILLED (§7), not asked
6 units and date
7 the first real number   cost · overlap · levers

  one holding, today          7 steps
  a five-fund portfolio      23 steps
  CAS, if casparser existed   5 steps  -- and it is not installed (§3.0)
```

**23 steps is the number §3.0 exists to attack**, and it is the strongest
argument for CAS import being a funded sub-project rather than an "if he wants
it". Named here because §3.0 describes the problem in prose and never counts it.

**Design consequence:** single-user is the default and the safe state for the
regulatory question above — **conditional on the login screen**, which is the
part that makes it true. If it is
ever shared, the sell-side language and the "holding out" surface are what need
review — not the analysis.

---

## 9. Open, and honest about it

**47 things are open. 38 were open and are now closed.**

Both of those numbers were wrong until pass 80 — the line said *35 and 13*,
and had said some version of it since pass 37 while the tables underneath it
grew. The closed count was less than half the truth, which made this plan
look like it was fixing less than it was. **A stated count drifting from the
table it describes has now happened three times here** (passes 77, 78, and
this line), so `tests/test_plan_counts.py` now reads both tables and fails
if either number in this sentence is wrong.

They were one table until pass 37, and 48 paragraph-length rows with the
finished ones mixed into the live ones is not a list anyone can act on —
somebody looking for what still needs doing had to read all of it to find
half of it. Split below. **Nothing was deleted**: a closed row is the only
record of what this plan used to get wrong, and deleting that is exactly
what §11.4 says a record must never do.

### 9.1 Still open

**40 items, tagged one by one rather than pattern-matched.** Passes 77 and 78
both grouped this table with regexes over the row text, and both produced
wrong counts — *ceiling*, *slab* and *ability* appear in rows that have
nothing to do with money, and four landed in the wrong bucket. **The counts
below come from reading each row and stamping it**, and the stamp is in the
row, so the next recount cannot drift from it.

```
slice 0   hygiene and the gate                7
slice 1   one holding, end to end             4
slice 2   the universe pull                  10
slice 3   the AI layer                        3
slice 4   the screens                         9
scope     what this document IS               2
decide    Manan decides — not a build task    6
Manan     blocked on Manan                    1
limit     recorded limits, not to-dos         5
```

**Two things the shape says.** Slice 4 still carries the most, so **risk sits
at the far end of the build** — which has been true since pass 38 and survived
twelve more items. And the second-largest group is not build work at all:
**five rows are things Manan has to decide**, and three more are what this
document says it is. Those were invisible until the ten source documents in
this repo were read, at pass 59.

| | |
|---|---|
| `scope` 🔴 **Five gaps from `bachatt-teardown.md`'s own list are still unaddressed here** | That file's *"Behind — and it is not close"* table has fourteen rows; §2 closed three (min investment, TER, AUM) via the Groww layer without citing where the gaps were named. **Five remain unaddressed. Pass 92 correction: four of the five now *appear* — §2's comparison table names hybrid rank+magnitude, the 8 return windows, the 6-tier risk score and market regime — so *"appear nowhere"* is no longer true. Naming a gap is not closing it, and only `diversification rules` is still absent entirely**: hybrid rank+magnitude normalisation (*"#1 by 0.1pp scores the same as #1 by 8pp"* — §14's own range rule, broken inside the scorer), 8 return windows against our 3, a cross-category risk tier *"built because SEBI's is flat"*, **market regime — zero mentions in this document**, and diversification rules (max 2 per sub-category, dominance, AMC spread). Row 2 is the cheapest and the sharpest. **Action:** four of the five are now named in §2's comparison table (pass 92), so what remains is a decision per gap, not research: **each gets a line in §5 as a refusal with its reason, or a line in a slice as work.** `diversification rules` is the only one still absent entirely and needs reading before it can be either. |
| `decide` 🔴 **Three things the surface map exposed, none of which slice 4 can settle itself** | Built on pass 99. **1. `Today` and `Holdings` are one file.** `Portfolio.tsx` renders levers, cost review, overlap *and* the holdings list, and `/` redirects to it; §3.1 and §3.2 describe them as two surfaces. Splitting one page in two is a product decision, and neither §3 nor slice 4 says which keeps `/portfolio`. **2. `Decide.tsx` has no surface in this plan at all** — 428 lines, routed at `/decide`, rendering levers and holdings, neither renamed nor retired anywhere in 5,700 lines. Does it become `Today`, or does it go? **3. Slice 4.3 is priced wrong as a consequence.** *"`Today` and `Why`"* is 2 sessions, but `Why` does not exist — its content is scattered across `Decide`, `Screener` and `Research` today — so that step is one rewrite plus one new page, priced as one. |
| `decide` 🔴 **The rebalancer's band is specified in the PRD, and its weekly job has no runner** | PRD §5.6 sets `drift_threshold: float = 5.0  # 5% absolute drift` and `rebalancer.py` implements it line for line — **the second of three "outstanding defects" that is really a faithful build of the spec**, so fixing it is a specification change. And the PRD's *"check runs every Sunday via scheduled job"* has nothing to run it: `run_rebalancing_check` is called by `tests/test_scheduler.py` **and nothing else**, because commit `8a5e4d2` deleted the in-process scheduler to make the free deploy possible and the Sunday job did not move to GitHub Actions with the nightly ones. **So §9.1's "must not surface this rebalancer" is already true by accident** — and anyone re-adding a scheduler restores a weekly alert built on a band this plan calls wrong. Slice 0: put that in a comment at the band. **Last verified pass 84:** `run_rebalancing_check` has exactly one caller, `tests/test_scheduler.py`. |
| `slice 1` 🔴 **The badge §11.7 calls the largest number this app will ever show has no path from what the user types** | *`Regular plan — Direct saves ₹X/yr`* fires on plan type resolved from the scheme code. **Measured on pass 136: the catalogue contains zero regular plans.** `fund_catalogue.json` is 4,957 entries and `build_fund_catalogue.py` says why — *"Direct plans only: a regular plan of the same fund carries a distributor…"* — which is the right universe to *recommend* from. The ten entries matching *REGULAR* are false positives: funds named **Regular Savings Fund** that are themselves Direct plans. **And nothing bridges the gap:** `direct_twin` appears 0 times in `app/`, `regular_to_direct` 0, `plan_type` once. **So the one case this badge exists for — he holds a regular plan and does not know what it costs him — is the case where his scheme code is not in the universe and no mapping exists to the direct twin.** 🟢 **The data to fix it is already committed:** `expense_ratios.json` carries **both** plan TERs for **1,385** funds, keyed on the direct code, because AMFI files both. **What is missing is the join, not the numbers.** Slice 1.1 already adds a `plan_type` column, which records *which* plan a holding is; it does not resolve a regular code to its direct sibling, and the row should say so. **Action — and pass 137 corrected the mechanism pass 136 proposed, by checking it.** The proposal was that both plans share an `NSDLSchemeCode` stem. **They do not.** AMFI's TER row is **one scheme carrying both plans' figures inside it** — `HDFC/O/H/ARB/07/08/0017` has `D_TER=1.50` and `R_TER=2.09`, and 7 of 7 sampled rows are the same shape. There is no separate regular code to join from, so there is no stem. **The real edge is a name.** The identifier a user types is the six-digit AMFI scheme code, and AMFI's NAV feed — the source `build_fund_catalogue.py` already reads — carries **both plans as separate rows**; the builder drops the regular ones on purpose. **So the fix is to keep what is already being discarded:** at catalogue build time, index regular→direct by the same normalised scheme name `build_expense_ratios.py` uses for its own join (plan and option suffixes stripped, punctuation collapsed, within one fund house). **No new source, no new request, one index built from rows already fetched and thrown away.** |
| `slice 1` 🔴 **The risk questionnaire averages ability with willingness — and the PRD specifies it** | Two of the PRD's four questions measure **willingness** (reaction to a 30% drop, investment experience) and two measure **ability** (income stability, liabilities); `calculate_risk_score` takes a flat mean, and `asset_allocator.py` implements it line for line. Demonstrated: `[10,9,2,1]` (freelance, heavy loans, buys the dip), `[1,3,8,10]` (stable job, no loans, would panic-sell) and `[6,6,6,6]` **all score 6, "moderate"**. High willingness pays for absent ability, so the household least able to hold through a fall is handed more equity. **Ability is a ceiling, not a term in a mean** — and this is §1.3's finding made before the user sees a number. Fixing it **departs from the PRD**, which is a decision to record rather than slip in. Slice 1.1's acceptance is that those three answer sets do not produce one profile. **Last verified pass 95:** `calculate_risk_score` is `round(sum/len)`, and `[10,9,2,1]`, `[1,3,8,10]`, `[6,6,6,6]` all return **6**. |
| `decide` 🟡 **The PRD says 4-5 users; §8 argues safety from one — softened on pass 67** | `NexTrade_PRD_v1.md` executive summary: *"Users: **Personal use + 4-5 close friends/family**"*. §8 calls one person *"categorically outside SEBI's Investment Adviser definition"* and files sharing with friends as a hypothetical grey zone. **It is the stated user base, not a contingency.** The legal reading does not change — no enforcement action without a fee, no client-count exemption — but three things stop being deferred: the sell-side language review is due before the first shared link; §8.2's credential argument goes live on the first shared login rather than on deployment; and DPDP applies the moment another person's data is stored, which the PRD makes a plan rather than a possibility. **Slice 0 must ask what §0 never did: how many people will use this?** ⚠️ Softened on pass 67: the PRD's non-goals also say *"Multi-user public SaaS (Phase 1 is personal)"* and *"Robo-advisor with SEBI RIA license (out of scope legally)"* — a ceiling, compatible with 4-5 friends. It is not the flat contradiction first reported. What survives: *"not a public SaaS"* is not the same claim as *"outside the Investment Adviser definition"*, and only §8 makes the second. |
| `decide` 🔴 **§3.4 ships manager tenure with no evidence it earns the space** | `docs/why-there-is-no-fund-manager-screen.md` (2026-08-21) refused that surface for **two** reasons and this plan answered only one. The data reason is gone — **39 of 39 Groww payloads carry `fund_manager`, `date_from` and `funds_managed[]`**, so tenure and the manager's other schemes arrive free. The evidence reason stands: *"this project has measured fund **selection** three times and found it weak — 50%, 38%, 68% with three of seven years at or below chance. Cost predicted at 87%. **Manager identity is a narrower claim than fund selection and would have to clear a higher bar than either.**"* §3.4 must either measure it or treat it as §5 treats every unearned surface — a fact about the fund, never a reason to buy. **Not: ship it because the field is now in the payload.** |
| `slice 0` 🟡 **This review added twelve guards that check the document, and they run inside the step labelled "unit tests"** | `tests/test_plan_counts.py`, `test_plan_structure.py`, `test_plan_refusals.py`, `test_plan_endpoint_counts.py`, `test_category_names.py` and `test_ter_coverage.py` — **18 tests** — assert things about *this document* and about committed data, not about application behaviour. They are cheap (**5.36s of a ~75s suite, 7%**) and every one is mutation-tested. **The problem is the label.** `check.sh`'s first step is `step "unit tests"`, and a stale count in §9.1 makes it report `1 failed, 1623 passed` — so a builder touching no code sees the code gate go red. Demonstrated: changing *47 things are open* to *46* turns the step red. The failing test names it (`test_headline_matches_both_tables`), so it is traceable, but the step says something untrue about what broke. 🟢 **Keeping them in the suite is right** — §11's whole argument is that a claim nothing checks is a claim that goes wrong quietly, and moving document claims out of the gate would make them exactly that. **Action: `check.sh` gains a separate step** — *"the document still matches the repo"* — running those six files, so a red result says which kind of thing broke. One `step` and one `run` line; the tests do not move. |
| `slice 0` 🔴 **The entire free-deployment mechanism lives on two commits that are not on `main`** | Pass 138 followed the boot-time store fetch to its source and found the reason `gh release list` has been empty since pass 62. **The mechanism itself is correct and complete:** `.github/workflows/nightly.yml` seeds from the existing asset (line 63), rebuilds, creates the `nav-store` release if absent and uploads with `--clobber` (110-113); `scripts/fetch_nav_store.py` unpacks it at boot, and its docstring gives the reasoning — *"Committing it would add ~24 MB to git history per day… every free tier that offers a persistent disk wants a credit card"*. **Nothing is wrong with the design. It has simply never been pushed.** `origin/main` is at `0203060`; the local branch `free-deploy-groww-universe` is **two commits ahead** — `208f396` (the plural-category fix, 24 funds) and **`8a5e4d2`, which adds `nightly.yml`** — and `nightly.yml` **does not exist on `origin/main`**. So the workflow has never run, no asset has ever been published, and §16.5's whole deployment rests on work that exists in one place. ⚠️ **`git log --not --remotes` reports 0 here and is wrong** — a stale remote-tracking ref makes it silent; `git log origin/main..HEAD` lists both commits. **This sits beside the 17 untracked files in slice 0's "commit what exists": same shape, larger — that bullet counts files with no history, and this is a design whose history no other clone has.** |
| `slice 0` 🟡 **Three of the seven committed data files cannot say how old they are** | §14 makes coverage a **type**, and `ScreenerCoverageOut` carries `as_of` and `stale_days` because *"a nightly precompute that quietly goes stale returns 200 with old numbers and nothing catches it"*. The files under `app/data/` do not all hold to that. **Datable:** `track_record.json` 6 days, `base_rates.json` 8, `factor_evidence.json` 22, `expense_ratios.json` 33 (AMFI files monthly, so it is due rather than alarming). **Not datable:** `fund_catalogue.json` — 1 MB, the file that defines the whole universe — carries no build date; its age is recoverable only sideways, from the newest `latest_nav_date` among 4,957 entries, which puts it at **38 days**. `stock_universe.json` (751 stocks) and `sector_benchmarks.json` carry **nothing at all**. 🔴 **`sector_benchmarks.json` is the one that matters:** twelve sectors of median P/E, P/B, ROE and dividend yield, and those are what decide whether a stock reads as cheap or dear. The module already applies the right discipline in one dimension — `built_from()` returns the peer count and the screen shows it, on the stated grounds that *"cheap versus peers means nothing without knowing how many peers"* — **and the same sentence is true of when.** A P/E median from three months ago against today's price is a stale comparison that presents itself as a current one. **Fix is one field per file and one line on the screen**, matching what the fund side already does. |
| `slice 0` 🟡 **The return slider's range is defined twice** | `portfolio.py` returns `return_bounds` with the comment that the assumed return *"may have been clamped"* — the field exists so the UI need not guess the range. `Decide.tsx` guesses anyway: `min={4} max={16}`. **They agree today** (`RETURN_BOUNDS = (0.04, 0.16)`) and nothing keeps them agreeing; move `RETURN_BOUNDS` and the slider still offers the old range while the backend clamps, so the user drags to a number the app does not use — the exact failure `return_bounds` was added to prevent. `tests/test_return_bounds_agree.py` pins the two together and was **mutated to confirm it fails on drift**. The real fix is one line in `Decide.tsx`: read the field |
| `slice 0` 🔴 **`SECURITY.md` says "not publicly deployed" and `FREE-NO-CARD.md` describes a public deployment** | Checked on pass 62: **`gh release list` is empty**, so the `nav-store` asset the deployment depends on has never been published — the app is **not deployed**, and the deploy doc describes the route rather than the state. §8.2's credential argument is therefore **dated, not wrong**: it goes live the day the first asset is published, and the two documents contradict from that moment. **Slice 0 gains a line: publishing the store also updates `SECURITY.md`'s deployment sentence.** Separately, that file's *"No rate limiting"* is already stale — `middleware/rate_limit.py` exists, is wired in `main.py`, is tiered by what an abuser would gain, and has its own tests. |
| `slice 4` 🔴 **§15's navigation and the app's navigation share one destination out of six** | §15 is 85 lines answering Manan's *"ek dum clear navigation, kei har cheez pata lage"*, and it is **the only section in this document with zero verification passes against it** — which pass 140 is. Side by side, `§15 specifies` → `the app ships`: `Today` → `Portfolio` (`/portfolio`) · `Holdings` → `Research` (`/research`) · `Find` → `Decide` (`/decide`) · `Ask` → `Screener` (`/screener`) · `You` → **`Goals`** (`/goals`) · `Why` pinned → `You` (`/profile`). **Only `You` appears on both sides.** Three of §15's six do not exist as pages at all — `Today`/`Holdings` are one file, `Ask` and `Why` are unbuilt (§9.1's surface map) — and **the app navigates to two things §15 never mentions**: `Decide` (428 lines, routed, already unmapped by that map) and **`Goals`**, which is the goal flow §3 specifies no surface for, sitting in the primary navigation. **So §15 was written without opening `App.tsx`, the same way §3's surfaces were.** 🟡 **One thing it asks for is already honoured in substance:** it forbids collapsing to a hamburger because *"a hidden nav is the opposite of the ask"*, and the shipped nav is a horizontal bar that `overflow-x-auto` **scrolls** rather than hides — the intent met by a different means than the specified icon rail. **Action:** §15 is rewritten against the six real destinations, or those six are renamed to §15's — and that choice is the `Today`/`Decide` question already filed for Manan, because it is the same question. |
| `slice 4` 🔴 **The redesign specifies no goal surface, and goals are three routes, 1,115 lines and the PRD's own centre** | §3 names six surfaces and **not one of them is a goal screen**: across the whole section the word *goal* appears 3 times and there is no subsection for it. What ships today: `/goals` → `Goals.tsx` (210), `/goals/new` → `GoalNew.tsx` (202), `/goals/:id` → `GoalDetail.tsx` (144), plus `GoalFundPlan.tsx` (316) and `EditGoal.tsx` (243) — **1,115 lines across three routes**, against **757 goal records** in `nextrade.db`. **This is not a small omission, because the PRD this plan extends is a goal calculator** — §0's own summary of it is *"give it a target, a horizon and an assumed rate of return, and it solves for the monthly SIP"*. So slice 4 redesigns the surfaces around the thing the product was built to do and leaves that thing untouched, without saying it is out of scope. **Two ways out, and both are Manan's:** state the goal flow as deliberately unchanged in Phase 1 — which is defensible, it works — or price it, in which case slice 4's 11 sessions are short by a screen and a half. **What is not defensible is the current position, where a reader cannot tell which was meant.** **Action:** this is Manan's call and it is stated in the `decide` row beside it — but the *document* fix is unconditional either way: **§3 gains one line naming the goal flow and saying which of the two it is**, deliberately unchanged or deferred. A reader currently cannot tell that the question was even asked. |
| `slice 4` 🟡 **Eighteen API fields are computed, typed, and shown to nobody** | Following the `unscorable` finding to its class: of **302 response fields** declared across the three API clients, **26 are never referenced outside the client that types them**. 🔴 **The first reading of that was wrong and is worth keeping:** it looked like the track record was unpublished — `beats_chance`, `hit_rate`, `spread_pp` all unrendered — when `plain_words.py` turns them into a sentence server-side, *"That is a coin flip, and we say so rather than round it up."* **Narrating on the backend is the stronger design**, because a frontend cannot drop the caveat by forgetting a field. Eight of the 26 work that way. **The remaining eighteen reach no reader by either route**, and they are not all alike: `cagr_1y/3y/5y` going unshown may be this plan's own argument against past-return emphasis working correctly, while `p05`/`p95` (the base-rate band beside a `worst` that *is* shown), `downside_capture`, `worst_recovery_days`, `lifetime_cost`, `realised_gain`, and the `rankable`/`peer_group`/`nav_points_available` coverage trio are decisions nobody recorded making. **Slice 4's job is to decide each one — render it or delete it** — because a field that is computed, typed and dropped costs upkeep and reads as coverage that is not there 🟢 **Re-verified on pass 104, because the method that produced it had just been caught being wrong elsewhere.** Pass 90 filed a finding on a grep that scanned the wrong file set, and pass 103 found it false; this row came from the same kind of search, so it was checked three ways instead of one. **One:** a direct search of every `.ts`/`.tsx` outside the three API clients — all eighteen absent. **Two:** the backend prose layer, which is how `beats_chance` and seven others *do* reach a reader — none of the eighteen appears in it. **Three:** generic rendering, the way a field could reach a screen without ever being named — the eleven `Object.entries` / `Object.keys` call sites all iterate a specific nested object (`excluded`, `byClass`, `not_covered`, `factors`, `grouped`, `moved_to`, `params`), and **not one iterates a top-level response**, so nothing can leak through. The finding stands. |
| `slice 4` 🟡 **The ranking page's disclosure of excluded funds is one line for up to 195 of them — and pass 90's version of this row was wrong** | 🔴 **The error first.** Pass 90 filed this as *"hides 589 of 1,878 funds and says nothing"*, on the strength of a check that looked for the string `fund-rankings` inside page files. That string lives in the API client, so `Research.tsx` was never scanned. **It does disclose**: lines 532-536 render *"Left out of the ranking: <names>. <reason>."*, and line 772 does the same for stocks. The finding was false and is corrected here rather than quietly softened. **What survives is smaller and real.** `score_peer_group_v2` drops a fund without a full three-year window — correct, it cannot be scored on evidence it lacks — and **589 of 1,878 catalogue funds across the 37 browsable categories are dropped that way**, 195 of them in `Other Scheme - Index Funds` alone. Three things follow. **One:** that disclosure prints *every* excluded name into a single sentence, so the honest case degrades into a 195-name paragraph exactly where it matters most. **Two:** it prints `unscorable[0].reason` and applies it to all of them, so when funds are excluded for different reasons only the first is shown. **Three:** there is no denominator — *"ranked 169 of 364"* would say in four words what the name list cannot. **Fix stays small:** a count, one reason per group, and the names behind a disclosure. |
| `slice 4` 🔴 **Slice 4's component criteria have no runner — the frontend has no unit-test layer** | No `vitest`, no `jest`, no `.test.tsx`; `package.json` scripts are `dev`/`build`/`lint`/`preview`. So *"each device renders its empty and loading states"*, *"overlap shows n/a never 0%"* and *"the badge fits 34 characters"* are checkable statements with nothing to check them. 🟢 **Four Playwright harnesses do exist** — `sweep.mjs` (every page, both themes, fails on console errors or API 400+, and `--empty` as a brand-new user), `a11y.mjs`, `mobile.mjs`, `shots.mjs` — so slice 4 needs a **component runner added to a project that already has page-level verification**, not a stack invented. ⚠️ And `shots.mjs` already screenshots every page in both themes, which §13.9b scheduled as new work for slice 4.1: that job is *running* it, not building it. **Action:** slice 4 cannot assert a component criterion it cannot run, so **either a unit-test layer is added to slice 0 — one dev dependency and one script entry — or every component criterion in slice 4 is rewritten as something `sweep.mjs`, `a11y.mjs` or `mobile.mjs` already checks.** The second costs nothing and is the honest default; the first is a decision to spend a session. **What is not acceptable is the present state**, where criteria are written as though a runner exists. **Last verified pass 95:** `package.json` scripts are `dev`, `build`, `lint`, `preview`; no test dependency of any kind. |
| `slice 4` 🟡 **The visual system had nothing to look at — partly fixed** | Rated on pass 44 with the last unused lens in this project's arsenal (`plan-design-review`, 0-10 per dimension). Direction 9, tokens 8, states 9, anti-slop 9, devices spec 8 / built 0 — and **SHOWN: 2**, **which §13.9b now records as 2 → 5 after pass 45 acted on it.** Pass 95 adds the second number here because a reader of §9.1 alone saw only the 2, and the row's own body says it was acted on. It stops at 5, not higher, because §13.9b holds that a 10 needs a screenshot of the built thing and nothing is built. Counted: **three layout sketches in the whole document, all in §3**, for seven surfaces; **§13 has none**, and its §13.6 is titled *"Understanding by looking"*. Manan's brief was *"dekar smjh aajye"* and the section answering it can only be read. **Acted on in pass 45, not filed:** §13.4 now carries four sketches — the four badge kinds together (only one is tinted), the row at three densities (only `padding-block` moves, figures stay 13px), the stat tile with and without its sparkline, and the bullet chart. **SHOWN 2 → 5.** It is not a 10 because **a 10 is a screenshot of the built thing**, which slice 4.1 still owes this document. |
| `decide` 🔴 **§8 argues safety from client count and never names the mechanism** | The on-ramp counted (§8.2): step 1 is **sign in**, and the deployment is **public** (`*.vercel.app`, `*.onrender.com`). *"Single-user is the safe state"* is not a property of the app — it is a property of the login screen, which §8 never mentions. 🟢 Separately, §8.1 audited the **dormant** path: `oauth_account` has **0 rows** while **600 of 600** users carry a password hash. The path everyone uses was never reviewed and is clean — **Argon2id**, and a JWT secret that refuses the `.env.example` value and enforces a 32-char floor. §8.1's finding stands but should not read as "sign-in is weak". |
| `slice 1` 🟡 **The on-ramp is 23 steps for a real portfolio, and §3.0 never counted it** | 7 steps to the first real number with one holding; **23 with five funds**; 5 if CAS import worked — and `casparser` is not installed (pass 21). §3.0 describes this problem in prose and never puts a number on it. **23 is the strongest argument for CAS being a funded sub-project rather than an "if he wants it".** |
| `scope` 🔴 **"31 sessions" has no defined unit, and was priced against a greenfield reading** | *Session* is defined **nowhere** in this document, yet it carries every estimate. Against the repo's own history it is very large: **158 commits, 20 active days, 56 calendar days** built the entire current app — 49 endpoints, 92 schemas, 7 migrations, 1,577 tests, a 5.2M-row NAV store, 49 `.tsx` files — so **31 sessions is 155% of everything built so far.** And the number predates passes 26-35, which found repeatedly that work priced here as new already exists (`fund_ter_history`, `/portfolio/overlap`, §14's rules as 24 response contracts, a 34-field `ScreenedFundOut`, four of seven tools with live endpoints). **Re-priced on pass 41** rather than left as a note: 2.3 down (overlap exists), 3.2 up (typing an API nobody typed), 4.2 and 4.4 up (nothing installed, zero of eight devices). **31 → 33 on pass 41, then → 34 on pass 42** when the waking state moved to slice 0 — **and the redistribution matters more than the total**: slice 2 got cheaper, 3 and 4 dearer, so the old schedule broke in the middle rather than at the end. The unit is still undefined, and **slice 1 remains the only estimate with evidence under it.** |
| `Manan` **1,686 holdings pull** | ~4 minutes, once a month. Not run — needs his approval given §2.1. §11.3 reduces the steady state to roughly a dozen requests a month once the first pull is done. |
| `slice 2` **1,792 vs 1,741** | Groww's own filter page reports 1,741, independently confirmed. Live NFOs account for 13. **38 unexplained.** All three counts go on screen rather than picking one. **Pass 128: this is the one open row that cannot be re-verified, and the reason is on this list.** Re-counting 1,741 needs a live `st_filter` call, and browser permission for `groww.in` is one of the approvals still with Manan. **So its provenance is 2026-08-25 and will stay that way until that approval lands** — which is worth stating rather than leaving the row looking merely unchecked. |
| `limit` **FCA gamification figures** | Could not be re-verified. Direction stands on Barber & Odean; the numbers do not go on screen. |
| `limit` **§1.1 is under-powered, and that is not fixable here** | Five non-overlapping cohorts at the long horizons. This store cannot answer the question at 5y+ no matter how the estimator is written; it would need a longer NAV history. Recorded as a limit, not a to-do. |
| `limit` **Momentum, separately** | `nextrade-prediction-research` records t=+3.11 over 32 years on a cross-sectional design. §1.1 neither confirms nor refutes it — different question, and the plan must not use one to overturn the other. A dedicated re-test on the new 26-year stock archive is Phase 2 work. |
| `limit` **Gemini TPM / RPD** | Unknown, and **not closeable** — checked 2026-08-28: Google publishes no free-tier RPM/TPM/RPD for any model, stating limits are account-specific, visible only in AI Studio, and auto-updating. RPD was deliberately not measured because bounding it means exhausting it, which costs Manan a day of use. RPM re-measured instead: **60 concurrent in 4.8s, no 429** — ~50× the 15 RPM assumed. Design unchanged and now justified rather than merely cautious: 429 is a normal response with template fallback (§4.4). |
| `limit` **Debt credit risk** | Structurally unavailable free. §6. |
| `slice 3` 🔴 **Two of the four "already served" tools sit behind untyped endpoints** | Mapped all 49: **37 declare a `response_model`, 12 do not** — re-counted on pass 94, because the row read *34 and 12*, which sums to 46 against 49 routes. The twelve untyped are `POST /test`, the two auth redirects, `GET /evidence`, `GET /momentum`, five advisor POST calculators, and two DELETEs. `tax_regime` → `POST /advisor/tax-saving` and `base_rates` → `GET /research/evidence` are both **untyped** — they answer correctly and describe nothing. §3.2 says *"the JSON shape is what `check_all` validates and what the cache key hashes, so it is written before any of them"*, and §4.4 hashes `tool_json`: **a tool whose endpoint has no declared shape cannot be grounded or cached**, and `base_rates` carries §1.4. Meanwhile `ScreenedFundOut` (34 fields) and `FundAnalysisOut` (27) already exist while §3.4 designs the fund page as new. **Slice 3.2's real first task is giving response models to endpoints that already answer** — smaller than writing eighteen tools, and a different job. **Action, written on pass 127:** these two are **prerequisites of slice 3.2, not work beside it**. §3.2's acceptance is that a tool declares its JSON schema *before* its implementation and that `check_all` validates against it — so `POST /advisor/tax-saving` and `GET /research/evidence` get response models **first**, before any tool wraps them, and the other ten untyped routes are listed there as a decision rather than a backlog. |
| `slice 3` 🔴 **The plan names zero of the 49 API endpoints that already exist** | 49 routes across 6 routers — advisor 14, portfolio 12, research 10, screener 10, auth 2, alerts 1. The row said **not one appears in this document**; **pass 94 counted seven** — `/advisor/tax-saving`, `/portfolio/cost-review`, `/portfolio/overlap`, `/research/evidence`, `/research/funds/search`, `/research/momentum`, `/screener/fund/122639` — every one of them named outside §9.1, so this is not the row quoting itself. **Forty-two are still unnamed**, which is the part that remains open. Mapped to §3.5's seven tools, **four already have a working endpoint** (`/research/funds/search`, `/portfolio/overlap`, `/research/evidence`, `/advisor/tax-saving`), one is a Groww field (pass 26), `switch_cost` has an adjacent-but-different route, and `company_exposure` has nothing. §4 says *"the capability exists for roughly eight"* — **"roughly" was doing all the work and nobody checked which.** `/portfolio/overlap` is §1.5's entire look-through finding, live behind a route, while §16.2 plans the store beneath it as new. Makes slice 3.2 look generous and slice 4 riskier: those screens call these endpoints and **this plan has never looked at one response shape.** **Action:** slice 3.2 already owns writing the tool registry (§3.5b), and that registry is where the remaining forty-two belong — each marked *tool-backed*, *internal*, or *retire*. **It is one table, not forty-two decisions**, and it is the thing that stops the next section pricing an endpoint that exists. |
| `slice 4` 🔴 **Zero of §13.6's eight visual devices exist, and slice 4.4 priced five** | Counted against the frontend: no dot grid, rebased line, stacked bar, bullet chart, underwater, slope, fan or sparkline. Every grep hit was prose in a comment (*"a fund only earns a bullet point"*). The word *"remaining"* implied three were done; none is, and **sparkline appears in no slice at all** while §3.2 puts one in every `Find` row. `lib/chart.ts` is genuine reusable groundwork but exports no rebasing function. **Action:** 4.4 is the one slice-4 step whose price nothing already-built reduces (pass 110), so it is priced correctly at three sessions — **the correction is that the step says five and the number is eight**. Rebased line, sorted stacked bar and sparkline join the list, and §3.2 puts a sparkline in every `Find` row, so that one is load-bearing rather than decorative. |
| `slice 4` 🔴 **A device §13.6 forbids is already shipped, and nothing says to remove it** | `components/AllocationPie.tsx` is a recharts `PieChart`, `innerRadius={52}`, rendered on `GoalDetail.tsx`. §13.6: *"never a pie — weights should be comparable, not estimated from angles."* A builder adds the stacked bar and leaves the donut, and allocation then appears **two ways on two screens** — the §14 consistency failure this repo commits most often, entering through the door marked "new component". Slice 4.4 now deletes it. **Last verified pass 95:** `AllocationPie.tsx` exists and `GoalDetail.tsx` still imports it. |
| `slice 4` 🔴 **The two libraries slice 4.2 is built on are not installed** | §3.2 names `@tanstack/react-virtual` 3.14 and `@tanstack/react-table` 9.2 *"versions checked live today"* — that confirmed they exist **on npm**, not here. The frontend has **26 deps, no virtualisation library, no table library, no motion library**. Same shape as `casparser`: named, versioned, priced into an estimate, absent. Slice 4.2's acceptance is *"1,686 rows scroll without dropping frames"*, which begins with two installs and a first integration. `recharts`/`lucide-react`/`shadcn` **are** present, so §13's charts and icons are real. 🔴 **Pass 101 changed what this item asks.** `Screener.tsx` already paginates at `PAGE_SIZE = 100`, with a comment naming the exact failure virtualisation would prevent — *"1,689 rows across 21 columns is forty thousand nodes; the page stops responding and the accessibility walk times out"*. **So the question is no longer when to install them, it is whether to.** Installing both and rewriting the one view that already works, to reach an acceptance criterion (*"1,686 rows scroll without dropping frames"*) that describes a design this repo rejected on measured grounds, is the more expensive of the two options and the one currently written down. **Whichever way it goes, slice 4.2 is smaller than 4 sessions:** category-first, per-fund reasons, facets, sorting and coverage all ship today; what is genuinely absent is overlap-at-choosing and the compare tray. **Last verified pass 95:** `@tanstack/react-virtual`, `react-window` and `react-virtualized` are all absent from `package.json`. |
| `slice 0` 🟡 **`screener_score.in_sample` has taken exactly one value, ever** | 10,346 of 10,346 rows are `in_sample = 1`. A column named for a distinction the scorer has never actually made — worth either using or removing before §1.1's in/out-of-sample discussion leans on the schema. **Last verified pass 84:** **10,346 of 10,346** rows at `in_sample = 1`, in `.navstore/nav.db`. |
| `slice 2` 🔴 **`is_passive`'s two signals are one — the `index` boolean is absent from the scheme endpoint** | `index` key present in **0 of 39** cached scheme payloads. It lives on the `st_filter` listing (where "375 of 375" was measured), not on scheme detail, so wherever the app reads a scheme the OR's first clause contributes nothing and everything rests on the name regex that has three false positives. **A two-signal design that silently becomes one is worse than one**, because nobody watches the signal they believe is redundant. **Action — likewise already decided elsewhere.** Slice 2.1's step now reads that the pull **must include the `st_filter` listing, not only scheme detail**, because that is where `index` lives. That amendment was made on pass 88 and this row was never updated to point at it. **The second signal exists; it is one endpoint away.** |
| `slice 2` 🔴 **"101 codes with no local history" is 18, or unverifiable** | Measured: `nav_history` covers **4,939** scheme codes, `fund_catalogue.json` lists **4,957**, so only **18** catalogue codes lack any local NAV. The plan's 101 must have been counted against the **Groww buyable universe** — which is the fourth of §12's non-retained figures, so it cannot be checked at all. Consequence: **slice 2.2's size is unknown**, not the 1 session it was priced at. Separately, `nav_source.last_error` is populated on 5 rows, so the failure field works and simply is not surfaced — which is what 2.2's acceptance now requires. **Last verified pass 96:** catalogue **4,957**, `nav_history` covers **4,939**, so **18** — reproduced exactly. |
| `slice 2` 🟡 **The storage sizing is exact arithmetic on an equity-only sample** | 39 cached payloads give mean **78.3** holdings/fund; 78.3 × 1,686 = **132,070**, reproducing §16.2 exactly, and 12 × 78 = **940** reproduces §16.4's "~1,000 rows/month". Both sums check out — **and the cache holds zero debt funds** (§12), while a liquid or short-duration fund routinely holds several hundred instruments. Even within equity the spread runs 51 (ELSS) to 107 (Large & MidCap), and ×1,686 spans **48,894 – 428,244**. Since §16.5 this figure also sizes a **release asset downloaded at every cold start**, so a 2-3× miss decides whether the boot stays near the 23.9 MB the free tier is built around. Slice 2.1 must pull a **stratified sample including debt** before sizing on 78.3. **Last verified pass 96:** 39 cached payloads, mean **78.3** holdings per fund — reproduced exactly. |
| `slice 2` 🔴 **23 fund houses have no expense ratio at all — 297 live funds, including Groww's own AMC and PPFAS** | **Full account in §2.5**, assembled over passes 118-123 and moved there on pass 129 because it had reached 7,700 characters in this cell. In one paragraph: `build_expense_ratios.py` walks AMFI's AMC ids to a hardcoded `_MAX_MF_ID = 55`, and **ids 56-86 hold at least 24 live fund houses** — proven by probing AMFI directly, `MF_ID=63` is Groww, `64` Parag Parikh, `77` Zerodha, `82` JioBlackRock. **297 live funds carry no TER**, **151 of them are old enough to be ranked**, and the scorer gives those a fabricated `_NEUTRAL = 0.5` — median cost — on the one pillar with measured predictive power. Worst in `Liquid` (13 of 37 scored) and `ELSS` (10 of 37), where cost is most of the decision. **The fix is one line**; `tests/test_ter_coverage.py` pins it until then. |
| `slice 2` 🔴 **37 buyable funds are missing from the category they belong to — the count was wrong three times before pass 117** | AMFI publishes the SEBI category as free text and does not spell it one way. `208f396` fixed the plural for the buyable set; **eleven more variants are still live** across the 1,408 schemes AMFI publishes a current TER for. **What pass 82 claimed, and what is actually true.** It said the funds get *ranked in a bucket of six* and shown as *"2 of 6"*. They do not: `fund_catalogue._browsable()` requires an exact SEBI prefix **and** ≥5 funds, and `/fund-rankings/{category}` returns **404** for anything else — so a variant never reaches `score_peer_group_v2` at all. **The real harm is absence, not a wrong percentile:** those funds are unreachable through category browse, and the peer group they should have joined is computed without them. Pass 82 also said 32 funds; **10 of the 32 are closed-ended `Series` schemes** — every one of the `ELSS`-labelled ten — which `inputs.py` excludes deliberately and documents. **22 open-ended funds are genuinely lost:** 8 in `Index Funds - Equity Funds` (all Aditya Birla, against `Other Scheme - Index Funds`'s 364), 6 in `Equity Schemes - Thematic Fund` (*Schemes*, plural — 4 Mirae, against `Equity Scheme - Sectoral/ Thematic`'s 246), and 8 one-fund `Income/Debt Oriented Schemes - …` buckets. **The fix is per-AMC, not per-fund** — the loss concentrates as Aditya Birla 9, Kotak 5, Mirae 4, HSBC 2, UTI 1, SBI 1, because the label follows the AMC's own submission. `LEGACY_SCHEME_TYPES` already rescues the *prefix*; **no map exists for the sub-category**, which is why *Thematic Fund* never meets *Sectoral/ Thematic*. `tests/test_category_names.py` pins all eleven. **Mapping each to its real category needs a human** — an automatic nearest-name match filed *Thematic* under `Contra Fund` 🔴 **Third correction, pass 117, and this one was inside my own guard.** Passes 82-103 defined *live* as **has a row in `expense_ratios.json`** — 1,408 schemes. But **1,701 catalogue funds published a NAV since 2026-08-01**, so that proxy under-counts by **353**, and among the missing was `Mahindra Manulife Large Cap Fund` (code 146549, 1,830 NAV rows, latest 2026-08-24) sitting under `Equity Schemes - Large Cap Fund` — a twelfth variant nobody had seen. Recounted on *published a NAV this month*: **48 variant-labelled funds across 19 labels, 11 closed-ended series, and 37 open-ended funds genuinely lost** — up from 22. New labels the TER proxy hid include `Hybrid Schemes - Aggressive Hybrid Fund`, `Hybrid Schemes - Balanced Advantage Fund/ Dynamic Asset Allocation` and four more `Income/Debt Oriented Schemes - …`. `tests/test_category_names.py` now reads liveness from `nav_history`, and pins all nineteen. |
| `slice 2` 🔴 **"SEBI's 2.25% TER ceiling" is not a ceiling** | Measured in this repo's own AMFI file (`expense_ratios.json`, 2,793 values): **241 above 2.25% (8.6%), max 3.46%, and no density edge at 2.25%** — the distribution runs straight through it. A real cap leaves a cliff; this leaves none. SEBI's limit is almost certainly **AUM-slab-based and scheme-type dependent**, so 2.25% is the top of one slab, not a universal bound. Consequence: §2.3's flat gate **under-detects** — a ₹10,000cr fund at 2.0% is over its own slab and passes, while being a worse deal than several the gate catches. `aum_crore` is already collected, so a slab-aware gate is implementable; **the slab table is what is missing**, and could not be sourced (WebSearch exhausted 200/200, Firecrawl `402`, four SEBI paths guessed and failed). Until sourced, the gate ships as *"unusually high for a direct plan"* with no claim of breach — **and pass 82 calibrated that line rather than leaving it a phrase.** Splitting the 2,793 values by plan: **229 of 1,396 regular plans exceed 2.25% (16.4%)** against **12 of 1,397 direct plans (0.9%)**, direct p99 = **2.20%**. So the same number is a useless signal on regular and a sharp one on direct — and direct is what this app recommends, which is why the interim wording is the right interim. Pass 82 also swept the whole 1.00–2.50% range for a cliff anywhere, not just at 2.25%: the strongest below/above density ratio is **2.2:1 at 1.15%**, the mode of the distribution. **There is no regulatory edge in this data at any level**, which is stronger than the original claim and closes the question of whether 2.25% was merely the wrong constant. |
| `slice 0` 🔴 **The app's most frequent UI state was missing, and the API client cannot survive it** | Render free *"sleeps after 15 minutes idle, ~1 minute to wake"*, so for an app opened a few times a week **almost every session is a cold start** — the modal experience. §13.5's ten states, in a table titled *"the half that was entirely missing"*, did not include it, and its `loading, first paint` rule (*"skeletons, no spinner"*) is the worst available presentation of a 60-second wait. `src/lib/api.ts` is 56 lines with **no timeout and no retry**; a sleeping instance returns nothing rather than a 401, so the one error path it has never fires and the request hangs on axios' default of no timeout. Resolved as an **eleventh state** in §13.5 with a detectable trigger (>2s on a session's first request) and falsifiable acceptance in slice 4.1: **test against a stopped server, not a mocked delay**. **Last verified pass 93:** `src/lib/api.ts` is still **56 lines** with no timeout and no `AbortController`. |
| `slice 2` 🔴 **§16 describes a machine this app does not run on — the largest finding of twelve passes** | Commit `8a5e4d2`, three days before this plan, moved the app to **Vercel + Render free + Turso + GitHub release assets** and states *"the disk no longer has to persist."* §16 names three local SQLite files and mentions `Turso` **0** times, `release asset` **0**, `at boot` **0**; all 14 hits for "Render" are UI *rendering*. Consequences: `nextrade.db` is a **network database** in production, so slice 1.1's real holdings and §4.4's narration cache both change shape; **`.holdings/hold.db` has no route to the running app at all, so look-through (§1.5) cannot work as designed**; and `stock_daily`'s 9.3M rows point at the file that gets trimmed to 23.9 MB and downloaded at every boot. Resolved in **§16.5**, which separates the committed archive from the published runtime copy. 🔴 **Pass 97 audited every artefact §16 names, and the pattern is bigger than the machine.** Of its 396 lines: `.holdings/hold.db` does not exist and neither do its three tables (pass 96); and **`stock_daily` — described as *"~9.3M rows of OHLCV plus delivery across ten columns"* in the present tense — appears nowhere at all**: not a table in `nextrade.db`, `.navstore/nav.db` or either test database, not a migration, not a model, not a line of any script, and `.stockcache/` is empty. **So that is three artefacts §16 states as present which are all slice-2 output.** What §16 gets right is checkable and checked: `nav_history` is **5,187,035 rows** against its 5.19M, and `trim_nav_store.py` really is `con.backup(dst)` followed by one `DELETE FROM nav_history`. **And the pass-21 correction it produced still stands** — `con.backup()` copies the whole file, so when 2.4 creates `stock_daily` the trim must exclude it. **The reasoning was right; the tense was wrong**, and a reader cannot tell which parts of §16 are the repo and which are the plan. Slice 2.4's *"within sight of 23.9 MB"* rests on an estimate, not a measurement, and should say so. |
| `decide` 🔴 **The rebalancer's band is absolute, and this plan's own §14 says it should not be** | `advisor/rebalancer.py` still reads `drift_threshold: float = 5.0` against `abs(current - target)`. A 5pp band on a 5% gold sleeve requires it to **double** before triggering; on a 60% equity sleeve the same 5pp is an 8% relative move. Recorded in `nextrade-code-defects` as needing ±20% **relative** and **tax-aware** bands, and absent from every version of this plan until now. The tax half is the sharper contradiction: §14 says *"a trade is never sorted among the levers"* because a sale is priced, and a rebalancer that ignores capital gains is that exact error inside a different module. **Named here, not scheduled** — Phase 1 is advisory and does not rebalance, so the requirement is that the rebuild must not surface this rebalancer, not that it be fixed now. |
| `slice 2` 🔴 **§2's four headline figures cannot be reproduced from this repo** | 1,686 buyable · 94.2% TER agreement · 86 of 123 Large Cap passive · 0 of 913 debt holdings rated. All measured live on 2026-08-27; **none of the inputs were retained**, `groww_universe.json` does not exist, and the 39 cached payloads are **all equity, zero debt**. Not wrong — *unauditable*, which §11.4 calls worse than no record. Slice 2.1 now has to re-print all four and correct any that moved. Also bounds §17.6's ambiguity measurement to equity payloads. **Last verified pass 96:** `groww_universe.json` still absent; `.growwcache/` still holds 39 equity payloads and no debt. |
| `slice 2` 🔴 **"Backed up" was asserted three times and nothing did it** | §16 called `.holdings/hold.db` *"irrecoverable, backed up"* while no backup script, cloud account or git tracking existed — and gitignoring it (above) removes the last candidate. **Not yet built:** the committed monthly gzipped dump is specified in §16.4 and owned by slice 2.3. 🔴 **Pass 96 checked the store itself and it does not exist.** `.holdings/` is absent; none of `fund_holdings`, `fund_managers` or `groww_universe` appears in `nextrade.db`, `.navstore/nav.db` or either test database. What is on disk is `.holdingscache/` — **10 hash-named JSON files, 1.9 MB, every one refetchable.** So the honest position is **better on risk and worse on the document**: nothing irrecoverable is unbacked today, because nothing irrecoverable exists — but §16 describes `.holdings/hold.db` in the present tense as *"append-only, irrecoverable, backed up"* and lists its three tables, and it is **entirely slice 2.3's future output**. That is the same defect as the row above it: **§16 describes state this repo does not have**, once a machine and once a store. The backup work stays owned by 2.3; what changes is that it is a risk that begins then, not one running now. **Last verified pass 96:** `.holdings/` absent, `data/holdings-dumps/` absent, none of the three tables in any database. |
| `slice 1` 🟡 **600 fixture users in a single-user app** | Measured: 600 users, 414 holdings across 396 distinct `user_id`s. Not a legal issue (§8's argument is about real people), but it makes a dropped `WHERE user_id` return plausible-looking data instead of an empty result — a screen that looks right and is not. Scoped into slice 1.1 with a test as the acceptance criterion. **Last verified pass 95:** `nextrade.db` holds **600 users, 414 holdings, 396 distinct `user_id`s** — the row's three figures, unchanged. |
| `slice 3` **Neither `groww.py` nor `grounding.py` has a caller** | **1,329 lines (537 + 792) and 73 tests of unwired code**, re-counted on pass 84 — the row said *1,019 and 61*, written before this session extended `grounding.py`, and never re-totalled. Zero non-test modules under `app/` import either. The test counts in §7 read as integration evidence and are not. **Action — and this plan already worked it out and did not write it back here.** Pass 88 established that **slice 1.4 becomes `grounding.py`'s first caller**, because the cost badge's figures must pass `check_all` against whatever produced them; and **slice 2.1's universe pull is `groww.py`'s first caller**. So neither needs a task of its own — both need the row to point at the slice that already claims it. |

**Pass 84 checked every open row that asserts something about the code,
against the code.** Three passes running had produced a claim that measurement
supported and the source did not, so this sweep is the systematic version of
what pass 83 did once. **Thirteen of the forty-one rows name a module, symbol
or file; twelve were exact.**

```
row  4  run_rebalancing_check has one caller, a test        exact
row  5  flat mean; [10,9,2,1] [1,3,8,10] [6,6,6,6] all -> 6 exact
row  8  rate_limit.py exists and is wired at app/main.py:75     exact
row 10  check.sh runs eleven checks                         exact  (10 step groups, 11 run calls)
row 11  frontend has no unit-test layer                     exact  (no test devDependency, 4 scripts)
row 29  screener_score: 10,346 of 10,346 in_sample = 1      exact  (in .navstore/nav.db, not nextrade.db)
row 31  4,957 catalogue / 4,939 with NAV / 5 last_error     exact
row 38  groww_universe.json absent                          exact
row 41  "1,019 lines and 61 tests"                          STALE -> 1,329 and 73
```

**The one that was wrong was wrong the same way §9's headline was:** a count
written once and never re-totalled while the thing it counted grew. Both were
my own numbers, and neither was caught by reading — only by counting again.
**The plan's older body held up; the errors of the last three passes were in
text written this session.**

**Pass 87 did the same for structure, and the document navigated worse than it
read.** Manan asked for *"ek dum clear navigation"*; that applies to the plan a
reviewer has to walk as much as to the app.

```
604 cross-references, 77 distinct     every one resolves
102 numbered headings                 4 were out of numeric order
§13   0 1 2 ... 9 9b 12 11 10   ->   ... 9b 10 11 12
§16   1 2 3 4 6 5              ->   1 2 3 4 5 6
§0    2 3 1                    ->   1 2 3
```

**Fixed by moving the text, not by renumbering** — §16.5 is referenced eight
times and §13.12 three, so changing the labels would have broken live
references to fix a cosmetic one. The reorder was checked by asserting the
document's multiset of lines was identical before and after.

🟡 **And one real fragility, left visible rather than silently patched.** §5's
nine refusals are referenced **thirteen times by position** — `§5.2`, `§5.6` —
but they are an ordinary markdown ordered list with no headings. Insert a tenth
refusal at position three and every reference from `§5.4` onward quietly means
something else, in the one section whose job is to say what the app will not do.
References to the PRD's own §5 are correctly written `PRD §5.6`, so the two
documents do not collide. `tests/test_plan_refusals.py` pins the nine in order
and rejects a `§5.n` outside the list; **it was mutated to confirm it fails on an
insertion**, because a change-detector that cannot detect the change is the
`check.sh` mistake again.

**Pass 88 asked the one question a build plan fails hardest on: does any slice
need something a later slice builds?** Two did, and both were in slice 1 — the
first slice, the one everything after it is re-priced against.

```
slice 1.2  "the disagreement count re-prints (71 of 1,233)"   needs the bulk pull   slice 2.1
slice 1.4  "check_all against the tool JSON that produced it"  needs tool contracts  slice 3.2
```

**1.2 was the worse of the two.** Comparing Groww TER against AMFI across 1,233
funds is not *one holding, end to end* — it is the universe, and
`backend/.growwcache/` holds **39** payloads. Worse, *94.2% TER agreement* is
**already one of slice 2.1's four acceptance figures**, so slice 1 had taken on
a universe-wide criterion it had no data for and that something else already
owned. Its acceptance is now about the held fund.

**1.4 was a wording fault with a real consequence.** `check_all(generated,
claims, source)` takes `source: object`, so it runs against whatever slice 1
has; only the phrase *"the tool JSON"* presumed §3.2. Fixing the wording exposes
something the schedule had not noticed: **slice 1.4 becomes `grounding.py`'s
first caller** — the exact gap §9.1 records and slice 3.1 was priced to close.
So 3.1 is smaller than it looks, and the guard starts being enforced in slice 1
rather than slice 3.

**The other thirteen acceptance criteria carry no forward dependency**, and
the slice bodies reference no later slice except slice 0's note that the waking
state moved *out* of 4.1 — a move, not a dependency.

**Every open row now says what to do, or says who has to decide — pass 127.**
A finding that names a defect and stops is half a finding, and thirteen rows
stopped. Five of those were right to: two wait on Manan, two are questions only
he can settle, and one is a recorded limit with no action by definition. **The
other eight were build items with no stated next step, and they now have one.**

**Two of the eight had already been solved by a later pass that never wrote the
answer back.** `grounding.py` has no caller — and pass 88 established that slice
1.4 becomes its first caller. `is_passive`'s second signal is missing — and pass
88 amended slice 2.1's pull to fetch the `st_filter` listing where that signal
lives. **The plan knew both answers and left both rows reading as open
questions**, which is its own failure mode: a document long enough to argue with
itself in two places.

**Every open row now says when it was last checked — pass 128.** Twenty-six
rows carried no provenance at all, which for a document whose whole discipline
is *where did this number come from* is its own defect: a reader could not tell
a row measured at pass 12 from one measured at pass 120. **Twelve were stamped
from passes that had verified them and never written it back** — the risk
questionnaire's three answer sets, the 600/414/396 fixture counts, the absent
virtualisation libraries, `AllocationPie` still imported, 4,957 against 4,939,
78.3 holdings per fund, `.holdings/` still absent, 10,346 of 10,346.

**Thirty of forty-four now cite a pass.** Of the fourteen that do not: **five are
`limit` rows**, which record what cannot be known and so have nothing to verify;
**five wait on Manan**; **three were written in the last four passes** and carry
their measurement inline. **One — `1,792 vs 1,741` — is genuinely unverifiable,
and by something on this same list**: re-counting needs the `groww.in` browser
permission that is still pending.

**A readability check, and one row that had stopped being one — pass 129.**
Forty-four rows, median **880** characters. The distribution is fine except at
the top: the cost-data finding had reached **7,702 characters in a single table
cell** — three pages of prose in a box a renderer will not break — because six
passes each appended to it rather than moving it. **It is now §2.5**, and the row
is a paragraph pointing there. Longest remaining row: **2,790**.

⚠️ **And the move was made wrong first.** §2.5 was inserted *before* §2.4 —
precisely the heading-order defect pass 87 found and fixed, reintroduced by the
pass that knew about it. Caught by re-running that pass's own check, which now
reports **0 headings out of order** across the document.

🟢 **Pass 130 gated both, because both were found by luck and one was a reintroduction.** `tests/test_plan_structure.py`: every heading must be in numeric order, and no open row may exceed **3,000 characters** — above that a finding has earned its own subsection and the row should point at it. **Both were mutated to confirm they fail**: §2.4 and §2.5 swapped, and a row padded past the limit. **The ordering one matters most** — pass 87 fixed that defect by hand, pass 129 committed it again, and nothing between them would have said so.

**What is actually waiting on Manan, separated from what is merely scheduled —
pass 133.** §8's user-count question turned out to be a scheduling input rather
than a blocker (§8.-1). The same test applied to the rest:

```
BLOCKS THE PLAN AS IT STANDS
  Manan's real portfolio      the design is validated against a plausible portfolio,
                              not his. Every screen decision, the badge vocabulary,
                              the levers order — all reasoned against holdings that
                              do not exist. Chrome permission for groww.in is the ask.

SCHEDULED WORK, NOT A BLOCK
  the 1,686 holdings pull     ~4 minutes, once. It is slice 2.1's own first step;
                              the approval is needed when that slice runs, not now.
  committing 17 untracked     already the second bullet of slice 0 ("Commit what
  files                       exists"), with the count and the risk stated there.

A SCHEDULING INPUT
  how many people use it      §8.1 does not turn on it, §8.2 explicitly retires
                              client count as the mechanism, and the legal reading
                              is unchanged. It moves three dates, not one decision.
```

**So one thing is genuinely blocking, not four.** This document has been carrying
all four at the same weight, which makes the plan read as more stalled than it
is — and the one that does block is the one nobody would guess from the list: not
an approval to *do* something, but the absence of the portfolio every design
choice was made for.

### 9.2 Closed, kept for the record

Each was a live defect in this document or the code beneath it. They stay
because a plan that quietly deletes what it got wrong is a plan nobody can
calibrate against — and this one was wrong often enough that the calibration
is the useful part.

| | |
|---|---|
| ✅ **The design rested on a portfolio nobody had — Manan said to invent one, pass 151** | *"app groww random koi apni marzi se portfolio bana kei karlo"*. Built from **real live funds**, one per category a retail investor actually holds, each the **median-cost** fund in its category rather than the cheapest — realistic, not flattering: `148990` ICICI Flexicap ₹60,000 · `119528` ABSL Large Cap ₹50,000 · `147445` Mirae Midcap ₹40,000 · `119544` ABSL ELSS ₹50,000 · `120406` JM Liquid ₹47,827. **₹2,47,827 across five funds**, which is the figure §3.1's mockup already used. The three questions it was holding open: **(1) look-through** — only 1 of the 5 has holdings in the cache, so this needs slice 2.3's pull; §3.3b already settled *whether to build it* on 741 pairs. **(2) density** — five rows, not twelve, and pass 100 found `Portfolio.tsx` is already a table, so the question §3.2 defers was answered in code. **(3) badges** — all five are Direct, so **`Regular plan — Direct saves ₹X/yr` fires zero times**, which *confirms* pass 136: the catalogue holds no regular plans, so a portfolio built from it structurally cannot trigger the badge §11.7 calls the largest number this app will ever show. ⚠️ **A first count said two funds were regular — that was my own 52-character name truncation**, caught by re-reading the full names. |
| ✅ **File:line citations were only correct in context — path-qualified on pass 145** | Pass 143 verified §14's six line references and got them right only because the sentence above them says *"Against `backend/app/schemas/`"*. A first attempt resolved `portfolio.py` by searching `app/` and landed on **`app/routers/portfolio.py`**, where line 262 is `[_to_input(h) for h in holdings], …` rather than *"the UI must not render it as zero"* — **six citations would have been reported stale on the strength of opening the wrong file.** Measured: `portfolio.py` resolves to `app/routers/portfolio.py` **and** `app/schemas/portfolio.py`; `research.py` likewise; only `main.py` is unique. Of the four cited paths in this document, **exactly one — `schemas/portfolio.py` — carries its directory.** 🟢 **Nothing is currently wrong** — every citation resolves correctly when read with its prose, and pass 143 confirmed all six word for word. **The defect is that they are only correct in context**, and a line number is the one kind of reference a reader follows *out* of context. **Fix: path-qualify all of them** — write the directory, not the bare file name. ✅ **Done on pass 145**, and the bulk substitution that did it promptly ate its own counter-example: the sentence briefly read *"write X, not X"*, because a regex rewriting every citation also rewrote the one quoted as the wrong form. **Eight citations now carry their path and every one was re-read against the line it quotes.** 🟢 **Pass 146 swept the document for the same collapse elsewhere — 17 contrast pairs, 0 collapsed** — and gated it: `tests/test_plan_structure.py` fails on any *"X, not X"*, mutation-confirmed. **A bulk edit cannot tell a form being recommended from the same form being warned about, so the document has to.** |
| ✅ **§11 was 513 lines on verification naming one of the nine files that do it — written on pass 115** | This repo carries **2,319 lines of verification harness**: `validate_nav_integrity.py` (729), `consistency.py` (470), `edge_cases.py` (271), `isolation.py` (216), `a11y.mjs` (204), `shots.mjs` (148), `mobile.mjs` (112), `sweep.mjs` (46) and `check.sh` (123). **§11 mentions `check.sh` and nothing else** — zero references to `validate_nav_integrity`, `consistency.py`, `isolation.py` or `edge_cases.py`, and zero to what they establish. **This is §3.0's defect at the section whose whole subject is verification.** The cost is concrete and has already been paid twice: pass 112 read the two scorers' cost asymmetry as an oversight when `consistency.py` documents it as deliberate under a heading saying so, and passes 26-35 kept discovering shipped work because the plan reasoned from itself. **What §11 is missing is not a citation, it is five facts** it currently has no way to know: the store is sampled back against `mfapi` so a restatement is noticed (inserts are `ON CONFLICT DO NOTHING`, so nothing else could); fund scores are **recomputed** from the store and held against the run's own recorded inputs; the newest run is checked for agreeing with itself; research and screener are held to the same fund **set** while their order is protected as deliberate; and accounts are checked for reaching each other's data. **Slice 0 gains a read, not a build.** **Closed by §11.10**, which reads all four backend harnesses and states what each establishes: the store sampled back against `mfapi` so a restatement is noticed, fund scores **recomputed** from the store against the run's own inputs, the newest run checked against itself, research and screener held to one fund set while their order is protected as deliberate, a stranger with a valid session checked against the owner's objects in both directions, and the advisor fed a one rupee target, ₹50 crore and a negative return. **Slice 0's line is a read, and it is done.** |
| ✅ **The plan's surfaces and the app's pages were two vocabularies with no map — built on pass 99** | Slice 4 was 11 sessions written in `Today`, `Why`, `Find`, `Ask`, `Holdings`, of which **not one was a page in this app**; across 35 mentions only 2 sat within 120 characters of a page file, and five of the twelve pages were never named at all. **Closed by reading `App.tsx`'s route table and what each page renders**, now a table at the head of slice 4: `Today`/`Holdings` → `Portfolio.tsx`, `Find` → `Screener.tsx`, `Why` and `Ask` → do not exist. The five unnamed pages are named there with their routes and line counts. **What the map found is filed as decisions below, not left inside this row.** |
| ✅ **`check.sh` runs eleven checks and this document mentioned it once — closed, verified on pass 93** | Found on pass 58, **recounted on pass 75 after I wrote "nine" twice from a comment in the file rather than from the file**. It runs pytest, NAV-store integrity, the frontend typecheck+build, edge cases (*"no 500s, no NaN"*), **cross-view consistency**, **account isolation**, the page sweep seeded *and* `--empty`, mobile, and accessibility. Three corrections follow: §8.2 said the safety case rests on a login screen it never names — `isolation.py` has been gating *"can one account reach another account's data"* all along; §11.4's concern about a record that stops matching its source is what `consistency.py` exists for, in the same voice; and slice 0's "marker gate" is a **step to add to a 123-line gate**, not a gate to build. The file also carries the fix for the failure this project keeps citing: `bash -o pipefail -c`, without which *"seven of the nine checks could not fail"*. **Verified today:** `check.sh` is exactly the **123 lines** this row claims, `pipefail` appears 3 times in it, `isolation.py` is named 5 times in this document and `consistency.py` 4 — so all three corrections landed and the row's own condition, *mentioned once as work to do*, is false: `check.sh` now has **20 mentions and its own §13.12**. Also repaired here: the row read *"It runs It runs pytest"*. |
| ✅ **This plan is an extension of the PRD's advisor, not a redesign — §0 now says so (pass 72)** | The PRD's SIP engine takes `annual_return_rate` as a **parameter** and looks nothing up. Across its 2,330 lines: **AMFI 0, mfapi 0, bhavcopy 0, Groww 2 in passing** — its only sources are `yfinance` and Angel One, both for the trading half. **The advisor it specifies is a calculator that never touches a fund.** This plan's entire §2 data layer, §1's five findings, the look-through, the cost verdict and the exit signal are **new scope**, and the 34-session estimate is the cost of the extension. The PRD's advisor is not hypothetical — it shipped, 600 users and 757 explained goals. **Fixed on pass 72 rather than filed:** §0 now opens with what it extends and what it leaves alone, states that the calculator shipped and works, and adds the two things it had assumed — the user count (§8.-1) and `/ask` as expansion (§17.5a). Reading it as "the PRD rebuilt" gets cost and risk wrong the same way: §2 looks like plumbing that existed, and §1's research looks like background rather than the thing that justifies the extension. |
| ✅ **`/ask` is scope beyond the PRD — §0 now says so, verified on pass 92** **Closed:** §0's scope block now carries the line *"`/ask` is an expansion beyond the PRD, whose LLM only ever explains a computation that just ran"*, with the consequence — that this one choice is why the grounding apparatus exists — stated beside it. The row's own condition was *"§0 does not say so"*. | PRD §5.7 fires the LLM in exactly three places — after SIP, after allocation, after tax saving — always **explaining a computation that just ran**, with every number handed to it pre-computed. §3.5 proposes a chat answering arbitrary questions. **That one choice is why the entire grounding apparatus exists**: when the model only narrates supplied numbers, hallucination is structurally hard, which is why 757 real generations had **zero** ungrounded figures; when the user can ask anything, the model picks tools and characterises results, and `check_all`, the refusal set and the registry are all holding that. §0 should record it as an expansion, since the AI layer's whole cost follows from it. Also dropped: the PRD's stated tone rules — *"3-4 sentences max"*, *"use emojis sparingly"* — which appear nowhere in §13 or §17. |
| ✅ **This plan never opened the PRD or its own research files — closed by passes 59-72, verified on pass 92** **Closed:** counted in the document today — `NexTrade_PRD_v1.md` named 6 times, `SECURITY.md` 12, `START_HERE.md` 4, `DEPLOY.md` 3, and `what-actually-predicts-returns.md` / `does-the-score-work.md` 4 each. §0.1 is the admission itself. | `NexTrade_PRD_v1.md` is **2,330 lines** — executive summary, personas, architecture, Part A advisor, Part B trading agent, tech stack, data sources, schema — and this document does not name it. Nor `SECURITY.md` (44 lines, while §8.1/§8.2 audited credentials), `DEPLOY.md`, `START_HERE.md`. **And §1, "the five findings the whole design rests on", cites none of `what-actually-predicts-returns.md` (285 lines), `does-the-score-work.md`, `do-factors-work-here.md`, `does-the-stock-score-work.md`, `why-there-is-no-fund-manager-screen.md` or `bachatt-teardown.md` — files in the same directory, with those questions as their titles.** The largest instance of the pattern this document recorded six times: read the plan, not the repo. **Slice 0's first task, ahead of the marker gate:** reconcile all ten and record in §12 whether each agrees, supersedes, or is superseded. |
| ✅ **The stock-score refusal now states what it does not know — pass 78** | §3.5 said *"the stock score's own measured record (won on NIFTY 500, lost on NIFTY 50)"* and stopped. It now carries the magnitudes — **+10.6% against −5.0%, mean IC −0.084** — the conclusion *"a result that reverses sign when you change the index is not a signal"*, and the admission that was missing entirely: **13 of the score's 100 points have never been tested**, because `dividend_yield` and `promoter_history` are empty in every observation and the promoter-stake adjustment has no measurement behind it. "Not shown to predict" and "part of it was never measured" are different admissions; only the first was being made. |
| ✅ **`START_HERE.md`'s status line — fixed on pass 75** | It said *"Phase: research + planning complete… **no app code yet**"*, dated 2026-06-29, and 158 commits had landed since. The file that tells a beginner *or a fresh AI agent* to read it first was telling them the app did not exist. Replaced with what is actually there — **49 endpoints, 92 schemas, 7 migrations, 1,603 tests, `check.sh`'s 11 checks, 5.2M NAV rows, 49 `.tsx` files, 600 users, 757 explained goals, and "Deployed: no"** — plus a pointer saying the plan is an **extension** of Part A, not a rebuild. ⚠️ **Two numbers in that replacement were wrong when first written and were caught by verifying them**: schemas are 92 not 88, and `check.sh` runs **11 checks in 10 groups**, not nine. "Nine" came from a comment inside the file rather than a count of it — which is the same mistake, inside the fix for it. |
| ✅ **The last three uncalled pure-logic functions — tested on pass 56** | `fund_facts.rank_at_horizons`, `fund_facts.holdings_for` and `category_ranking.rank_category`. Each test pins a claim the code's own comments make: a rank counts **only peers that have the number** (a denominator is a coverage claim, and "3 of 47" when 40 have no figure describes a field that does not exist); a fund with no figure of its own is **omitted, not ranked last** (n/a is not worst); an unparsed AMC reports `covered=False` rather than failing, because *"this fund holds nothing"* and *"we cannot see what it holds"* are different facts; and `rank_category`'s promise that **a goal's horizon prices the commission gap without reordering the list** — otherwise the same fund is best on one screen and third on another. ⚠️ My first `rank_at_horizons` test was itself wrong: it gave one peer and blamed the code for dropping the horizon, when the ≥2 guard is correct. The test failed, which is what a test is for. |
| ✅ **`build_stock_verdict` — the sentence a buyer reads — tested on pass 55** | Never named by any test, and it is what turns a score into words. `nextrade-stock-scorer-findings` records a 14-day-old listing scoring **100/100, "Strong Buy"**; `is_scoreable()` refuses that input now, but nothing checked the verdict layer. Six tests pin what §14 and §5 argue for — the headline names its peer group, a thin sector says so rather than silently claiming one, unpublished measures become a counted caveat instead of findings, the 52-week position carries *"not a view on where it goes next"*. **Three mutations, all caught.** Suite 1,591 → 1,597. |
| ✅ **`screener/fund_facts.py` tested — pass 54, and the coverage sweep is complete** | The last module the pre-existing suite never named, and the one that assembles the fund page's cost section. Four tests pin what its own comments argue for: **the ten-year saving is compounded, not multiplied** (1.03pp on a lakh is ~₹10,780, not ₹10,300 — the two diverge by only 5%, which is why the wrong one survives a glance); no rupee figure at all when the direct plan is not cheaper (*"the direct plan saves you ₹-400"* is arithmetic, not information); `None` not `0.0` for an unknown fund (§14: missing cost is neutral); and both ratios come from **one** loader so the page and the verdict can never disagree. **All three mutations caught.** Every service module is now named by a test. |
| ✅ **Momentum's stated coverage now derives from its computation — pass 53** | `window()` produced `measured_from`/`measured_to` from hardcoded calendar days while `score()` indexed trading rows; a mutation moving the calendar figure passed the suite. It now reads the span off the rows actually scored, with a documented fallback. **And the fix's own verification found more:** `_SKIP_DAYS 21 → 42` still survived, because the new test derives the window *from* the constants and moves with them — **consistency cannot pin correctness**. A second test pins `_LOOKBACK_DAYS == 250` and `_SKIP_DAYS == 21` to the t = +3.11 measurement they belong to. Both caught. Suite 1,584 → 1,587. |
| ✅ **`fund_evidence.py`'s missing tests — written on pass 52** | The module that defines what *1y* means had no test file; the mutation `WINDOWS 1y 365 → 300` passed 1,577 tests. `tests/test_fund_evidence.py` now pins the window lengths, the history-supports-the-window rule, None-not-empty-object, and the percentage→fraction TER conversion. **Re-mutated: all three caught.** ⚠️ The first TER test was itself decoration — it asserted against an *unknown* scheme code, so `None` short-circuited the conversion and it reported green while the mutation survived. Caught only because the mutation was re-run rather than trusted. Suite 1,577 → 1,584. |
| ✅ **"1,577 tests pass" now means something — measured on pass 49** | Nine mutations on the constants that decide money — cess, LTCG rate, LTCG exemption, the 12-month threshold, its boundary, two grounding guards, RSI period, goal inflation. **9 of 9 caught, 0 survived.** Not proof of completeness; it is the first evidence of any kind that the count is load-bearing, and it is what `nextrade-verification-gate` says to demand after a `check.sh` that could not fail. See §11.9, which also records the poisoned-bytecode trap the run produced. |
| ✅ **The long-term threshold now counts months — fixed on pass 48** | `is_long_term_equity` was `holding_days > 365`; Section 2(42A) counts **calendar months**. `fifo.py` now compares the sale date against the twelve-month anniversary, with 29 Feb clamping to 28 Feb rather than granting a free day. **8 of 8 boundary cases correct**, including the three that previously reported 12.5% where 20% was owed. `366` would have been the same mistake in the other direction and is explained in the docstring. Regression test in `tests/test_portfolio_fifo.py`; suite 1,576 → 1,577. `LONG_TERM_EQUITY_DAYS` is kept for display and is no longer what decides the rate. |
| ✅ **The backwards trim criterion — closed on pass 21, filed on pass 48** | Slice 2.4 now reads *"`trim_nav_store.py` must **EXCLUDE** `stock_daily` and `corporate_actions`"*, the opposite of what it said, with the test that the gzipped output stays near 23.9 MB after the archive lands. The row sat in §9.1 for twenty-seven passes after the thing it described was fixed. |
| ✅ **"Zero false positives" — claim corrected, and there is no code to fix** | Pass 17 found three (`Inflation INDEXED Bond Fund` × 3), and pass 25 found a better signal entirely (name↔`benchmark` token overlap: passive 1.00, active max 0.33). **`is_passive` does not exist anywhere in the repo** — grep returns nothing — so both are specifications waiting on slice 2.1, not live defects. The tested regex (`\bindex\b\|…\|\betfs?\b`, 452 → 449, removes exactly the three) and the benchmark signal are both written into §2.3. |
| ✅ **Two Groww fields, decoded — closed on pass 47** | The mapping was carried as *"inferred from magnitudes, not confirmed"*. **Now measured against the local NAV store**, which had the answer all along: `simple_return.return3y` is the **cumulative** 3-year return — **12 of 12** funds match a NAV-derived cumulative figure — and `sip_return.return3y` is a **monthly-SIP XIRR** — **9 of 9** within 0.58pp of a simulated SIP, most within 0.3pp. Both fields are now readable, and the older `sip_return3y`/`sipReturn3y` pair that disagreed (43.44 vs 27.43) can stay unread. |
| ✅ **"The 18 tools in §3.5" — §3.5 names seven, and enumerates none — closed** | **Closed on pass 46: §3.5b now carries the enumerated registry** — 18 rows, each with what it answers, its backing route and a status. 13 live, 2 live-but-untyped, 3 genuinely new. So slice 3.2 is *type two endpoints, wrap fifteen, build three* — and the three new ones (`look_through`, `company_exposure`, `switch_cost`) are the most distinctive things in the product, which is where the effort should land. |
| ✅ **The app asks Google for a refresh token it never uses, and stores it in plaintext on Turso — closed** | **Closed on pass 46.** `access_type=offline` deleted from `routers/auth.py` — the request is gone, so there is no long-lived credential to store or encrypt. The token-exchange error log now emits status plus 120 characters, not the whole body, and the authorization-code prefix is no longer logged at all. Scopes were already identity-only. |
| ✅ **`why_ranges` is a caveat that cannot be wrong, because it is not computed — closed** | **Closed on pass 46.** `build_track_record.py` now computes `why_ranges` from the run it belongs to — `RUNS` and the window counts actually observed — instead of re-emitting a hardcoded sentence about five runs while `RUNS` was 3. A caveat that is a constant is decoration. |
| 🟢 **§14 was consistency-checked against vault notes, not code — and the code enforces it harder** | §14 states it was checked against `traa-decisions`/`traa-gotchas`/`traa-base-rates`: **prose against prose**, the error pass 20 named. Against `app/schemas/`, which this plan never opened, its rules appear **24 times as response contracts** — *"the UI must not render it as zero"*, *"Never dropped silently"*, *"a screen that hides its own coverage is lying by omission"* (in this section's own voice), `unpriced_invested`, `price_as_of`, `stale`. Coverage is a **type**, `ScreenerCoverageOut`, whose docstring says `as_of` and `stale_days` are not optional *"because a nightly precompute that quietly goes stale returns 200 with old numbers"*. **So §14 is stronger than it claims:** these are not principles to remember but fields a rebuild must actively delete — inherited automatically by any screen consuming the existing endpoints, which this plan names none of. |
| 🟢 **§1.5's headline is half-shipped, and the half that is shipped already has the discipline** | `OverlapPairOut` carries `common_weight` (*"share of net assets in the same securities, matched on ISIN"*), `shared_securities`, and `holdings_as_of` — that is §1.5's *"29 common names, 46.8% overlap"*, live behind `GET /api/v1/portfolio/overlap`. Its own comment already says **"None means unmeasured — the UI must not render it as zero"**, so §14's rule is encoded, not pending. **The other half is genuinely absent:** nothing computes *"₹1,00,000 in, ₹90,945 reached equity"* — and pass 26 found the input (`holdings[].nature_name = "CASH"`), so it is one aggregation, not an engine. Planning the headline as one block is how the built half gets rebuilt and the unbuilt half gets assumed. |
| ✅ **The migration chain replays from empty and reproduces the live schema exactly** | Never run before: `alembic upgrade head` against an empty database — which is what a fresh **Turso** deploy does. All 7 migrations run clean, and the resulting schema is **identical** to the live one (tables, columns, types, nullability). Both `op.alter_column` calls are `users.phone` nullability and replay fine; **no `batch_alter_table` anywhere**, so no table rebuilds cross the network. Slice 1.1's column additions rest on this and it holds. |
| 🟢 **757 real LLM generations were in the database, and grounding.py scored zero hallucinations on them** | §4 reads as though no LLM has run here. `goals.llm_explanation` is populated **757 of 757**, all written before `grounding.py` existed. Checked against their own rows: **0 ungrounded figures.** The 46 spelled-out-number flags were **all false positives** — the words sat inside the user's own goal name (`Edge fifty crore`) quoted back correctly. Fixed with a verbatim-quote exemption (4-char floor); **757/757 now pass**, and a genuinely smuggled `twenty` is still caught. §3.4's adversarial suite no longer needs inventing — it starts from these 757. |
| 🟢 **`fund_ter_history` is not an engine to build — Groww ships 11 years of it** | `historic_fund_expense[]` is present in **39 of 39** payloads: median **1,091 daily entries**, back to **2013-06-30**, ~130 months, median **187 distinct TER changes** per fund. §3.5 lists it among five *"genuinely new"* engines; it is a field read. **One of five removed from slice 3.2.** It also corrects a design choice: `as_of` was in `groww_universe`'s PK partly to *accumulate* TER history for §3.4's chart — accumulating monthly would take **eleven years** to reach what one request returns, and the chart would show one point on day one. See §16.6. Also found: `historic_exit_loads[]` (exit-load history, 1-6 entries), `holdings[].nature_name = "CASH"` (an explicit field for §1.5's cash-vs-equity split, currently inferred), and `groww_scheme_code` holding an **ISIN**, not a scheme code. |
| 🟢 **`benchmark` is a better passive signal and the plan never mentions it** | Name↔benchmark token overlap: passive **1.00, 1.00, 1.00**; active mean **0.05**, max 0.33. A passive fund's name contains its whole benchmark (`UTI Nifty Next 50 Index Fund` / `NIFTY Next 50 TRI`); an active fund's shares nothing (`Abakkus Small Cap Fund` / `NIFTY Smallcap 250 TRI` = 0.00). **Structural, not orthographic — so it fixes the `Inflation Indexed Bond Fund` false positives at the root** instead of by maintaining a list of words that merely look like "index". n=3 passive, so slice 2.1 confirms on the full universe before it replaces anything; the regex stays as a second opinion with disagreements counted. |
| ✅ **The mechanism behind "86 of 123" is confirmed, even though the count is not** | Three Nifty index funds in the cache, all filed by Groww under `sub_category = "Large Cap"`. The premise of §2.3 — that Groww classifies an index fund by the cap it tracks — is established from retained data. Only the count still needs the pull. |
| ✅ **One of §12's six figures reproduced — and the join key it needs was never written down** | 32 of 39 cached Groww payloads join to `expense_ratios.json`; **31 of 32 agree within 0.10pp = 97%** against the claimed 94.2% over 1,233. Claim stands. **But the join is `scheme_code` ↔ the file's top-level AMFI code key, and joining by NAME returns exactly zero** — the two sources spell every fund differently, so a builder reaching for the name field (the one a human reaches for) gets an empty result with no error. Neither the key nor that trap appears anywhere in this plan. Slice 2.1 now joins on `scheme_code`, counts the unjoined as a first-class number, and fails if it joins on name. |
| ✅ **The undeclared-dependency class is closed, after three instances** | `numpy`, `pandas` (pass 11) and now `requests` were each imported directly by `app/` and declared nowhere, arriving via `mftool`/`yfinance`/`twilio` — **and this plan retires `yfinance`**, so consumer and supplier move opposite ways. A fourth, `casparser`, is named in §3.0 and **is not installed at all** (`ModuleNotFoundError`), while slice 1.1 prices it as though it were. Rather than hunt a fifth, `tests/test_declared_dependencies.py` walks `app/`'s AST and fails on the class; it separates a module pulled in by a **declared extra** (`fastapi-users[sqlalchemy]` — asked for) from one that arrives by luck. **Shown failing** before being kept. |
| ✅ **`pandas` was imported by seven files and declared nowhere — fixed 2026-08-28** | Found by checking the plan against this project's own memory rather than against the repo. `screener/scoring.py`, `metrics.py`, `stock_scoring.py`, `basket.py`, `basket_build.py`, `universe.py` and `marketdata/fund_holdings.py` all import it directly; it was arriving **only transitively through `mftool` and `yfinance`**. `requirements.txt` even *documents* this — *"pandas arrives transitively through yfinance"* — next to the line where **numpy got a pin for exactly the same reason.** numpy got the fix, pandas got the comment. 🔴 **And this plan makes it worse:** §2 retires yfinance for prices, removing one of the two suppliers of a dependency the whole scoring engine imports. Now declared `pandas>=3.0,<4.0`. |
| ✅ **Three tax questions closed against the ITD's own portal — 2026-08-28** | §10 carried the capital-gains surcharge cap and the ₹1.25L LTCG exemption as *unverified risks needing a second source*. Both confirmed at `incometax.gov.in`, and **verifying the first one changed the specification**: the cap is `min(slab, 15%)`, not a flat 15% — the enhanced 25%/37% tiers are disapplied, the 10% and 15% tiers are not. Coding a flat 15% would have overcharged everyone between ₹50L and ₹1Cr, a fresh error one bracket below the one being fixed. Marginal relief confirmed at all four thresholds, in the same words as slice 1.3's acceptance criterion. **Still single-sourced and not hardcoded:** the 80D/80CCD/87A/112A renumberings — the portal writes everything in 1961-Act numbering, so it cannot corroborate them. |
| ✅ **`.holdings/` was not gitignored — fixed 2026-08-28** | Found by a fifth review pass checking §16 against the filesystem instead of reading it. The previous revision moved the look-through store out of `.navstore/` for a good reason and never told git the new path; `.gitignore` ignored `.holdingscache/`, which nothing references. One `git add -A` after slice 2 from committing a growing binary DB — **the same class of risk as the `.growwcache/` gap, created by the revision that fixed it.** Second time in this plan that moving a file to protect it is what exposed it. |
| ✅ **`grounding.py`'s four holes — closed 2026-08-28** | All four fixed, each with the case that found it pinned as a test, plus the two extras this row used to list (plural `isins`, Unicode minus) which were real. 38 tests → 50; full suite 1,561 → 1,571. The path-ambiguity claim was **under**stated: measured across all 39 cached Groww payloads it rejected 230,067 of 240,404 citable figures (**95.7%**, not the 90% written down) and **every collision was same-meaning**, so it was rejecting correct output and catching nothing; now 0.2%. **One honest limit remains, by design:** the predicate rule only covers fields in a maintained list, so an unruled field is reported in `Grounding.unruled` rather than checked — the hole is bounded and counted, not eliminated. See §17.6. |

---
| ~~Tax parameters for FY 2026-27~~ | **Resolved — see §10.** Every value is unchanged; the section numbers are not. |
| ~~§1.1's estimator is biased~~ | **Resolved.** It was never biased — the drift was variance from one control draw per cohort. 200 draws puts every control within 0.003 of 0.500 and the gate passes honestly. |


## 10. Tax — verified, and the answer splits in two

Checked today because the module docstring says FY 2025-26 and it is now
FY 2026-27, and because tax is the largest single number this app reports.
Full record in [[traa-tax-fy2627]].

**Every value is unchanged.** Budget 2026-27 (1 Feb 2026) made no change to
personal income tax. Slabs, standard deduction (₹75,000 / ₹50,000), 87A
(₹12L/₹60,000), 4% cess, 80C ₹1.5L, 80CCD(1B) ₹50,000, 80CCD(2) at 14%, equity
STCG 20% / LTCG 12.5% above ₹1.25L — all confirmed current. **No numeric
constant in `tax_regime.py` or `tax_advisor.py` needs editing.**

🟢 **Pass 125 made the annual re-check unmissable instead of manual.** The confirmation above was done by hand, once; nothing made the *next* one visible. `tests/test_tax_regime.py` now fails the moment the Indian financial year moves past the last year `tax_regime.py`'s first line names — not a claim that anything is wrong, a prompt to check the Budget. The module docstring now names **both** FY 2025-26 and FY 2026-27, which is what was actually verified. 🔴 **And the first version of that guard was inert.** It scanned the first 600 characters, which include prose mentioning *FY 2026-27* and *FY 2023-24*, so backdating the declaration still left a recent year for `max()` to find — **the mutation survived**. Narrowed to the first line only, it catches it. A guard that cannot fail is the `check.sh` mistake, and it took a mutation to notice.

🟢 **So pass 126 mutation-tested every guard written in this review, not just that one.** Each was given a change it is supposed to notice, run, and restored:

```
test_plan_endpoint_counts   an untyped route becomes typed            CAUGHT
test_ter_coverage           _MAX_MF_ID raised from 55 to 90           CAUGHT
test_category_names         a variant merged into its real category   CAUGHT
test_plan_counts            an owner tag set to an unknown value      CAUGHT
test_plan_counts            a stated group size drifts from the tags  CAUGHT
test_declared_dependencies  a used dependency removed from reqs       CAUGHT
test_tax_regime             the declared financial year backdated     CAUGHT (after the fix)
test_return_bounds_agree    RETURN_BOUNDS moved (pass 91)             CAUGHT
test_plan_refusals          a tenth refusal inserted (pass 87)        CAUGHT
```

**Nine of nine, and the one that was inert was found only because it was tried.** Reading a guard tells you what it intends; running it against the change it claims to catch tells you whether it does.

🟡 **One thing stays on a single source, and now for a known reason.** The
80D→126, 80CCD→124, 87A→156, 112A→198 renumberings could not be corroborated:
the ITD portal reached above writes **every** section in 1961-Act numbering
(`111A`, `112A`, `112`), which is consistent with this section's own finding that
current forms tax FY 2025-26 income — but it means the authoritative source
cannot confirm the new numbers. **80C→123 has three sources and is safe; the
other four have one and are not hardcoded.** Showing both numberings (below) is
what makes that survivable rather than blocking.

**And the Income-tax Act, 2025 came into force on 1 April 2026 and repealed the
1961 Act outright.** `80C` is now **Section 123** (three independent sources).
Other mappings — 80D→126, 80CCD→124, 87A→156, 112A→198 — come from a single
article and are **not to be hardcoded without a second source.**

The decisive practical fact: **the ITR forms being filed right now still use the
old numbering**, because they tax FY 2025-26 income, earned before the new Act
commenced. Forms with the new numbering are not expected before ~April 2027.

> **So the app shows both:** `80C (now Section 123, Income-tax Act 2025)`.
> Someone cross-checking against this year's form needs `80C`; someone reading
> the Act needs `123`. Picking one makes the other wrong. This is a product
> decision, recorded here rather than made silently in a patch.

### A defect found while checking, which was not what we were looking for

**`tax_regime.py` has no surcharge logic at all.** Not stale — absent since the
start.

```
₹50L – ₹1Cr   10%        ₹2Cr – ₹5Cr   25%
₹1Cr – ₹2Cr   15%        > ₹5Cr        25% new (capped) / 37% old
```

Above ₹50L the two-regime comparison is wrong, and it is wrong **in the new
regime's favour**, because the new regime's surcharge is capped at 25% while the
old runs to 37%. That is precisely the income level where the rupee difference
is largest. Goes into `nextrade-code-defects` and into slice 1.3.

**The fix is not the table above.** Writing those four rates into a function
would produce a second wrong answer, because two rules sit on top of them and
both bite in this app specifically:

1. **Marginal relief.** Surcharge is a cliff: crossing ₹50L by ₹1 would add
   roughly ₹1.4L of surcharge if applied naively. Marginal relief caps the total
   extra tax at the extra income, so the effective rate ramps rather than jumps.
   Omitting it makes every figure just above each of the four thresholds wrong,
   and wrong by more than the surcharge itself at the margin. **Any surcharge
   implementation without marginal relief is worse than none**, because the
   current code at least fails in a single obvious direction.
2. **✅ The capital-gains surcharge cap — VERIFIED 2026-08-28, and the wording
   matters more than the number.** This was written as an unverified risk needing
   a second source. It is now confirmed against the **Income Tax Department's own
   portal** (`incometax.gov.in`) — not a second source but the authoritative one:

   > *"The enhanced surcharge of 25% & 37%, as the case may be, is not levied,
   > from income chargeable to tax under sections 111A, 112, 112A and Dividend
   > Income. Hence, the maximum rate of surcharge on tax payable on such incomes
   > shall be 15%"*

   🔴 **And it is not a flat 15% — which is how this document first wrote it, and
   how it would most naturally be coded.** What is disapplied is the **enhanced**
   surcharge: the 25% and 37% tiers. The 10% and 15% tiers still apply normally.
   So the rule is `min(slab_surcharge, 15%)` on that income, **not** `15%`.
   Hardcoding a flat 15% would *overcharge* someone between ₹50L and ₹1Cr, whose
   correct rate on gains is 10% — inventing a fresh error at the income level
   just below the one this defect already breaks. **Verifying the claim changed
   the specification**, which is the whole reason the plan refused to hardcode it
   on a single note.

   The practical effect stands: at ₹3Cr income the salary carries 25% surcharge
   and the gains carry 15%, so applying the slab rate to a redemption overstates
   the tax on the single number this app exists to get right.

   *(Act sections are spelled out, never written `Section` as `§`. Everywhere else
   in this document `§` means a section of THIS plan, so `§112` would read as a
   cross-reference to a section that does not exist — a reviewer chases it, finds
   nothing, and distrusts the paragraph.)*

**Marginal relief is confirmed by the same source**, at all four thresholds, with
the mechanism stated as: total tax and surcharge must not exceed the tax payable
at the lower threshold plus the income above it. That is **word for word** the
acceptance criterion §7 gives slice 1.3 — *one rupee more income, at most one
rupee more tax* — so the test and the statute now say the same thing.

So slice 1.3's task is "surcharge **with** marginal relief and `min(slab, 15%)`
on 111A/112A/112 income", not "add a surcharge table". All three parts are now
verified against the Income Tax Department's own portal rather than recalled.

### ✅ A third defect, found on pass 15 and fixed on pass 48: the long-term threshold counted days, and the law counts months

`portfolio/fifo.py` decides the single most consequential fact in this app:

```python
LONG_TERM_EQUITY_DAYS = 365
return self.holding_days > LONG_TERM_EQUITY_DAYS
```

Section 2(42A) does not say 365 days. It says a listed equity share or
equity-oriented fund is **short-term when held for not more than twelve
months** — so long-term requires *more than twelve months*, counted in calendar
months. A day count is a proxy for that, and the proxy breaks **every time the
holding period spans a 29 February.** Measured:

```
buy 2024-01-01  sell 2025-01-01   366d   code=LONG   law=SHORT   <-- disagree
buy 2023-03-01  sell 2024-03-01   366d   code=LONG   law=SHORT   <-- disagree
buy 2023-12-15  sell 2024-12-15   366d   code=LONG   law=SHORT   <-- disagree
buy 2024-03-01  sell 2025-03-01   365d   code=SHORT  law=SHORT
buy 2024-02-29  sell 2025-02-28   365d   code=SHORT  law=SHORT
```

**Three of five boundary cases disagree, and every disagreement runs the same
way**: the code says long-term where the statute says short-term, so the app
reports **12.5% where 20% is owed** — understating the tax by 7.5 percentage
points of the gain, on precisely the day it tells the user the wait is over.

Roughly one purchase date in four has its twelve-month anniversary on the far
side of a leap day, so this is not a rare boundary; it is a quarter of them.

**The fix is not `366`.** That is the same mistake with a different constant and
it breaks the non-leap years instead. **Calendar-month arithmetic** is the only
form that matches the statute: long-term when the sale date is strictly after
the same day twelve months later. And because the anniversary is a cliff worth
7.5pp, §14's rule applies — *a value that moves with an assumption is a range* —
so on the boundary day itself the app says **"one more day removes all doubt"**
rather than asserting a rate.

✅ **Fixed on pass 48, not deferred to slice 1.3.** `fifo.py` now compares the
sale date against the twelve-month anniversary — `_months_after()`, with 29 Feb
clamping to 28 Feb so a leap-day purchase gets no free day. The five rows above
became eight boundary cases and **all eight pass**, including the three that
previously reported 12.5% where 20% was owed. `tests/test_portfolio_fifo.py`
carries them, and `LONG_TERM_EQUITY_DAYS` survives for display only, with a
comment saying it no longer decides the rate.

### Two more, one changed and one a live risk

- **CHANGED:** SGB premature redemption (after the 5-year window, before 8-year
  maturity) is **no longer tax-exempt** from 1 April 2026. Full maturity remains
  tax-free. New SGB issuance is still discontinued.
- **✅ CONFIRMED 2026-08-28** (this read "RISK, unverified"): the ₹1.25 lakh LTCG
  exemption is a **Section 112A** provision covering **equity shares and
  equity-oriented mutual funds only**. The ITD portal writes the threshold as
  *"Capital Gain income u/s 112 A … up to ₹1,25,000"* and treats Section 112 —
  where gold ETFs, debt-oriented and international funds sit — separately, with
  no such threshold. **The rule the plan already assumed is correct and now
  sourced:** the equity exemption is never applied outside equity. Doing so would
  overstate a tax saving, the exact class of error the tax lever was rebuilt to
  remove.

---

## 11. The things a plan of this size usually leaves out

An adversarial review listed six omissions. Each is answered here rather than
discovered during the build.

### 11.1 What "horizon" means

Three separate rules price against it — the levers engine, the cost badge's
breakeven, and the base-rate class on a category. It is defined once:

> **Horizon is per goal, not per user.** It is the years remaining to that
> goal's target date. A holding tagged to no goal uses the **profile horizon**,
> which is asked for once and defaults to nothing — with no horizon, the cost
> badge shows the annual saving and the breakeven **and refuses to conclude**,
> because "is 2 years too long?" has no answer without it.

That refusal is the point. An assumed horizon is how the tax lever originally
showed every user a ₹36.8L number that applied to almost none of them.

### 11.2 Every screen's degraded state, specified

§2.1 says the app degrades without Groww. That is only true if it is drawn.

| surface | Groww down | holdings stale >45 days | TER rejected by the two-source gate | fund left the buyable universe |
|---|---|---|---|---|
| Today | levers unaffected (they run on AMFI + user data); "what changed" says it is not current | unaffected | unaffected | unaffected |
| Holdings | value, XIRR and benchmark unaffected; verdict badges that need holdings are withheld **with the reason named** | overlap and look-through withheld, disclosure date shown | that row shows `cost from one source` instead of a cost verdict | row renders from the **last good pull**, marked "no longer sold on Groww — held, not buyable" |
| Look-through | not rendered; says which month it would have used | rendered with the date prominent | unaffected | that fund's slice marked stale |
| Find | ranks on AMFI alone, banner at the top of the list, not a footnote | unaffected | fund excluded from cost ranking, listed with the reason | excluded from Find, still visible in Holdings |
| Ask | tools return the gap; the model narrates the gap | same | same | same |

**The fourth column is the one nobody plans for.** `parse_universe` drops
`available_for_investment != 1`, and Manan can own a fund Groww has stopped
selling. Without this, his own holding would silently have no TER, no holdings
and no manager. The Holdings screen therefore reads from a **union** of the
current universe and every scheme code the user actually holds.

### 11.3 Look-through storage

1,686 funds × **78.3 disclosed lines on average** (measured across 39 cached
payloads; median 73, range 29–254) ≈ **132,000 rows a month**, and the pull is
~4 minutes. That is a store, not a cache.

- A table keyed `(scheme_code, portfolio_date, name)` in the **existing
  `nav.db` file** — it is already a separate SQLite store built for exactly this
  shape, and a second file is a second thing to back up.
- **Only funds the user holds are pulled on the monthly cadence.** The full
  1,686 pull happens once and then only for funds newly held or newly listed.
  Manan holds perhaps a dozen; the honest steady state is a dozen requests a
  month, not 1,686.
- **Disclosures are append-only.** Last month's holdings are the record of what
  the fund held last month, and overwriting them destroys the only way to detect
  drift.
- **Staleness is shown, never inferred.** SEBI requires monthly disclosure, so
  anything older than ~45 days means the AMC or the pull failed, and the screen
  says which.

### 11.4 The scoreboard has to be regenerated, or it becomes marketing

§3.6 makes `track_record.json` the centrepiece of the app's honesty. A published
record that no longer matches the engine is worse than no record.

> `check.sh` regenerates it and **fails if any published figure moved by more
> than a stated tolerance without the file being updated in the same commit.**

The measurements it holds — 50%, 38%, 87%, and now §1.1's "cannot distinguish
from noise" — are claims about the current code. They stop being true silently.

### 11.4b 🔴 The failure this document committed while being written

An adversarial review put this as the biggest unnamed risk, and it is right,
because it had already happened four times inside one afternoon:

> **This document is a hand-transcribed cache of measurements with no
> regeneration path, and it went stale during its own review.**

- §1.1's table was edited, the script it quotes was fixed an hour later, and
  §1.1, §9 and §11.5 became false **in the same session they were written**.
- §1.1's prior-measurement figures disagreed with `track_record.json` in every
  cell — 60 windows against 44, 50% against 43%, a quartile figure assigned to
  the wrong side, "45 of 52" against 43. They came from a vault note rather than
  the file.
- §4.3 said "21 tests" when there were 38.
- §5.1 still carried a conclusion §1.1 had explicitly retracted.

Four independent drifts in a document whose §11.5 is titled *"What this document
will and will not claim"*. The failure is not any single wrong number — it is
that **the honesty discipline is enforced in prose, and prose has no test.**
Someone reading this in six months will trust the "measured today" framing, and
most of it will be wrong in ways no gate can see.

**The fix is the one §11.4 already writes for `track_record.json`, applied to
the document that cites it:**

- Each script writes a small JSON beside its output — `track_record.json`
  already does, `validate_exit_signal.py` gains one, and so do the universe and
  TER counts.
- The document holds **markers** rather than typed numbers.
- **`check.sh` fails when a marker disagrees with its JSON.** Not a lint — the
  same gate that runs the tests.
- Anything that genuinely cannot be regenerated is tagged **`[quoted, not
  regenerated]`**, which §11.5 already has the vocabulary for. Every figure in
  this plan attributed to an outside paper carries it.

Until that exists, **§12 is the single reconciliation point** and every count in
the document is expected to agree with it.

### 11.5 What this document will and will not claim

Written down because §1.1 got it wrong twice.

**Every measured claim carries:** the script that produces it, the store it read,
n as observations (not cohorts), a control where one is constructible, and an
interval. A number without those is a quotation, and quotations are labelled.

**Refused outright:**
- reading a group against 0.500 when its own control is not 0.500
- reporting overlapping windows as independent tests
- a nominal significance from one of twelve tests, in either direction
- any figure this session could not re-verify: the FCA 11%/12% gamification
  numbers, Akepanidtaworn's ~80bps, DALBAR and Mind-the-Gap in every form,
  Kinnel's expense quintiles, and the single-source Income-tax-Act section
  mappings beyond 80C→123

**Pre-registered, before the build:** the exit-signal gate is
`validate_exit_signal.py`; its pass condition is that **every control lands
inside 0.470–0.530**, and it now passes with all controls between 0.497 and
0.503 — because the instrument was fixed, not because the band was widened. The
band stays where it is. If a future change drifts a control outside it, that is
a failure to investigate, not a threshold to adjust.

### 11.6 Sequencing, and what actually blocks what

The ten steps are not independent, and one of them gates almost everything.

```
slice 0  marker gate · commit what exists · fix the exit-signal gate
   │
   ▼
slice 1  ONE HOLDING, END TO END          ← the first thing he can look at
   1.1 schema + a holding in
   1.2 its cost, both sources        ← the money gate; nothing downstream
   1.3 surcharge + marginal relief     is trustworthy before this
   1.4 the badge, on a real row
   │
   ├────────────► slice 2  widen the universe
   │                 2.1 Groww universe   2.2 NAV backfill
   │                 2.3 holdings + look-through   2.4 stock store + corp actions
   │
   ├────────────► slice 3  the AI layer
   │                 3.1 fix grounding    3.2 tool contracts
   │                 3.3 Gemini client    3.4 /ask
   │
   └────────────► slice 4  the rest of the surfaces
                     4.1 navigation  4.2 Find  4.3 Today + Why  4.4 the devices
```

Slices 2, 3 and 4 depend on slice 1 and on each other only where marked —
2.3 must precede 4.2's overlap-at-purchase, and 3.2 must precede 3.4.

**Steps that §11 added and §7 did not carry, now folded in:** CAS import as
**step 0** (§3.0); the `track_record.json` regeneration gate and the document
marker gate (§11.4, §11.4b); the Holdings **union** of the buyable universe and
held scheme codes (§11.2), because `parse_universe` drops
`available_for_investment != 1` and Manan can own a fund Groww stopped selling;
and §2.1's degraded-state assertion — *a screener run with `groww.py` forced to
raise must still return a ranking and must contain PPFAS* — which is the single
test that makes graceful degradation real and appeared in no step.

**Step 9 is not a gate as written.** With 200 control draws the control is
0.500 ± 0.008 by arithmetic, so "build fails if the control leaves 0.470–0.530"
can never fire. Before the fix it could never pass (twelve seeds, twelve reds).
Neither version tests anything about funds. The gate becomes: **the distinct
formation-date count per row is printed and the run fails if any row prints an
interval on fewer than four dates** — which is a condition the data can actually
violate.

**1.2 and 1.3 gate the money.** Cost is the only measured signal and 55% of the
score; until the two-source gate and the surcharge fix are in, every rupee figure
downstream is provisional.

**And slice 1 exists to move the discoveries forward.** The schema gaps (§16),
the badge-width contradiction (§7.5), the plan-type problem and the harness
rewrite (§7.6) all surface inside it — at a session each, in week two, instead
of as a rewrite in week nine.


### 11.7 The biggest risk in this plan, which nothing above names

Not Groww blocking the endpoints — §11.2 draws that. Not the regulation — §8
settles it. It is this:

> **Every rupee this app reports rests on data typed in by hand, and nothing
> checks it.**

The portfolio is manual (§0, Manan's call). XIRR, the benchmark comparison, the
cost badge's capital-gains arithmetic, the look-through weights and every lever
in `Today` are computed from transactions he entered. A wrong date, a
transposed amount, a forgotten SIP instalment — none of it raises an error. It
produces a slightly different number that looks exactly as authoritative as a
correct one. This project's whole discipline is that **a wrong number that looks
right is worse than a missing one**, and manual entry is the largest generator
of them in the system.

Three checks, none of which need his permission for anything:

1. **Units against NAV.** For every fund holding, `units × today's NAV` must
   equal the reported value. It does by construction — which is exactly why the
   useful version is the reverse: **rebuild the transaction history from NAVs
   and flag any lot whose implied purchase NAV is outside that day's actual
   NAV** by more than a rounding tolerance. A date typed a month late shows up
   immediately.
2. **Plan type from the scheme code, never from the name.** Already a recorded
   gotcha: code 118955 is Direct despite what the name suggests, and TER is
   filed under the *direct* code even for a regular-plan holding. If a holding
   turns out to be a **regular** plan, the cost lever is the largest single
   number the app will ever show him — and getting that wrong in either
   direction is the most expensive mistake available.
3. **Cross-check against Groww's own portfolio, when he grants it.** He is
   logged in; the extension permission is pending (§9). `stocks_router/v4/holding`
   and `mf/prime/v1/portfolio/dashboard` exist and are read-only
   (`docs/groww-endpoints.md`). That turns manual entry from an unverified input
   into a **reconciled** one, and it is the single highest-value thing still
   blocked on him.

Until (3) exists, every screen that prices a decision should carry the
provenance of the numbers it used — not a disclaimer, a statement: *"computed
from 14 transactions you entered, last updated 12 March."* A number whose origin
is visible can be checked. One whose origin is invisible gets believed.


### 11.8 What Phase 1 must leave room for, so Phase 2 is not a rewrite

Trading is explicitly out of scope (§0). But three decisions taken now are
expensive to reverse later, and one of them is already made correctly.

| decision | taken now as | why it survives into a trading phase |
|---|---|---|
| **Price history** | NSE bhavcopy store, 26 years, daily, survivorship-correct by construction (§2.2) | A signal that cannot be backtested point-in-time cannot be traded. This store is the prerequisite, and building it for advisory costs nothing extra. |
| **The LLM boundary** | narrates, never decides, never computes (§4.2) | A 64%-accuracy layer must not gain order capability by drift. Writing the boundary as an architecture rather than a policy is what stops that. |
| **The order path** | does not exist | Nothing to disable later. Adding it would be a deliberate act with its own review, not a flag flip. |

And one thing Phase 1 should deliberately **not** do: pre-build hooks, adapters
or abstractions "for Phase 2". The repo's own record is that speculative
generality is what makes the second version harder, not easier. The stock store
earns its place because advisory needs base rates and delivery history today —
not because trading might want it.

---


### 11.8b The verifier that was wrong about the numbers — pass 76

Pass 75 caught two wrong figures by measuring what it had just written, so
pass 76 ran the same check across every number added in the ten-document
reconciliation. **It reported eight failures. All eight were the checker.**

```
                        checker said   the number said
PRD                        2331             2330
SECURITY.md                  45               44
does-the-score-work.md      119              118
...and five more, every one off by exactly one
```

The figures were taken with `wc -l`, which counts newlines. The verifier used
`text.split("\n")`, which returns one more element when a file ends in a
newline — **as every one of these does**. Nine of nine re-checked with the
original method: **zero mismatches.**

> **An off-by-one that lands on every row at once is not eight errors, it is
> one — in the instrument.** The tell was that they were *all* wrong and all
> wrong by the same amount; a real drift would scatter.

**This is the same failure this section documents in `check.sh`, `why_ranges`,
the path-ambiguity rule and a test of mine — arriving from the opposite side.**
Those four could not fail. This one could not pass. **Both are instruments
reporting on themselves**, and a verifier is not exempt from the rule it
enforces: it needed its own control, and the control was to re-measure with the
method the numbers came from.

**Had it been trusted, this document would now carry eight corrections that
corrected nothing** — and §11.4's record would have been made worse by the act
of checking it.

### 11.9 Can this test suite fail? Measured, because this repo has been here before

1,577 passing tests is not evidence until something is broken on purpose.
`nextrade-verification-gate` records a `check.sh` that **could not fail for its
whole life** and was hiding three real failures, and §11.4 exists because of it.
Nobody had ever asked the same question of the suite itself.

**Nine mutations, on the constants that decide money:**

```
cess 4% -> 5%                       CAUGHT
LTCG rate 12.5% -> 15%              CAUGHT
LTCG exemption ₹1.25L -> ₹1L        CAUGHT
long-term 12 months -> 24           CAUGHT
LTCG boundary, > becomes >=         CAUGHT
prose-quote guard disabled          CAUGHT
unicode-minus handling removed      CAUGHT
RSI period 14 -> 21                 CAUGHT
education inflation 10% -> 20%      CAUGHT

9 of 9 caught · 0 survived
```

**Every money-affecting constant tried is defended by a test that fails when it
moves.** That is not proof the suite is complete — it is nine samples — but it
is the first evidence of any kind that the number 1,577 means something, and it
is the specific evidence this repo's history says to demand.

**A second batch, on the modules the first one did not touch — and two
survived.**

```
rebalance band 5pp -> 15pp             CAUGHT
healthcare inflation 13% -> 3%         CAUGHT
80C cap ₹1.5L -> ₹50k                  CAUGHT
ret3y performance weight 0.55 -> 0.75  CAUGHT
risk volatility weight 0.55 -> 0.85    CAUGHT
momentum stated window 30d -> 60d      🔴 SURVIVED
fund_evidence WINDOWS 1y 365 -> 300    🔴 SURVIVED
```

⚠️ **One earlier "survivor" was my own error and is worth recording rather than
quietly dropping.** A first attempt at the scoring weight replaced the first
literal `0.55` in the file — which sits in a **docstring** showing the formula,
twenty lines above the real weight in `PERFORMANCE_TERMS`. Mutating a comment
and concluding the tests are weak is the same shape as every confident-wrong
answer in this document: **the artefact looked mutated and was not.** Re-run
against the actual tuple, it is caught.

✅ **1. `fund_evidence.py` had no test file at all — written on pass 52, and
the gap is closed by measurement rather than by assertion.** `WINDOWS = {"1y": 365,
"3y": 1095, "5y": 1825}` defines what *1y*, *3y* and *5y* mean in every piece of
fund evidence this app produces. It is imported by `routers/research.py`,
`routers/portfolio.py`, `category_ranking.py`, `screener/serve.py` and
`fund_facts.py` — **and `tests/` contains nothing that names it.** Changing what
a year means passed 1,577 tests. That was the widest single coverage hole found
here, and it sat under §1.4's base rates.

`tests/test_fund_evidence.py` now pins the window lengths, the rule that a
window only appears when the history supports it, the None-not-empty-object
contract, and the percentage-to-fraction conversion for TER. **Re-mutated
afterwards, all three now fail the suite:**

```
1y 365 -> 300   (the one that survived)   CAUGHT
5y 1825 -> 900                            CAUGHT
TER "/ 100.0" deleted                     CAUGHT
```

⚠️ **And the first version of that TER test was itself decoration, which is the
part worth keeping.** It asserted against an *unknown* scheme code, which
returns `None` before the conversion ever runs — so it passed while the
mutation still survived. **A test written to close a hole, that does not close
it, and reports green.** It only showed up because the mutation was re-run
against the new test instead of trusted. Rewritten against `103490`
(`QUANTUM VALUE FUND`, `direct_ter 1.12`), it asserts `0.0112` and catches the
deletion.

> That is the same shape as `check.sh`, as `why_ranges`, and as the
> path-ambiguity rule — **written in good faith, green, and measuring
> nothing.** Four instances now, in one codebase, found four different ways.
> A new test is not evidence until something has been broken against it.

✅ **2. The momentum score's stated coverage was decoupled from its computation — fixed on pass 53.**

```python
_LOOKBACK_DAYS = 250     # TRADING days -- and the comment above them reads:
_SKIP_DAYS     = 21      # "changing either means the t-statistics above no
                         #  longer describe what is being computed"

def window(today=None):
    end = (today or date.today()) - timedelta(days=30)    # CALENDAR, hardcoded
    return end - timedelta(days=365), end                 # CALENDAR, hardcoded
```

`window()` produces `measured_from` and `measured_to` in
`/research/momentum`'s response — **the app's own statement of what the ranking
covers.** It is a second, independent expression of the same span, tied to the
first by nothing. **They agree today** (250 trading days ≈ a year, 21 ≈ a
month), which is why no test notices; they agree by arithmetic coincidence, and
the module's own comment says those constants are exactly the kind that get
changed deliberately.

**§14 says coverage is stated, not hidden.** A coverage claim that can drift
from the computation without anything failing is that rule with an extra step
in it.

**Done:** `window()` now reads the span off the same rows `score()` indexes when
given a price frame, and `routers/research.py` passes one that was actually
scored. The calendar form survives as a documented fallback for when there is no
frame — honest for a label, and written down rather than silent.

**And the verification produced a second finding the first fix could not
reach.** Re-mutated:

```
window() reverted to the hardcoded calendar span   CAUGHT
_SKIP_DAYS 21 -> 42                                🔴 SURVIVED
```

The new test derives the stated window **from** those constants, so moving them
moves both sides and consistency still holds. **Consistency and correctness are
different properties, and the first cannot pin the second.** The module's own
comment says why it matters — *"the lookback and skip are the validated ones;
changing either means the t-statistics above no longer describe what is being
computed"* — and `nextrade-prediction-research` records t = +3.11 over 32
survivorship-adjusted years for **this** specification, carried in the response
beside every score. A second test now pins `_LOOKBACK_DAYS == 250` and
`_SKIP_DAYS == 21` to the measurement they belong to. Both mutations caught.

⚠️ **Two corrections to what an earlier draft of this section said.**
`momentum.py` is **not** untested — it is named in `test_basket_parity.py`,
`test_stock_score.py` and `test_screener_serve.py`. What it lacked was a test
binding `window()` to `score()`, which is a narrower and more interesting gap
than "no tests". And the scan that produced the "untested modules" list was
briefly **contaminated by the test files written today**; excluding them, the
pre-existing suite named none of four modules — `grounding.py` and `groww.py`
(both written for this plan, both since covered), `fund_evidence.py` (pass 52),
and ✅ **`screener/fund_facts.py`, 170 lines — tested on pass 54.** Its own
docstring says it assembles the fund page's cost section, *"the one number this
project has measured as predictive"* — 87% against 68% for past record. Four
tests, three mutations, all caught: the ten-year saving compounds rather than
multiplies, no rupee figure appears when the direct plan is not cheaper, an
unknown fund gets `None` rather than `0.0`, and both ratios come from one
loader. **With it, every service module in this codebase is named by a test.**

🔴 **And on pass 55 that sentence turned out to be true and misleading, which
is the more useful finding.** "Named by a test" was the wrong measure — the same
mistake, one level up, as the TER test that asserted against a code returning
`None`. Measured properly, by profiling which **functions** the suite actually
calls:

```
 25.0%   1/ 4   screener/fund_facts.py      <- the module tested on pass 54
 33.3%   1/ 3   advisor/category_ranking.py
 33.3%   1/ 3   advisor/stock_analysis.py
 33.3%   1/ 3   advisor/stock_ranking.py
 33.3%   1/ 3   marketdata/promoter.py
 33.3%   3/ 9   marketdata/announcements.py
```

**Six modules exercise under a third of their functions.** Three of the six are
low for a legitimate reason — `promoter`, `announcements` and `pricing` are
network fetchers, and a unit test that calls a live API is a worse test. Setting
those aside, **four pure-logic functions are never named anywhere in the
suite:**

```
fund_facts.holdings_for          <- pass 54 tested cost_for and stopped
fund_facts.rank_at_horizons      <- same
category_ranking.rank_category
stock_analysis.build_stock_verdict
```

✅ **`build_stock_verdict` is the one that speaks, and it is tested now.** It
turns a score into the sentence a buyer reads, and
`nextrade-stock-scorer-findings` records a company with fourteen days of price
history scoring **100/100, labelled "Strong Buy"** — the model awarding its best
grade to the thing it had computed nothing about. `is_scoreable()` refuses that
input today; **nothing checked what the verdict layer says.** Six tests now pin
the sentences §14 and §5 argue for: the headline names its peer group, a thin
sector says so instead of silently claiming one, unpublished measures produce a
counted caveat rather than appearing as findings, and the 52-week position
carries *"not a view on where it goes next"*. **Three mutations, all caught.**

✅ **All four closed on pass 56, and re-profiled rather than assumed:**

```
screener/fund_facts.py::cost_for           CALLED
screener/fund_facts.py::holdings_for       CALLED
screener/fund_facts.py::rank_at_horizons   CALLED
advisor/category_ranking.py::rank_category CALLED
advisor/stock_analysis.py::build_stock_verdict  CALLED
```

**The five modules lowest now are all legitimately low**, and saying so matters
as much as the fixes: `announcements` and `promoter` are network fetchers,
`fund_holdings` parses AMC spreadsheets, `momentum`'s remaining pair reach
yfinance, and `stock_ranking`'s two uncalled functions are `_inputs_for` and the
`load` closure — **both of which I had classified "PURE LOGIC" on pass 55 and
both of which fetch live prices.** A unit test that calls a live API is a worse
test, so 33% there is the right shape, not a hole.

⚠️ **And the first test written for `rank_at_horizons` was wrong.** It supplied
one peer and asserted the horizon should still rank, blaming the code for the
`≥ 2` guard — which is correct, because "rank 1 of 1" is not information. The
test failed, which is what a test is for, and the fix was to the test.

> **Two passes in a row, the thing that was wrong was a claim I had just made
> about my own work.** Pass 54 said the sweep was complete; pass 52 said a test
> closed a hole. Both were reported green and both were measured false by the
> next check. **A coverage claim is a claim, and it needs the same treatment as
> any other number in this document.**

🔴 **And the first run left a trap worth writing down, because it cost twenty minutes
and would cost anyone else the same.** After the mutations restored, **26 tests
failed while every source file matched `HEAD`** — `git diff` clean, `CESS_RATE`
reading `0.04` in the file, and the runtime reporting `0.05`.

**Poisoned bytecode.** `shutil.copy`/`shutil.move` preserve mtime, so the
restored file carried its *original* timestamp — older than the `.pyc` compiled
from the mutant. Python's default invalidation is `(mtime, size)`, and `0.04`
and `0.05` are **the same number of bytes**. The cache looked valid and was not.

> **A source file can be correct, `git diff` can be empty, and the tests can
> still be running the mutant.** Any mutation harness here clears
> `__pycache__` between runs, and any confusing failure whose diff is clean
> should suspect the cache before the code.

### 11.10 What already verifies this app — read on pass 115, not cited before

§11 spent 513 lines on how this plan should be checked and named one of the nine
files that already check it. **2,319 lines of harness exist.** What each
establishes, from reading them:

**`validate_nav_integrity.py` — 729 lines, the largest.** Five things.
`against_the_source` refetches a sample from `mfapi` and holds the store against
it — **necessary because inserts are `ON CONFLICT DO NOTHING`, so a stored date
is never corrected and nothing else in this repo could notice a restatement**.
`invariants` is everything that must hold with the network unplugged.
`latest_run` asks whether the newest completed run agrees with itself.
`recompute` **rebuilds fund scores from the store and holds the run's own
recorded inputs to them** — an end-to-end check that the numbers on screen come
from the data claimed. `cross_view` holds research and the screener to the same
set of funds.

**`consistency.py` — 470 lines.** Cross-surface facts, each written with the bug
it exists to prevent: a holding's typed name against AMFI's (*"every figure was
right, about the wrong fund"*), a portfolio chart against the total printed above
it, one fund score across three surfaces, a rank that must not renumber under a
filter. **And the gate §6 needed and did not have:** research and the screener
rank the same funds in different orders **on purpose** — cost on one, trailing
record on the other — so only the *set* is checked, under a heading that says
nobody should ever "fix" the order.

**`isolation.py` — 216 lines.** Two real accounts, then a stranger holding a
valid session of their own is checked against the owner's objects, and the
stranger's own listings are checked for the owner's things. **It separates
"could not test this" from "this leaked"**, on the stated grounds that printing
the second for the first sends someone hunting a breach that never happened.

**`edge_cases.py` — 271 lines.** Adversarial inputs against the advisor: a one
rupee target, ₹50 crore, already-saved-more-than-the-target, a negative return —
asserting the commitment stays finite and that shortfall equals total minus
affordable.

**Four frontend harnesses** — `a11y.mjs` (204), `shots.mjs` (148), `mobile.mjs`
(112), `sweep.mjs` (46) — are accounted for in §13.11, which is the one place
this document did open the harness before being told to.

**Why this belongs in §11 rather than a footnote.** Two of this document's own
failures came from not knowing it: pass 112 read the two scorers' cost asymmetry
as an oversight when `consistency.py` documents it as deliberate, and passes
26-35 repeatedly priced shipped work as new. **A verification section that does
not name the verification is how a plan starts arguing with a repo that already
agrees with it.**

## 12. Reconciliation — every count in this document, in one place

A previous review found six different universe sizes used interchangeably. They
are all correct and they measure different things, so they are stated together
rather than left to be inferred:

**Two reconciliations, kept apart.** An earlier draft merged them into one line
and neither closed.

**A — inside the feed, and it closes exactly:**

```
  3,410   every row st_filter returns (all plan types and options)
  1,741     scheme_type == "Growth" AND available_for_investment == 1
   −55       the same fund under a second slug   ← expected, not an error
  1,686     distinct AMFI scheme codes                     ← THE UNIVERSE
```

**B — against what Manan saw, and it does not close:**

```
  1,792   what he counted on groww.in on 2026-08-25
  1,741   what st_filter returns today, and what Groww's own filter page
          reports in its payload (independently confirmed)
     13   live NFOs, from /v1/api/data/mf/v1/nfo/list
     38   still unexplained — two days apart, or a different filter state.
          NOT a defect until it is diagnosed, and it never appears in the
          product. §11.4b: this is a note to a reviewer.
```

**Coverage of the 1,686:**

```
  1,677   carry a TER                       9 do not
  1,585   have local NAV history            94.0%
  1,531   rankable   = 1,686 − 153 under a year − 2 wound up
  1,430   were scored in run 8, before any of this work
    101   need a NAV backfill  (1,686 − 1,585)
  1,658   Zerodha's independent count — 28 apart, which is the cross-check
```

⚠️ **1,430 scored and 1,531 rankable are not in tension**: 1,430 is what run 8
managed *before* the backfill, 1,531 is what is reachable *after* it. Build step
3 closes the 101, and 1,531 is its target.

**Cost:**

```
  1,233  funds with BOTH Groww and AMFI TER   →  71 disagree >0.10pp   94.2% agree
  1,158    of those, also scored              →  56 disagree >0.10pp   95.2% agree
     31  Groww direct TERs above the 2.25% statutory ceiling
     13  Groww index funds above the 1.00% index cap   (worst 8.66%)
     12  AMFI direct TERs above the ceiling
     71  scored funds not buyable on Groww    (of the 1,501 in run 8)
```

**Active vs passive:**

```
    375  funds the `index` flag calls passive        0 false positives (375/375)
     67    more the name regex adds                  0 false positives, all ETF FoFs
  86/123  share of Groww's "Large Cap" that is passive              70%
```

**Holdings, measured on the 39 cached payloads rather than assumed:**

```
   78.3  mean disclosed lines per fund   median 73   range 29–254
132,070  rows a month if all 1,686 were pulled
```

An earlier draft said "~130 lines, ≈220,000 rows" — that was PPFAS's shape (152)
taken as typical. §11.3's steady state is a dozen funds a month regardless.

**Stocks:**

```
  3,475  rows in today's NSE bhavcopy
  2,632    SERIES == 'EQ'  — the universe
    605  non-EQ rows still publishing numeric delivery, across 8 series
    751  the committed universe this replaces  (746 matched; 5 not in EQ, one a DUMMY scrip)
  1,886  NSE main-board names currently missed
```

**Store and tests:**

```
nav.db     5,187,035 rows · 4,939 schemes     ← the one figure; §1.4's
                                               "5,183,632 / 3,992" is the
                                               base-rate script's filtered
                                               subset, not the store
users        600 · goals 757 · holdings 414 · transactions 2,670 · oauth 0
           §16.1's five, re-verified against nextrade.db on pass 50. They
           were stated only in §16.1 while THIS section's title claims
           "every count in this document, in one place" -- so either they
           belong here or the title is an overclaim. They belong here.

tests      1,577 backend  ·  groww.py 23  ·  grounding.py 50
           ·  request-path memory 2  ·  declared dependencies 1
           the last two are GUARDS, not coverage: each was written after a
           defect that no existing test could have caught, and each was
           shown failing before being kept (§14, §9.2)
```

**Sampling note:** §1.5's "40/40 funds across 20 AMCs" was a live stratified
sample; `.growwcache/` holds 39 payloads because one was fetched before caching
was on. Different numbers, different things.

🔴 **And a harder fact about those 39, found 2026-08-28 by re-deriving them
rather than re-reading them: they are all equity, and §2's headline numbers have
no retained inputs at all.**

```
cached          39 payloads · Small/Flexi/Mid Cap 6 each · Large Cap 6 · ELSS 5
                Large & MidCap 5 · Multi Cap 5      DEBT FUNDS: 0

not retained    the st_filter universe pull      -> "1,686 buyable"
                the TER two-source cross-check   -> "94.2% agree, 71 disagree"
                the sub_category passive scan    -> "86 of 123 Large Cap"
                the debt holdings scan           -> "0 of 913 across 14 funds"
```

`groww_universe.json` does not exist on disk. So four of the most load-bearing
figures in this document — the ones that justify the active/passive split (§2.3),
the TER gate (§2.3) and the whole debt position (§2.4, §6) — **are assertions
with a date, not results anyone can re-derive.** Re-running the passive scan on
what *is* cached gives 3 of 6 Large Cap, which neither confirms nor contradicts
86 of 123; it is a different and far smaller sample.

**§11.4 of this document says a published record that no longer reproduces is
worse than no record.** That rule was written about the app's own scoreboard and
it applies here without modification.

**What this does and does not change.** It does not make the numbers wrong —
they were measured live and written down the same day. It makes them
*unauditable*, which for a plan whose stated purpose is surviving an outside
reviewer is close to the same problem. **So slice 2.1's acceptance criterion is
not "ingest the universe", it is "ingest the universe and re-print these four
figures"**, with any that disagree corrected here rather than quietly dropped.
Retaining the raw pull is the cheap half; the point is the comparison.

⚠️ **The same limit applies to a measurement made in §17.6.** The path-ambiguity
rejection rate (95.7% → 0.2%) was computed across these 39 payloads, so it is an
**equity-only** result. Debt payloads carry different fields, and the collision
structure could differ. Stated here rather than in a footnote because it is the
one number in §17.6 that is a sample rather than a proof.

**The product shows two counts: 1,686 listed, 1,531 ranked.** Everything else
lives here or in `Why`. Picking one number and hiding the rest is the omission
this project reports in other apps; printing all six on a screen is the
reviewer's worksheet leaking into the product.


---

### 12.1 The one reconciliation that closes from this repo, and it was missing — pass 142

§12 exists so every count sits in one place, and it reconciles the **buyable**
universe: 1,686, 1,677 with a TER, 1,585 with NAV, 1,531 rankable, *1,430 scored
in run 8*. **Every one of those is measured against `groww_universe.json`, which
does not exist** — the §12 problem this section documents about other figures
applies to its own.

**Meanwhile `screener_run` reconciles exactly, from a table in this repo, and
appears nowhere here:**

```
id  as_of        universe   scored  unscorable
 2  2026-08-20      4,957    1,466      3,491
 4  2026-08-21      4,957    1,477      3,480
 7  2026-08-25      4,957    1,480      3,477
 8  2026-08-25      4,957    1,501      3,456     1,501 + 3,456 = 4,957
```

**So the run scored 1,501, and §12 says 1,430.** The most likely reading is that
1,430 is the *intersection* of run 8 with the buyable set — 1,501 scored overall,
1,430 of them buyable — but §12 does not say so, and the difference cannot be
checked without the file §12 itself records as not retained. **Two things follow.**
The 1,430 should carry its denominator or be marked unverifiable like the other
four. And the run's own numbers — **4,957 in, 1,501 scored, 3,456 unscorable,
summing exactly** — belong in a reconciliation section, because they are the only
figures here a reviewer can reproduce today.

## 13. The visual system

Manan: *"visually dekh kar maza aana chahiye, lagna chahiye financial site"*,
*"UI/UX 0 hai"*, and then — *"lively sa hona chahiye, 3D design jaisa"*, with
*"ek dum clear navigation"* and *"dekh kar samajh aa jaye"*.

An earlier §13 was measurements plus a list of prohibitions. A product review was
blunt about it: roughly 60% "never do X", one type size specified, no grid, no
component anatomy, no states, no responsive decision, and — the real failure —
**no stated direction**. Prohibitions do not compose into a screen.

### 13.0 The direction, stated once, because it settles a hundred decisions

> **An instrument, not a dashboard.** Dense where numbers live, generous where
> decisions live, and **depth used to separate layers of meaning, never to
> decorate.**

That resolves the tension in the brief. Vercel and Linear are right that
gradients, glows and glass read as untrustworthy on money — and they are
developer tools, and importing their austerity wholesale is what makes a
consumer finance product read as cold and unfinished. The way out is that **the
liveliness comes from the information, not from the chrome**: real charts at real
size, tinted elevation rather than grey borders, type that actually contrasts,
and motion that only ever happens because the user did something.

The density call, which everything else follows from:

| surface | density | why |
|---|---|---|
| `Today`, fund and company pages | **generous** — 8pt rhythm, large type, charts at full width | these are read once and acted on; they are the "maza aana chahiye" surfaces |
| `Holdings`, `Find` | **dense** — 40px rows, tabular figures, pinned column | these are scanned, and a scan wants information per inch |
| `Ask`, `Why` | **reading width**, max 68ch | prose |

### 13.1 What is already right, and four things measured wrong

Right, and untouched: OKLCH for every colour in both themes; `--gain` / `--loss`
as dedicated tokens; one desaturated blue accent; `.num` / `.tnum` wired with
`font-feature-settings: 'tnum' 1`; Inter Tight / Geist / Geist Mono as a real
three-face split; `prefers-reduced-motion` at `index.css:206`.

| | measured | fix |
|---|---|---|
| screener unvirtualised | `Screener.tsx` **2,012 lines**, **0** matches for "virtual" | `@tanstack/react-virtual` 3.14 + `@tanstack/react-table` 9.2 |
| loss 53% hotter than gain | `--gain` chroma .128 vs `--loss` .196 | `--loss: oklch(.535 .145 27)` light, `oklch(.695 .145 25)` dark |
| hero number in mono | Geist Mono at display size | Inter Tight 2.75rem/500, `tabular-nums` on. Mono's only justification is column alignment and a hero figure has nothing to align against |
| Recharts on defaults | `CategoricalChart` is the largest chunk, **300 kB / 89 kB gzip** | hero charts only; sparklines are a hand-rolled `<svg><polyline>` |

### 13.2 Tokens

**Space** — 4pt base, 8pt rhythm.
`--space-1..12` = 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 px.
Within a group 4–8, between groups 16–24, between sections 32–48.

**Grid** — 12 columns, page max **100rem** (already set), gutter 24px, page
padding 24px desktop / 16px mobile. Reading surfaces cap at 68ch regardless.

**Radius** — `--r-sm 6px` (chips, badges) · `--r-md 10px` (panels, inputs) ·
`--r-lg 16px` (cards that lift) · full only for avatars. Three values, not seven.

**Elevation — depth by tint, not by shadow.** This is where the "3D jaisa" comes
from without a single glow:

```
--surface-0   the page ground        oklch(.991 .002 265)  light   oklch(.165 .008 265) dark
--surface-1   a panel resting on it  oklch(1    0    0  )          oklch(.205 .010 265)
--surface-2   a row lifted on hover  oklch(.985 .004 265)          oklch(.245 .012 265)
--surface-3   the thing you are      oklch(1    0    0  ) + ring   oklch(.275 .014 265) + ring
              acting on
```

Each step is a **lightness move of ~4 points and a chroma move of ~2**, so
surfaces separate by depth of colour rather than by a border. Shadows are used
**once**, on `--surface-3`: `0 1px 2px oklch(0 0 0 / .04), 0 8px 24px
oklch(0 0 0 / .06)` — large, soft, low opacity. Never on a resting card, never
on a chart, never on a badge. Hairlines stay for table rules and panel edges;
they are structure, and elevation is state.

**Multi-series colour** — the compare tray takes four funds and the palette has
one accent, which is a real hole. Four series, equal lightness, wide hue
separation, all distinguishable under deuteranopia:

```
--series-1  oklch(.55 .13 252)   blue    (the accent, so "yours" is always blue)
--series-2  oklch(.60 .12 155)   green
--series-3  oklch(.62 .13 65)    amber
--series-4  oklch(.55 .14 305)   violet
```

Sentiment (`--gain` / `--loss`) is **never** a series colour. A chart that uses
green for a fund and green for a gain has taught the reader nothing.

### 13.3 Type scale

| role | face | size / line | weight | notes |
|---|---|---|---|---|
| hero figure | Inter Tight | 44 / 1.05 | 500 | `tabular-nums`; currency mark at 0.5× |
| page title | Inter Tight | 32 / 1.1 | 600 | `tracking-[-0.02em]` |
| section header | Inter Tight | 20 / 1.25 | 600 | |
| panel title | Inter Tight | 16 / 1.3 | 600 | |
| body | Geist | 14 / 1.6 | 400 | |
| table header | Geist | 12 / 1.4 | 500 | uppercase, `+0.04em` |
| table cell, text | Geist | 13 / 1.45 | 400 | |
| **table cell, number** | **Geist Mono** | 13 / 1.45 | 400–500 | `.num` |
| badge | Geist | 12 / 1 | 500 | |
| caption / provenance | Geist | 12 / 1.5 | 400 | `--muted-foreground` |

Body-to-hero contrast is **3.1×**. The measured problem was 1.7×, and that
single ratio is most of why the old pages read as timid.

### 13.4 Component anatomy

**Badge** — the component the whole Holdings screen rests on.
Height 22px · padding 0 8px · radius `--r-sm` · 12/500 · **max 26 characters
then middle-ellipsis** · optional leading ▲/▼ glyph, never colour alone.
Four kinds, and **only the money kind is tinted**:

```
money      --loss-subtle bg, --loss text        "₹5,000/yr cheaper elsewhere"
relation   --surface-2 bg, --foreground text    "41% the same as HDFC Flexi Cap"
state      no fill, hairline ring               "Too new to rank"
withheld   no fill, dashed ring, muted          "cost unverified — one source"
```

§13.6 bans "a badge for ordinary metadata"; these are not metadata, they are the
verdict, and the ban stands for everything else.

**Panel** — `--surface-1`, hairline border, radius `--r-md`, padding 24, title
16/600, no shadow. Every component owns its own panel (§14) so an empty one
never leaves a bordered box behind.

**Table row** — 40px comfortable / 32 compact / 48 spacious, the toggle changing
`padding-block` only so numbers stay 13px at every density. Hover lifts to
`--surface-2`. Selected gets `--surface-3` plus a 2px accent left rule. Pinned
column background must match the row exactly or the pin reads as a rendering
glitch on scroll.

**Stat tile** — label 12/500 uppercase muted, figure 24/500 mono, delta as a
badge. No sparkline unless there are ≥20 real points (§13.6).

---

**And here it is, because §13.9b rated `SHOWN` at 2 out of 10.** The four
sketches below are the fix, not an illustration: each encodes a rule stated
above that prose states poorly — what is tinted against what is not, and what
changes with density against what must never change.

**The badge, all four kinds at once.** The point is that only one is tinted:

```
  ┌──────────────────────────────────┐
  │ ▼ ₹5,000/yr cheaper elsewhere    │  money    --loss-subtle bg, --loss text
  └──────────────────────────────────┘           the ONLY tinted kind

  ┌──────────────────────────────────┐
  │ 41% the same as HDFC Flexi Cap   │  relation --surface-2, --foreground
  └──────────────────────────────────┘

  ╭──────────────────────────────────╮
  │ Too new to rank                  │  state    no fill, hairline ring
  ╰──────────────────────────────────╯

  ╭ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╮
  │ cost unverified — one source     │  withheld no fill, DASHED ring, muted
  ╰ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╯
                                        22px tall · 12/500 · ▲▼ never alone
                                        34 chars then middle-ellipsis (§7.5)
```

**The row at three densities.** Only `padding-block` moves. **The figures stay
13px at every density** — that is the whole rule, and it is the one a builder
gets wrong:

```
compact 32px   │ HDFC Flexi Cap Fund      │ 1.02% │ ▼ ₹5,000/yr cheaper   │
               ├──────────────────────────┼───────┼───────────────────────┤
comfortable    │                          │       │                       │
      40px     │ HDFC Flexi Cap Fund      │ 1.02% │ ▼ ₹5,000/yr cheaper   │
               │                          │       │                       │
               ├──────────────────────────┼───────┼───────────────────────┤
spacious 48px  │                          │       │                       │
               │ HDFC Flexi Cap Fund      │ 1.02% │ ▼ ₹5,000/yr cheaper   │
               │                          │       │                       │
               └──────────────────────────┴───────┴───────────────────────┘
                ↑ PINNED. Its background must equal the row's exactly, or
                  the pin reads as a rendering glitch while scrolling.
                                            ↑ .tnum — 13px at all three
```

**The stat tile, and the rule that keeps it honest:**

```
  ┌─────────────────────┐   ┌─────────────────────┐
  │ XIRR                │   │ XIRR                │   label 12/500 upper muted
  │ +9.4%               │   │ +9.4%    ╱╲__╱      │   figure 24/500 mono
  │ ▲ +0.6pp this month │   │ ▲ +0.6pp            │   delta as a badge
  └─────────────────────┘   └─────────────────────┘
     ≥20 real points? NO         ≥20 real points? YES
     -> no sparkline             -> sparkline earns its place
```

**The bullet chart (§13.6), which replaces a whole table:**

```
  TER          ├────────▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░┤   the fund      1.02%
                        ╎              ▲               peer median  0.88%
  3y return    ├──────────▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░─┤   IQR band      shaded
                              ╎    ▲
  max drawdown ├───▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░─┤
                     ╎  ▲
                     └─ category median, a vertical rule — not a second bar
```

One row per metric, and *"how does this fund sit against its peers"* is answered
without the reader comparing numbers in their head. **This is the device §1.4's
base rates and §3.2's cost verdict both want**, and it is one of the eight that
does not exist yet (§9.1).

### 13.5 States — the half that was entirely missing

| state | treatment |
|---|---|
| **loading, first paint** | skeletons at the true final height, no spinner. The layout must not move when data lands |
| **loading, refresh** | the old value stays, dimmed to 60%, with a 2px indeterminate rule at the panel top |
| **narrating** (LLM) | three-dot pulse inside the sentence's own space, 400ms; the surrounding numbers are already there because Python computed them |
| **template fallback** (§4.1, the validation chain) | the sentence renders in `--muted-foreground` with a small `computed` chip. **The user can tell**, and that is deliberate — a fallback that looks like a generation is a lie about provenance |
| **withheld** | dashed-ring badge plus one line saying *why*, never a blank cell. A blank means "zero"; a dash means "not measured"; they are different facts |
| **stale** | value at full contrast, an `as of 31 Jul` caption beneath. Never greyed — the number is true, just old |
| **empty, no data yet** | one sentence and one action, never an illustration |
| **empty, filtered to nothing** | the filter that did it, and a one-click undo |
| **error** | what failed, what still works, and what to do. `groww.py`'s `GrowwUnavailable` renders as *"Groww is not answering. Cost is from AMFI only and marked as such."* |
| 🔴 **cold start — the backend is asleep** | **The most frequent state in this app, and it was missing from a table whose own title is "the half that was entirely missing."** `deploy/FREE-NO-CARD.md`: Render free *"sleeps after 15 minutes idle, ~1 minute to wake."* Manan opens this a few times a week, so **almost every session he starts is a cold start** — it is the modal experience, not an edge case. Treatment below. |
| **focus** | 2px accent ring, 2px offset, on every interactive element including virtualised rows |

🔴 **The eleventh state, and why it is not just an eleventh row.**

The row above `focus` is the state a user of this app meets more often than any
other, and every part of the design as written handles it wrongly:

- **`loading, first paint` says "skeletons at the true final height, no spinner".**
  That is correct for a 200ms response and it is the *worst available*
  presentation of a 60-second one: a frozen skeleton, no explanation, for a full
  minute. It reads as a broken app, every single session.
- **`src/lib/api.ts` has no timeout and no retry.** Checked 2026-08-28 — 56
  lines, an auth header interceptor and a 401 redirect. A sleeping Render
  instance does not return 401; it returns nothing until the container is up, so
  the 401 path never fires and the request simply hangs on axios' default of
  *no timeout at all*. An unbounded request is its own defect independent of this
  one.
- **§5 and §14 both say the user is told what is happening.** *"what failed,
  what still works, and what to do"*; *"the user can tell"*. A silent minute is
  the one place this design lies by omission, and it does it more often than it
  does anything else.

**Treatment, and it is cheap because the condition is detectable.** A warm free
instance answers in milliseconds, so the first request of a session taking more
than ~2s is a cold start with near-certainty:

```
0 - 2s        skeletons, no spinner            §13.5 as written, unchanged
> 2s, first   "Waking the server. This takes about a minute on the free
   request     tier -- it sleeps after 15 minutes idle." Elapsed seconds
   of a        counting up, because a number that moves is the difference
   session     between waiting and wondering. Skeletons stay beneath it.
> 90s         the `error` state, with the same sentence plus a retry
```

**The line is honest rather than apologetic**: it names the cause, gives the
real duration, and does not pretend the app is fast. That is the same standard
§4.1's `computed` chip meets — *a fallback that looks like a generation is a lie
about provenance*, and a cold start that looks like a hang is a lie about health.

**Slice 4.1 owns it, and its acceptance is falsifiable:** with the API stopped,
the app shows the waking state within 2 seconds and the error state by 90 —
tested against a stopped server, not a mocked delay, because the thing being
verified is what happens when nothing answers at all.

### 13.6 Understanding by looking — the devices, and where each is used

Manan's third ask. Each of these replaces a number the reader would otherwise
have to interpret:

- **Dot grid for a base rate.** *"20 of every 100 stretches lost money"* draws as
  100 dots, 20 filled in `--loss`. §1.4 already writes the sentence this way
  because people read counts better than percentages; the grid is the same
  decision in pixels.
- **Rebased line for any comparison**, both series indexed to 100 at the window
  start, with a **value badge at each line's right end** instead of a legend.
- **Sorted horizontal stacked bar for allocation and look-through**, never a
  pie. Weights should be comparable, not estimated from angles.
- **Bullet chart for a fund against its peer group** — the fund's value as a
  bar, the category median as a vertical rule, the interquartile range as a band
  behind it. One row per metric, and the whole "how does this fund sit" question
  is answered without a table.
- **Underwater plot for drawdown**, filled to zero, always `--loss`, inverted so
  the deepest point is lowest.
- **Slope chart for before/after** — what a switch costs and returns.
- **Fan band for anything forward-looking**, 2–3 translucent bands, never a
  single line implying certainty.
- **Sparkline in a table cell**: 56×20, 1.6px, no axis, coloured by the sign of
  the period, endpoint dot. Hand-rolled SVG.

🔴 **Pass 30 counted these against the frontend. Zero of the eight exist, and
slice 4.4 prices five.** Grep hits for "bullet", "stacked" and "underwater" are
all prose in comments — *"a fund only earns a bullet point"*, *"stacked they read
as two topics"*. `lib/chart.ts` is real and reusable (UTC date handling, axis
ticks, padded domains, tooltip style, series merge) and its header even mentions
*"a rebased line"* as motivation — **but exports no rebasing function.**

```
dot grid   rebased line   stacked bar   bullet chart          <- 0 built
underwater   slope   fan band   sparkline                     <- 0 built

slice 4.4 lists: dot grid, bullet, underwater, slope, fan     <- 5 of 8
unpriced entirely: rebased line, sorted stacked bar, SPARKLINE
```

The word *"remaining"* in slice 4.4 implies three are done. None is. **Sparkline
appears in no slice at all**, and §3.2 puts one in every `Find` row.

🔴 **And one device already ships in the form this section forbids.**
`components/AllocationPie.tsx` is a recharts `PieChart` with `innerRadius={52}`
— a donut — rendered on `GoalDetail.tsx`. The rule three bullets above is
*"never a pie… weights should be comparable, not estimated from angles."*

**Nothing in this plan says to remove it.** A builder implements the stacked bar,
adds it, and the app then shows allocation **both ways on different screens** —
which is the §14 consistency failure this repo has committed most often, arriving
through the door marked "new component". **Slice 4.4 acceptance gains one line:
`AllocationPie` is deleted, not deprecated, and `GoalDetail` uses the bar.**

Gridlines horizontal only at 8–10% ink. Tooltip is a crosshair plus a card, not
hover-per-point. Every rupee figure through
`Intl.NumberFormat('en-IN')` — 2-2-3 grouping is native to the locale.

### 13.7 Motion

Linear's phrase is the rule: *"structure should be felt, not seen."*

**Never:** a number counting up (it asserts a rate of change that did not happen
and shows false intermediate values); any animation on virtualised scroll (rows
must appear in the scroll event's own frame); spring or bounce anywhere near a
figure; anything at all without a user action behind it.

**Allowed:** row expand 180ms ease-out · tab cross-fade 150ms · elevation change
on hover 100ms · a sparkline's first draw 350ms, once, on mount only · panel
enter 200ms fade+2px rise, first paint only. `prefers-reduced-motion` removes
all of it and nothing breaks.

### 13.8 Responsive

**Desktop-first, phone-complete.** Breakpoints 640 / 1024 / 1440.

- **`Holdings` below 1024 stops being a table.** Each holding becomes a card:
  name and badge on line one, value and XIRR on line two, the reason on line
  three. A pinned-column virtualised table on a 390px screen is a worse table,
  not a smaller one — and Groww is a phone.
- **`Find` stays a table on mobile** but drops to three columns (name, cost,
  badge) with horizontal scroll for the rest, because it is a comparison surface
  and cards destroy comparison.
- **Look-through's stacked bar** stays full width; the company table becomes
  cards.
- **Charts** keep their aspect ratio and lose tick density, never height.
- The sidebar (§15) collapses to icons at 1024 and to a bottom bar at 640.
  **Never a hamburger** — five destinations hidden behind a click is the
  opposite of the ask.

### 13.9 Defaults that would otherwise be invented

Dark is the default and follows the system; the toggle is three-state
(light / system / dark) and persists. `Holdings` sorts by the badge's rupee value
descending — the row worth acting on is first. `Find` sorts by cost ascending
within the chosen category. Grouping off by default. Every table is fully
keyboard-navigable including the virtualised body, and `⌘K` is global.

### 13.9b The rating, because a spec that cannot be scored cannot be argued with

`plan-design-review` asks for each dimension rated 0-10 with what a 10 looks
like. Applied to this section on pass 44 — the last unused review lens in this
project's own arsenal:

```
dimension          score  what a 10 looks like, and where this sits
-----------------  -----  ----------------------------------------------
direction            9    one line that settles arguments without being
                          consulted. "An instrument, not a dashboard" plus
                          the density table does that.
tokens               8    every value derivable, none invented at use
                          time. OKLCH throughout, --gain/--loss as their
                          own tokens, elevation by tint. 16 values given.
type scale           8    every role named so nobody picks a size. 11 are.
states               9    the states nobody writes are written: template
                          fallback, withheld, stale, and the cold start.
                          A 10 also covers offline; this does not.
anti-slop            9    specific, not generic -- and §13.10 marks its own
                          unsourced claim as unsourced, which is rarer than
                          the list itself.
devices: SPEC        8    eight named, each replacing a number a reader
                          would otherwise have to interpret.
devices: BUILT       0    zero of eight exist (§9.1).
SHOWN                2 -> 5   raised on pass 45 by acting on this row
                          rather than filing it: §13.4 now carries four
                          sketches. Not a 10 -- a 10 is a screenshot of the
                          built thing, which slice 4.1 owes this document.
```

🔴 **`SHOWN` is 2, and it is the one worth acting on.** Counted across the whole
document: **three box-drawn layout sketches, all of them in §3**, for seven
surfaces. **§13 — 322 lines, eleven sub-sections, the section that owns the
visual system — contains none.** Its §13.6 is titled *"Understanding by
looking"* and there is nothing in it to look at.

That is a direct miss against the brief. Manan asked for *"dekar smjh aajye"* —
understanding that arrives by looking — and the section answering that ask can
only be read. A builder reconstructs every layout from sentences; Manan cannot
tell whether this is what he asked for until slice 4 renders it.

*(An earlier draft of this bullet said "zero images in the plan". That was
wrong — it measured §13 and generalised to the document. §3 has three sketches.
The corrected claim is narrower and still holds.)*

✅ **Done on pass 45 rather than filed.** §13.4 now carries four sketches, and
each was chosen because it encodes a rule prose states badly:

- **the four badge kinds together** — the point is that *only one is tinted*,
  which four separate prose lines cannot show and one picture does;
- **the row at all three densities** — showing that only `padding-block` moves
  and **the figures stay 13px**, which is the rule a builder gets wrong;
- **the stat tile with and without its sparkline** — the ≥20-points rule made
  visible as a comparison rather than a condition;
- **the bullet chart**, the device §1.4 and §3.2 both want and neither has.

**`SHOWN` moves 2 → 5.** Not higher, because **a 10 is a screenshot of the
built thing**. Slice 4.1 still owes this document that, and until it lands
nobody can compare pixels to intent — only prose to intent.

### 13.10 Anti-slop

Vercel's Geist docs reject, verbatim: *"Decorative gradients, glows, blobs,
stripes, textures, glass, or ornamental shadows... A badge, pill, or rounded
capsule for ordinary metadata... A dark rounded rectangle around every chart."*

Finance-specific, and each is a real product this way:

- **A sparkline on every stat card** whether the trend is real or not.
- **Badge overload** — "Strong Buy" + "5★" + "Low Risk" stacked. The scoring
  engine refuses to reduce a fund to one adjective; the UI must not paste five
  back on. §3.2's precedence rule exists for this.
- **A progress bar with no denominator.** "Portfolio Health: 78%" with no stated
  scale is the fastest way to look generated rather than reasoned.
- **Glassmorphism over a gradient** — reads as a crypto wallet, which is the
  precise opposite of the brief.
- **`groww_rating` rendered as a rating** — §2.3, Groww's own metadata cannot
  agree whether it is out of 5 or out of 10.

⚠️ The claim that **large red surfaces distort investor judgement could not be
sourced**, and one 2018 study on the Balloon Analogue Risk Task failed to
reproduce a red effect. Sentiment lives in small badges on **CVD and WCAG 1.4.1
grounds** — ~8% of men have red-green deficiency and colour may never be the only
channel, which is why every gain/loss badge also carries ▲/▼. Do not cite the
red-judgement claim as settled.

### 13.11 What verifies the frontend, and what does not — pass 57

Fifty-six passes went into the backend's 1,603 tests and never asked what
stands behind the 49 `.tsx` files. Asked now, the answer is two-sided and both
sides change §7.

🔴 **There is no unit-test layer at all.** No `vitest`, no `jest`, no
`.test.tsx` anywhere, and `package.json`'s scripts are `dev`, `build`, `lint`,
`preview` — nothing runs a component in isolation. **Every per-component
acceptance criterion this document wrote for slice 4 has no runner**: *"each
device renders its empty and loading states"*, *"overlap shows n/a when
unmeasured, never 0%"*, *"the badge fits 34 characters"*. They are checkable
statements with nothing to check them.

🟢 **But four Playwright harnesses already exist, and they cover what unit
tests would not:**

```
sweep.mjs    every page, both themes -- fails on uncaught errors, console
             errors, or any API response of 400 or worse. Also `--empty`,
             as a brand-new user with no data.
a11y.mjs     every page against the mechanical accessibility failures
mobile.mjs   every page on a small iPhone and a Pixel -- its own header
             records two failures "both invisible at 1440 and both found
             here the first time"
shots.mjs    every page, both themes, seeded account
```

`sweep.mjs --empty` is the strongest of the four for this plan: §13.5's
*"empty, no data yet"* state and §3.0's whole on-ramp are exactly what a
brand-new user meets, and something already loads every page in that condition
and fails on a console error.

⚠️ **And `shots.mjs` corrects §13.9b, which I wrote three passes ago.** That
section says `SHOWN` cannot reach 10 until *"a screenshot of the built thing"*
lands, and gives slice 4.1 that job as new work. **The harness that screenshots
every page in both themes already exists.** What slice 4.1 owes is not building
it — it is *running* it and putting the output where a reader can see it.

**So slice 4's shape changes.** It does not need a test stack invented; it needs
**a component-level runner added to a project that already has page-level
verification** — a smaller and better-understood job than the criteria implied,
and one the four existing harnesses give a template for.

### 13.12 🔴 `check.sh` already exists and runs eleven checks — pass 58, recounted on pass 75

The previous section is right that there is no component runner, and it is
written as though that were most of the story. It is not. **A verification gate
exists at the repo root and this document mentions it once, as something slice 0
should build.**

```
./check.sh
  unit tests            pytest, 1,603
  nav store integrity   validate_nav_integrity.py -- "the stored NAVs are still true"
  frontend build        npm run build -- typecheck and build
  edge cases            edge_cases.py -- "no 500s, no NaN"
  cross-view consistency consistency.py -- "the same fact agrees with itself"
  account isolation     isolation.py -- "nothing crosses between accounts"
  page sweep            sweep.mjs, seeded AND --empty
  mobile                mobile.mjs -- "fits, and every control is thumb-sized"
  accessibility         a11y.mjs -- "labels, headings, contrast, tab order"

  and one this list omitted until pass 75:
  scoring parity        verify_scoring_parity.py -- "our numbers still equal
                        the reference", across library versions
```

⚠️ **"Nine" was taken from the file's own comment, not counted from the file.**
It has **10 `step` groups and 11 `run` checks**. The comment says nine because
it was written when there were nine. **Quoting a document's self-description
instead of measuring it is the mistake this section is about**, committed
inside the section that is about it.

**Three of these correct findings this document made about itself:**

🔴 **§8.2 said the safety case rests on a login screen it never names.** True —
and `isolation.py` has been gating exactly that all along: *"can one account
reach another account's data, or reach anything unauthenticated… walks every
route that takes an id or reads a session and tries it as a stranger and as
nobody."* The mechanism §8 forgot to mention is the mechanism something already
tests on every run.

🔴 **§11.4's whole concern is a record that stops matching its source.**
`consistency.py` exists for the same reason, in the same voice: *"A wrong number
is a bug you can find. Two different right-looking numbers for the same thing is
worse: nothing errors, nothing logs, and the reader quietly stops believing any
of it."* It checks the seams where one fact is computed by more than one path.

🔴 **§7 slice 0 proposes a "marker gate" as new work.** What is new is the
marker JSON idea; the gate it hangs from is 123 lines old.

**And the file carries its own account of the failure this project keeps
citing.** `nextrade-verification-gate` records that `check.sh` could not fail;
the fix is in the source with the reason:

> *"`set -o pipefail` at the top of this file does NOT reach a child `bash -c`.
> Without the flag here, **seven of the nine checks could not fail**: this
> script printed "All clear" on a run where mobile.mjs had exited 1 and had said
> so on the line above the green tick."*

**So slice 0's real first task is smaller and different**: add the marker step to
a gate that already runs nine, and make §12's counts one of the things
`consistency.py` refuses to let drift.

## 14. What the rebuild must not lose

A redesign is the most reliable way to throw away things that were learned
expensively. Each of these is a decision already taken in this repo, with a
reason, and several were bugs before they were rules. **They survive the
rebuild.** Consistency-checked against `traa-decisions`, `traa-gotchas` and
`traa-base-rates` on 2026-08-27 — two of them were missing from an earlier draft
of this plan and are here because of that check.

🟢 **Pass 143 checked the citations, not the prose — all six resolve exactly.**
§14's claim rests on line references into `backend/app/schemas/`, and a line
number is the first thing to go stale in a file that changes. Re-read today:

```
app/schemas/portfolio.py:262   # and the UI must not render it as zero.
app/schemas/portfolio.py:287   # Funds left out, by name, with the reason. Never dropped silently.
schemas/research.py :226   # them. A screen that hides its own coverage is lying by omission.
app/schemas/portfolio.py:102   unpriced_invested: float
app/schemas/portfolio.py: 64   price_as_of: date | None = None
app/schemas/portfolio.py: 89   stale: dict[str, str] = {}
```

**Six of six, word for word.** That the line numbers still land is itself
evidence — those schemas have not churned since pass 34 wrote them down.

⚠️ **The near-miss is worth keeping.** A first attempt resolved `portfolio.py`
by searching `app/` and matched **`routers/portfolio.py`**, where those lines say
something else entirely — six citations would have been reported stale on the
strength of reading the wrong file. §14 says *schemas*, and reading the sentence
before the number is what saved it.

🔴 **That check was run against the wrong artefact, and pass 34 found out by
running it against the right one.** Those three are **vault notes**. This
section describes decisions **implemented in code**, and it was verified by
comparing prose to other prose — the exact error pass 20 named: *stopping at the
artefact instead of going to what produces it.*

Against `backend/app/schemas/`, which this document had never opened, **§14's
rules appear 24 times as enforced response contracts:**

```
"the UI must not render it as zero"        app/schemas/portfolio.py:262   <- n/a, never 0%
"Never dropped silently"                   app/schemas/portfolio.py:287   <- excluded, by reason
"A screen that hides its own coverage      app/schemas/research.py:226    <- and in this
 is lying by omission"                                           section's own voice
unpriced_invested / unpriced: list[str]    app/schemas/portfolio.py:102   <- missing cost is neutral
price_as_of / stale: dict[str, str]        app/schemas/portfolio.py:64,89 <- staleness
```

And coverage is not a convention but a **type**:

```python
class ScreenerCoverageOut(BaseModel):
    """as_of and stale_days are not optional. A nightly precompute that quietly
       goes stale returns 200 with old numbers and nothing catches it."""
    universe / scored / shown / new_funds / categories_total /
    categories_ranked / thin_categories / unscorable / missing_columns /
    as_of / stale_days
```

> **This makes §14 stronger than it claims, and the correction matters more than
> the reassurance.** As written, this section is a list of decisions a rebuild
> must *remember*. Measured, they are **fields a rebuild would have to actively
> delete** — a screen that drops coverage does not forget a principle, it breaks
> a response model. Provided slice 4 consumes the existing endpoints, it
> inherits them; and §9 records that this plan names **none of the 49**.

### Money

- **Every recommendation is a direct plan.** A regular plan is the same
  portfolio with a distributor's commission inside the NAV. Non-negotiable, and
  it was missing from this document until the consistency pass.
- **The tax lever is priced from where the user already is**, not between the
  two options. The new regime has been the statutory default since FY 2023-24,
  so anyone who never filed a declaration is already in it — showing them the
  full ₹2.45L gap bills them again for a saving they took years ago. Already on
  the cheaper regime → **₹0 and "Already done"**. Equal → **no lever at all**,
  because there is no decision.
- **Missing cost is neutral, never dropped.** Dropping unpriced funds once put
  three of them into a Large Cap top five.
- **A trade is never sorted among the levers, and a gate is not a lever.** Equity
  share would top the list at ₹34.8L; it is the price of holding through a fall,
  not free money. Debt at 42% priced over fifteen years reads ₹1.87 crore, which
  is true and dishonest.
- **A value that moves with an assumption is a range. A contested magnitude gets
  no number at all.**

### Evidence

- **Thin records are shrunk toward neutral.** A fund with 3.4 years has all its
  windows inside one market, and that market was good.
- **Stocks are scored sector-relative**, never absolute — our own medians run
  from Energy at P/E 10.9 to Consumer Defensive at 49.3, so an absolute screen
  is a sector bet wearing a valuation label.
- **A base-rate class never widens.** "Equity funds lost money in 18% of years"
  and "Small Cap funds did" are different claims, and substituting one for the
  other is the silent widening this project reports in other apps.
- **Unmeasured is "n/a", never 0%.** 0% overlap means perfectly diversified,
  which is the opposite of "we could not tell".
- **Coverage is stated, not hidden.** A screen that ranks 50 of 751 and calls
  them "best" is lying by omission.

### The deployment, which §16.5 shows this plan had not accounted for

- 🔴 **`pandas` is imported inside a function, and that is load-bearing.**
  `marketdata/fund_holdings.py` line 305 imports it *inside* `_open_workbook`,
  not at module top. Nothing says why, and the docstring above it explains only
  the Excel-engine choice. **Measured 2026-08-28:**

  ```
  baseline python                13 MB
  + fund_overlap (numpy)         49 MB   ← the request path today
  + pandas                       80 MB   (+30)
  ```

  `deploy/FREE-NO-CARD.md` measures the serving API at **46 MB RSS** against
  Render free, and commit `8a5e4d2` states that moving the pandas work off the
  host is *what removed the need for a paid tier*. A top-level import — the
  tidier, more obvious form, which any linter or reviewer would suggest — puts
  **~30 MB back on every request process, a 66% increase**, and `fund_overlap`
  imports `fund_holdings` so it would arrive on the look-through path
  specifically. **No test would fail.** The rebuild keeps the deferred import,
  and slice 2.3 asserts `'pandas' not in sys.modules` after importing the
  overlap path — the only form of this rule that can fail.

- **The memory-heavy work stays on the runner, not the host.** Ingestion,
  scoring and the holdings pull run in GitHub Actions on 16 GB. The host serves.
  Any Phase 1 feature that would compute at request time what could be computed
  nightly is a change to the deployment, not just to a screen.

### Language and surface

- **Plain sentence first, arithmetic one click behind.** Manan's own words when
  a screen opened with `t = +3.11`: *"kuch samajh nahi aa raha"*. The numbers
  were not removed — a claim that cannot be checked is what every other app
  ships.
- **Risk is shown with the ranking, not in a footnote.** Momentum's crash record
  sits *above* the table it qualifies. A list of green percentages with the
  caveat on another page will be read wrong.
- **Every component owns its own surface.** Wrapping empty components in a page
  gave three empty bordered boxes and no explanation.
- **A peer group is labelled with the group it actually came from** — a panel
  once said "Banks - Regional" over six companies including two insurers.
- **`formatPercent()` is never bypassed.** Its whole job is the ×100, and
  bypassing it once printed 0.01% for a fund charging 0.67%.

### Failure modes

- **Freshness is calibrated from the portfolio, not the calendar.** One fund
  publishing yesterday while another has not for three weeks means the market
  was open — which is what ended the false Diwali warnings.
- **Production refuses to start on a bad config.** Relative SQLite, wildcard
  CORS and a weak JWT are three failures that produce no runtime error; startup
  is the only place they can be seen.
- **Rate limiting counts failures only on the auth tier.** Brute force *is*
  failed attempts; charging successes protects nothing and punishes the local
  harnesses, which all share one IP.
- **A verification tool must be able to say no.** `check.sh` runs
  `false | tail -1` against itself and exits 2 if that passes, because this repo
  has caught its own tooling measuring nothing **four separate times**.


---

## 15. Navigation

Manan, 2026-08-27: *"ek dum clear navigation, kei har cheez pata lage — stocks
ka, funds ka, research, kuch bhi"*. The plan had screens and no navigation model
at all, which is a real omission: §3 lists six surfaces and never says how a
person moves between them.

### 15.1 The structural problem: this app is a graph, not a tree

Most apps are a tree — sections containing pages. This one is not, and the
reason is the feature that makes it worth building:

```
     Holdings ──► a fund you own ──► its holdings ──► a company
        ▲                                                │
        │                                                ▼
        └──────── funds you own that hold it ◄──── every fund holding it
```

A user lands on HDFC Bank because it is 5.2% of their equity across four funds
(§1.5), clicks through to one of those funds, sees its other holdings, clicks
another company — and is now three hops from where they started with no
section-based idea of "where" they are. Groww does not have this problem because
Groww has no look-through. **We do, and a tree-shaped nav will strand people.**

### 15.2 Three layers, each doing one job

**1. A persistent sidebar — "which part of the app am I in".**
Five destinations, never more: `Today` · `Holdings` · `Find` · `Ask` · `You`,
with `Why` (the scoreboard, §3.6) pinned at the bottom because it is a
statement, not a task. Collapses to icons on narrow screens, never to a hamburger
— a hidden nav is the opposite of the ask. The current section stays lit
regardless of how deep the page is.

**2. A trail — "how did I get to this page".**
Not breadcrumbs, which describe a hierarchy this app does not have. A **path of
where you actually walked**, at most four hops, each clickable:

```
Holdings ›  PPFAS Flexi Cap ›  HDFC Bank ›  ICICI Prudential Bluechip
```

Clicking any step returns to it with its state intact. This is what makes the
graph traversable instead of a maze, and it is the single most important
navigation element in the product.

**3. A command palette — "take me to a thing by name".**
`⌘K` over every fund (1,686), every stock (2,632), every screen and every
methodology note. This is the thing that makes 4,300 entities navigable without
a menu tree, and Koyfin's search-first bar is the reference — the strongest
"serious instrument" signal in that whole product is that search comes before
menus.

### 15.3 Rules that follow

- **Every entity page is a real URL and survives a reload.** `/fund/122639`,
  `/stock/RELIANCE`. A user who wants to send himself a link, or come back
  tomorrow, must be able to.
- **Cross-links state their relationship, never just the name.** Not
  "HDFC Bank" but **"HDFC Bank — 7.55% of this fund"**, and on the way back
  **"held by 4 of your funds"**. The number is the reason to click; a bare link
  makes the user guess what they will get.
- **A holding is one click from anywhere it is mentioned.** Named in a lever, a
  badge, a chat answer, or an overlap row — it links.
- **Find is one surface, not two.** Funds and stocks share it, with a segmented
  control, because a person looking for "where should this money go" does not
  start by choosing an asset class. It remembers which side you were on.
- **The chat is a destination, not a floating bubble.** A bubble over a data
  screen implies support; this is an instrument you use deliberately. And it
  links out — an answer naming a fund carries that fund's link.

### 15.4 What this rules out

- **No hamburger on desktop.** Hiding five items behind a click, on a screen
  that is 100rem wide, to save space that is not scarce.
- **No tabs inside tabs.** The fund page already has sections; a second tab
  layer inside a tabbed shell is where people lose their place.
- **No modal for anything with its own content.** A fund opened in a modal has
  no URL, cannot be linked, and traps the back button.
- **No infinite scroll on Find.** A user who scrolls 400 funds and reloads must
  land where they were, which infinite scroll cannot promise.


---

## 16. Data model — what exists, and the seven things this plan adds

The plan described screens and sources and never said where anything is stored.
Every table below was read off the live databases rather than recalled.

### 16.1 What is already there

```
nextrade.db            (app data, SQLAlchemy + Alembic)
  users            600   risk_score · risk_profile · annual_income · monthly_expenses
  goals            757   goal_type · target_amount · current_savings · target_date
  holdings         414   user_id · name · asset_type · identifier · category
  transactions   2,670   holding_id · txn_date · txn_type · units · price · amount
  oauth_account      0

.navstore/nav.db       (a separate file on purpose — 189 MB, WITHOUT ROWID)
  nav_history  5,187,035   scheme_code · nav_date · nav
  nav_source       5,190   first/last_nav_date · row_count · zero_rows · last_error
  screener_run         7   as_of · universe_size · scored · unscorable
  screener_score  10,346   run_id · code · category · sub_category · score · grade · risk_tier
  screener_input  12,244   run_id · code · roll1y..roll3y · vol · sortino · max_dd · nav_fresh
  screener_unscorable 24,353  run_id · code · reason
```

`transactions` already carries FIFO lots, which is what §3.2's switch-cost
arithmetic needs and why that arithmetic is possible at all.

### 16.2 What this plan adds

🔴 **An earlier draft put all of this in `nav.db`, and that was wrong for one of
them.** `.gitignore` line 33 says of `.navstore/`: *"The NAV spine: ~184 MB of
public, rederivable data. Never committed."* That is the correct description of
NAV history and of stock bhavcopy — both re-downloadable in minutes.

**Fund holdings are not.** Groww serves only the current month, so a July 2026
disclosure that is deleted is gone permanently, and §11.3's whole rationale for
append-only is that last month's holdings are the only evidence of drift.
Putting an irrecoverable record inside the store the repo treats as a disposable
cache — and which `trim_nav_store.py` rebuilds — is how it gets destroyed.

```
.navstore/nav.db      NAV history · stock_daily · corporate_actions · screener_*
                      large, market-wide, re-downloadable, gitignored

.holdings/hold.db     fund_holdings · fund_managers · groww_universe snapshots
                      APPEND-ONLY and IRRECOVERABLE. Separate file, separate
                      backup, and trim_nav_store.py cannot reach it.

nextrade.db           everything user-scoped
```

**In `.navstore/nav.db`** — large, market-wide, regenerable:

```
stock_daily         symbol · trade_date · OHLC · volume · turnover · trades
                    deliv_qty · deliv_pct · series · isin
                    PK (symbol, trade_date) · ~9.3M rows, mirrors nav_history

corporate_actions   symbol · ex_date · kind · ratio_from · ratio_to
                    face_value · subject · adjustable
                    → `adjustable` is a stored column, not an inference: a
                      demerger has no ratio, and §2.2 marks the window
                      unadjustable rather than guessing

**In `.holdings/hold.db`** — append-only, irrecoverable, backed up:

groww_universe      one row per buyable scheme, per pull date
    as_of · scheme_code · search_id · name · amc · sub_category · is_passive
    ter · aum_crore · fund_manager · min_sip · min_lumpsum · exit_load
    PK (as_of, scheme_code)
    → as_of is in the key for §11.3's "when did this fund leave the buyable
      set", which a single overwritten snapshot destroys.
      🟢 NOT for TER history any more -- see §16.6

fund_holdings       one row per disclosed line, per disclosure month
    scheme_code · portfolio_date · name · stock_search_id · sector
    instrument_type · weight_pct · market_value
    PK (scheme_code, portfolio_date, name)
    ~132,000 rows a month at full coverage; a dozen funds in steady state
    ⚠️ BOTH FIGURES ARE EQUITY-ONLY -- see the note below
    APPEND-ONLY — last month's disclosure is the only way to detect drift

fund_managers       scheme_code · person_name · since   (tenure, for §3.4)

ter_agreement       scheme_code · as_of · groww_ter · amfi_ter · agrees
                    → §2.3's two-source gate has to be inspectable, not
                      recomputed silently at read time
```

**In `nextrade.db`** — user-scoped, small, and backed up with the account:

```
holdings   + plan_type ('direct' | 'regular')  resolved from the scheme code
                                               and CONFIRMED by the user (§3.0)
           + last_reconciled_at                per holding, not global (§3.0)

lever_actions   user_id · lever_key · shown_at · acted (bool) · asked_at
                → §3.6's missing record. Without it the app can never measure
                  whether its own advice helped, and the levers list keeps
                  recommending something done three months ago.

narration_cache user_id? · tool_json_hash · text · claims_json · model · created_at
                → §4.4: keyed on the hash of the tool JSON, never on the
                  question. If the score has not moved the sentence is not
                  regenerated.
```

### 16.3 Three decisions this makes explicit

**Why two market files and not one.** `trim_nav_store.py` exists and rebuilds
`.navstore/`. Anything inside it is something that script may legitimately
delete. So the split is not tidiness — it is the difference between data the
repo can throw away and data it cannot.

🔴 **This paragraph used to end with a slice-2.4 acceptance criterion that was
backwards, and pass 21 caught it by RUNNING the script instead of reasoning
about it.** It said: *"`trim_nav_store.py` must also learn about `stock_daily`
and `corporate_actions`, or it silently drops 26 years of stock history."*

It does not drop them. It **copies them, in full.** The script does not
re-declare a schema and select tables — it calls `con.backup(dst)`, a whole-file
snapshot, and then issues exactly one `DELETE FROM nav_history`. Its own comment
says so: *"copying rather than re-declaring the schema also means indexes, types
and any column added later arrive on their own instead of being dropped here."*
Reproduced on a synthetic store:

```
before trim                     after trim (the PUBLISHED store)
  nav_history       2 rows        nav_history          1 row
  stock_daily   9,300 rows        stock_daily      9,300 rows   <- survives, whole
  corporate_actions 1 row         corporate_actions    1 row
```

**And the real risk is the one §16.5 already names**, which makes this a
contradiction inside this document rather than only an error: the published
store is trimmed to **23.9 MB gzipped** and **downloaded by the app at every
cold start**. `stock_daily` is ~9.3M rows of OHLCV plus delivery across ten
columns — against `nav_history`'s 5.19M rows of three — so putting it in
`.navstore/nav.db` does not lose it, it **ships it to the phone, every wake.**

**Corrected acceptance for slice 2.4:** `trim_nav_store.py` must learn to
**exclude** `stock_daily` and `corporate_actions` from the published copy, not
to preserve them — and the test is that the gzipped output stays within sight of
23.9 MB after the stock archive lands. What Phase 1 needs from 26 years of stock
history is a base rate: a computed table of a few thousand rows, which is what
gets published.

> The old criterion would have had someone build a guard against a failure that
> cannot occur, while the failure that does occur shipped. **That is worse than
> no criterion**, and it survived twenty passes because every one of them read
> the sentence instead of running the script.

**Why holdings are append-only.** Overwriting a disclosure destroys the only
evidence of drift, which is one of §3.2's badges. The cost is ~132k rows a
month at full coverage and far less in practice.

⚠️ **Both storage figures are arithmetically exact and drawn from an
unrepresentative sample — checked on pass 18.** The 39 cached payloads give a
mean of **78.3 holdings per fund**, and 78.3 × 1,686 = **132,070**, reproducing
the number in §16.2 to the row. §16.4's *"a dozen funds in steady state"* is
12 × 78 = **940**, which is the "~1,000 rows/month" that justified committing a
gzipped dump. **The arithmetic is right. The sample is all equity** — §12 already
established the cache holds **zero debt funds** — and the spread inside even that
sample is wide:

```
Large & MidCap  mean 107   Flexi Cap  mean  74      overall mean  78.3
Small Cap       mean 101   Large Cap  mean  62      range x1,686:
Mid Cap         mean  79   ELSS       mean  51      48,894 - 428,244
Multi Cap       mean  74
```

A liquid or short-duration debt fund routinely holds several hundred
instruments, so the universe mean is **structurally likely to sit above 78.3**
and the true monthly figure above 132,070. That is unmeasured, not estimated —
there is no debt payload to measure.

**It matters twice, and the second time is new.** It sizes the append-only store
(§16.4), and since §16.5 it also sizes a **release asset the app downloads at
every cold start**. A number that could be 2-3× larger than written is a number
that decides whether the boot download stays near the 23.9 MB the free tier is
built around. **Slice 2.1's acceptance already re-prints §2's four figures; this
is the fifth** — pull a stratified sample that includes debt before sizing
anything on 78.3.

**What is deliberately NOT stored.** Anything derivable — look-through weights,
overlap percentages, badge states, narration for a fund nobody opened. They are
computed from the tables above, because a stored derivative is a thing that can
disagree with its source, and §14's consistency rule is the one this repo has
broken most often.

### 16.4 "Backed up" was a word, not a mechanism — three findings, 2026-08-28

A fifth review pass, this one checking §16 against the filesystem rather than
reading it, found that the section's central safety argument was not carried
through anywhere.

🔴 **1. `.holdings/` was not in `.gitignore`.** The previous revision moved the
look-through store out of `.navstore/` for a good reason and never told git
about the new path. `.gitignore` line 45 ignores `.holdingscache/` — a cache dir
next to `.stockcache/` and `.newscache/`, referenced by nothing in the
codebase — and nothing at all ignored `.holdings/`. The first `git add -A` after
slice 2 would have committed a growing binary SQLite file. **This is the same
class of live risk as the `.growwcache/` gap, introduced by the very revision
that fixed that one, and it is the second time in this plan that moving a file
to protect it has been the thing that exposed it. Fixed now**, with the reason
written next to the rule.

🔴 **2. There is no backup, and the section asserted one three times.**
*"separate backup"*, *"append-only, irrecoverable, backed up"*, *"backed up with
the account"* — nothing performs any of these. There is no backup script, no
cloud account (§0 is a free, no-card deployment), and the store is now
gitignored, so **git is explicitly not backing it up either**. The split from
`.navstore/` protects the data from `trim_nav_store.py` and from nothing else,
while the section's own argument is that losing it is permanent.

**The fix, sized to the data rather than to the fear.** §16.2 says ~132,000 rows
a month *at full coverage* but *"a dozen funds in steady state"* — so the real
monthly volume is on the order of a thousand rows. A `sqlite3 .dump | gzip` of
that is well under a megabyte, which means **the backup can simply be committed**:

```
.holdings/hold.db              live store, gitignored, append-only
data/holdings-dumps/YYYY-MM.sql.gz   committed monthly, text, diffable
```

Git is the only durable store this deployment has, so the backup has to be
something git can hold — which a compressed SQL dump is and a binary DB is not.
Slice 2 owns writing the dump step; **the acceptance criterion is that deleting
`.holdings/` and restoring from the newest dump reproduces the store**, tested
once, because a backup nobody has restored from is not a backup. This is the
same standard §11.4 applies to the published record and the same one this repo
has caught its own tooling failing four times.

🟡 **3. The database has 600 users, and this app is single-user by design.**
Measured: `nextrade.db` holds **600 users and 414 holdings spread across 396
distinct `user_id`s** — seeded fixture data. §8's entire safety argument is that
*no other person receives advice*, and slice 1 puts Manan's real portfolio into
this file alongside 600 fictional ones.

That is not a legal problem — the rows are invented — but it is two build
problems the plan had not named. **First, every query in slice 1 must be
`user_id`-scoped, and with 396 populated users a missing `WHERE` clause returns
plausible-looking data instead of an empty result** — the failure mode is a
screen that looks right and is not, which is the hardest kind to notice and the
kind §14 says this repo keeps shipping. **Second, "is this my money or a
fixture?" has to be answerable at a glance**, or the first reconciliation
(§3.0) is checking Manan's real holdings against a synthetic portfolio.

**Decision:** slice 1.1 gets a real user record with a known id, and its
acceptance criterion is that **the fixture users are unreachable from every
surface** — not deleted (they are what 1,610 tests run against), but provably
not addressable. A test that passes with the fixtures present and would fail if
any query dropped its scope.


### 16.5 🔴 The data model assumes a machine this app does not run on

Found on pass 12, by reading the git history instead of the code. The most
recent commit on this branch is **`8a5e4d2`, three days before this plan was
written**: *"deploy free with no credit card, by removing the two things that
needed one."* Everything in §16 above was written without it.

**What that commit established, and it is still true:**

```
Frontend      Vercel Hobby            Backend API   Render free
Nightly jobs  GitHub Actions          NAV store     GitHub RELEASE ASSET
User accounts TURSO (libSQL)          HTTPS         platform subdomains
```

> *"So the disk no longer has to persist. The store is read-only at runtime;
> the thing that writes it runs on GitHub."*

The NAV store is trimmed (4,939 schemes → 1,723; 189 MB → **23.9 MB gzipped**),
published as a release asset, and **downloaded by the app at boot**. The
memory-heavy pandas work left the host entirely and runs on a 16 GB runner.
**That is what made a card unnecessary**, and it is the only reason this project
has a free deployment at all.

**§16 mentions none of it.** Counted: `Turso` **0**, `libSQL` **0**,
`release asset` **0**, `at boot` **0**, `fetch_nav_store.py` **0**. Every one of
the 14 occurrences of "Render" in this document is UI *rendering*. §16 names
three local SQLite files on one persistent disk — which is precisely the machine
`8a5e4d2` removed the need for.

**Three concrete consequences, each of which would surface as a broken feature
rather than a build error:**

**1. `nextrade.db` does not exist in production — it is Turso.** §16.2 adds
`lever_actions` and `narration_cache` "in `nextrade.db`". In the deployed app
that is a **network database**, so those are Turso migrations, and every
narration cache lookup is a round trip rather than a local read. That is still
overwhelmingly worth it — tens of milliseconds against a Gemini call — but it
has to be *known*, because §4.4's caching design is currently priced as free.
More seriously: **slice 1.1 puts Manan's real holdings in this file.** On an
ephemeral Render disk a local SQLite file is lost on every restart. The Turso
path is already built and documented; the plan simply never says so.

**2. `.holdings/hold.db` has no route to the running app.** The NAV store works
because it is *read-only at runtime* and delivered as a release asset. The
holdings store is **written** by a monthly pull and **read at request time** —
§16.3 deliberately stores nothing derived, so look-through and overlap are
computed live from it. Gitignored (§16.4), not a release asset, not on a
persistent disk: **as this plan stands, look-through — §1.5, one of the five
findings the whole design rests on — cannot run in the deployed app.**

🟡 **And §16.4's committed gzipped dump, written one pass earlier, is a *third*
mechanism that diverges from the established one without saying so.** On
inspection the divergence is correct and worth keeping, but only because the two
artefacts do different jobs, and that has to be written down or someone will
"fix" it back:

```
data/holdings-dumps/YYYY-MM.sql.gz   the ARCHIVE. Committed, versioned, tiny.
                                     Release assets are explicitly replaceable
                                     and versionless -- fine for a store rebuilt
                                     nightly, WRONG for an append-only record
                                     whose whole value is its history.

hold.db.gz  (release asset)          the RUNTIME COPY. Read-only, downloaded at
                                     boot beside nav.db.gz, produced by the same
                                     workflow. This is what look-through reads.
```

Two artefacts, two jobs, one written by the other. Neither replaces the other.

**3. `stock_daily`'s ~9.3M rows are pointed at the file that gets trimmed and
downloaded.** §16.3 already flags that `trim_nav_store.py` must learn about
`stock_daily` *"or it silently drops 26 years of history"* — but the opposite
failure is the one that bites in production: if trim **keeps** it, the boot
download stops being 23.9 MB and every cold start on a free host pays for it.
The resolution is the same shape as the NAV trim: **publish only what is read at
request time**, keep the full archive on the runner. What Phase 1 actually needs
from 26 years of stock history is a base rate, and a base rate is a computed
table of a few thousand rows, not a price series.

**Why this was invisible for eleven passes.** Every earlier method compared the
document to something *inside* the repo — its own prose, the filesystem, live
measurements, the code, the memory. **The deployment lives in a commit message
and a `deploy/` folder that no check had reason to open.** A plan can be
internally consistent, externally verified, and buildable, and still describe an
application that runs somewhere else.

**Slice 0 gains one step, and slice 2.3's acceptance changes:** the store paths
in §16.2 are re-stated against Turso and release assets before any of them is
built, and 2.3 is not done until **look-through answers from a fresh boot with
no persistent disk** — which is the only test that distinguishes the two designs.

---

### 16.6 🟢 Groww already ships eleven years of daily TER, and this plan was going to spend eleven years rebuilding it

Pass 26 inventoried **every field** in the 39 cached payloads — 416 distinct
paths — and compared them against this document. **311 appear in at least 30 of
39 payloads and are named nowhere here.** Most are STP/SWP transaction plumbing
that advisory-only Phase 1 has no use for. One is not:

```
historic_fund_expense[]   {expense_ratio, as_on_date, frequency, turn_over_ratio}

  39 of 39 funds carry it       median 1,091 entries, max 1,169
  earliest observation          2013-06-30
  median span                   130 months  (~11 years), DAILY
  median distinct TER changes   187 per fund
```

**§3.5 lists `fund_ter_history` among five "genuinely new" engines to build in
slice 3.2. It is a field read.** That is one of five removed from the build.

**And it corrects a design decision, not just an estimate.** §16.2 put `as_of`
in `groww_universe`'s primary key partly so monthly snapshots would *accumulate*
TER history for §3.4's chart. Accumulating monthly from today would take
**eleven years** to reach what one request already returns — and the chart would
show a single point on day one instead of a decade. `as_of` stays in the key,
but for §11.3's *"when did this fund leave the buyable set"*, which genuinely
cannot be recovered any other way.

**Honest scope limit:** this lives on the **scheme detail** endpoint, one request
per fund. Charting TER for a fund the user opens is therefore free. Ranking all
1,686 funds *on TER history* would still need the universe pull, so
`fund_cost_rank` stays a new engine.

**Two smaller finds from the same inventory, both worth taking:**

- `historic_exit_loads[]` — `{as_on_date, front_load, back_load, cdsc, note}`,
  1 to 6 entries per fund. Exit load **history**, sparse but real, which §3.2's
  switch-cost arithmetic currently treats as a single current value.
- `holdings[].nature_name` — `"CASH"` on repo lines, alongside `sector_name` and
  `corpus_per`. §1.5's headline *"₹1,00,000 into equity funds; ₹90,945 reached
  equity"* depends on separating cash from equity, and this is an **explicit
  field** rather than something to infer from an instrument name.
- ⚠️ `groww_scheme_code` holds an **ISIN** (`INF2JJD01177`), not a scheme code.
  A field named for one identifier carrying another is exactly the trap
  §11.7 and `groww.py`'s guards exist for.

## 17. The narration contract

§4 gives the architecture and §3.5 gives the tool registry. Neither says what is
actually sent, what comes back, or what happens when it fails — which is the
difference between a design and something buildable.


🟢 **All five rules verified against `grounding.py` — pass 141, and this was the
second-least-checked section in the document.**

```
1  every figure comes from the tool output   check() / _used_numbers
2  digits, never words                       spelled_out, run live below
3  name the source field for every figure    check_claims / _PREDICATES / quote
4  a cited list row names its subject        _names_entity / _siblings
5  if the data does not answer, say so       unruled / the refusal path
```

**Rule 2 was the one worth testing rather than reading**, because a rule about
model output is easy to state and easy to leave as an instruction. Run against
the module:

```
check("The fund returned thirty three percent last year.", {"ret": 33.0})
    -> spelled_out ('thirty', 'three')   ok False
check("The fund returned 33% last year.",                  {"ret": 33.0})
    -> spelled_out ()                    ok True
```

⚠️ **And the irony belongs in the record.** This guard rejects spelled-out
numbers on the grounds that **they cannot be checked** — while pass 89 found that
*this document's own* verification was blind to exactly that, which is how
*"thirty-six review passes"* sat on the front page while the log held eighty-four.
**The code was stricter than the plan about the same failure, and the plan is the
thing that argues for rigour.**

### 17.1 What the model is sent

```
system      role, scope, and the four hard rules:
              - every figure must come from the tool output below
              - use digits, never words ("thirty three" cannot be checked)
              - name the source field for every figure you use
              - when a list row is cited, name the row's subject too
              - if the data does not answer the question, say so and stop
tools       the registry from §3.5, as typed function declarations
context     the tool JSON, verbatim, unflattened
question    the user's, or for inline narration a fixed instruction
```

**Domain and units are stated explicitly every time**, because they were the
difference between a correct sentence and this, generated live on 2026-08-27:

> *"A lower **Translation Error Rate** (TER) of 0.63 compared to the median of
> 1.02 indicates that the evaluated translation is of higher quality."*

Confident, fluent, and the wrong domain entirely.

### 17.2 What comes back

`responseSchema`, verified working on `gemini-3.1-flash-lite` including `enum`
and `ARRAY`:

```json
{
  "sentences": ["..."],
  "claims": [
    {"value": "0.69", "field": "ter_pct"},
    {"value": "7.55", "field": "holdings.0.weight_pct",
     "entity_field": "holdings.0.name", "entity_value": "HDFC Bank Ltd"}
  ],
  "insufficient": false,
  "insufficient_reason": null
}
```

`claims` is not optional and not decoration — it is what `check_claims` compares
against, and §4.3 shows that without it a figure can be cited from the wrong
field and pass. `entity_field` is **required whenever the path runs through a
list**, because a path proves the number and never proved the subject.

### 17.3 Validation, and what happens on failure

Every response goes through `check_all` — the three checks together, because
each alone has a live hole (§4.3):

```
1  generate
2  check_all(text, claims, tool_json)
3  pass  → render, cache under sha256(tool_json)
   fail  → retry ONCE, appending the failure verbatim to the prompt:
             "0.33 does not appear in the source. Do not compute."
4  fail again → render the deterministic template. The user sees a
   `computed` chip (§13.5) so a fallback never impersonates a generation.
```

**One retry, not three.** A model that could not ground it twice is not going to
on the third, and each attempt costs latency the user is watching.

**Every attempt is logged** — tool JSON, generated text, claims, verdict — so
any answer is replayable and §11.5's grounding-fidelity number is a measurement
rather than a claim.

### 17.4 Caching

🔴 **`sha256(tool_json)` alone is wrong, and it returns a wrong answer rather
than a miss.** Two *different questions* over the same portfolio hash
identically and the second gets the first's sentence. And editing the system
prompt serves stale text forever.

```
key = sha256(tool_json ‖ normalised_question ‖ model_id ‖ prompt_version)
```

- **`normalised_question`** is empty for inline narration, which is the case the
  original design was thinking of — that is why the mistake was easy to miss.
- **`prompt_version`** is bumped by hand when the system prompt changes, and a
  bump invalidates everything. Without it the most dangerous edit in the system
  has no invalidation path.
- **TTL 30 days, eviction by LRU**, and an explicit invalidation when the
  underlying NAV or holdings change — the data moving is the only thing that
  *should* invalidate, and it has to actually be wired rather than assumed.

Sized against the measured rate limit (§4.4): roughly ten holdings, twenty
screen views and twenty chat turns a day is ~50 calls — comfortable at 15 RPM
even if the newer key's headroom disappears.

### 17.5 Where the LLM must not be in the path at all

Inline verdicts, badges and every rupee figure render **from the deterministic
JSON, before any model call returns**. Narration arrives afterwards and adds
sentences, never numbers. So the screen is correct and complete with the AI
layer switched off entirely — which is also the honest test of whether the AI
layer is doing anything.

### 17.5a The prompt that wrote those 757 generations — pass 70

§4 designs the AI layer without once opening PRD §5.7, which specifies one.
Reading it explains the pass-27 result and finds three things §4 should carry.

```python
FA_SYSTEM_PROMPT = """
You are NexTrade's friendly Indian financial advisor.
Explain financial plans in simple Hinglish (Hindi-English mix).
Be warm, practical, and concise (3-4 sentences max).
Never guarantee returns. Always say "projected" not "guaranteed".
Use emojis sparingly. Be encouraging but realistic.
"""
```

🟢 **1. It explains the zero hallucinations.** §17.5b reports that 757 real
generations contained **no ungrounded figures**, and reads it as a happy
result. It is not luck: the PRD's user message hands the model every number it
is allowed to use — goal name, target, years, SIP, allocation, total invested,
projected wealth — as pre-computed text. **The model was never asked to
calculate.** That is §4.2's architecture, specified before §4 restated it.

🟢 **And the instruction that survived 757 times is one line:** *"Never
guarantee returns. Always say 'projected' not 'guaranteed'."* Every sampled
generation carries *"Ye projected hai, guaranteed nahi"*. **That is measured
evidence that a single prompt constraint holds across a corpus**, which is worth
more to §4.1 than any argument about validation chains.

🔴 **2. §4 drops two stated product decisions.** *"Be warm, practical, and
concise (**3-4 sentences max**)"* and *"**Use emojis sparingly.** Be encouraging
but realistic."* §13 specifies type scales, badge anatomy and eleven states and
says nothing about tone or emoji; §17's narration contract says nothing either.
These are decisions someone made, they are visible in every generation, and no
part of this plan carries them.

🔴 **3. `/ask` is new scope, and this plan never says so.** The PRD's LLM fires
in exactly three places — *"after SIP calculation… after asset allocation…
after tax saving"* — always **explaining a computation that just ran**. §3.5
proposes a chat where the user asks arbitrary questions.

**That is a different and much larger surface**, and it is the reason §4's
grounding work matters far more here than it would for the PRD's design. When
every number is in the prompt and the model only narrates, hallucination is
structurally hard. **When a user can ask anything, the model chooses which tools
to call and what to say about the results**, and `check_all`, the refusal set
and the 18-tool registry all exist to hold that. **§0 should record `/ask` as
an expansion beyond the PRD rather than an implementation of it**, because the
cost of the whole AI layer follows from that one choice.

### 17.5b 🟢 The AI layer is not greenfield — 757 real generations were sitting in the database

Pass 27 inventoried every column in both databases against this plan. §4 says
*"there is no Gemini client"*, which is true, and this document reads throughout
as though no LLM has ever run here. **`goals.llm_explanation` is populated in
757 of 757 rows.** A Groq path shipped, ran, and left a corpus:

> *"Aapka goal 'buisness' ke liye projected monthly SIP Rs 32,447 hai, 5.0 saal
> ke liye. Paisa 50% equity, 40% debt, 10% gold mein lagega. Ye projected hai,
> guaranteed nahi…"*

Every one was generated **before `grounding.py` existed**. So they are the
adversarial corpus §3.4 asks for, already written, by the real prompt, in the
real voice, about real rows. Running `check()` over all 757 against their own
source rows:

```
ungrounded figures                     0        <- zero hallucinated numbers
spelled-out number words          46 texts      <- ALL false positives
after the fix below               757 / 757 pass
```

**🟢 Zero hallucinated numbers in 757 real generations.** That is the strongest
evidence this plan has for its own AI design, and it was available the whole
time.

**🔴 And it found a real defect in `grounding.py` by running it, which no amount
of reading had.** All 46 spelled-out-number flags were the same false positive:
the words were inside the **user's own goal name** — `Edge fifty crore`,
`Edge a hundred years out` — quoted back correctly. Not smuggled arithmetic; the
user's phrasing echoed. **6% of real output is precisely the rate at which a
guard stops being read.** Fixed: a number word inside a verbatim quote of a
source string is exempt, with a 4-character floor so a short value cannot
licence every number word in the text. 50 tests now, and the two cases above are
pinned.

**What this changes in the plan.** §3.4's *"adversarial suite"* is no longer
something to invent — it starts from 757 real texts. And §4's framing needs one
correction: the LLM path is **not** greenfield. It shipped, it ran, and its
output sits ungrounded in the shipped database, which is the strongest argument
the validation chain has for existing at all.

### 17.6 The four known holes, now closed — and the two more that closing them found

An adversarial review found four defects in `grounding.py` after its last
rewrite. This section used to list them as open, deferred to slice 3.1. **They
are now fixed, each with the case that found it pinned as a test** — 38 tests
became 50, and the module is the one artefact in this plan with no known defect
left in it.

Two of the four were closed by *reading the sentence*, which nothing did before:

1. **Entity binding never compared to the text.** `check_claims` compared the
   claim to the *payload* — name matches row, number matches row — and never
   looked at the prose. So a model could cite `holdings.0.name = "HDFC Bank
   Ltd"` entirely correctly and write *"Reliance Industries is 7.55% of the
   fund"*. Membership: pass. Field: pass. Entity: pass. And the fund does not
   hold Reliance. **Closed:** the subject must now be named in the sentence
   carrying the figure or the one before it, and no second row from the same
   list may be named alongside it. The previous-sentence allowance is
   deliberate — *"HDFC Bank is the largest holding. It is 7.55%…"* is correct
   prose, and a check that rejects correct prose gets switched off.

2. **An honest citation of a different real field defeated every check.** The
   payload says `peer_count: 44`; the model cites `peer_count` truthfully and
   writes *"the fund returned 44% over the last year"*. Nothing in the claim is
   false — the *sentence* is, and the sentence is what the user reads.
   **Closed:** `_PREDICATES` states what each field may be used to assert, and
   the sentence carrying the figure must carry one of that field's words.
   **The bound is honest:** an unruled field is not checked, it is *reported* in
   `Grounding.unruled`. That does not eliminate the hole, it narrows it from
   "any field can say anything" to "any field nobody has written a rule for" —
   and makes the remainder countable instead of invisible.

3. **The temporal-year exemption was dead under `check_all`.** `check` exempted
   a payload year written in a temporal phrase; `check_text_claims` did not. Each
   function's own tests passed and the *combination* rejected roughly one
   generation in six for correctly writing the date it was given. **Closed:**
   one helper, `_used_numbers`, owns the rule and every check calls it. This is
   the failure worth remembering — two correct fixes that broke each other, and
   no unit test could see it because neither function was wrong alone.

4. **Path-ambiguity rejected almost everything and caught nothing.** The plan
   estimated ~90%. **Measured across all 39 cached Groww scheme payloads:
   230,067 of 240,404 citable figures — **95.7%** — and every single collision was
   between fields that mean the *same* thing.** `stats.0.stat_1y` and
   `return_stats.0.return1y` are both −0.59 because Groww ships the one-year
   return under two names; citing either is honest. **Closed:** the rule fires
   only when the colliding paths carry *different* predicate rules. Re-measured
   on the same 39 payloads: **585 rejections, 0.2%.** What the rule was really
   guarding — citing one path while meaning another — is now caught by the
   predicate check, which reads the sentence.

**And closing them surfaced two more, both live:**

5. **A Unicode minus was invisible to the sign check.** The sign was made part
   of the number token specifically so a loss could not narrate as a gain. Then
   U+2212 — *the character this very document uses* — parsed as no sign at all,
   reinstating the exact bug through a character the pattern had never been
   shown. U+2212, U+2013, U+2012 and U+2010 now normalise to ASCII.

6. **A plural identifier key reopened the ISIN hole.** Moving identifier
   matching from substring to whole-word fixed a real false positive
   (`portfolio_date` contains "folio") and silently un-matched `identifiers.isins`,
   so every digit inside an ISIN became a grounded fact again — *"the fund holds
   879 securities"* from `INF879O01027`. Keys are now singularised, and **both**
   directions have a test.

> The pattern across all six is one thing: **every fix in this module has, at
> least once, been the cause of the next defect.** That is why the count of
> tests matters less than the fact that each one pins a case that actually
> happened.

**The module is still evidence for this plan, not shipped code.** It has no
caller. It exists to prove the architecture is implementable and to find this
class of defect before the build — which it did, six times.


---

*Sources for every claim: `docs/groww-endpoints.md`, `docs/zerodha-endpoints.md`,
and the vault notes `traa-groww-data-layer`, `traa-nse-archive`,
`traa-gemini-verified`, `traa-exit-signal-measured`, `traa-visual-direction`.*


---

## 18. The review log

Every pass used a method the previous one had not. That was the whole
technique, and the rate below is the only real evidence about readiness.

**Is it ready to build? Here is the rate rather than an opinion**, since each
pass deliberately used a method the previous one had not:

```
pass 1-4   reading the document              41 findings
pass 5     document vs filesystem             3   one a live risk
pass 6     document vs measurement            2   3 of 5 checks came back clean
pass 7     document vs itself                 3   ALL THREE self-inflicted
pass 8     "could someone BUILD from this?"   1   but it was the load-bearing one
pass 9     unverified claims, tools not yet used  2 closed · 1 bounded
pass 10    the document against itself, again      1   self-inflicted only
pass 11    the plan against the project's MEMORY   2 live · 1 stale memory
pass 12    the plan against GIT HISTORY           1   the largest yet
pass 13    the plan against the DEPLOY BUDGET     1   an unwritten invariant
pass 14    the plan against the FREE TIER's UX    1   the app's commonest state
pass 15    the code against the STATUTE it cites  1   money, in the wrong direction
pass 16    a claimed threshold against real DATA   1   the ceiling is not a ceiling
pass 17    a claimed ZERO, re-counted                1   plus a stronger validation
pass 18    every absolute claim, re-derived          1   right sum, wrong sample
pass 19    THE SCOREBOARD against itself             1   a real smell, wrong diagnosis
pass 20    pass 19's own finding, re-derived         1   half of it was wrong
pass 21    claims about code, by RUNNING the code     1   a criterion pointing backwards
pass 22    the whole DEPENDENCY class, mechanically   2   found, and the class closed
pass 23    the last two unrun claims                  1   "101" is 18, and unverifiable
pass 24    reproducing a figure from retained data    1   claim stands, join key was unwritten
pass 25    mechanism vs count, separated              2   and a better signal found
pass 26    every payload field vs the plan            4   one REMOVED work from the build
pass 27    every DB column vs the plan                3   757 real generations, and a fix
pass 28    the auth path, which §8 never read         3   a credential asked for and unused
pass 29    migrations + frontend deps                 1   and the first genuinely CLEAN area
pass 30    the "already built" assumption, counted    2   0 of 8 devices, and a forbidden one ships
pass 31    the three remaining uncounted numbers      1   "18 tools" is seven, and unlisted
pass 32    the plan against the API that exists       1   49 endpoints, zero named
pass 33    the first response SHAPE, read             1   §1.5 is half-shipped already
pass 34    §14's rules against the SCHEMAS            1   verified against notes, not code
pass 35    all 49 response shapes, at once            1   two tools have no contract
pass 36    can this DOCUMENT do its job?           1   its "one page" was 329 lines
pass 37    §9's usability, and navigation            2   35 open mixed with 13 closed
pass 38    32 open items, grouped by action          2   incl. one of pass 37's own
pass 39    my own edits, verified against the plan   1   four stale counts, all mine
pass 40    the plan's own ESTIMATE, against history   1   31 sessions = 155% of the repo
pass 41    fifteen passes of findings -> a schedule    -   31 -> 33, redistributed
pass 42    the primary USER JOURNEY, traced          1   the first screen shipped last
pass 43    the on-ramp, COUNTED in steps             2   and the used auth path, unreviewed
pass 44    the DESIGN system, rated 0-10          1   SHOWN scores 2 of 10
pass 45    acting on pass 44 instead of filing it  -   SHOWN 2 -> 5, four sketches
pass 46    closing what could be closed NOW        -   4 open items -> closed
pass 47    a field mapping the store could settle    1   12/12 and 9/9, decoded
pass 48    open items already closed, plus a real fix  3   incl. the LTCG month count
pass 49    can the SUITE fail? nine mutations       -   9/9 caught, 0 survived
pass 50    vault + memory + §12, re-verified        4   3 of them my own edits
pass 51    mutations on the UNTOUCHED modules        2   a module with no test file
pass 52    writing the missing tests, then RE-mutating 1   my own new test was decoration
pass 53    binding a coverage claim to its computation 2   consistency is not correctness
pass 54    the last untested module              -   72 of 72 now named by a test
pass 55    NAMED vs CALLED, profiled                2   pass 54's own claim was misleading
pass 56    the three functions pass 55 exposed      1   my own first test was wrong
pass 57    what verifies the FRONTEND               2   no unit layer; four harnesses exist
pass 58    the gate at the repo root, never opened  3   nine checks, and three of my findings corrected
pass 59    the documents in this plan's OWN folder  1   a 2,330-line PRD, never opened
pass 60    reconciling the first of those ten       2   a better argument was already written
pass 61    the second of the ten                   1   my own famous correction was wrong
pass 62    SECURITY.md, 44 lines, never opened     3   incl. "is this thing even deployed?"
pass 63    a refusal this plan half-overturned      1   the data reason died, the evidence one did not
pass 64    where §1's control discipline came from   1   quoted a result, dropped its source
pass 65    the stock score's own test                2   87 of 100 points, and a fifth self-flattering gate
pass 66    the PRD's first table                    2   the app has 4-5 users, not one
pass 67    twenty lines further into the PRD        1   pass 66 overstated it; and a gap, not a conflict
pass 68    the PRD's Part A, read properly          1   a known defect turns out to be specified
pass 69    the same, for the rebalancer             3   two of three defects are the spec
pass 70    the PRD's LLM section                    3   /ask is new scope; and why 757 held
pass 71    the PRD's data sources, counted          1   the advisor it specifies never touches a fund
pass 72    fixing §0 instead of filing it           -   the framing, corrected at the front
pass 73    the teardown's fourteen-row gap table    2   three closed uncited, five never mentioned
pass 74    the last two root documents             2   the front door says the app does not exist
pass 75    fixing the front door, then verifying it 2   two of my own new numbers were wrong
pass 76    verifying every number from 59-75      0   8 false alarms, all from the checker
pass 77    regrouping §9.1 after the reconciliation 1   I wrote the conclusion before the count
pass 78    the five unclassified rows              1   one was a claim I could fix outright
pass 79    grouping §9.1 a third time              1   the regex matched "ceiling" and "slab"
pass 80    the counts §9 states about itself       2   35/13 were really 40/30
pass 81    slice 2's eight items read together     2   incl. an acceptance written twice
pass 82    the TER gate, and what a cap looks like 2   one was a bug 208f396 half-fixed
pass 83    reading the code before believing me     1   pass 82's harm and count were both wrong
pass 84    all 13 code claims, against the code     1   12 exact; the 13th was my own stale count
pass 85    the same fact, stated in two places       5   the sessions total disagreed with its own slices
pass 86    what Manan asked, against what is written 2   two constraints shaped every section, unrecorded
pass 87    the document as a thing to navigate      2   4 headings out of order, 13 refs on a bare list
pass 88    does any slice need a later slice?       2   both in slice 1, the one that re-prices the rest
pass 88b   counting what I had just asserted        2   "twenty-two" was 13, and 3.2 had no acceptance
pass 89    numbers spelled as words, not digits     1   the readiness verdict on page one was stale
pass 90    what the ranking page does not show      1   31% of the universe, silently
pass 91    every field the API returns, traced      2   my first reading of 8 of them was wrong
pass 92    open items that were already closed      3   one had carried a tick mark for 20 passes
pass 93    the same question, slice 0's five        1   3 of 5 confirmed still genuinely open
pass 94    slice 3's three, and their arithmetic    2   34 + 12 had been read past as 49
pass 95    slice 1's three and slice 4's seven      1   nine of ten exact; casparser still absent
pass 96    slice 2's nine, against the filesystem   1   the irrecoverable store does not exist
pass 97    every artefact §16 names                 1   a third one it describes in present tense
pass 98    the repo's files against the plan's      1   slice 4 names none of the pages it rebuilds
pass 99    building the map instead of filing it    3   Decide.tsx has no surface in 5,700 lines
pass 100   §3.2 against the file it lands on        1   a deferred decision was already taken
pass 101   §3.3 against Screener.tsx                1   virtualisation re-solves a solved problem
pass 102   §3.1 against Portfolio.tsx               2   a rewrite would drop three honesty states
pass 103   every honesty state the app ships        2   pass 90's finding was false; corrected
pass 104   re-checking what grep alone had found    0   the 18-field row survives three checks
pass 105   the same re-check on pass 98's count     1   five unnamed pages were six
pass 106   the same question for components         1   §3.0 names none of the on-ramp's own code
pass 107   opening the four it never named          1   §3.0's screen already exists, and works
pass 108   §3.4 against both detail pages           1   4 of 5 sections over-estimate, not under
pass 109   §3.5 and §3.6, finishing the sweep       1   my own 4-of-5 was an incomplete sample
pass 110   slice 4.1, the last unmeasured step      2   'sidebar' is a top nav; 'trail' was trailing
pass 111   slices 1 and 3 against their own files   0   accurate; the over-estimate is only slice 4
pass 112   §6's debt defect, in both scorers        3   there are two, and CAGR is in neither
pass 113   what check.sh already says about that    1   pass 112 read a design as an oversight
pass 114   §11 against the harness it describes     1   513 lines on verification, 1 file named
pass 115   reading the harness, writing §11.10      -   closes it; a read, not a build
pass 116   §1's evidence against backend/scripts    1   six validators exist, none cited
pass 117   what 'live' means, inside my own guard   1   22 lost funds were 37; the proxy hid 353
pass 118   why those 353 have no TER                1   23 whole AMCs, incl. Groww's own, at zero
pass 119   every hardcoded bound in the backend     0   12 exist; only the TER one loses data
pass 120   probing AMFI to settle the cause         1   proven; and PPFAS was missing too
pass 121   the missing TER, into the scorer         1   scored as median cost, invisibly
pass 122   how much of it reaches a ranking         1   9% of the ranked universe; direction unknown
pass 123   the direction, with the right params     1   no group bias; the per-fund harm stands
pass 124   how old every committed data file is     1   three cannot say; one decides cheap or dear
pass 125   the tax year, and a guard for it         1   my own first guard was inert
pass 126   mutating every guard I wrote             0   9 of 9 catch; none inert
pass 127   which open rows say what to DO           8   two were already answered elsewhere
pass 128   when each open row was last checked      12  26 had no provenance at all
pass 129   whether the rows are still readable      2   one cell had reached 7,700 characters
pass 130   gating both, since one had recurred     -   heading order and row length, mutated
pass 131   where the AMC ids actually end          -   86, and the fix is a rule not a number
pass 132   whether §8 really turns on the count     1   it does not; §8.2 says so itself
pass 133   which blocks are blocks                  1   one of four; two were already scheduled
pass 134   what the real portfolio would settle     1   three questions, not the design
pass 135   is look-through worth building?          -   yes; 29% of pairs share a fifth
pass 136   can each badge fire at all?              1   the biggest one cannot; no regular->direct
pass 137   checking the fix I had just specified    1   the stem does not exist; the edge is a name
pass 138   why no release asset has ever existed    1   nightly.yml is not on main
pass 139   how much exists in exactly one place     -   12,423 lines; the docs outweigh the code
pass 140   §15, the only section never verified     1   one destination of six matches
pass 141   §17's five rules, against the code       0   all five enforced; rule 2 run live
pass 142   §12 against the run table                1   the reproducible count was the missing one
pass 143   §14's six line citations                 0   all exact; nearly misread as all stale
pass 144   every file:line citation in the plan     1   3 of 4 names exist twice in app/
pass 145   path-qualifying them                     -   closes it; the regex ate its own example
pass 146   every 'X, not Y' pair in the document    0   17 intact; now gated and mutated
pass 147   what my own guards cost the code gate    1   a doc typo reds the 'unit tests' step
pass 148   reproducing §1.1's pivot from the store  -   52 windows, +2.1pp, 43/52 — exact
pass 148b  the guard caught me making pass 129's    -   §1.8 inserted before §1.7; suite went red
pass 149   testing §1.1's lookahead assumption      1   cost is stable as a number, not as a rank
pass 150   running it both ways on 21 funds         1   the sign flips; n is far too small to settle
pass 151   a portfolio, invented on instruction     -   closes the last thing blocked on Manan
```

**Three passes running, the same failure in a different word.** Pass 29:
*"versions checked live"* meant checked **on npm**, not in `package.json`. Pass
30: *"the **remaining** devices"* assumed three were done; none was. Pass 31:
*"the **18** tools in §3.5"* — §3.5 names seven and enumerates none.

> **A number in prose is a claim, and this document has been treating its own
> numbers as counts when they were estimates written once and never re-derived.**
> Every one that has been re-counted has moved.

Two of the three were checked and are **sound**: nav.db really does hold exactly
four `screener_*` tables, and §7.6's *"sixteen new components"* is a narrative
sentence describing the **old** build order, not a specification — it prices
nothing and is left as prose. ⚠️ Although the same docstring that counts the four
tables says they are *"copied verbatim"*, which pass 21 showed is not the
mechanism: `trim_nav_store.py` copies the **whole file** and deletes from one
table. The count is right and the description of how it gets there is not.

✅ **Pass 29 produced the first substantive area that came back with nothing
wrong, and that is worth recording as carefully as a defect.** The Alembic chain
was replayed from an empty database — the thing a fresh Turso deploy does and
which nobody had ever run:

```
7 migrations, empty -> head, no error
resulting schema vs the live database: IDENTICAL
  same tables, same columns, same types, same nullability
```

So slice 1.1's first act — adding `plan_type`, `goal_id`, `last_reconciled_at`
to `holdings` — rests on a chain that is a faithful description of the schema,
and it is. The two `op.alter_column` calls are both `users.phone` nullability
and replay fine. No `batch_alter_table` anywhere, so no table rebuilds cross the
network to Turso.

🔴 **The frontend was not clean.** 26 dependencies, and **no virtualisation
library, no table library, no motion library** — while §3.2 names
`@tanstack/react-virtual` and `@tanstack/react-table` by version. `recharts`,
`lucide-react` and `shadcn` are present, so §13's charting and icons are real.

**Pass 22 stopped finding instances and closed the class.** `pandas` (pass 11)
and `casparser` (pass 21) were both dependency defects found by accident, and
`numpy` had been one before that. So instead of looking for a fourth, an AST
walk over `app/` compared every third-party import against `requirements.txt`:

```
20 third-party modules imported by app/
 requests    imported by marketdata/nse_delivery.py, declared nowhere,
             arriving via mftool / yfinance / twilio        <- now declared
 starlette   guaranteed by fastapi's own pin                <- exempt, and the
                                                               exemption asserts
                                                               fastapi is declared
 casparser   not installed at all; only named in this document
```

**The hazard is not that the imports fail — they succeed.** Some other package
happens to supply them, so no test ever fails. **And the supplier is a package
this plan intends to remove:** `yfinance` is retired for prices (§2), and it is
one of the two suppliers of every instance found. The consumer and the supplier
are moving in opposite directions.

`tests/test_declared_dependencies.py` now fails on the whole class. It
distinguishes the two cases that look identical from the outside: a module
pulled in by a **declared extra** (`fastapi-users[sqlalchemy]`) is *asked for*
and passes; a module that arrives because someone else's dependency needs it
does not. **Shown failing** by removing `requests` before being kept.

🔴 **Pass 19 went back to the claim everything else rests on, and found the
published record contradicting itself.** `app/data/track_record.json` is the
file passes 1-4 already caught this document misquoting — the reason §1.1 was
rewritten. It was never re-examined on its own terms. Two things in it:

**1. The denominator. ⚠️ This bullet claimed a contradiction that pass 20 then
disproved, and the correction is left in rather than tidied away**, because the
mistake is the same shape as the ones this document keeps recording.

*What pass 19 wrote:* every signal records `windows: 44, low 44, high 44`, while
`why_ranges` says *"five consecutive runs of the identical script gave 37, 35,
36, 35 and 35 windows out of 44"* — so either the rates divide by windows that
returned no data and understate themselves, or the caveat is stale.

*What reading the code settled — both halves of that were wrong:*

- **`windows` counts RESOLVED windows, not attempted.** In
  `validate_quartiles.py` and `why_not_returns.py` a window is appended to the
  tally only after passing every guard — enough history, ≥12 ranked funds, ≥12
  forward returns. `len(rows)` is what survived. **Nothing is divided by empty
  windows and no rate is understated.**
- **`why_ranges` is not a measurement.** It is a hardcoded string literal in
  `build_track_record.py`, re-emitted verbatim on every rebuild. `RUNS = 3` in
  that same file, and the sentence describes **five** runs — so it cannot be
  describing the run that produced this data, and never was.

**So the data does not contradict itself. The file contains a fixed sentence
that reads as though it describes the data.** That is a smaller defect than
claimed and a real one: 🔴 **a self-report that cannot be wrong, because it is
not computed.** It will be re-emitted unchanged after any future re-run and will
describe none of them. This repo has caught the identical shape before — a
`check.sh` that could never fail — and §11.4 exists because of it.

**Fix, small and mechanical:** `why_ranges` reports the *observed* window counts
of the runs it just performed, or it says nothing. A caveat that is a constant is
decoration.

**2. Two of four signals show zero run-to-run variation in all six fields.**

```
past_3y     6/6 fields  low == high     <- the "selection does not predict" claim
nav_level   6/6 fields  low == high
cost        3/6                          spread 2.1-2.2, IC 0.195-0.197
blend       2/6                          spread 0.7-0.9, IC 0.104-0.107
```

`why_ranges` states the sample varies run to run because mfapi fetches vary.
`cost` and `blend` show exactly that. `past_3y` and `nav_level` show none of it
across three runs, in every field including `rank_ic` to three decimals. That is
not impossible, but it is the pattern you would also see if those two blocks'
ranges were carried rather than recomputed — and `past_3y` is the block this
plan leans on hardest.

**Neither is evidence the finding is wrong.** §1.4's independent measurement and
the outside literature both point the same way, and `cost` beating `past_3y` is
not in doubt. What is in doubt is whether **these specific published percentages
can be reproduced**, and §11.4 of this document is explicit that a record which
no longer reproduces is worse than no record at all.

**So slice 0 gains a gate, and it is narrower than pass 19 proposed** now that
the denominator question is settled: re-run `build_track_record.py` at
`runs_per_measurement` ≥ 5 so `low`/`high` are computed over enough runs to mean
anything, **make `why_ranges` report the runs it actually performed**, and
publish whatever reproduces. §1.1 stands unless it moves.

> **And the lesson from pass 19 → 20 is the one worth keeping.** Pass 19 found a
> real smell and reasoned from the file alone to a confident, wrong conclusion —
> that published hit rates were understated. Reading two scripts settled it in
> minutes. **Every confident wrong answer in this whole exercise has come from
> stopping at the artefact instead of going to what produces it**: the surcharge
> formula, the TER ceiling, the deployment target, and now this.

**Pass 8 asked the only question that matters here** — *could a builder start
1.1 tomorrow morning with nothing but this document?* — and found that **13 of
16 build steps named what to build and never said how anyone would know it was
done and right.** The three that did were all written in the last two days.

That is not a cosmetic gap. This repo's own history is a verification gate that
could never fail (`check.sh`), and §11.4 exists because a record that cannot
fail is a decoration. A build step with no acceptance criterion is the same
object: "done" becomes a judgment call, made by the person who wants it to be
done. **All 16 steps now carry a falsifiable criterion** — 1.3's is *"the tax on
one rupee above each surcharge threshold exceeds the tax below by at most one
rupee"*, which is the definition of marginal relief and cannot be argued with;
3.1's requires the grounding check to be **shown failing** when removed, because
a guard nobody has watched fail is a guard nobody knows runs.

**Pass 7 is the one that changed the answer.** It summed the slice table instead
of reading the total (31, not 32 — slice 3.1 dropped a session when
`grounding.py` was fixed early and nobody re-added), checked every fraction
against its own percentage (95.7%, written as 95%), and caught `§112` being used
for an Income-tax Act section in a document where `§` means a section of *this
plan*. It also verified 34 fractions, 56 cross-references, 20 tables and 86 code
fences clean.

**Every one of pass 7's three findings was introduced by passes 5 and 6.** None
came from the original document. That is a materially different state from
"still finding things": the document has stopped yielding *latent* defects and
now only yields *fresh edit* defects — which is the condition where further
review passes measure the editing, not the plan.

**The answer, stated as precisely as it can honestly be stated.**

*Is this plan perfect?* No document is, and no amount of reading one establishes
it. That question has no achievable answer and pursuing it further would be
theatre.

*Is it good to build from?* **Yes, and that is a testable claim rather than a
feeling.** It means every step names what to build, where it goes, and a
criterion that can fail — which was **not** true before pass 8 and is true now.
It also means the things still unknown are *named, scoped, and each carries the
test that closes it*: §2's four unreproducible figures close in 2.1 by
re-printing them, the AI layer closes in slice 3 by acquiring a caller, and both
are written into the table rather than left to be rediscovered.

**What it does not mean.** It does not mean the app will be right — slice 1
exists precisely because a plan cannot know what one real holding will teach it.
It does not mean the four figures are correct, only that they will be checked.
And two things remain outside this document entirely: browser permission to read
Manan's real portfolio, and approval for the monthly holdings pull.

**Pass 9 asked a different question again: what did this document mark as
unverified, and had every available tool actually been tried?** Web search was
exhausted; the ITD's own portal was not. Two flags closed against it (§10), and
**closing the first one changed the specification** — the capital-gains surcharge
cap is `min(slab, 15%)`, not the flat 15% this document had written, and coding
the flat version would have overcharged an entire income bracket. That is the
argument for verifying a claim you are already confident about.

**Pass 11 checked the plan against this project's own 31 memory files** — the
accumulated findings of months of work — and that was the one direction never
tried. It found **five recorded defects that appeared nowhere in this document**.
Three had since been fixed in code (the stock scorer that once gave a 14-day-old
listing 100/100 now refuses it by name); **two were live**, and one of those —
undeclared `pandas` — is made *worse* by this plan's own decision to retire
yfinance. It also found a memory file asserting a defect that no longer exists,
which is the same §11.4 failure pointing the other way.

**The lesson: a plan can be internally perfect and still contradict what the
project already learned.** Nine passes of checking the document against itself,
the filesystem, measurements and external sources could not have found this,
because the knowledge was in neither the prose nor the code.

**Pass 12 read the git history rather than the code, and found the largest gap
in the document.** The newest commit on this branch — three days before this plan
was written — removed the app's need for a persistent disk, and §16 was written
as though it still had one. **Eleven earlier passes could not have found it**:
every one of them compared the document to something inside the repo — its prose,
its files, its measurements, its memory. The deployment lives in a commit message
and a `deploy/` folder that no check had a reason to open.

**Passes 13 and 14 stayed in pass 12's direction — the parts of the system no
check treats as reviewable — and both paid.** 13 found that the free deployment's
memory budget rests on a single `import` written inside a function, undocumented,
which any linter would "fix" and no test would catch (there is a test now, shown
failing). 14 found that the app's **single most frequent UI state** — the free
tier waking up, which is most sessions — was absent from the states table, and
that the API client has neither a timeout nor a retry to survive it.

**Both were invisible to the first eleven passes for the same reason: they live
at the seam between the document and the platform**, and every earlier method
looked at one side or the other.

**So the honest sentence has to be weaker than it was one pass ago**, and it is
worth writing down why: after pass 10 this document said no original findings
remained. Pass 11 found two. Pass 12 found one that invalidates part of §16.
**Three times now — the surcharge formula, the undeclared dependency, and the
deployment target — confidence has been the thing that was wrong.**

What can still be said: there is no longer a known question about this
plan that another review pass could answer. Pass 7's findings were all
self-inflicted by passes 5 and 6; pass 8's single finding is fixed; pass 9
emptied the unverified list down to one item that the authoritative source
structurally cannot settle, and which is not hardcoded anywhere because of it.
**The next thing that teaches us anything is slice 1.**
Two things remain blocked on Manan — browser permission to read his real
portfolio, and approval for the monthly holdings pull.

---
