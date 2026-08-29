# The build

This is the instruction. `phase-1-redesign.md` is the evidence — 6,608 lines and
148 review passes — and every claim here cites back to it rather than repeating
it. Read §0 of this file, then build in order.

**Scope: advisory only.** Nothing here places an order, sizes a trade, or times
a market. Trading is Phase 2.

---

## 0. Five things the review changed, before you start

Each of these was found by measuring rather than reading, and each one changes
what you would otherwise build.

**1. Much of what this plan describes already exists.** Seven §3 sections were
measured against the files they land on. Four came back already built:

```
§3.0  the on-ramp screen    SHIPPED   StartHere.tsx makes the same argument
§3.1  Today                 PART      Levers.tsx complete; BaseRatePanel exists elsewhere
§3.2  Holdings              SHIPPED   already a table; the "deferred" decision was taken
§3.3  Find                  MOSTLY    pagination already solves the volume problem
§3.4  Fund and Company      ADDITIVE  TER series, manager tenure, sector holdings absent
§3.5  Ask                   NEW       no chat surface, no /ask route, no registry
§3.6  Why                   NEW       no /why route
```

**The over-estimate is concentrated where the repo already had something.**
Slices 1, 2 and 3 describe what is missing accurately, item by item — verified
against their own files. **Slice 4's eleven sessions cannot be read as written.**

**2. `_MAX_MF_ID = 55` is costing 297 funds their cost data.** Cost is this
product's method. `build_expense_ratios.py` walks AMFI's AMC ids to a hardcoded
ceiling; ids 56–86 hold at least 24 live fund houses — **63 Groww, 64 Parag
Parikh, 77 Zerodha, 82 JioBlackRock** — proven by probing AMFI directly. 297
live funds carry no TER, **151 of them are old enough to be ranked**, and the
scorer gives those `_NEUTRAL = 0.5` — a fabricated median cost, indistinguishable
from a measurement. **Fix this first; it is one function.**

**3. The cost claim is real but smaller than written.** §1.1's +2.1pp ranks funds
by *today's* TER at decision dates up to eight years earlier. Cost turns out to be
stable as a number and **not as a rank** (correlation +0.34 at 2018; the median
fund moved six places of twenty-four). Re-run within category on real
contemporaneous filings: **+12.0pp with today's TER, +3.6pp with the TER filed
that month.** The effect survives; the lookahead roughly triples it. Sample is
thin (4–6 category-windows) — **the honest number is not yet known, and slice 2.1
can settle it with data it already pulls.**

**4. The badge worth the most cannot fire.** `Regular plan — Direct saves ₹X/yr`
is what §11.7 calls the largest single number this app will ever show. The
catalogue holds **zero regular plans** (deliberately — it is the recommendation
universe), and nothing maps a regular scheme code to its direct twin.
`expense_ratios.json` already carries **both** plans' TERs for 1,385 funds. **The
numbers are there; the join is missing.**

**5. The deployment has never run.** `.github/workflows/nightly.yml` publishes
the NAV store as a release asset and `fetch_nav_store.py` unpacks it at boot —
the mechanism is complete and correct. It is on a branch that is not on
`origin/main`, which is why `gh release list` is empty and the app is not
deployed.

---

## Slice 0 — the instrument, and the things that are one command away

Nothing here is a feature. All of it is cheap and all of it protects what comes
after.

