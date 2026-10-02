# NexTrade — development plan

The task list for the next stretch of work, written so each task can be picked up
cold. Read `CONTRIBUTING.md` first (setup, checks, rules, known traps).

**How to use it:** take tasks in order unless told otherwise. One task = one
branch = one PR. Every task lists **Done when** — the PR is reviewed against
exactly that list, so read it before writing code, not after.

Sizes: **S** ≈ half a day to a day · **M** ≈ one to three days.

---

## Where things stand (2 Oct 2026)

Shipped and on `main`:

- **Portfolio** page — value, XIRR, benchmark, levers, cost review, look-through
  ("what you actually own"), fund overlap, filings.
- **Holdings** page — sortable table, weight per holding, expandable row with
  every transaction, two-step delete, and "Where your money is" (asset class +
  category, bar ⇄ donut).
- **Landing** page, 404 page, Research / Why / Decide / Screener / Goals / You.
- `services/portfolio/asset_class.py` — places each holding in equity /
  international / debt / gold / hybrid from its AMFI category.

Known problems these tasks fix:

- Fund prices come from mfapi.in, which can lag AMFI by days (seen: 4 days). → **T2**
- Fixing a wrong transaction means deleting the whole holding. → **T5**

---

## Order

| # | Task | Size | Why this position |
|---|---|---|---|
| T1 | Decide page: honest "equity" wording | S | Warm-up: learn the codebase and the checks on a tiny change |
| T2 | Live fund prices from AMFI | M | Every number on every page depends on today's price |
| T3 | Portfolio insights strip on Holdings | M | The "understand my whole portfolio at a glance" ask |
| T4 | Tax view per holding | M | Real money; almost no app shows it clearly |
| T5 | Edit / delete one transaction | M | Basic functionality that is missing |
| T6 | Tags on each holding row | S | Points at the row that needs attention |
| T7 | SIP detector + missed-SIP flag | S | Know your SIPs are actually running |
| T8 | Sector split + concentration | M | Hidden bets made visible |
| T9 | Each fund vs its own index | M | The only fair performance check |
| T10 | "Explain" a holding (AI) | M | Plain-language understanding, kept cheap |

---

## T1 — Decide page: honest "equity" wording · S

**Why.** The Decide page says *"You are about N% in equity"*. That figure comes
from `services/advisor/asset_mix.py`, which deliberately counts **gold and
overseas funds as equity** (its question is "how much can fall a long way").
The Holdings page now shows gold and international separately, so the two pages
disagree on the same portfolio.

**Build.** Change the sentence so it says what the number measures, e.g.
*"About N% of your money is in things that can fall a long way — equity, plus
gold and overseas funds."* Do **not** change the calculation.

**Where.** `backend/app/services/advisor/levers.py` (the `detail=` text of the
`equity_share` lever, ~line 696). No test pins this sentence today — **add one**
that asserts the new wording names gold and overseas funds.

**Done when**
- [ ] The sentence names what is included (gold, overseas), and a test pins it.
- [ ] The number is unchanged for the same portfolio.
- [ ] All backend tests pass; screenshot of the Decide page attached.

---

## T2 — Live fund prices from AMFI · M

**Why.** `marketdata/mutual_fund.get_latest_nav()` takes the last row of
mfapi.in's history. mfapi mirrors AMFI but has lagged it by up to 4 days. Every
portfolio value, gain and XIRR inherits the lag — and no warning fires, because
the staleness check compares funds with *each other*, and they all lag equally.

**Build.** Today's NAV comes from **AMFI's own file**
(`https://portal.amfiindia.com/spages/NAVAll.txt` — public, no key, ~1.5 MB,
one row per scheme with its latest NAV and date). History (charts, XIRR cash
flows) stays on mfapi.

- Reuse `services/screener/amfi.py`: `fetch_navall()` (already cached) and
  `parse_navall()` → `list[NavRow(code, nav_date, nav)]`.