| | what | acceptance |
|---|---|---|
| **0.1** | **Push the branch.** `origin/main` is behind; `nightly.yml` is not on it | `gh release list` shows `nav-store` after the first nightly run |
| **0.2** | **Raise the AMC ceiling — but not to a number.** Walk AMFI's ids until **eight consecutive** return nothing. Eight is four times the largest gap observed inside the live range (56–57, 59–60, 65–66 are empty; 86 is the top, with 24 empties above it). A constant goes stale the same way 55 did | after a rebuild, **zero live fund houses have zero TER coverage**; `tests/test_ter_coverage.py` flips from pinning the defect to failing on it |
| **0.3** | **Make the builder report its coverage** — houses found, schemes matched, catalogue funds still without a TER. Its docstring currently claims the unresolved are *"mostly ETFs and closed-ended schemes"*, which was false while 297 open-ended funds were missing, and is what kept the gap invisible for eleven passes | the run prints the three counts and fails if coverage drops |
| **0.4** | **Give every committed data file an `as_of`.** Three of seven cannot say how old they are: `fund_catalogue.json` (the universe — its age is only inferable from the newest `latest_nav_date`, 38 days), `stock_universe.json`, and **`sector_benchmarks.json`**, whose P/E and P/B medians decide whether a stock reads cheap or dear | every file in `app/data/` carries a build date, and the stock page shows it beside the peer count it already shows |
| **0.5** | **`Decide.tsx` reads `return_bounds`** instead of hardcoding `min={4} max={16}`. They agree today and nothing keeps them agreeing | `tests/test_return_bounds_agree.py` is deleted because it has nothing left to pin |
| **0.6** | **Separate the document gate.** 18 of the suite's tests check *this documentation* against the repo. They belong in the suite — §11's whole argument is that an unchecked claim goes wrong quietly — but `check.sh`'s step is labelled *"unit tests"*, so a stale count in a doc reds the code gate | **break one document claim and one code behaviour, separately, and the two steps go red separately.** Changing `47 things are open` to `46` must red the document step and leave the unit-test step green; breaking a service must do the reverse. A single step that goes red for both cannot tell a builder which they broke |
| **0.7** | **The waking state.** Render free sleeps after 15 minutes, so for an app opened a few times a week **almost every session is a cold start**. `src/lib/api.ts` is 56 lines with no timeout and no `AbortController` | a >2s wait shows the waking state, not a frozen skeleton; a cold boot is exercised in `sweep.mjs` |

---

## Slice 1 — one holding, end to end

The first slice that produces a number a person acts on. Everything after it is
re-priced against what this one actually costs.

| | what | acceptance |
|---|---|---|
| **1.1** | **Schema and one holding.** `holdings` gains `plan_type`, `goal_id`, `last_reconciled_at`, and the `amfi_code ↔ search_id ↔ isin` triple — **plus a fourth edge: regular code → direct code.** Build it by keeping what `build_fund_catalogue.py` already fetches and discards: AMFI's NAV feed carries both plans as separate rows, and the join is the normalised scheme name `build_expense_ratios.py` already uses. **Not** an `NSDLSchemeCode` stem — AMFI's row carries both plans' TERs *inside it*, so no such stem exists | a regular scheme code resolves to its direct twin and the saving prints; and a query that loses its `user_id` scope **fails a test** — 600 fixture users and 396 populated ids mean a dropped `WHERE` returns plausible data rather than nothing |
| **1.2** | **Its cost, from both sources.** Groww TER against the committed `expense_ratios.json`, the 0.10pp agreement gate, the plausibility ceiling, and the active/passive split | both sources agree within 0.10pp **for the held fund**, or the disagreement is shown rather than averaged; one source shows `n/a`, never `0`. **Not** the universe-wide 94.2% figure — that is slice 2.1's and needs its pull |
| **1.3** | **Surcharge and marginal relief** in `tax_regime.py`. It has neither today; its `marginal` is *"marginal rate"* in a slab comment | at each of ₹50L, ₹1cr, ₹2cr, ₹5cr, tax on **one rupee above** exceeds tax below by **at most one rupee before cess**. ✅ **Corrected while building it (slice 1.3, done):** the criterion used to say *at most one rupee*, full stop. That is only true pre-cess — the law applies relief to tax+surcharge and levies the 4% cess on the relieved total, so the figure a person actually pays rises by **₹1.04**. Measured: the pre-cess difference is **exactly ₹1.0000** at all four thresholds in both regimes. Plus the capital-gains cap, which is a **separate rule**: gains under 111A/112A/112 carry surcharge at no more than **15%** however high income goes, so someone with ₹6cr of salary pays 37% on the salary tax and 15% on the gains tax — conflating them overstates a redemption by a fifth of its bill |
| **1.4** | **The cost badge, all four numbers** — saving, exit load, tax as a *deferral*, breakeven against the horizon | badge fits **34 characters**; every figure passes `check_all` against **the payload that produced it** (`source: object` — §3.2 later standardises that payload); the tax term reads as a deferral, asserted as a string. **This makes slice 1.4 `grounding.py`'s first caller**, which is the gap §9.1 records and slice 3.1 was priced to close |

⚠️ **The on-ramp is real work and is not in this slice.** Measured off the
components: `AddHoldingDialog` is three fields and a submit, `AddTransactionDialog`
four — **≈4.6 interactions per fund, so 23 for five funds.** What closes it is
**CAS import** (`casparser`, still not installed) and **a SIP entered as a rule
that expands to lots**. The empty-state screen §3.0 argues for already exists:
`StartHere.tsx` leads with the two-field tax question instead of the afternoon-long
import, for the same reason §3.0 gives.

---

## Slice 2 — the universe, and the cost data

The largest slice and the one carrying the most open items. **2.1 closes four of
them at once** — they are one problem wearing four hats: a number measured
against a population this repo did not keep.

| | what | acceptance |
|---|---|---|
| **2.1** | **Groww universe ingestion → `groww_universe.json`.** The pull **must include the `st_filter` listing, not only scheme detail** — that is where the `index` boolean lives (0 of 39 cached scheme payloads carry it), so without it `is_passive` stays a one-signal design wearing two. Screener filters to the **union of buyable and held** | **not "it ingested" but "it re-prints §2's four figures"** — 1,686 buyable, 94.2% TER agreement, 86 of 123 Large Cap passive, 0 of 913 debt holdings rated — with **the raw pull retained**, and any figure that moved corrected in the document. None of the four is reproducible today |
| **2.1b** | **Settle the cost claim while the pull is open.** `historic_fund_expense` is one request per fund and gives eleven years of daily TER (PPFAS: 1,166 rows, 12.8 years). Re-run §1.1's measurement ranking each decision date on **the TER filed that date**, within category | §1.1 states the contemporaneous figure, or states that it is smaller than the published one. **The current +2.1pp carries an advantage it did not earn** |
| **2.2** | **NAV backfill.** The figure *"101 codes"* could not be reproduced: measured against `fund_catalogue.json` (4,957) only **18** lack any row in `nav_history` (4,939). 101 must have been counted against the buyable universe, which is one of the four unretained figures — **so this step's size is unknown, not one session** | after the run, held codes with no local NAV is **0**, and the run prints the starting count. Failures write `nav_source.last_error` and are **counted in the report** — 5 rows carry one today |
| **2.3** | **Holdings store, look-through, overlap.** `.holdings/` is gitignored, so git is not its backup — this step also writes the monthly `sqlite3 .dump \| gzip` into `data/holdings-dumps/` | **delete `.holdings/`, restore from the newest committed dump, get the same store.** And the sizing: the 39 payloads behind *78.3 holdings/fund* are **all equity**, so pull debt funds too and re-print. Across 1,686 the honest range is **48,894 – 428,244 rows**, and the plan states one number inside it |
| **2.4** | **NSE bhavcopy and corporate actions** | `trim_nav_store.py` must **EXCLUDE** `stock_daily` and `corporate_actions` from the published copy — it calls `con.backup()`, a whole-file snapshot, then one `DELETE FROM nav_history`. ⚠️ `stock_daily` **does not exist yet** — the *"~9.3M rows"* §16 states in the present tense is an estimate, and slice 2.4's *"within sight of 23.9 MB"* rests on it |

---

## Slice 3 — the AI layer