- Build a `{code: NavRow}` map **once per day**, not per holding.
- `get_latest_nav(code)`: use AMFI's row when it is **newer** than mfapi's last
  point; otherwise mfapi's. If AMFI is unreachable or the code is missing, fall
  back to mfapi silently (log a warning).

**Where.** `backend/app/services/marketdata/mutual_fund.py` (or a small new
`marketdata/amfi_latest.py` it calls), tests in `backend/tests/`.

**Done when**
- [ ] With AMFI newer than mfapi, `get_latest_nav` returns AMFI's NAV and date.
- [ ] With AMFI older, equal, unreachable, or missing the code → mfapi's.
- [ ] The NAVAll file is fetched at most once per day per process, not per holding.
- [ ] Tests use fixture text — **no network**. Include a fixture row for a
      regular plan and one with `N.A.` as the NAV.
- [ ] Holdings page header ("Fund NAVs as of …") shows the AMFI date — screenshot.

**Watch out.** `parse_navall` validates the whole file (header, row counts) and
raises `AmfiFeedError` on a malformed one — treat that as "unreachable", don't
let it 500 the portfolio page.

---

## T3 — Portfolio insights strip on Holdings · M

**Why.** The owner wants to understand the whole portfolio at a glance. The facts
exist across five panels; nothing puts the important ones in one place.

**Build.** A backend endpoint returning a short list of plain-sentence insights,
each **computed by rules from numbers the app already has** (no AI):

| Insight | Source | Example |
|---|---|---|
| Asset mix | `asset_class` on each holding | "75% equity, 14% debt, 7% gold, 4% international" |
| Commission drag | cost review (`FlaggedHoldingOut.annual_cost`) | "2 regular plans cost you ₹4,328 a year" |
| Same position twice | overlap pairs, correlation ≥ 0.90 | "Mirae Large & Midcap and HDFC Mid Cap move as one (0.96)" |
| Hidden repeats | look-through, `via` length > 1 | "31 companies reach you through 2+ funds" |
| Concentration | holding weights | "Your largest holding is 20% of the portfolio" |
| Unread money | `asset_class == "other"` | "₹X could not be classified" |

Each item: `{kind, tone: "info" | "attention", text, value, link}`. Return only
items that apply; order "attention" first. Frontend: a strip of compact cards
above "Where your money is" on Holdings.

**Where.** New `backend/app/services/portfolio/insights.py` (pure functions —
pass in the already-computed pieces), a route in `routers/portfolio.py`
(`GET /api/v1/portfolio/insights`), a schema, and a component in
`frontend/src/components/`.

**Done when**
- [ ] Every insight has a unit test with a hand-built input, including the
      "does not apply → not returned" case.
- [ ] The route is in `_HEAVY_PATHS` (it reuses heavy computations).
- [ ] Each number in each sentence matches the panel it came from (check on the
      demo account; note the values in the PR).
- [ ] Screenshots light / dark / phone.

**Watch out.** Call the service functions directly; don't make the backend call
its own HTTP endpoints.

---

## T4 — Tax view per holding · M

**Why.** Selling at the wrong time costs real money, and the rules depend on
what the fund holds and when each unit was bought. The app already tracks every
purchase lot (`services/portfolio/fifo.py`, `Lot.buy_date`).

**Build.** A pure module `services/portfolio/tax_lots.py` that, for one holding's
open lots and today's price, returns:

- unrealised gain split into **long-term** and **short-term**;
- for short-term lots: the **next date** a lot turns long-term and the gain that
  becomes long-term on that date ("₹40,210 turns long-term in 23 days");
- ELSS only: each lot's **lock-in end** (3 years from its buy date) and units
  still locked.

Plus, portfolio-wide: **long-term gain realised this financial year** (1 Apr –
31 Mar) against the ₹1.25 lakh yearly exemption — used and remaining.

Rules (Finance Act 2024; put them in **one** constants table with a source
comment):

| Kind (from `asset_class`) | Long-term after | Notes |
|---|---|---|
| Equity funds, stocks | 12 months | LTCG 12.5% above ₹1.25L/yr; STCG 20% |
| Debt funds bought on/after 1 Apr 2023 | never | taxed at slab at any holding period |
| Debt funds bought before 1 Apr 2023 | 24 months | 12.5% |
| Gold ETF (listed) | 12 months | 12.5% |
| Gold fund of funds, international funds | 24 months | 12.5% |
| Hybrid | depends on equity share | **ask before building** — out of scope for v1, show "not computed" |

Frontend: in the expanded holding row, a small "Tax" block; on the Holdings
header, the ₹1.25L used / remaining.

**Done when**
- [ ] Boundary tests: a lot bought exactly 12 months ago, one day short, one
      day over; a debt lot on 31 Mar 2023 vs 1 Apr 2023; an ELSS lot unlocking
      today.
- [ ] Financial-year boundary test (gain realised 31 Mar vs 1 Apr).
- [ ] Hybrid shows "not computed", never a guess.
- [ ] Screenshot of an expanded row with mixed long/short lots.

**Watch out.** "12 months" means calendar months (use the existing
`_months_after` in `fifo.py`), not 365 days. No buy/sell advice in the copy:
"turns long-term on 14 Oct" is a fact; "wait before selling" is advice.

---

## T5 — Edit / delete one transaction · M

**Why.** A typo in one purchase can only be fixed by deleting the whole holding
and re-entering every transaction.

**Build.**
- `PATCH /api/v1/portfolio/holdings/{holding_id}/transactions/{txn_id}` and
  `DELETE` of the same path.
- Ownership: the holding must belong to the caller; a transaction on someone
  else's holding → **404** (not 403 — don't confirm it exists).
- Re-validate the **whole** ledger after the change with `apply_fifo` (as
  `add_transaction` already does): editing or deleting a buy must not leave a
  later sell selling units that no longer exist → **400** with the reason.
- `amount` is recomputed server-side (`units * price`), never taken from the client.
- Frontend: edit and delete buttons per row in the expanded holding's
  transaction table; delete asks to confirm; on success invalidate every key in
  `PORTFOLIO_QUERY_KEYS`.

**Done when**
- [ ] Tests: edit OK; delete OK; other user's transaction → 404; delete a buy
      that a later sell depends on → 400 and nothing changed; amount ignored
      from client.
- [ ] Holdings value, XIRR and the Portfolio page update after an edit without
      a page reload.
- [ ] Screenshots of the edit dialog and the delete confirm.

---

## T6 — Tags on each holding row · S

**Why.** The table shows numbers but not which row needs attention.

**Build.** At most **one tag** per row, plus "+N" if more apply:

| Tag | Fires when | Data |
|---|---|---|
| `Direct saves ₹3,056/yr` | regular plan with a known direct twin | cost review |
| `Same as HDFC Mid Cap (0.96)` | overlap correlation ≥ 0.90 | overlap pairs (match by scheme code) |
| `Too new to rank` | under 1 year of NAV history | NAV history length |

Priority when several apply: the one with a rupee value first.

**Where.** The cost review's `FlaggedHoldingOut` has `name` but no
`holding_id` — **add `holding_id`** so the frontend doesn't match on names.
Frontend: `pages/Holdings.tsx`.