| | what | acceptance |
|---|---|---|
| **3.1** | **Wire `grounding.py`.** The module is 792 lines with 50 tests and, until slice 1.4, **zero non-test callers** — a guard with nothing behind it. ✅ **`switch_badge.py` is now the first**, and its suite includes the failing-guard proof below: a tenfold overstatement of the saving is fabricated into the detail text and `check_all` rejects it. What remains is the *rest* of the surfaces | **no narration reaches any surface without `check_all`** — proven by removing the check in a test and asserting a fabricated figure *does* reach the screen. A guard has to be shown failing |
| **3.2** | **The 18 tool functions and their JSON contracts.** None exists; roughly eight wrap existing engines and four are new. **`POST /advisor/tax-saving` and `GET /research/evidence` get response models first** — they are two of the four already-served tools and both are untyped, and a tool with no declared shape cannot be grounded or cached. Of 50 routes, **40 declare a `response_model` and 10 do not** ✅ both prerequisites done | every tool declares a JSON schema **before** its implementation, and a tool whose output does not validate against its own schema **fails the suite**; `check_all` rejects a figure absent from the payload it claims to come from, **proven by removing the figure**; the cache key hashes the contract |
| **3.3** | **A Gemini client.** There is none — `services/llm/client.py` is **exactly 26 lines of Groq**, and `Settings` declares only `groq_api_key` while `GEMINI_API_KEY` sits unread in `.env` | a **forced 429** is retried using the API's own `retryDelay`; when retries are exhausted the surface falls back to template narration **with the app still correct** |
| **3.4** | **`/ask`, the refusal set, the adversarial suite** | **every refusal in §5 has a test that the answer is refused.** A refusal set with no test is a paragraph |

**The claims decision:** the model returns `(value, entity_name)` pairs and **the
backend resolves them to paths**. Asking the model to emit `holdings.0.weight_pct`
is asking it to index into a list — the exact task FinSheet-Bench measures at 19.6%.

---

## Slice 4 — the screens

🔴 **Re-price this slice before starting it.** Every step was measured against
the file it lands on:

```
4.1  navigation      nav exists but is a HORIZONTAL TOP NAV, not a sidebar
                     deep links work · back works · ABSENT: the trail, and ⌘K
4.2  Find            category-first, per-fund reasons, facets, sorting, coverage all ship
                     ABSENT: overlap-at-choosing, compare tray
                     DISPUTED: virtualisation — Screener.tsx already paginates at
                     PAGE_SIZE = 100, with a comment naming the exact failure it
                     prevents ("1,689 rows across 21 columns is forty thousand
                     nodes… the accessibility walk times out")
4.3  Today and Why   Today is a rewrite of Portfolio.tsx; Why is a NEW page whose
                     content is currently scattered across Decide, Screener, Research.
                     Two different jobs, priced as one step
4.4  the devices     zero of eight exist — the only step nothing already-built shrinks
```

**The map you need, which the plan did not have until pass 99:**

```
plan surface   route                     page file          lines
Today          / -> /portfolio           Portfolio.tsx        358
Holdings       /portfolio                Portfolio.tsx        358   ← same file
Find           /screener                 Screener.tsx       2,012
Why            —                         does not exist
Ask            —                         does not exist

routed, and named nowhere in the plan until pass 105:
  /screener/stock/:ticker  StockAnalysis.tsx  611   shows the stock verdict §3.5 argues about
  /profile                 Profile.tsx        208   where §14's tax-regime lever must live
  /goals                   Goals.tsx          210
  /goals/new               GoalNew.tsx        202   part of the 23-step on-ramp
  /login                   Login.tsx          136   the first screen, and the cold start
```

**Build order: 4.4 first**, because nothing already-built shrinks it and §3.2
puts a sparkline in every `Find` row — everything after it draws on the devices.