**Done when**
- [ ] Each tag shows on the demo account where expected (list which rows in the PR).
- [ ] A row with nothing to say shows **no** tag (no "Fine" / "OK" label).
- [ ] The Gain column stays visible (owner's decision).

---

## T7 — SIP detector + missed-SIP flag · S

**Why.** The owner should see which SIPs are running and notice a missed one.

**Build.** Pure function in `services/portfolio/` that looks at one holding's
buys and decides: SIP or not; amount; usual day of month; last instalment;
**missed** if the expected date plus 7 days has passed with no buy.

A SIP = at least 3 buys in consecutive calendar months, amounts within ±10% of
their median, on days of month within ±5 of each other.

Show it in the row ("SIP ₹10,000 · ~5th") and a missed one as an attention
item (and in T3's strip if T3 has landed).

**Done when**
- [ ] Tests: steady SIP; lump sums only (not a SIP); SIP with one skipped month
      (missed); amount stepped up 10% mid-way (still a SIP); two buys only (not
      a SIP).
- [ ] Demo account: correct detection noted in the PR.

---

## T8 — Sector split + concentration · M

**Why.** Five funds can be one big bet on banks. The look-through already knows
every company and its industry.

**Build.**
- Sector split: group the look-through companies by `industry`, sum
  `share_pct`, show the top 8 + "Other". Show the coverage line
  ("read from 64% of your money") — never present it as complete.
- Concentration: largest holding %, top-3 holdings %, and the largest
  **company** exposure combining funds **and directly held stocks** (HDFC Bank
  held directly + through three funds = one number). The look-through today only
  opens funds — match direct stocks to it by company name/ISIN.

**Done when**
- [ ] Combined company exposure tested with a stock held both directly and via a fund.
- [ ] Coverage shown wherever the sector split is shown.
- [ ] Chart goes through `ChartFrame`; colours written out in full (CONTRIBUTING §5).

---

## T9 — Each fund vs its own index · M

**Why.** Judging a small-cap fund against the Nifty 50 says nothing about the
fund. The fair comparison is its own category index.

**Build.**
- Index history from **niftyindices.com** total-return series (public, no key):
  `POST https://www.niftyindices.com/BackPage/getTotalReturnIndexString` with
  JSON body `{"cinfo": "<json string of {name, startDate, endDate, indexName}>"}`,
  dates as `dd-Mon-yyyy`. Needs a browser `User-Agent`, `Referer`
  `https://www.niftyindices.com/reports/historical-data`, and a plain `GET` of
  the home page first (sets cookies). Fetch in yearly chunks. **The old
  `/Backpage.aspx/...` path now redirects to a login page — don't use it.**
- A table mapping AMFI sub-category → index (Large Cap → NIFTY 100, Mid Cap →
  NIFTY MIDCAP 150, Small Cap → NIFTY SMALLCAP 250, Flexi / Multi / Focused /
  ELSS → NIFTY 500, Large & Mid → NIFTY LARGEMIDCAP 250; index funds → the index
  in their name). Debt, gold, international, hybrid → **no comparison** (say so).
- Per holding: replay the holding's own cash flows into the index with the
  existing `services/portfolio/benchmark.compare_to_benchmark()` — it already
  accepts any price series.
- Cache index series on disk, refreshed daily.

**Done when**
- [ ] Mapping table tested; unknown categories return "no comparison", never
      the Nifty 50 by default.
- [ ] Fetcher tested with fixture JSON — no network in tests.
- [ ] Shown in the expanded row: "+2.1 pp a year vs Nifty Smallcap 250".

---

## T10 — "Explain" a holding (AI) · M

**Why.** Plain-language understanding of one holding's numbers. AI use is kept
low on purpose (cost).

**Build.**
- Backend builds a **fact sheet** for one holding from existing numbers (value,
  invested, gains, XIRR, tax view from T4, tags from T6, benchmark from T9 if
  present) and asks the model for 2–3 plain sentences using
  `services/llm/gemini.generate()` (returns `None` when no key — handle it).
- **Number check:** every number in the answer must appear in the fact sheet
  (normalise ₹, commas, %). Any unknown number → discard the answer and return
  a rule-written fallback.
- Run the question through the existing refusal gate
  (`services/llm/refusals.refusal_for`) — no buy/sell advice, no predictions.
- Cache one explanation per holding per day.
- Frontend: an "Explain" button in the expanded row.

**Done when**
- [ ] Tests with a mocked model: clean answer passes; answer with an invented
      number falls back; no key → fallback; advice-shaped answer → fallback.
- [ ] No test makes a real model call (`tests/conftest.py` blanks the keys —
      don't undo that).
- [ ] At most one model call per holding per day (show how in the PR).

---

## Not for this list (owner / lead only)

- Scoring parity with the reference implementation (needs the reference
  checkout, which only the owner's machine has).
- Anything touching deployment, secrets, or the nightly job.