| | what | acceptance |
|---|---|---|
| **4.4** | **§13.6's eight devices** — dot grid, bullet, underwater, slope, fan, **rebased line, sorted stacked bar, sparkline**. The step used to say five; the count is eight, and `lib/chart.ts` gives real groundwork (UTC dates, axis ticks, padded domains, tooltip style) but **no rebasing function** | each device renders its **empty and loading** states, not a blank box — §13.5's ten states exist because those two were missing entirely. And **`AllocationPie.tsx` is deleted, not deprecated**: it is a shipped recharts donut on `GoalDetail`, §13.6 says never a pie, and leaving it means allocation is shown two ways on two screens |
| **4.2** | **`Find`'s two genuinely absent features** — overlap-at-the-moment-of-choosing, and the compare tray. Everything else in §3.3 ships: category-first (52 references), a stated reason per fund (26), facets (36), sorting (70), coverage including `unscorable` (51) | opening a fund shows **what share of it he already owns**, and shows **`n/a` when unmeasured, never `0%`** — §14, because 0% reads as perfectly diversified, the opposite of "we could not tell". ⚠️ **Do not add virtualisation without deciding it first** (decision 4 below): `Screener.tsx` paginates at `PAGE_SIZE = 100` with a comment naming the exact failure it prevents, so the acceptance *"1,686 rows scroll without dropping frames"* describes a design this repo already rejected on measured grounds |
| **4.1** | **The trail and `⌘K`.** Navigation, deep links and back already work — the nav is a **horizontal top bar**, not the sidebar §15 specifies, and it `overflow-x-auto` scrolls rather than hiding, which honours §15's *"a hidden nav is the opposite of the ask"* by a different means | from a company page reached through a fund, **the trail names both hops** and each is clickable; `⌘K` reaches every one of the six real destinations. **Deep links already resolve on a cold load** — assert it rather than build it |
| **4.3** | **`Today`, and `Why` as a new page.** These are two different jobs: `Today` is a rewrite of `Portfolio.tsx`, `Why` does not exist and its content is currently scattered across `Decide`, `Screener` and `Research` | **every figure on `Today` appears in `Why` with its source named** — §14's coverage rule applied to the app's own front page. And **the three honesty states survive the rewrite**: a `misnamed_as` holding still says so, a stale price still says *"This value is not current"*, and a `price_error` holding is still excluded from returns by name |

⚠️ **4.3 is priced as one step and is two.** Splitting `Portfolio.tsx` into
`Today` and `Holdings` is decision 2 below; building `Why` is new work. Do not
start 4.3 before that decision lands.

**Delete `AllocationPie.tsx`.** It is a shipped recharts donut on `GoalDetail`,
§13.6 says never a pie, and leaving it means allocation is shown two ways on two
screens.

---

## What must not be lost

A redesign is the most reliable way to throw away things learned expensively.
§14's rules are enforced **24 times** in `backend/app/schemas/` — verified line by
line, all six citations exact:

```
app/schemas/portfolio.py:262   # and the UI must not render it as zero.
app/schemas/portfolio.py:287   # Funds left out, by name, with the reason. Never dropped silently.
app/schemas/research.py:226   # …a screen that hides its own coverage is lying by omission.
app/schemas/portfolio.py:102   unpriced_invested: float
app/schemas/portfolio.py:64   price_as_of: date | None = None
app/schemas/portfolio.py:89   stale: dict[str, str] = {}
```

**And three honesty states `Portfolio.tsx` carries that no section mentions.** A
rewrite written from §3.1 alone would drop all three:

- **`misnamed_as`** — the holding that names one fund and analyses another
- **`stale_days`** — *"Priced from a NAV of …, which is N days behind your other funds. This value is not current."*
- **`price_error`** — *"Live price unavailable, so this is left out of the returns"*

**And the disagreement that must stay one.** `scripts/consistency.py` carries a
section saying so: Research ranks on **cost**, the screener ranks on **trailing
record**, and the same fund can be first on one and twenty-second on the other.
**Nobody should ever "fix" that.** Only the *set* of funds must agree.

---

## What verifies this

2,319 lines of harness already exist. `check.sh` runs eleven checks.

- **`validate_nav_integrity.py`** (729) — refetches a sample from `mfapi` and holds the store against it, **necessary because inserts are `ON CONFLICT DO NOTHING`** so nothing else could notice a restatement; **recomputes** fund scores from the store against the run's own recorded inputs; checks the newest run agrees with itself
- **`consistency.py`** (470) — one fund score across three surfaces; a rank that must not renumber under a filter; a chart against the total printed above it
- **`isolation.py`** (216) — a stranger holding a valid session, checked against the owner's objects **in both directions**, and it separates *"could not test this"* from *"this leaked"*
- **`edge_cases.py`** (271) — a one rupee target, ₹50 crore, already-saved-more-than-the-target, a negative return
- **`a11y.mjs`, `mobile.mjs`, `sweep.mjs` (seeded and `--empty`), `shots.mjs`**

**Frontend has no unit-test layer at all** — no `vitest`, no `jest`, no
`.test.tsx`, and `package.json` has four scripts: `dev`, `build`, `lint`,
`preview`. So slice 4's component criteria have no runner. **Either add one in
slice 0, or write every slice-4 criterion as something the four Playwright
harnesses already check.** The second costs nothing and is the honest default.

---

## Decisions this needs from Manan

Seven, and none of them blocks starting.

1. **Does `Decide.tsx` become `Today`, or go?** 428 lines, routed, rendering levers and holdings, neither renamed nor retired anywhere.
2. **`Today` and `Holdings` are one file.** Splitting `Portfolio.tsx` in two is a product decision; nothing says which keeps `/portfolio`.
3. **The goal flow** — `/goals`, `/goals/new`, `/goals/:id`, 1,115 lines, 757 records, and the PRD's own centre — has **no surface in §3**. Deliberately unchanged in Phase 1, or priced? Either is defensible; silence is not.
4. **Virtualisation, or not.** Installing `@tanstack/react-virtual` and `react-table` and rewriting the one view that already works, to reach an acceptance criterion describing a design this repo rejected on measured grounds.
5. **The risk questionnaire averages ability with willingness**, and the PRD specifies it. `[10,9,2,1]`, `[1,3,8,10]` and `[6,6,6,6]` all score 6 — the household least able to hold through a fall is handed the same equity as the one most able. **Ability is a ceiling, not a term in a mean.** Fixing it departs from the PRD.
6. **The rebalancer's 5pp absolute band** is specified in the PRD and built line for line — a 5% gold sleeve must **double** to trigger, while the same 5pp is an 8% relative move on a 60% equity sleeve. Fixing it is a specification change.
7. **How many people use this.** It moves three dates, not one decision: §8.1 does not turn on it and §8.2 explicitly retires client count as the mechanism — *"Single-user is not a property of this app; it is a property of the login screen."*

---

## How to know it is done

Not "it builds". Each slice has a criterion that can fail, and the ones worth
repeating:

- **A real holding renders a badge whose four figures each pass `check_all`.**
- **Deleting `.holdings/` and restoring from the committed dump gives the same store.**
- **Zero live fund houses have zero TER coverage.**
- **Tax on one rupee above each threshold exceeds tax below by at most one rupee.**
- **A fabricated figure, injected in a test, does *not* reach the screen.**
- **Research and the screener cover the same funds while ranking them differently.**

⚠️ **"Session" is defined nowhere and carries every estimate here.** Against this
repo's own history — 158 commits, 20 active days, 49 endpoints, 92 schemas, 7
migrations, 1,624 tests, a 5.2M-row NAV store — the slice headers sum to **34
sessions**, which was priced against a greenfield reading of a codebase that
turned out not to be greenfield. **Slice 1 is the measurement that re-prices
everything after it.** Treat the numbers as an ordering, not a schedule.
