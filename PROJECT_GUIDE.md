# NexTrade (`traa`): the complete project guide

**Written:** 2026-10-02 · **Covers:** every commit up to `a20b1d4` (2026-09-26) · **Branch:** `free-deploy-groww-universe`

This guide explains the whole project: what it is, why it exists, what has been
built, how the parts fit, what every folder holds, how to run it, and what is
still open. **Part II** records every piece of research in depth: what was
measured, how, the exact numbers, and what went wrong along the way. **Part
III** explains how the work is done. You can read it with no background. It is
also detailed enough for an engineer to start working from it.

> **How to read this**
>
> - **New to the project, or not technical?** Read §1–§5, then the glossary (§21).
>   That covers what the product is, what it believes, and what each screen does.
>   Then §22 (the research vocabulary) and §47 (worked examples in rupees).
> - **An engineer about to work on it?** Read §1, §3, then §6–§19 in order. §17
>   (working rules) and §18 (traps) will save you days. Then Part III (§39–§46).
> - **A researcher or reviewer?** Part II (§22–§38). Every study is written up
>   with its question, method, controls, results, caveats and the mistakes caught.
> - **An AI agent picking this up?** Read all of it. Then read `docs/BUILD.md` and
>   the newest 20 commits (`git log -20`) before trusting any document, this one
>   included. §17 and §40 explain why.
>
> **One warning.** This repo has a long, recorded habit of documents going stale
> while the code moves on. Every count in this guide carries the date it was
> measured and, where possible, the command that re-measures it. **If a number
> here disagrees with the repo, the repo wins.**

---

## Contents

1. [The 30-second version](#1-the-30-second-version)
2. [Who it is for, and the ground rules](#2-who-it-is-for-and-the-ground-rules)
3. [The big idea: what the research proved](#3-the-big-idea-what-the-research-proved)
4. [The story so far (timeline)](#4-the-story-so-far-timeline)
5. [What the app does, screen by screen](#5-what-the-app-does-screen-by-screen)
6. [How it is built (architecture)](#6-how-it-is-built-architecture)
7. [Folder-by-folder tour](#7-folder-by-folder-tour)
8. [Where every number comes from (data sources)](#8-where-every-number-comes-from-data-sources)
9. [The databases and caches](#9-the-databases-and-caches)
10. [The engines: how the important calculations work](#10-the-engines-how-the-important-calculations-work)
11. [The AI layer](#11-the-ai-layer)
12. [Security](#12-security)
13. [Testing and the quality gate](#13-testing-and-the-quality-gate)
14. [How to run it on your machine](#14-how-to-run-it-on-your-machine)
15. [Deployment: planned, not done](#15-deployment-planned-not-done)
16. [Status: what is done, what is next, what is open](#16-status-what-is-done-what-is-next-what-is-open)
17. [How we work here (rules and habits)](#17-how-we-work-here-rules-and-habits)
18. [Traps that have already cost time](#18-traps-that-have-already-cost-time)
19. [Which document answers which question](#19-which-document-answers-which-question)
20. [FAQ for a new helper](#20-faq-for-a-new-helper)
21. [Glossary](#21-glossary)

**Part II: the research, in depth**

22. [How to read the research, and the scoreboard of everything measured](#22-how-to-read-the-research-and-the-scoreboard-of-everything-measured)
23. [Can anyone pick the better fund? Measured five ways](#23-can-anyone-pick-the-better-fund-measured-five-ways)
24. [When to leave a fund: the exit-signal study](#24-when-to-leave-a-fund-the-exit-signal-study)
25. [Base rates: holding period decides the outcome](#25-base-rates-holding-period-decides-the-outcome)
26. [Stocks: the stock score, factors, and 32 years of Indian data](#26-stocks-the-stock-score-factors-and-32-years-of-indian-data)
27. [Overlap and look-through: what you really own](#27-overlap-and-look-through-what-you-really-own)
28. [Data investigations: what each source really contains](#28-data-investigations-what-each-source-really-contains)
29. [The Bachatt teardown](#29-the-bachatt-teardown)
30. [Competitor research](#30-competitor-research)
31. [The outside evidence base, graded](#31-the-outside-evidence-base-graded)
32. [Behaviour and decision clarity](#32-behaviour-and-decision-clarity)
33. [Advisor methodology and planning numbers (researched, partly built)](#33-advisor-methodology-and-planning-numbers-researched-partly-built)
34. [Tax research](#34-tax-research)
35. [Regulation research](#35-regulation-research)
36. [AI research](#36-ai-research)
37. [Design research](#37-design-research)
38. [Research inventory, open questions, and where the sources disagree](#38-research-inventory-open-questions-and-where-the-sources-disagree)

**Part III: how we work**

39. [The loop: from a sentence in Hinglish to a shipped, checked number](#39-the-loop-from-a-sentence-in-hinglish-to-a-shipped-checked-number)
40. [Adversarial review: the method behind 152 review passes](#40-adversarial-review-the-method-behind-152-review-passes)
41. [Build discipline](#41-build-discipline)
42. [Verification culture and the 24 rules of measurement](#42-verification-culture-and-the-24-rules-of-measurement)
43. [How we write: commits, comments, documents, memory](#43-how-we-write-commits-comments-documents-memory)
44. [How decisions with Manan are made and recorded](#44-how-decisions-with-manan-are-made-and-recorded)
45. [The tools we use, and the ones that failed us](#45-the-tools-we-use-and-the-ones-that-failed-us)
46. [How much to trust each part of the app](#46-how-much-to-trust-each-part-of-the-app)
47. [Worked examples: what the app tells a real person, in rupees](#47-worked-examples-what-the-app-tells-a-real-person-in-rupees)

---

## 1. The 30-second version

**NexTrade** is a personal investing web app for India. The folder is called
`traa`. The GitHub repo is `Manan0802/trading-agent-`.

It answers one question: **"What should I actually do with my money, and how
much is each choice worth in rupees?"**

It does **not** buy or sell anything. Manan (the owner and only real user)
invests through **Groww** himself. NexTrade is the advisor beside that. It:

- tracks what he owns (mutual funds and stocks), with real returns (XIRR) and
  live prices;
- shows what he owns *underneath* his funds (look-through), and when two of his
  funds are really the same bet (overlap);
- ranks every decision by what it is worth in rupees: tax regime, direct vs
  regular plans, saving more, tax harvesting. Fund picking is on that list too,
  priced at **₹0**, because the research found it does not predict;
- screens the ~1,660 funds he can actually buy on Groww, and ~750 NSE stocks;
- plans goals (retirement, house, education): how much to invest monthly and
  where;
- explains itself in plain language, and keeps the arithmetic one click away.

**Stack:** Python **FastAPI** backend, **React + TypeScript + Vite** frontend,
**SQLite** databases. The data comes from free public sources: AMFI, mfapi.in,
Groww, NSE, yfinance and Screener.in.

**State on 2026-10-02:** working and feature-rich on Manan's Mac. **Not deployed
publicly yet.** 203 commits, 2,094 tests. The "Part B" trading agent in the
original plan has **not been started**, on purpose (see §2).

---

## 2. Who it is for, and the ground rules

These rules shape every decision in the code. If something in the repo looks
strange, one of these is usually the reason.

| Rule | What it means | Where it was decided |
|---|---|---|
| **Single user: Manan.** | The design rules are his to change. If he asks for something that breaks a written rule, point it out **once**, then do what he says and **update the rule and its test** so the code and the docs agree. | Agreed 2026-09-23 |
| **Advisory only.** | Nothing places an order, sizes a trade or times the market. The trading agent (Part B) is a later phase. | *"buss tumara goal advisory tak ka hai"*, 2026-08-27 |
| **Groww is where he invests.** | The fund universe is "funds buyable on Groww, plus anything he already holds". A fund he cannot buy is trivia, not advice. Do not "fix" this filter. | `docs/phase-1-redesign.md` §0 |
| **Bachatt is reference only.** | Bachatt is a separate company product (Manan works there). We may **read** its code at `~/BachattDev/sip-optimizer` for ideas and port documented formulas in our own code. We **never** call its systems (database, `investment.bachatt.app`, the `bachatt` MCP server) and never copy its files verbatim. | *"bachatt se humara kuch lena dena ni hai"* |
| **Copy Bachatt's fund and stock scoring until ours is proven.** | The Screener uses a faithful port of Bachatt's scoring. It is checked against their real source code. | 2026-09-23 |
| **Keep AI use low.** | Gemini is wired in. Use it only where it earns its place. Every number it writes is checked (§11). | 2026-09-23 |
| **Free and public data only.** | No paid APIs. Budget is about ₹0–800/month. | PRD / START_HERE |
| **Honesty over polish.** | "Not available" is never shown as `0`. Stale prices say they are stale. Coverage gaps are named on screen. Claims the app cannot back are refused. | `docs/phase-1-redesign.md` §14 |
| **No hosted "Artifacts".** | Deliverables go in chat or in files on disk (the repo's `docs/`, or the Obsidian vault). **Subagents must be told this explicitly.** | Manan, twice |

**Original non-negotiables from the PRD, still true:** money projections say
"projected", never "guaranteed". The money maths is deterministic and
unit-tested. If trading ever happens: paper money first, NSE cash segment only,
and a risk manager that nothing, including AI, can override.

---

## 3. The big idea: what the research proved

This is the most important section. The whole product was rebuilt around these
findings, and they override intuition, including the intuition of whoever wrote
the code.

### 3.1 Picking funds by their past returns does not work

The question: if you rank funds by their past 3-year return, do the top-ranked
ones beat the bottom-ranked ones over the **next** 3 years?

It was measured on real NAV history, using only information available at each
past date. The answer is no. Funds were compared against others in their own
category.

| Signal used to rank funds | Top quarter vs bottom quarter, next 3 years | Windows where top beat bottom | Rank IC (−1 to +1; 0 = useless) |
|---|---|---|---|
| Past 3-year return | 19.4% vs 20.2% (**worse** on top, −0.9pp) | 19 of 44 (43%) | −0.025 |
| **Cost (expense ratio, cheapest first)** | **20.6% vs 18.4% (+2.1pp)** | **36 of 44 (82%)** | **+0.195** |
| NAV level (₹10 "cheaper" than ₹1,000) | 20.1% vs 19.8% | ≈ chance | ≈ 0 |

Source: `backend/app/data/track_record.json`, measured 2026-08-22 by
`backend/scripts/why_not_returns.py`. The app publishes this scoreboard on its
own `/why` page, including the parts that make it look bad.

The same question was asked other ways too. Every answer pointed the same way:

- **Our own fund score** picked winners in 50% of 60 windows, a coin flip
  (`docs/does-the-score-work.md`).
- **Manan's own idea**, ranking on lifetime return since launch, scored 38%:
  worse than a coin (`scripts/validate_lifetime_ranking.py`).
- **Bachatt's ported score** did better, 68% over 235 category-years, but 3 of
  7 years were at or below chance. Two good years carried the average
  (`scripts/measure_score_edge.py`). Do not show the 68% without the
  year-by-year table.
- **Mixing past return with cost** halves cost's predictive power. Past return
  is not neutral information. It is noise, and it dilutes the signal.

**Caveat, stated honestly:** the cost result ranks funds on *today's* expense
ratio at past dates (a mild "lookahead"). Re-measured on the expense ratio filed
*at that time*, the effect survives but shrinks (+12.0pp → +3.6pp within
category, on a thin sample of 4–6 windows). The honest size is not known yet.
See `docs/BUILD.md` §0.3.

> **In one line:** `fund return = market + manager + luck − cost`. Only cost is
> knowable in advance.

### 3.2 What that means for the product

- The app's own fund ranking (on Research) weights **cost 55%, risk 25%,
  consistency 20%, past return 0%**. Past return is still **shown**, because it
  is a true fact, but it does not move a fund up the list.
- The **Levers** engine ranks money decisions by rupee value. For a typical user,
  tax regime, direct vs regular plan and saving more are worth lakhs. "Pick the
  best fund" appears on the list at **₹0**, on purpose. Leaving it off would
  hide the point.
- The **commission line**: every fund comes in a "regular" plan (with distributor
  commission) and a "direct" plan (no commission, same portfolio). The median
  difference is about 0.64 percentage points a year. NexTrade prices what a
  user's regular-plan holdings cost them over their horizon. A commission-paid
  distributor structurally cannot show this.

### 3.3 The one thing that does predict: momentum (for stocks)

Stocks that went up most over the past 12 months (skipping the latest month)
tend to keep outperforming over the next year. It was measured two ways:

- On our own NSE universe: +2.1% a year vs the universe, t = +2.99 (quarterly
  rebalance). Annual rebalance survives trading costs.
- On IIMA's 32-year, survivorship-adjusted Indian factor data: momentum (WML)
  +13.4%/yr, t = +3.11. Value (HML) +8.6%, t = +2.39. Size is **negative** in
  India (−2.8%).

**The catch:** momentum does **not** fail in crashes. It fails in **rebounds**.
In 2009 the market rose +91.6% and momentum lost −53.5%. The app shows that
risk **above** the momentum table, never below it. It is a return enhancer,
never a hedge.

Full record: `docs/do-factors-work-here.md`, `docs/what-actually-predicts-returns.md`.

### 3.4 Other findings that shaped the product

- **Selling is where people lose.** Professionals sell worse than at random. So
  the app refuses "sell your worst fund" advice (§11.3).
- **Holding period decides outcomes** far more than fund choice.
- **Look-through matters.** Two plausible funds can be 47% the same underlying
  holdings.
- **Attention features make people trade more, and trading loses money**
  (Barber & Odean; an FCA experiment found push notifications raised trading by
  11%). So: no news feed, no price alerts, no streaks. The only "news" is
  **exchange filings for companies you actually hold** (manager changes,
  promoter selling, audit issues).
- **99% clarity about the decision is achievable. 99% confidence in the outcome
  is not.** The product aims at the first.

---

## 4. The story so far (timeline)

All dates are 2026. The commit counts per day come from `git log`.

| When | What happened |
|---|---|
| **Jun 28–30** | Research and planning. The 2,330-line PRD (`NexTrade_PRD_v1.md`), an open-source survey (`docs/research/2026-06-28-oss-landscape.md`), a build spec, and a 12-task "Phase 1 Financial Advisor" plan. Committed Jun 30. |
| **Jul 5–6** | Backend and frontend scaffolds. The original Phase 1: SIP calculator, risk questionnaire, equity/debt/gold allocation matrix, 80C/80D tax tips, a rebalancing drift check, a Groq LLM explaining a goal in Hinglish, a Twilio WhatsApp sender, goal CRUD. |
| **Jul 8–12** | Login: Google OAuth (with PKCE fixes), then email/password as a fallback. |
| **Jul 17** | **The scope reset.** Manan rejected the calculator as *"not even 0.1 percent"* of a real advisor. New scope: live fund and stock data, real portfolio tracking with XIRR, named fund recommendations. |
| **Jul 20** | Portfolio models and API, mfapi.in fund data, yfinance stock data, XIRR and FIFO accounting, valuation, the first fund scoring engine, recommendations by name, "vs the index" comparison, the Portfolio and Research pages. |
| **Jul 21–22** | Three wrong-answer defects fixed: the tax regime (now computes both), per-goal inflation, and allocation across the whole balance sheet (EPF/PPF/FDs). A design language. All SEBI categories and the full NSE universe instead of 16 hand-picked funds. |
| **Jul 27** | **The pivot day (27 commits).** It was measured that fund selection does not predict and cost does. The product was rebuilt around that: one scoring model (old ones deleted), the Levers engine, the profile page, the regular-plan cost review, sector-relative stock scoring, a teardown of Bachatt's code. |
| **Jul 28–31** | Goal list and editing. Three verification harnesses (adversarial inputs, cross-view consistency, account isolation) plus page/mobile/accessibility sweeps. Real fund holdings from 7 AMCs' monthly spreadsheets. A "holding names one fund but analyses another" detector. Rate limiting, security headers, production startup guards. |
| **Aug 1** | Every screen given the "dashboard" treatment. Found that the verification scripts had been pointed at **other apps** on the same machine. Fixed. |
| **Aug 6** | Momentum measured (t = +3.11 over 32 years) and shipped as a screen. "Plain language first, arithmetic one click behind" became the default. |
| **Aug 8** | Found that `check.sh` **could never fail**. It was hiding three real failures. Fixed, and it now tests itself first. |
| **Aug 20–21** | **The Screener (35 commits).** A local store of every fund's NAV history (5M+ rows). A nightly scoring run. Bachatt's fund and stock scoring ported exactly and proved equal to their source. A basket optimiser. Detailed fund and stock pages. Base rates ("what this kind of fund has done to people before"). The `/decide` page. |
| **Aug 22–25** | The app's own scoreboard published. A deployment kit, then a **free, no-credit-card** deploy design (GitHub Actions + Render + Vercel + Turso). |
| **Aug 27–28** | **The Phase 1 redesign plan.** `docs/phase-1-redesign.md`, 6,608 lines, reviewed adversarially **148 times**. Discovered Groww's public data layer (buyable universe, full holdings, managers, 11 years of daily expense ratios). |
| **Aug 29** | **`docs/BUILD.md` and the whole build in one day (32 commits)**, slices 0 to 4 (§16.1). |
| **Aug 31 – Sep 16** | Fixes. The "Today" page renamed **Portfolio** and redesigned to "answer first, argument behind a fold". A real **landing page** (front door) instead of a bare login. |
| **Sep 23** | **Roadmap agreed with Manan** (§16.2). Holdings rebuilt: sortable table, weight per position, asset allocation with a **bar ⇄ donut toggle**. |
| **Sep 26** | Allocation charts fit their panels, and each slice gets its own colour. *(Latest commit.)* |
| **Oct 2** | Codex tool-arsenal files appeared (`.agents/`, `.codex/`, `AGENTS.md`). They are untracked and unrelated to the app's code. |

---

## 5. What the app does, screen by screen

Every page lives in `frontend/src/pages/`. The top navigation and the ⌘K
palette use one shared list (`NAV` in `App.tsx`), so they cannot drift apart.

| Route | Page file | What you see there |
|---|---|---|
| `/` | `Landing.tsx` | The **front door** for someone who has never heard of the app. It leads with what the app **cannot** do (pick winning funds), because that is the honest differentiator. Every figure on it is one `/why` also proves. Scroll-reveal motion. Signed-in users go to `/portfolio`. |
| `/login` | `Login.tsx` | Email and password, or Google. After login you land on the dashboard, not a form. |
| `/portfolio` | `Portfolio.tsx` | **"How am I doing"**, answer first. Total value, real return (XIRR), comparison with the same money in the index, the **one lever worth the most money** (with the ₹0 ones folded away), regular-plan cost review, overlap between your funds, look-through to companies, and filings for companies you hold. **Empty state:** `StartHere`, the three first steps ordered by what each is worth in rupees. The cheapest high-value step (the tax question) comes first. |
| `/portfolio/holdings` | `Holdings.tsx` | **The task page.** A sortable table of every position: units, cost, value, gain, weight, XIRR. Add a fund (picked from AMFI's list so the name and code cannot disagree) or a stock (typed NSE ticker). Add purchases and sales. Asset allocation (equity / overseas / debt / gold) as a sorted stacked bar **or** a donut, with a toggle. Honesty states: *misnamed* holding, *"this value is not current"*, *"live price unavailable, left out of returns"*. |
| `/research` | `Research.tsx` | **"What has been shown to work."** Fund categories ranked by **our own cost-weighted score**, with a verdict sentence per fund. Stocks scored against **sector medians**. The **momentum screen**, with its crash/rebound risk shown above the table. The 32-year factor evidence. |
| `/why` | `Why.tsx` | **Where every number on the front page comes from**, and how often the app's own claims have been right (the scoreboard in §3.1). |
| `/decide` | `Decide.tsx` | **What to do next, ranked by rupee value.** Sliders for monthly SIP and assumed return (the range comes from the server). Shows "certain" levers, "behaviour" levers, trades kept apart, and gates. Base-rate panel. *(Open question: should this page merge into Portfolio or go away? §16.4.)* |
| `/screener` | `Screener.tsx` | **"Find a fund."** The whole buyable universe scored nightly with **Bachatt's ported method**. Top 5 per category, a flat sortable list at `?view=all` (paginated, 100 per page, on purpose), coverage shown openly, a **compare tray** (2–3 funds side by side), a **Stocks** tab (Bachatt's stock scorer, with a note on what it includes), and a **Basket** tab (the ported basket optimiser). |
| `/screener/fund/:schemeCode` | `FundAnalysis.tsx` | One fund, Groww-style but plain-spoken. NAV chart against its category (rebased), key stats, cost, holdings, "if you had invested", rank at each horizon. **"You already own X% of this"**, shown while you choose. Base rates. A sentence for every panel. |
| `/screener/stock/:ticker` | `StockAnalysis.tsx` | One company. Price chart, fundamentals where **every ratio carries its sector median** (not just P/E), peers ranked by index membership, score breakdown (business vs momentum), and which of your funds hold it. |
| `/goals` | `Goals.tsx` | Your goals, and what they **all together** demand each month against what you have. |
| `/goals/new` | `GoalNew.tsx` | Create a goal: target, date, risk answers. |
| `/goals/:id` | `GoalDetail.tsx` | The plan: monthly SIP, equity/debt/gold split, **named funds with rupee amounts** (`GoalFundPlan`), levers priced against **this** goal, edit (with the consequence shown before saving), and an AI explanation that is checked against its own numbers. |
| `/profile` ("You") | `Profile.tsx` | Income, current tax regime, and similar. Without this the biggest lever (tax) cannot be priced. |
| `/auth/callback` | `AuthCallback.tsx` | Google OAuth landing. |
| anything else | `NotFound` in `App.tsx` | "There is no page at this address", with the way back. |

**Things on every page:**

- **⌘K command palette** (`CommandPalette.tsx`) reaches every destination.
- **The trail** (`Trail.tsx`): *Portfolio › Fund X › Company Y*, each hop
  clickable.
- **The waking notice** (`WakingNotice.tsx`). The planned free host sleeps after
  15 minutes and takes about a minute to wake. If the first request takes more
  than 2 seconds, the app says it is waking instead of showing a frozen skeleton.
  `lib/api.ts` gives up after 90 seconds with a message saying the server may
  still be waking. There is no automatic retry.
- **Light/dark theme**, following the operating system unless set.

**Backend only, no screen yet:** `POST /api/v1/ask`, a one-question AI endpoint
with refusals and number-checking (§11). Roadmap step 8 puts a screen on it.

---

## 6. How it is built (architecture)

### 6.1 The picture

```
 ┌──────────────────────────── Browser ────────────────────────────┐
 │  React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui         │
 │  React Query (fetch + cache)  ·  axios (lib/api.ts)             │
 │  Recharts + 10 hand-built chart "devices" (components/charts)   │
 └───────────────▲─────────────────────────────────────────────────┘
                 │  JSON over HTTP, every path starts /api/v1
                 │  JWT in the Authorization header
 ┌───────────────┴──────────── FastAPI (uvicorn) ───────────────────┐
 │ middleware:  CORS → rate limiter (3 tiers) → security headers    │
 │ routers:     advisor · portfolio · research · screener ·         │
 │              ask · auth · alerts · fastapi-users (jwt/register)  │
 │ services:    advisor/  portfolio/  screener/  marketdata/        │
 │              llm/  alerts/                                       │
 │ jobs:        APScheduler (local only): 23:45 NAV capture,        │
 │              00:15 score the universe (IST)                      │
 └──────┬──────────────────┬──────────────────┬─────────────────────┘
        │                  │                  │
  nextrade.db         .navstore/nav.db    app/.holdings/holdings.db
  (users, goals,      (5.3M NAV rows +    (what every fund holds,
   holdings,           nightly scores)     month by month; cannot
   transactions)                           be re-downloaded)
        │
  app/data/*.json  ← committed reference data, rebuilt by scripts/build_*.py
  .navcache .stockcache .holdingscache .newscache .growwcache  ← disk caches

 External (all free / public): AMFI · mfapi.in · Groww · NSE archives ·
 yfinance · Screener.in · NSE/BSE filings · IIMA factor library ·
 Google Gemini (AI) · Groq (old AI path) · Twilio (WhatsApp, dormant)
```

### 6.2 Request lifecycle, using "open my portfolio" as the example

1. The browser hits `/portfolio`. React Router lazy-loads `Portfolio.tsx`. Each
   page is split into its own bundle so the chart library is not downloaded by
   people who see no chart.
2. React Query calls `GET /api/v1/portfolio` through `lib/portfolio-api.ts` →
   `lib/api.ts` (axios with the JWT and a timeout).
3. FastAPI: CORS checks the origin, the rate limiter counts the call (per user
   when logged in, per IP otherwise), and the security headers are stamped.
4. `routers/portfolio.py` loads **only this user's** holdings (ownership is
   checked; a stranger gets 404, not 403).
5. `services/portfolio/valuation.py` turns each transaction ledger into units,
   cost and value (FIFO lots), prices it through `marketdata/pricing.py` (fund →
   NAV, stock → yfinance), computes XIRR (`returns.py`), and flags stale prices
   (`freshness.py`).
6. The response is validated against a Pydantic schema
   (`schemas/portfolio.py`). Many schemas encode honesty rules: "missing is not
   zero", "excluded funds are listed with a reason".
7. The page renders: answer first, details folded.

### 6.3 The nightly pipeline (how the Screener stays fresh)

```
23:45 IST  nav_refresh_job   AMFI NAVAll.txt  → nav_history    (+ mfapi gap-fill)
00:15 IST  nightly_job       nav_history → metrics → Bachatt score → grade → tier
                             → screener_run / screener_score   (refuses to publish
                               a run that looks broken)
```

- **Locally:** both jobs run inside the API process (APScheduler,
  `app/jobs/scheduler.py`). They are on by default and switched off with
  `SCREENER_JOB_ENABLED=0`.
- **Planned production:** the same two steps run **in order** on GitHub Actions
  (`.github/workflows/nightly.yml`). The store is trimmed to buyable funds,
  gzipped (~24 MB) and published as a GitHub release asset. The app downloads it
  at boot. **This has never run yet** (§15).

### 6.4 Tech choices, and why

| Choice | Why |
|---|---|
| FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic | Typed request/response contracts. Schema changes go through migrations, never ad-hoc. |
| SQLite in development; Turso (libSQL, SQLite-compatible) planned for production accounts | Zero setup now, and portable. |
| `fastapi-users` | Email/password (Argon2id hashes) + Google OAuth + JWT. |
| React Query | Server state with per-query cache keys. Every query that depends on holdings is invalidated together. |
| Tailwind v4 + shadcn/ui + Base UI | A token-based design system (`src/index.css`). |
| Recharts + hand-built devices | Eight "devices" from the design spec (dot grid, bullet, underwater, slope, fan, rebased line, sorted stacked bar, sparkline), plus a donut and a frame. |
| oxlint | Fast frontend linting (`npm run lint`). |
| Playwright scripts | The only frontend tests. There is no unit-test layer (no vitest/jest), on purpose for now. |
| scipy | Only for the basket optimiser (SLSQP, to match Bachatt's solver exactly). |
| pandas | Imported **inside functions** on the request path, on purpose (§18). |

**Python 3.12 only.** 3.14 breaks the pydantic-core wheels. The venv is
`backend/venv`.

---

## 7. Folder-by-folder tour

### 7.1 The repo root (`traa/`)

| Path | What it is |
|---|---|
| `backend/` | The FastAPI app, its scripts, tests and data (§7.2). |
| `frontend/` | The React app and its browser harnesses (§7.3). |
| `docs/` | Plans, measurements and research write-ups (§7.4, §19). |
| `deploy/` | Deployment kit for two routes: the Oracle VPS route (Caddy + systemd + setup script) and the free no-card route (§15). |
| `data/holdings-dumps/holdings.sql.gz` | The **committed backup** of the fund-holdings store (§9). It exists because Groww only serves the current month, so past months cannot be downloaded again. |
| `.github/workflows/nightly.yml` | The nightly NAV-refresh + scoring + publish job, planned for production. |
| `NexTrade_PRD_v1.md` | The original 2,330-line product spec (Part A advisor, Part B trading agent). The PRD's advisor is a **goal calculator**. Everything about picking real funds was added later as new scope. |
| `START_HERE.md` | The old front-door doc. Its status box was updated 2026-08-28. Its "how to build" section still points at the original 12-task plan, which is history now. |
| `DEPLOY.md` | Deployment runbook: production config guards, environment variables, disk needs. |
| `SECURITY.md` | What is enforced and what risk is accepted, with reasons. Its "no rate limiting" line is stale (rate limiting now exists). |
| `PROJECT_GUIDE.md` | This file. |
| `dev.sh` | Starts API (:8020) and web (:5173) together. Refuses to start if either port is taken. |
| `check.sh` | The quality gate: 12 checks in 11 steps (§13). |
| `.gitignore` | Read it. Several entries carry warnings: `.growwcache/` must never be committed, and `.holdings/` is gitignored, so git is **not** its backup. |
| `.claude` → `../claude-transfer/.claude` | **Symlink** to Manan's shared Claude Code config hub, used by all his projects. Editing it edits every project. |
| `.env` → `../claude-transfer/.env` | **Symlink** to the hub's env file. The app's real secrets live in `backend/.env` instead. |
| `.mcp.json` → `../claude-transfer/.mcp.json` | **Symlink.** The shared MCP server list. That file is tracked in a public git repo, so **never put a key in it**. Keys go in `claude-transfer/.claude/settings.local.json`. |
| `AGENTS.md`, `.agents/`, `.codex/` | Codex CLI "arsenal" hooks (added 2026-10-02, untracked). They point Codex at Manan's tool catalog. Nothing to do with the app. |
| `.playwright-mcp/`, `logs/` | Scratch output from browser-automation tools. Gitignored. Safe to ignore. |
| `nextrade.db` (root, 0 bytes) | A stray empty file. The real database is `backend/nextrade.db`. |
| `.DS_Store` | macOS noise. |

### 7.2 `backend/`

```
backend/
├── app/                 the application
│   ├── main.py          creates the FastAPI app, middleware order, routers, startup checks
│   ├── config.py        Settings from env; REFUSES to boot on unsafe production config
│   ├── database.py      SQLAlchemy engine/session
│   ├── auth/            fastapi-users wiring, Google OAuth, PKCE, JWT backend
│   ├── models/          DB tables: user, goal, holding, transaction, oauth_account
│   ├── schemas/         Pydantic request/response shapes (the API's contracts)
│   ├── routers/         HTTP endpoints, grouped by area
│   ├── services/        all the real logic (see below)
│   ├── middleware/      rate_limit.py (3 tiers), security_headers.py
│   ├── jobs/            scheduler.py (nightly NAV + scoring; a weekly stub)
│   ├── data/            committed reference data (JSON), rebuilt by scripts
│   └── .holdings/       holdings.db: the look-through store (gitignored!)
├── scripts/             builders, validators, research measurements, harnesses
├── tests/               pytest suite (~150 files, 2,094 tests collected)
├── migrations/          Alembic: 7 revisions; head = 9d2c7b41f8ea
├── alembic.ini · requirements.txt · Procfile · runtime.txt (python-3.12)
├── .env / .env.example  real secrets (gitignored) / template
├── nextrade.db          dev database (gitignored)
├── .navstore/           nav.db (~197 MB) + the trimmed/gzipped publish copy
├── .navcache/ .stockcache/ .holdingscache/ .newscache/ .growwcache/   caches
├── venv/                Python 3.12 virtualenv
└── .parity-venv/        a SECOND venv pinned to numpy 1.26 + pandas 2.2, used
                         only to prove our scoring equals Bachatt's under THEIR
                         library versions
```

#### `app/routers/`: the API (53 routes in these files, plus fastapi-users' login/register/users routes and `/health`)

| File | Prefix | Endpoints (summary) |
|---|---|---|
| `advisor.py` | `/api/v1` | `POST /advisor/calculate-sip`, `/advisor/risk-score`, `/advisor/asset-allocation`, `/advisor/tax-saving`, `/advisor/whole-portfolio`; `GET/PATCH /profile`; goals CRUD (`/goals`, `/goals/{id}`); `GET /goals/commitment`; `GET /goals/{id}/recommendations` |
| `portfolio.py` | `/api/v1/portfolio` | holdings CRUD; `POST /holdings/{id}/transactions`; `GET ""` (summary); `/benchmark`; `/cost-review`; `/levers`; `/history`; `/overlap`; `/announcements`; `/look-through`; `/already-own/{scheme_code}`; `/company-exposure/{isin}` |
| `research.py` | `/api/v1/research` | `/funds/search`; `/funds/{code}`; `/fund-categories`; `/fund-rankings/{category}`; `/stocks`; `/stocks/ranked`; `/stocks/{t}/score`; `/stocks/{t}`; `/evidence`; `/momentum` |
| `screener.py` | `/api/v1/screener` | `/categories`; `/top-funds`; `/funds`; `/funds/{code}`; `/funds/{code}/analysis`; `/stocks`; `/stocks/{t}`; `/stocks/{t}/analysis`; `/baskets`; `/baskets/{id}` |
| `ask.py` | `/api/v1` | `POST /ask`: one question, refusals enforced **before** the model runs |
| `auth.py` | `/api/v1/auth/google` | `/authorize`, `/callback` |
| `alerts.py` | `/api/v1/alerts` | `POST /test`: sends a WhatsApp test **only to the caller's own number** (it used to be an open relay; fixed) |

Interactive docs at `http://127.0.0.1:8020/docs` when running.
Recount: `grep -cE '^@router\.(get|post|put|patch|delete)' backend/app/routers/*.py`.

#### `app/services/`: where the logic lives

**`services/advisor/`: money decisions, the goal calculator, our own scoring**

| File | Plain-language job |
|---|---|
| `sip_calculator.py` | Monthly SIP needed for a target, with inflation and existing savings. (Original PRD.) |
| `asset_allocator.py` | Risk questionnaire → risk score → equity/debt/gold split. ⚠️ It averages *ability* and *willingness* to take risk; see §16.4. |
| `goal_inflation.py` | Per-goal inflation: education 10%, healthcare 13%, home/retirement 7%, wedding 8%, others 6%. |
| `goal_commitment.py` | What all goals together need each month vs what there is. |
| `goal_fund_plan.py` | Turns a goal's split into **named funds and rupee amounts**. Never emits an instalment too small to place. |
| `fund_universe.py`, `fund_catalogue.py`, `buyable.py` | Which funds exist, which can be bought, which only track an index. Gold funds are picked **by name**, because AMFI has no gold category and gold sits beside Nasdaq trackers. |
| `fund_metrics.py`, `rolling_returns.py`, `fund_evidence.py` | NAV history → rolling-window returns, worst periods, consistency. |
| `peer_normalise.py` | Raw metric → 0–1 score vs peers (rank blended with magnitude, scaled between the 10th and 90th percentile). |
| `fund_score.py` | **Our** fund score: cost 0.55, risk 0.25, consistency 0.20. Missing cost scores **neutral**, never dropped. Short records are shrunk toward neutral. |
| `fund_verdict.py` | Score → sentences ("across 1,414 three-year periods this fund never lost money…"). |
| `category_ranking.py` | Ranks one SEBI category end to end (feeds Research). |
| `fund_overlap.py` | How much your funds hold the same companies. |
| `cost_of_holding.py` | One held fund's cost from **two sources** (Groww and AMFI), with disagreements kept and shown. |
| `plan_pairs.py` | Regular plan → its direct twin. |
| `switch_badge.py` | "Regular plan: direct saves ₹X/yr": saving, exit load, tax as a **deferral**, breakeven vs horizon. Every figure is checked by `grounding.py`. |
| `levers.py` | **The thesis engine.** Every decision priced in rupees and ranked, under 4 rules (§10.3). |
| `tax_regime.py` | Indian income tax under **both** regimes, FY 2025-26 and 2026-27, with surcharge, **marginal relief**, the 15% cap on capital-gains surcharge, 87A rebate and cess. |
| `tax_advisor.py` | Tax-saving actions, offered only if they help in the regime that actually wins. |
| `whole_portfolio.py` | Allocation across **everything owned** (EPF, PPF, FDs, gold, ESOPs), not just tracked funds. Never suggests selling EPF. |
| `asset_mix.py` | "How much is really equity". ⚠️ It counts gold/overseas as equity risk. Holdings uses `portfolio/asset_class.py` instead (§16.4). |
| `stock_score.py`, `stock_analysis.py`, `stock_ranking.py` | **Our** stock score against **sector medians**: P/E 22, ROE 25, EPS growth 25, P/B 15, dividend 13. Missing data = half marks, never zero. Promoter stake change as the only adjustment. Deliberately **no** RSI/MACD/momentum. |
| `momentum.py` | The one measured predictor: 12-month return skipping the last month (250 + 21 trading days). |
| `track_record.py` | Serves the scoreboard (`track_record.json`). |
| `backtest.py` | An honest harness asking "does the score pick better funds?" |
| `rebalancer.py` | PRD's 5-percentage-point drift band. ⚠️ Known wrong; deliberately **not surfaced** (§16.4). |
| `money.py` | Writes rupees the Indian way (lakh, crore). |

**`services/portfolio/`: the user's own holdings**

| File | Job |
|---|---|
| `fifo.py` | First-in-first-out lots; long-term vs short-term by **calendar months** (Section 2(42A)), not 365 days. A leap-year bug was found and fixed. |
| `valuation.py` | Ledger → units, cost, value, gain. Pure arithmetic, **no network**. |
| `returns.py` | XIRR (money-weighted return), using `pyxirr`. |
| `freshness.py` | Is the price current or quietly frozen? Drives *"This value is not current"*. |
| `plan_identity.py` | Which plan a holding is really on. `misnamed_as()` catches a holding typed as one fund house whose code belongs to another. |
| `holding_cost.py` | What regular-plan holdings cost vs direct, compounded over the horizon. |
| `asset_class.py` | Equity / overseas / debt / gold buckets for the allocation chart. |
| `benchmark.py`, `history.py` | "Would I have done better buying the index?" and value over time. |
| `look_through.py` | Which companies you actually own through your funds, and how much. |
| `already_own.py` | "You already own 61% of this fund", shown at the moment of choosing. |

**`services/screener/`: the Screener (Bachatt's method, ported exactly)**

| File | Job |
|---|---|
| `reference.py` | The **only** place that knows where Bachatt's checkout lives (`~/BachattDev/sip-optimizer/server`). It is read-only by construction, and a test fails if any other file mentions the path. |
| `navstore.py` | The local NAV database (`.navstore/nav.db`). |
| `backfill.py` | One-off crawl of every fund's full history from mfapi. |
| `amfi.py` | Parses AMFI's daily file. Built so that a broken parse **cannot look like a quiet day**. |
| `inputs.py` | Which funds enter the ranking. Uses an **allowlist** of SEBI scheme types, because the feed invents junk labels a blocklist cannot catch. |
| `metrics.py`, `scoring.py` | Bachatt's exact arithmetic, transcribed. |
| `universe.py` | Score → grade → tier, in that order. |
| `pipeline.py` | The nightly run. Refuses to publish a broken one. |
| `serve.py` | Reads the latest accepted run back out. |
| `reasons.py`, `plain_words.py` | Why a fund is on screen, in sentences. A test **bans** the words *sortino, sharpe, alpha, beta, cagr, drawdown* from these sentences. |
| `analysis.py`, `fund_facts.py`, `base_rates.py` | Everything the fund page needs. Base rates = how often this category lost money, and how badly, since 2006. |
| `stock_scoring.py`, `stocks.py`, `sector_benchmarks.py`, `stock_analysis_page.py` | Bachatt's stock scorer, ported (50 fundamental / 41 momentum / 9 delivery points), and the stock page. |
| `basket.py`, `basket_build.py`, `basket_slots.py` | Bachatt's SLSQP basket optimiser, ported, with its quirks surfaced (§10.6). |

**`services/marketdata/`: talking to the outside world**

| File | Source |
|---|---|
| `mutual_fund.py` | mfapi.in (NAV history), with retry + disk cache. |
| `groww.py` | Groww's buyable universe and scheme details (holdings, managers, TER history). Guards against Groww's silent failure modes. |
| `fund_holdings.py` | AMC monthly portfolio spreadsheets (PPFAS, SBI, Nippon, ICICI, HDFC, and more). Infers fraction vs percent from the column's own total. |
| `holdings_store.py` | Keeps every fund's disclosed portfolio, queryable across funds (`app/.holdings/holdings.db`). |
| `stock.py` | yfinance (`.NS` tickers). Cache keyed on **(ticker, period)**; see §18. |
| `stock_universe.py` | The 751-stock catalogue. |
| `pricing.py` | One door for "what is this worth now". |
| `promoter.py` | Promoter shareholding by quarter, from Screener.in. |
| `announcements.py` | NSE/BSE filings for companies you hold. |
| `nse_delivery.py` | Delivery % from NSE's daily bhavcopy. |

**`services/llm/`: AI (§11).** `client.py` (one door + fallback), `gemini.py`
(free-tier-aware), `grounding.py` (every number must exist in the input),
`refusals.py` (what it will not answer), `tools.py` (20 tool contracts),
`advisor_prompts.py` (goal narration).

**`services/alerts/`**: Twilio WhatsApp sender and templates. Wired but dormant.

**`services/data_built.py`**: tells each screen how old each committed data file
is.

#### `app/data/`: committed reference data

Each file is rebuilt by a script and dated in `built.json`.

| File | What | Built by | As of |
|---|---|---|---|
| `fund_catalogue.json` | Every Direct-Growth scheme AMFI publishes, by SEBI category (~4,957). **Direct only, on purpose.** | `build_fund_catalogue.py` | 2026-08-29 |
| `groww_buyable.json` | 1,659 Groww-buyable funds: codes plus three attributes only (Groww's API is robots-disallowed, so raw payloads stay local). | `build_groww_universe.py` | 2026-08-29 |
| `expense_ratios.json` | Direct and regular TER per scheme, from AMFI. | `build_expense_ratios.py` | 2026-08-29 |
| `plan_pairs.json` | Regular code → direct twin (3,792 entries). | catalogue build | 2026-08-29 |
| `category_synonyms.json` | AMFI labels that mean the same SEBI category (it writes some in singular and plural). | `build_category_synonyms.py` | 2026-08-29 |
| `base_rates.json` | Per category: how often and how badly it lost money. | `build_base_rates.py` | 2026-08-20 |
| `track_record.json` | The app's scoreboard (§3.1). | `build_track_record.py` | 2026-08-22 |
| `factor_evidence.json` | IIMA 32-year factor results + momentum curve. | `build_factor_evidence.py` | 2026-08-06 |
| `stock_universe.json` | 751 NSE stocks (Nifty 50 / 500 / Total Market). | `build_stock_universe.py` | ~2026-07-22 (file date only) |
| `sector_benchmarks.json` | Sector medians of P/E, P/B, ROE, dividend yield. | `build_sector_benchmarks.py` | ~2026-08-21 (file date only) |
| `stock_score_ledger.csv` | A tiny ledger for the stock-score track record. | (validator) | |

#### `scripts/`: three kinds of script

- **Builders** (`build_*.py`, `backfill_nav_history.py`, `fetch_nav_store.py`,
  `trim_nav_store.py`, `seed_demo_portfolio.py`) create or refresh data.
- **Measurements** (`validate_*.py`, `why_not_returns.py`,
  `measure_score_edge.py`, `verify_scoring_parity.py`) are the research. They
  answer "does X actually predict?" and always include controls: a `random`
  column that must come out at chance and a `reversed` column that must mirror
  the result.
- **Live harnesses** (`edge_cases.py`, `consistency.py`, `isolation.py`,
  `validate_nav_integrity.py`, plus `_ratelimit.py`, a client that waits out our
  own rate limiter honestly) run against a live server from `check.sh`.

#### `tests/`

About 150 pytest files. The test file names describe behaviour, and most read
like a sentence (`test_disclaimer_is_enforced.py`,
`test_no_vendor_name_in_product.py`, `test_request_path_memory.py`). Some are
unusual on purpose:

- **Document tests** check that numbers written in `docs/` still match the
  repo (`test_plan_counts.py` and 7 others). `check.sh` runs them as a separate
  step.
- `test_declared_dependencies.py` fails if `app/` imports a package that is not
  declared in `requirements.txt`.
- `test_reference_repo_is_read_only.py` guards the Bachatt checkout.
- `test_request_path_memory.py` fails if pandas gets imported on the request
  path (free-tier RAM).

### 7.3 `frontend/`

```
frontend/
├── src/
│   ├── App.tsx          routes, layout, top nav (NAV list), auth guard, 404
│   ├── main.tsx         entry; applies theme before first paint
│   ├── index.css        design tokens: colours, gain/loss, radius, number utilities
│   ├── pages/           one file per route (§5)
│   ├── components/      feature components (Levers, CostReview, FundOverlap,
│   │                    LookThrough, StartHere, CompareTray, Trail, CommandPalette,
│   │                    WakingNotice, AddHolding/TransactionDialog, FundPicker…)
│   ├── components/charts/  the devices: AllocationDonut, Bullet, ChartFrame,
│   │                    DotGrid, Fan, RebasedLine, Slope, SortedStackedBar,
│   │                    Sparkline, Underwater
│   ├── components/ui/   primitives: button, panel, metric, stat, plain, notice,
│   │                    table, tabs, dialog, skeleton, reveal, in-view…
│   └── lib/             api.ts (axios + timeout/retry), auth.ts (token),
│                        portfolio-api.ts / research-api.ts / screener-api.ts
│                        (typed API clients + React Query hooks), format.ts
│                        (₹, %, and ONE glyph for "not available"), chart.ts,
│                        count-up.ts, use-tilt.ts
├── scripts/             Playwright harnesses (no unit tests exist):
│   ├── sweep.mjs        every page, both themes; fails on console errors or API ≥400
│   │                    (`--empty` = as a brand-new user)
│   ├── mobile.mjs       small iPhone + Pixel: fits, no sideways scroll, 44px tap targets
│   ├── a11y.mjs         labels, headings, contrast, keyboard tab order
│   └── shots.mjs        screenshots every page in both themes → shots/
├── shots/               screenshot output (gitignored; may be stale)
├── vite.config.ts       port 5173 on 127.0.0.1; /api proxy for tunnels
├── vercel.json          SPA rewrite for Vercel
├── .env.local           VITE_API_URL for local dev
└── package.json         scripts: dev, build (tsc -b && vite build), lint (oxlint), preview
```

**Design language** (see also `nextrade-ui-conventions` in memory): a
data-dense instrument panel for one expert user. Cool neutral greys, one muted
blue accent that cannot be confused with gain green or loss red. Gain and loss
are real tokens (`text-gain`, `text-loss`). `.num` (monospace, tabular figures)
is for table cells. `.tnum` is for figures inside sentences. `Panel` gives
bounded surfaces with hairline borders and **no shadows**: these are readouts,
not buttons. **Plain sentence first, numbers one click behind** (the `Plain`
primitive). Pages must not add their own outer `max-w` wrapper; `App.tsx`
already does that.

### 7.4 `docs/`

| File | What it is |
|---|---|
| `BUILD.md` | **The current build instruction.** Slices 0–4 (all built 2026-08-29), what must not be lost, Manan's 7 open decisions. Start here for engineering. |
| `phase-1-redesign.md` | The evidence behind BUILD.md: 6,608 lines, 20 sections, 148 adversarial review passes. Read §0, §7 and §9.1. §18 is the review log. Not light reading. |
| `what-actually-predicts-returns.md` | Answers *"cost ka kya hai, returns matter karte hain"* with measurements. |
| `does-the-score-work.md` | Our fund score vs a coin. |
| `does-the-stock-score-work.md` | The same for stocks. |
| `do-factors-work-here.md` | Momentum, value and low-vol on Indian data. |
| `why-there-is-no-fund-manager-screen.md` | Why manager tenure is not a reason to buy. |
| `bachatt-teardown.md` | How Bachatt's optimiser works, and where traa is ahead or behind. |
| `groww-endpoints.md`, `zerodha-endpoints.md` | Catalogues of public endpoints. Trading-capable ones are deliberately unused. |
| `research/2026-06-28-oss-landscape.md` | Open-source projects studied, with verdicts. |
| `superpowers/specs/…`, `superpowers/plans/…` | The June spec and 12-task plan. **Historical.** |

### 7.5 `deploy/`

| File | Route |
|---|---|
| `FREE-NO-CARD.md` | **The chosen route:** Vercel + Render free + Turso + GitHub Actions + release asset, ₹0/month, no card. |
| `README.md` | Which free host clears the app's real needs, read against the whole free-for-dev list. Lands on Oracle Always Free (needs a card). |
| `setup.sh`, `nextrade-api.service`, `Caddyfile`, `nextrade.env.example` | The Oracle/VPS route: systemd service, Caddy HTTPS reverse proxy, env template. |

---

## 8. Where every number comes from (data sources)

Everything is free and public. Each source has traps, and the traps are listed
because each one has already cost real time.

| Source | What we take | Used by | Traps / caveats |
|---|---|---|---|
| **AMFI `NAVAll.txt`** (`portal.amfiindia.com/spages/NAVAll.txt`) | Today's NAV for every scheme | Nightly capture → NAV store | Needs a browser User-Agent. Only carries the **latest** NAV, so a missed night is recoverable only via mfapi. Has zero-NAV placeholder rows before a fund launched (these once produced NaN rankings). |
| **mfapi.in** | Full NAV history per scheme, scheme category | Backfill, gap-fill, live prices, catalogue build | The list endpoint is **unstable**: it returned 75,372 schemes one minute and 37,689 the next, so builders refuse to write unless hand-checked codes survive. Category appears only on `/mf/{code}`. **It can lag AMFI by days**: on 2026-09-23 it was 4 days behind, and no warning fired because every fund lagged equally. Roadmap step 2 fixes this. |
| **AMFI TER API** (`amfiindia.com/api/populate-te-rdata-revised`) | Expense ratio for direct **and** regular plans | `expense_ratios.json` → cost pillar, cost review | It used to stop at AMC id 55, which **silently dropped 297 funds** including Groww's and PPFAS's AMCs. Now it walks ids until 8 consecutive empty ones. "SEBI's 2.25% cap" is **not** a flat cap in the data (slab-based), so the app says "unusually high for a direct plan" and never "breach". |
| **Groww** `st_filter` listing + scheme detail | Buyable universe, TER, AUM, min investment, managers + tenure, **full holdings**, 11 years of daily TER, exit-load history | `groww_buyable.json`, look-through, overlap | 🔴 **`/v1/api/*` is `Disallow` in Groww's robots.txt.** No login is needed, but that is not permission. Raw payloads stay in gitignored `.growwcache/`; only codes + 3 attributes are committed. The app must degrade without Groww. A hand-built slug returns HTTP 200 with **every field null**, so check `isin` is not null. Holdings arrive as positional arrays, so check that weights sum to ~100. Name joins to AMFI return **zero** matches: join on **scheme code**. `groww_scheme_code` actually holds an ISIN. |
| **AMC monthly portfolio spreadsheets** | ISIN-level holdings | `fund_holdings.py` (overlap) | File extensions lie (.xls that is really xlsx). Some AMCs use fractions, some percent. The header row moves. Month spellings are a habit, not a rule. HDFC needs a browser UA and a per-scheme URL. |
| **NSE archives** (`nsearchives.nseindia.com/content/indices/*.csv`) | Index constituents | `stock_universe.json` (751) | NSE's JSON API is cookie-gated. The archive CSVs work with just a browser UA. |
| **yfinance** (`.NS`) | Stock prices, P/E, P/B, ROE, dividend, `^NSEI` index | Stocks, sector medians, benchmark | `returnOnEquity` is missing for 8 of 12 big names, so we derive **ROE = P/B ÷ P/E** (±2.3pp). Dividend yield is `None` (not 0) for non-payers. Rate-limits big pulls. |
| **Screener.in** | Promoter holding by quarter | `promoter.py` | 12 years of P&L there also parses (not wired yet). |
| **NSE / BSE announcements** | Corporate filings | `announcements.py` | Filtered to companies **you hold**. Not a news feed. |
| **NSE bhavcopy** | Delivery % | `nse_delivery.py` | NSE's `quote-equity` returns **403**, so Bachatt's 9-point delivery factor is a constant 4.5 for every stock. This is disclosed. |
| **IIMA Indian Fama-French library** | 32 years of factor returns | `factor_evidence.json` | Lags about 7 months. |
| **Google Gemini** | AI narration and `/ask` | `llm/gemini.py` | Free-tier limits are unpublished and account-specific. A 429 is treated as normal, with template fallback. Model set by `GEMINI_MODEL` in `backend/.env` (`gemini-3.1-flash-lite`). |
| **Groq** | The original LLM path (Llama) | `llm/client.py` | Legacy. 757 goal explanations were generated through it; none contained an invented number. |
| **Twilio** | WhatsApp | `alerts/` | Dormant. |
| *Planned:* **niftyindices.com** | Total-return index per category benchmark | roadmap step 4 | The old `/Backpage.aspx/` path redirects to login. Use `/BackPage/getTotalReturnIndexString`. |
| *Cross-check:* **Zerodha** `api.kite.trade/mf/instruments` | 1,658 direct-growth funds | sanity check vs Groww's count | No TER. |

**Dead or stale:** `mfdata.in` (gone); NSE's insider-disclosure API (empties
out after April 2026).

**A changing world:** SEBI recategorised funds in Feb 2026 (new Life Cycle and
Sectoral Debt categories, Solution-Oriented discontinued). The Income-tax Act
2025 replaced the 1961 Act on 1 April 2026, so "80C" is now Section 123 (the app
shows both names). **Never hardcode a category list.**

---

## 9. The databases and caches

Measured 2026-10-02.

### 9.1 `backend/nextrade.db`: users and their money (SQLite dev; Turso planned)

| Table | Rows | Notes |
|---|---|---|
| `users` | 790 | Mostly **test fixtures and harness accounts**. The app is single-user by design, which is exactly why a dropped `WHERE user_id = …` would return believable-looking data instead of nothing. Ownership is tested. |
| `goals` | 979 | Each carries an AI explanation. |
| `holdings` | 624 | Fund or stock positions. |
| `transactions` | 4,740 | Buys and sells (a SIP is one row per month). |
| `oauth_account` | 0 | Google login is wired, but nobody has used it. |

Schema changes go **only** through Alembic (`backend/migrations/versions/`, 7
revisions, head `9d2c7b41f8ea`). `Procfile` runs `alembic upgrade head` before
every boot.

### 9.2 `backend/.navstore/nav.db`: the NAV spine (~197 MB, gitignored)

| Table | Rows | What |
|---|---|---|
| `nav_history` | 5,309,004 | Every published NAV of every fund. Inserts are `ON CONFLICT DO NOTHING`, so a stored value is never corrected, which is why `validate_nav_integrity.py` exists. |
| `nav_source` | 5,706 | Per-fund fetch status, including `last_error`. |
| `screener_run` | 7 | One row per nightly scoring run. |
| `screener_score` | 10,930 | Scores per fund per run. |
| `screener_unscorable` | 27,360 | Funds left out, **with the reason**. |
| `screener_input` | 13,042 | The inputs each score used (so it can be recomputed and checked). |

`nav.db.trimmed` / `.gz` is the published copy: buyable funds only, ~96 MB →
**23.9 MB gzipped**. It was verified to give identical metrics. It is
rederivable: delete it and the backfill rebuilds it (slowly).

### 9.3 `backend/app/.holdings/holdings.db`: the look-through store (4.9 MB)

Tables `portfolio` (384) and `holding` (27,448): what each fund held, month by
month. **This one cannot be rebuilt.** Groww serves only the current month, so a
lost month is gone for good. It is gitignored because it is a growing binary
file, so **git is not its backup**. The backup is a monthly gzipped SQL dump
committed to `data/holdings-dumps/holdings.sql.gz`. The test of that backup:
delete the store, restore from the dump, get the same store.

### 9.4 Caches (all gitignored, all rebuildable)

`.navcache/` (mfapi responses), `.stockcache/` (yfinance), `.holdingscache/`
(AMC spreadsheets / holdings), `.newscache/` (filings), `.growwcache/` (raw
Groww payloads, **never commit**). Deleting them costs speed, never
correctness. Each can be moved with an env var (`NEXTRADE_CACHE_DIR`,
`NEXTRADE_STOCK_CACHE_DIR`, `NEXTRADE_HOLDINGS_CACHE_DIR`,
`NEXTRADE_NEWS_CACHE_DIR`, `NEXTRADE_NAV_DB`).

**Leftovers you can ignore:** `backend/nav.db` (0 bytes) and
`backend/test_nextrade.*.db` (old test databases).

---

## 10. The engines: how the important calculations work

### 10.1 There are two fund rankings, and they are meant to disagree

| | Research page | Screener page |
|---|---|---|
| Engine | `services/advisor/` (ours) | `services/screener/` (Bachatt's, ported exactly) |
| Ranks on | **Cost 55%, risk 25%, consistency 20%**. Past return 0%. | Bachatt's formula over trailing record, **including its 14-day momentum and drawdown terms (27% of the score)**. Cost carries zero weight (§29) |
| Computed | On request | Nightly, for the whole universe, from the local NAV store |
| Why it exists | It is what our own evidence supports | Manan's call: replicate Bachatt until ours is proven |
| Measured edge | Cost: 36/44 windows (82%) | 68% over 235 category-years; 3 of 7 years at or below chance |

The same fund can be 1st on one and 22nd on the other. **Nobody should "fix"
that.** Only the *set* of funds covered must agree, and `consistency.py` checks
exactly that.

**Details of our score** (`fund_score.py`):

- **Consistency** is the *shape* of the rolling 3-year return distribution: how
  often a full 3-year holding made money, and how bad the worst one was. It is
  not the average. Example: Parag Parikh Flexi Cap had 1,414 three-year windows
  and never lost money (worst +0.8%/yr).
- **Short records are shrunk toward neutral**, not zero. A short record is an
  absence of evidence, not evidence of a bad fund. This was added after a
  3-year-old fund with 9 near-identical windows (all from one bull run) ranked
  above Parag Parikh.
- **Normalisation** blends percentile rank with magnitude, scaled between the
  10th and 90th percentile, so two extreme funds cannot squash everyone else.
- **Missing cost is neutral**, never dropped. Dropping it once pushed three
  unpriced funds into a top five.
- **Do not raise cost above 55%.** Fees predict return but not risk. Risk needs
  its own pillar, or the ranking becomes a sorted fee list.

### 10.2 There are two stock scores, and both are disclosed

- **Ours** (`advisor/stock_score.py`, on Research): fundamentals against
  **sector medians computed from our own 751-stock universe**. A P/E of 48 is
  normal for consumer goods (median 49.3) and expensive for energy (10.9).
  Missing data gets half marks. No technical indicators.
- **Bachatt's port** (`screener/stock_scoring.py`, on the Screener's Stocks tab):
  41 of 100 points are momentum indicators (RSI, MACD, EMA, support). Manan chose
  a faithful port **plus a disclosure on screen** (`method_note`). Quirks found
  and handled:
  - a stock with exactly 14 days of history scored **100/100 "Strong Buy"**
    (NaN clamped to 100), so `is_scoreable()` now refuses fewer than 15 closes;
  - growth measured off a loss takes full marks;
  - a stock with every input missing scores 47.5 ("Hold");
  - ROE is the only factor that can go negative.

### 10.3 Levers: every decision, priced in rupees (`advisor/levers.py`)

Each lever is a decision the user can make, with its rupee value over their
horizon, its **kind** (`certain` / `behaviour` / `trade` / `gate`), its
`evidence`, and when to `revisit`. The four rules:

1. **A trade is never sorted among the levers.** "Hold more equity" could top
   the list at ₹34.8L, but it is the price of holding through a fall, not free
   money. Trades are returned in a separate array, so they cannot be sorted in.
2. **A gate is not a lever.** An emergency fund or a debt level is priced per
   year carried, not as a scary lifetime number.
3. **A value that moves with an assumption is a range**, not a point.
4. **A contested magnitude gets no number.** "Stay invested" carries zero. The
   behaviour-gap literature agrees on direction but not on size.

**Price from where the user already is.** The new tax regime is India's default
since FY2023-24, so most salaried people already have that saving. The tax lever
shows **₹0, "Already done"** when you are on the cheaper regime, ranks first
when you are not, and disappears when both regimes cost the same.

### 10.4 Tax (`advisor/tax_regime.py`)

Both regimes, FY 2025-26 and 2026-27. It includes standard deduction, 87A rebate,
4% cess, **surcharge** (10% from ₹50L, 15% from ₹1cr, 25% from ₹2cr; above ₹5cr
the new regime caps at 25% while the old goes to 37%), and **marginal relief**.
Acceptance test: one rupee more income adds at most ₹1 more tax before cess
(₹1.04 after cess). Capital gains under 111A/112A/112 carry surcharge at no more
than 15%. The ₹1.25L LTCG exemption applies to **equity only**. Sanity check:
₹15L salary, no deductions → new regime ₹97,500 vs old ₹2,57,400.

### 10.5 Your portfolio's truth-telling

- **XIRR + FIFO**: real money-weighted returns. Long-term vs short-term counted
  in **calendar months**.
- **Freshness**: a fund priced from an old NAV says *"This value is not
  current"* on every view built from it.
- **Misnamed holdings**: a holding typed as "ICICI Corporate Bond" whose code
  AMFI publishes as Aditya Birla gets a warning naming the fund the numbers are
  really about. The check compares the **fund house**, not the name string, so
  nicknames like "PPFAS" do not trigger false alarms.
- **Regular → direct** (`plan_identity.py`, `plan_pairs.json`,
  `switch_badge.py`): finds your fund's commission-free twin and prices the
  switch, including exit load, the tax it brings forward (a **deferral**, not a
  loss), and breakeven against your horizon.
- **Overlap and look-through**: uses real holdings, not correlation. Sector
  overlap was tested and overstates true overlap about 1.75×. "n/a" when
  unmeasured, **never "0%"**, because 0% reads as "perfectly diversified".

### 10.6 Goals (the original PRD calculator, still working)

`sip_calculator` → `asset_allocator` → `goal_inflation` (per goal type) →
`goal_fund_plan` (named funds + rupee amounts) → AI explanation checked by
`advisor_prompts`/`grounding`. Levers can be priced per goal.

### 10.7 The basket optimiser (ported, with its quirks surfaced)

Bachatt's SLSQP allocator was ported with 100 differential tests. Measured
findings, all shown or handled:

- the conservative/balanced/aggressive × bullish/neutral/bearish settings change
  **nothing** (all nine agree to 1e-15);
- a "tactical overlay" breaks the weight caps the solver respected, so we return
  both versions;
- the bounds check quietly rewrites caps (15% becomes 25%);
- their code crashes under pandas 3; ours does not.

---

## 11. The AI layer

**In plain words:** the AI never decides anything and never invents a number.
It only puts into words what the code already computed. Questions the app has
decided not to answer are blocked **before** the AI is even called.

- **`llm/client.py`**: one door to the model. If the model fails, the app falls
  back to template text and **stays correct**.
- **`llm/gemini.py`**: Gemini with free-tier handling. On a 429 it waits for the
  API's own `retryDelay`, then falls back.
- **`llm/grounding.py`** (~800 lines, ~50 tests): **every number the model
  writes must already exist in the data it was shown, and must be about the
  right thing.** It catches "Reliance is 7.55% of the fund" when 7.55% was HDFC
  Bank's figure. It catches a loss written as a gain, including a Unicode minus
  sign (U+2212). It caught nothing wrong in 757 real goal explanations (that
  corpus is now the test suite). Every fix in this module has at least once
  caused the next bug, so change it carefully.
- **`llm/refusals.py`**: things the app will not answer, each with the
  **measured reason** instead of an apology:
  - sell the underperformer;
  - sell the winner;
  - concentration limits;
  - trailing stops;
  - price alerts;
  - AUM-bloat thresholds;
  - act on a manager change;
  - a behaviour-gap number;
  - place an order;
  - treat Groww's rating as a rating;
  - sell on no stated basis.

  That is 11 rules in code; the docstring still says "nine". Selling **is**
  allowed when the reason is cost (regular → direct), because that is the app's
  strongest advice.
- **`llm/tools.py`**: **20** read-only tools (the plan said 18; writing them
  down added two more resolvers, so every opaque id has a lookup). Each has a
  JSON contract written **before** the implementation: `resolve_fund`, `fund_facts`, `fund_analysis`,
  `holdings`, `overlap`, `cost_review`, `levers`, `benchmark`,
  `portfolio_history`, `base_rates`, `tax_regime`, `category_coverage`,
  `top_funds`, `stock_facts`, `fund_ter_history`, `look_through`,
  `company_exposure`, `switch_cost`, `resolve_stock`, `resolve_company`. A tool
  whose output does not match its contract **fails the test suite**.
- **`POST /api/v1/ask`**: one question in, one answer out. There is no screen
  for it yet.
- **Design decision:** the model returns `(value, entity name)` pairs and the
  **backend** resolves them to data paths. Asking a model to index into a list
  (`holdings.0.weight_pct`) is a known weak spot.

---

## 12. Security

| Area | What is in place |
|---|---|
| **Login** | `fastapi-users`: email/password hashed with **Argon2id**, Google OAuth with PKCE, JWT. |
| **Startup guards** (`config.py`) | In `ENVIRONMENT=production` the app **refuses to boot** if: `JWT_SECRET` is the public example value or shorter than 32 characters; `DATABASE_URL` is a **relative** SQLite path (a container would wipe it on redeploy); or `ALLOWED_ORIGINS` contains `*`. These catch failures that produce **no error at runtime**, so boot is the only place to catch them. |
| **Account isolation** | Every route that takes an id checks ownership and answers **404** to strangers (not 403, which would confirm the item exists). `scripts/isolation.py` runs 31 checks in both directions and separates "could not test" from "leaked". |
| **Rate limiting** (`middleware/rate_limit.py`) | Three tiers: **auth** (strictest, per IP, **failures only**), **heavy** (endpoints that hit upstream sources, per user), **default**. In-process memory, so it resets on restart. Moving `_Bucket` to Redis is the documented upgrade path. |
| **Headers** | `security_headers.py` stamps browser-enforced headers. Middleware order means a 429 still carries CORS headers. |
| **Input** | Every body is a Pydantic model with numeric bounds. All SQL goes through SQLAlchemy; no string-built queries. |
| **Secrets** | `backend/.env` is gitignored and has never been committed. MCP keys go in `claude-transfer/.claude/settings.local.json`, **never** in `.mcp.json` (public repo). |
| **Accepted risks** | The JWT is stored in `localStorage` (the app renders no user HTML and uses no `dangerouslySetInnerHTML`). react-router's CSRF advisory applies only to RSC mode, which is unused. |

**Lesson from a sibling project:** Manan's `stocksync` repo had a real `.env`
with live keys committed to a **public** GitHub repo. A `.gitignore` does
nothing to a file that is already tracked; `git rm --cached` is what makes it
work. Never `git add -A` without looking.

---

## 13. Testing and the quality gate

**The philosophy:** *a green result means nothing if a red one is impossible.*
Every check must be able to show itself failing. This repo found **four** times
that a verification tool had been measuring nothing:

- `check.sh`'s pipes swallowed exit codes, so it could never fail;
- the screenshot script photographed **another app's** login page 14 times and
  reported success;
- six scripts pointed at other projects' ports;
- harnesses shrank silently when rate-limited.

### `./check.sh`: 11 steps, 12 checks, in order

(Step 9 runs twice: once seeded, once as a brand-new account.)

0. **Self-control:** a pipeline that must fail is asserted to fail. If not, exit
   2.
1. **Unit tests** (`pytest`, minus the document tests).
2. **Document tests:** numbers in `docs/` still match the repo. Kept separate
   so a stale doc count does not turn the code gate red.
3. **NAV store integrity:** samples stored NAVs against mfapi and recomputes
   scores from recorded inputs.
4. **Scoring parity:** our port vs Bachatt's code under **their** pinned pandas
   2 / numpy 1.26 (`backend/.parity-venv`). Skipped, with a message, if that
   venv is missing.
5. **Frontend typecheck + build.**
6. **Adversarial inputs** (`edge_cases.py`): ₹1 targets, ₹50 crore, negative
   returns. No 500s, no NaN.
7. **Cross-view consistency** (`consistency.py`): the same fact agrees with
   itself on every screen.
8. **Account isolation** (`isolation.py`).
9. **Page sweep**, seeded and as a brand-new account (`sweep.mjs`).
10. **Mobile** (`mobile.mjs`).
11. **Accessibility** (`a11y.mjs`).

Steps 6–11 need the API on `:8020` (and the web app on `:5173` for 9–11). Run
against another address with `API=… APP=… ./check.sh`.

**Counts on 2026-10-02:** 2,094 tests collected
(`backend/venv/bin/python -m pytest --collect-only -q | tail -1`).

**Frontend:** no unit tests on purpose. Criteria are written as things the four
Playwright harnesses can check. Adding vitest is an open decision.

**The project's own verification rule** (from `.claude/rules`): "it compiled" is
not done. Run `npm run lint` and `npx tsc -b --noEmit` on frontend changes, and
`python -m py_compile` (or ruff if installed) on backend changes. Do not invent a
test runner or config without asking.

---

## 14. How to run it on your machine

### 14.1 First time

```bash
cd ~/Desktop/manan/traa

# Backend (Python 3.12 exactly)
python3.12 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env        # then fill in keys (all optional in dev)
(cd backend && venv/bin/alembic upgrade head)

# Frontend
(cd frontend && npm install)
```

**Data (only if starting from nothing):**

```bash
cd backend
venv/bin/python scripts/backfill_nav_history.py      # NAV store: minutes, crawls mfapi
venv/bin/python -c 'from app.services.screener import pipeline; pipeline.run_nightly()'   # first scores
venv/bin/python scripts/seed_demo_portfolio.py       # optional: a portfolio to look at
```

Without the NAV store, the Screener answers **503 with rebuild progress**, and
the startup log says exactly what to run.

### 14.2 Every day

```bash
./dev.sh          # API on http://127.0.0.1:8020/docs, app on http://localhost:5173
```

On Manan's Mac the servers already run under **pm2**: `traa-api`, `traa-web`,
and `traa-tunnel` (a Cloudflare tunnel for sharing the dev app). `pm2 list` /
`pm2 restart traa-api`. pm2 needs `--interpreter none` for the venv's uvicorn.

### 14.3 Ports: read this before you get confused

- **8020** = this API. **5173** = this web app.
- **8000 = `jba`** and **8010 = `freea`**: other projects on the same Mac. A
  script pointed at those runs every check **against a different app** and
  passes.
- Backend CORS allows `http://localhost:5173` and `http://127.0.0.1:5173`.
- Vite binds `127.0.0.1` explicitly; uvicorn binds `0.0.0.0`. These choices
  avoid IPv6 `localhost` traps (§18).

### 14.4 Environment variables (backend)

`ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET`, `ALLOWED_ORIGINS`, `FRONTEND_URL`,
`BACKEND_URL`, `TRUST_PROXY_HEADER`, `GEMINI_API_KEY`, `GEMINI_MODEL`,
`GROQ_API_KEY`, `TWILIO_*`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`,
`SCREENER_JOB_ENABLED`, `SCORING_REFERENCE_DIR`, and the cache-dir variables in
§9.4. Frontend: `VITE_API_URL` (baked in at build time).

---

## 15. Deployment: planned, not done

**State on 2026-10-02:** `gh release list` is empty. **The app is not
deployed.**

The deployment work lives on this branch (`free-deploy-groww-universe`, pushed
to GitHub). **`origin/main` is 47 commits behind it** (main stops at `0203060`,
2026-08-25). `nightly.yml` has therefore never run, and no NAV-store asset has
ever been published. Step one of deploying is merging or pushing this work to
`main`. That is Manan's call.

**The chosen free route** (`deploy/FREE-NO-CARD.md`):

| Piece | Where | Cost |
|---|---|---|
| Frontend | Vercel Hobby (`*.vercel.app`) | free |
| API | Render free (`*.onrender.com`) | free, no card |
| Nightly jobs | GitHub Actions | free |
| NAV store | GitHub release asset `nav-store` (downloaded at boot) | free |
| User accounts | Turso (libSQL) | free |

Render start command:
`python scripts/fetch_nav_store.py && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
Set `SCREENER_JOB_ENABLED=0` there, or two writers race on one file.

**Measured needs:** 46 MB RAM serving, 23.9 MB store, about 1.2 MB of writable
user data.

**What you give up:**

- Render sleeps after 15 minutes idle and takes about a minute to wake, so most
  visits are cold starts (hence the waking notice).
- Rate limits reset on every wake.
- GitHub may delay or drop scheduled workflows.
- Two free providers can suspend you without notice.

**The paid/VPS alternative** (Oracle Always Free needs a card, or Hetzner at
about ₹430/month) is in `deploy/README.md` with Caddy + systemd files.

**Before going public**, re-read `SECURITY.md`: the endpoints that proxy third
parties need their limits checked, and the Groww robots.txt question becomes
more serious once the app is not purely personal.

---

## 16. Status: what is done, what is next, what is open

### 16.1 Done: the `BUILD.md` slices (all on 2026-08-29)

| Slice | Delivered |
|---|---|
| **0: hygiene** | The AMC walk stops on evidence, not on the number 55. Every data file carries a build date. The return slider reads the server's range. Document tests run as their own `check.sh` step. **The waking state.** |
| **1: one holding, end to end** | Surcharge + marginal relief. The regular → direct mapping. A holding's cost from both sources with disagreements kept. **The switch badge** with four figures, each checked by `grounding.py`. |
| **2: universe and cost data** | The buyable universe (1,659, reproducible). Catalogue filters that were eating real funds fixed (74 recovered). The holdings store, look-through and dump backup. A trimmed published store. |
| **3: AI layer** | Response models for the AI-facing endpoints. A Gemini client that survives the free tier. A TER rebuild. `/ask` with refusals as code. The tool registry. Goal narration grounded. |
| **4: screens** | The eight chart devices with empty and loading states. Trail + ⌘K. Overlap-at-choosing + compare tray. The **Why** page. Portfolio and Holdings split into two pages (decision 2). |

**After that:** the Portfolio redesign and landing page (Sep 5); the Holdings
rebuild with the bar ⇄ donut allocation toggle (Sep 23–26).

### 16.2 Next: the roadmap agreed with Manan on 2026-09-23

1. ✅ **Holdings:** table rewrite + allocation chart with a **bar ⇄ donut
   toggle**. This overrides the old "never a pie" rule. The override is recorded
   in commit `354c247` and in `AllocationBreakdown.tsx`, but the rule text
   (`docs/phase-1-redesign.md` §13.6) and the docstring of
   `test_the_pie_is_deleted_not_deprecated` still say "never a pie". The test
   still passes only because it looks for the old `AllocationPie.tsx` file name.
   Updating both is still to do (§16.3).
2. ⬜ **Fund prices straight from AMFI `NAVAll.txt`**, because mfapi lagged 4
   days unnoticed.
3. ⬜ **Bachatt's display scale for scores** (their 2026-09-07 change: the best
   fund shows ~90 instead of ~71), exposed as a **new** field only.
4. ⬜ **Each fund against its own benchmark** (e.g. Small Cap vs Nifty Smallcap
   250 TRI) from niftyindices.com.
5. ⬜ **Badges column** on Holdings. The Gain column **stays** visible (this
   overrides the plan's §3.2).
6. ⬜ **News, three kinds:** NSE filings (exists), per-stock news for held
   stocks, category news. AI summaries minimal. Google News RSS is
   personal-use-only under its terms, so it is fine only while the app stays
   personal.
7. ⬜ **Stock watchlist** with a snapshot at save time. Gold/silver via
   `GOLDBEES.NS` / `SILVERBEES.NS`.
8. ⬜ **AI on screen:** a per-row "Explain" button and one ask box, on the
   existing `/ask` refusal gate + about 5 read-only tools + a number check.

### 16.3 Known defects still open (true as of 2026-10-02)

| Defect | Why it matters |
|---|---|
| **Debt funds are ranked on equity metrics.** | Debt risk is a sudden credit event or a duration loss, invisible in smooth NAVs (Franklin Templeton looked fine until it froze). The right inputs (YTM, duration, the SEBI Potential Risk Class cell) live only in PDF factsheets. |
| **The Decide page says "X% in equity" using `asset_mix.py`**, which counts gold and overseas as equity risk, while Holdings uses `asset_class.py`. | The two screens can disagree. Flagged, not reworded. |
| **The SEBI TER limit is slab-based**, but the slab table could not be sourced. | So the app says "unusually high for a direct plan", never "over the limit". |
| **Rate limits are per process.** | Fine for one user. Redis is needed beyond that. |
| **The monthly holdings pull** needs running (and approving) every month. | Groww serves only the current month; a missed month is lost. |
| **CAS import** (`casparser`) is not installed. | Entering a real portfolio by hand takes about 23 interactions for 5 funds. |
| **`START_HERE.md` and `SECURITY.md`** carry stale lines. | See §7.1. |
| **The "never a pie" rule was overridden in code but not in its doc or test.** | §13.6 of the plan and the test docstring still forbid what Holdings now ships. Rule 12 in §17 says to update both. |

### 16.4 Decisions waiting on Manan (from `docs/BUILD.md`)

1. Does `Decide.tsx` merge into Portfolio, or go?
2. ✅ Decided: `/portfolio` = summary, `/portfolio/holdings` = the table.
3. The goal flow (3 routes, ~1,100 lines, the PRD's centre) has no place in the
   redesign. Is it deliberately unchanged, or should it be redesigned too?
4. Virtualise the Screener list, or keep the 100-row pagination that was chosen
   on measured grounds?
5. **The risk questionnaire averages ability with willingness.** Answers
   `[10,9,2,1]`, `[1,3,8,10]` and `[6,6,6,6]` all score 6. Ability should be a
   ceiling, not part of an average. Fixing this departs from the PRD.
6. **The rebalancer's 5-point absolute band** (a 5% gold sleeve must double
   before it triggers). It should be ±20% relative and tax-aware. Currently not
   surfaced anywhere, and its weekly job is a stub.
7. How many people will use this. That changes the regulatory reading (§8 of the
   plan) and the data-protection duties. **Effectively settled on 2026-09-23**
   ("single-user and personal, Manan only"), but `BUILD.md` and the plan's §8.-1
   have not been updated to say so.

---

## 17. How we work here (rules and habits)

These come from real mistakes. Each one cost hours at least once.

1. **Test first.** Write the failing test, watch it fail, then make it pass. One
   commit per task.
2. **Show a check failing before you trust it.** For a guard: remove it in a
   test and prove the bad thing gets through. For a harness: break the thing and
   see it go red.
3. **A number in prose is a claim. Count it; do not copy it.** Every count
   re-counted in the redesign review had moved. Cite the script that produced a
   number.
4. **Read the producer, not the artefact.** Every confident wrong conclusion in
   this project came from reasoning about an output file instead of reading or
   running the code that writes it.
5. **Read the newest commits before trusting any document**, including this one.
   The biggest finding of the plan review (the deployment architecture had
   changed) was sitting in a commit message.
6. **Missing is not zero.** Use the single "not available" glyph from
   `lib/format.ts`. Never default an unknown to `0`.
7. **Disclose coverage.** Funds left out of a ranking are listed with a reason.
   Stale data says it is stale.
8. **Plain language first, arithmetic one click behind.** Manan's clearest
   feedback: *"mujhe abhi bhi kuch nahi samajh aa rha"* when screens led with
   `t = +3.11`. Never remove the numbers, only move them.
9. **Before adding any information feature, ask what decision it changes and
   whether that decision is worth money.** "It makes people trade more" counts
   against it.
10. **Never touch the Bachatt checkout.** Read through `screener/reference.py`
    only.
11. **Never commit** `.growwcache/`, `.holdings/`, `.navstore/`, any `.env`, or
    anything under `node_modules/`. Look before `git add`.
12. **When Manan overrides a written rule,** say so once, then follow him and
    update **both** the rule text and its test.
13. **Commit messages** state what was wrong, in plain words (`fix: a fund that
    failed to load took every other fund's score with it`). **Code comments
    explain why**, often with the incident that caused them. Match that density.
14. **Surgical changes.** Touch only what the task needs. Do not refactor nearby
    code. Do not invent a test runner or lint config without asking.
15. **No hosted Artifacts.** Chat or files on disk. Tell subagents explicitly.
16. **After any code change, explain it in plain language:** what changed, which
    files and what each does, what broke and how it was found, and a one-line
    summary (Manan's global rule).

---

## 18. Traps that have already cost time

| Trap | What happens | Fix / rule |
|---|---|---|
| Ports 8000 / 8010 belong to other projects | Scripts "pass" against the wrong app | Everything defaults to **8020**. `dev.sh` refuses busy ports. |
| `0.0.0.0:8020` binds even when `127.0.0.1:8020` is taken | The browser talks to the wrong app; every route 404s | `dev.sh` checks `lsof` first. |
| `localhost` resolves to IPv6 `::1` first | Chrome reports a **CORS error** that is really "connection refused" | Vite on `127.0.0.1`, uvicorn on `0.0.0.0`, both spellings in CORS. |
| `nohup … &` from a tool call | The server dies with the process group | Use **pm2**. |
| `set -o pipefail` does not reach `bash -c` | `harness \| tail` always exits 0 | `check.sh`'s `sh()` passes `-o pipefail` itself. |
| Our own rate limiter during the gate | Harnesses get 429, shrink silently or crash | `scripts/_ratelimit.py` honours `Retry-After` once. |
| A cache key missing an argument | A 1-year chart drew a cached 3-month frame | Stock cache keyed on `(ticker, period)`. |
| `nan < 100` is False | A clamp turned NaN into 100 (Strong Buy) | Refuse unscoreable inputs by name. |
| numpy `convolve` on a short array | Returns repeated full-history sums, not an empty array | Guard length before rolling windows. |
| Importing pandas at module top on the request path | +30 MB per worker; the free tier breaks; no test fails | Import inside functions. `test_request_path_memory.py` guards it. |
| A same-length, same-second edit + `.pyc` cache | A "sabotage" test silently runs the old code | `PYTHONDONTWRITEBYTECODE=1` and clear `__pycache__`. |
| A dependency that arrives only through another package | Works until that package changes | `test_declared_dependencies.py`. |
| AMFI category text varies (plural/singular, per AMC) | Real funds vanish from their category | `category_synonyms.json`; an allowlist of scheme types. |
| Scheme **name** vs scheme **code** | A typed name can point at a different fund | Codes drive everything; `misnamed_as` warns. |
| A substring regex for "index" | "Inflation **Index**ed Bond" counted as passive | Word-boundary regex. The `index` flag from Groww's `st_filter` is the real signal. |
| Ranking on today's TER at past dates | Lookahead inflates the cost effect | Stated as a caveat (§3.1). |
| Measuring stocks against a different index | Mid-caps "beat" the Nifty 50 for free | Benchmark against the **same universe**. Always run `random` and `reversed` controls. |
| `.gitignore` on an already-tracked file | Does nothing | `git rm --cached`. |
| Editing `traa/.mcp.json` | Edits the shared hub file for every project, which is in a public repo | Keys go in the hub's `settings.local.json`. |
| Chrome-extension / Puppeteer MCP screenshots | Failed repeatedly on this machine | Use local Playwright + `frontend/scripts/shots.mjs`. |

---

## 19. Which document answers which question

| Question | Read |
|---|---|
| Every study, method, number and mistake, in one place | **Part II of this guide (§22–§38)** |
| How the work is done, reviewed and recorded | **Part III of this guide (§39–§47)** |
| What exactly should I build next, and how will I know it is done? | `docs/BUILD.md`, then §16 here |
| Why is the product designed this way? Where is the evidence? | `docs/phase-1-redesign.md` §0, §1, §9.1, §14 |
| Does fund picking work? Does cost? | `docs/what-actually-predicts-returns.md`, `docs/does-the-score-work.md` |
| Does anything predict stocks? | `docs/do-factors-work-here.md`, `docs/does-the-stock-score-work.md` |
| How does Bachatt's system work, and what did we port? | `docs/bachatt-teardown.md` |
| What can Groww / Zerodha give us? | `docs/groww-endpoints.md`, `docs/zerodha-endpoints.md` |
| How do I deploy? | `deploy/FREE-NO-CARD.md`, `DEPLOY.md` |
| What is the security posture? | `SECURITY.md` (+ §12 here) |
| What did the original spec want, including the trading agent? | `NexTrade_PRD_v1.md` |
| Which open-source projects were studied? | `docs/research/2026-06-28-oss-landscape.md` |
| Longer context, decisions, measurements | Obsidian vault `~/Desktop/manan/manan-memory/Projects/traa/*.md` (e.g. `traa-architecture.md`, `traa-decisions.md`, `traa-gotchas.md`, `traa-running-it.md`, `traa-measurements.md`) |
| Claude's memory for this project | `~/.claude/projects/-Users-beastathome-Desktop-manan-traa/memory/` (index: `MEMORY.md`) |

---

## 20. FAQ for a new helper

**Why does the app say picking the best fund is worth ₹0?**
Because it was measured four ways and none predicted reliably, while cost did.
Leaving the line off would hide the most important finding. See §3.

**Why are there two different fund rankings that disagree?**
Research uses our evidence-based, cost-heavy score. The Screener uses Bachatt's
method, ported on purpose until ours is proven. They are meant to differ; only
their coverage must match. See §10.1.

**Why only Groww funds?**
Manan invests on Groww. A fund he cannot buy is not advice. The universe is
"buyable on Groww, plus whatever he already holds".

**Why no news feed, price alerts or "top movers"?**
The evidence says attention features make people trade more, and trading costs
money. The only feed is filings for companies you hold.

**Why won't the AI tell me to sell my worst fund?**
Because selling on past performance is measured to be a losing move. The app
**will** tell you to switch out of a regular plan into its direct twin, because
cost is the one thing proven to matter.

**Why are there 790 users if it is single-user?**
Test fixtures and harness accounts. That is also why every query must be scoped
by `user_id`, and why tests enforce it.

**Is it live on the internet?**
No. See §15. It runs on Manan's Mac (pm2), and sometimes he shares it through a
Cloudflare tunnel.

**What happened to the trading agent (Part B)?**
Not started, on purpose. Advisory first. The PRD describes it: NIFTYBEES swing
trading, backtest → paper money for months → real money only after that, with a
hardcoded risk manager. None of it exists in code.

**Can I use Bachatt's data or APIs?**
No. You can read their code to understand a formula, then build it with public
data in our own code.

**Something in a doc disagrees with the code. Which is right?**
The code, almost always. Then fix the doc, and if a test pins that doc number,
update it too.

---

## 21. Glossary

| Term | Meaning |
|---|---|
| **AMC** | Asset Management Company: a fund house (HDFC, SBI, PPFAS…). |
| **AMFI** | Association of Mutual Funds in India. Publishes every fund's daily NAV and expense ratios. |
| **SEBI** | India's market regulator. Defines fund categories ("Large Cap", "Flexi Cap"…). |
| **NAV** | Net Asset Value: the price of one unit of a fund, published daily. |
| **Scheme code** | AMFI's 6-digit id for a fund plan. The key to everything here; names are just labels. |
| **ISIN** | International id for a security (fund plan or share). |
| **Direct vs Regular plan** | Same fund, same holdings. Regular pays a distributor commission (~0.6–1%/yr more). Direct does not. |
| **Growth option** | Profits stay invested (vs IDCW, which pays them out). |
| **TER / expense ratio** | The annual fee a fund charges, as % of your money. The one thing proven to predict returns. |
| **AUM** | Assets Under Management: fund size. |
| **Exit load** | A fee for selling within a set period (often 1% within a year). |
| **SIP** | Systematic Investment Plan: a fixed amount invested every month. |
| **XIRR** | Your real annual return, accounting for when each rupee went in. |
| **FIFO** | First-in, first-out: the oldest units are treated as sold first (decides tax). |
| **STCG / LTCG** | Short-/long-term capital gains tax. Equity becomes long-term after **12 calendar months**. LTCG is 12.5% above a ₹1.25L yearly exemption (equity only); STCG is 20%. |
| **Old vs New tax regime** | Two ways to compute income tax. New is the default since FY2023-24, with fewer deductions and lower rates. |
| **80C (now Section 123)** | Deductions (ELSS, PPF, EPF…) that only help in the old regime. |
| **Surcharge / marginal relief** | Extra tax on high incomes. Marginal relief stops ₹1 of extra income costing lakhs of extra tax. |
| **ELSS** | Tax-saving equity fund with a 3-year lock-in. |
| **Index fund / ETF / passive** | Copies an index instead of picking stocks; usually cheaper. |
| **Look-through** | The companies you own *through* your funds. |
| **Overlap** | How much two funds hold the same things. |
| **Benchmark / TRI** | The index a fund is compared with; TRI includes dividends. |
| **Rolling returns** | Returns over every possible N-year window, not just one start date. |
| **Drawdown** | The fall from a peak to a low. |
| **Quartile** | A quarter of a ranked list (top quartile = best 25%). |
| **Hit rate** | How often the top group beat the bottom group. 50% = coin flip. |
| **Rank IC** | Correlation between a predicted ranking and the actual ranking. 0 = useless, +0.1 = meaningful in finance. |
| **t-statistic** | How unlikely a result is to be luck. Above ~2 is usually "real". |
| **Survivorship bias** | Only counting funds that still exist, which flatters results. |
| **Lookahead bias** | Using information that was not available at the time. |
| **Momentum (WML)** | Recent winners keep winning for a while; the one measured stock signal here. |
| **Value (HML), Size (SMB)** | Other "factors"; value works in India, size does not. |
| **Base rate** | How often things like this have gone a certain way before. |
| **Lever** | A money decision, priced in rupees, in the app's ranking. |
| **Grounding** | Checking that every number the AI writes came from real data. |
| **CAS** | Consolidated Account Statement: one PDF of all your mutual funds (import not built yet). |
| **Bhavcopy** | NSE's daily file of every stock's prices and volumes. |
| **NIFTYBEES** | An ETF tracking the Nifty 50; the planned Part B trading instrument. |
| **Bachatt** | Separate fintech product (Manan's workplace). A **reference only** for scoring methods. |
| **PRD** | Product Requirements Document (`NexTrade_PRD_v1.md`). |
| **Slice** | A vertical unit of work in `docs/BUILD.md` (0–4). |
| **pm2** | A process manager that keeps the dev servers running. |
| **Alembic** | Database migration tool. |
| **Render / Vercel / Turso** | Free hosting for the API, the web app, and the user database. |

---

---

# Part II: the research, in depth

This project is unusual in one way: **it tests its own answers, and when they
fail it changes the product instead of writing a brochure.** One line in the
Obsidian vault says it in Hinglish: *"ye app apne hi jawaab test karti hai, aur
jab wo fail hote hain toh product badal deti hai — brochure nahi banati."*

Part II records every study: the question, who asked it, the method, the
controls, the exact numbers, the caveats, what it changed, and **the mistakes
made along the way**. The mistakes are kept on purpose, because they are how the
methods got better.

Scripts live in `backend/scripts/`. Write-ups live in `docs/`. Longer notes live
in the Obsidian vault (`~/Desktop/manan/manan-memory/Projects/traa/`).

---

## 22. How to read the research, and the scoreboard of everything measured

### 22.1 The vocabulary, in plain words

| Term | Meaning here |
|---|---|
| **Decision date / formation date** | A day in the past where we pretend to choose, using only what was knowable that day. |
| **Window** | One decision date plus the period after it (e.g. "3 years forward"). |
| **Forward return** | What actually happened after the decision date. |
| **Quartile / quintile** | The ranked list cut into 4 or 5 equal groups. "Top quartile" = the best-ranked 25%. |
| **Hit rate / "won X of Y windows"** | How often the top group beat the bottom group. **50% is a coin flip.** |
| **Spread** | Top group's return minus bottom group's, in percentage points (pp) per year. |
| **Rank IC** | Correlation between the predicted ranking and what actually happened, using every fund, not just the top and bottom. 0 = useless. In finance, +0.05 to +0.10 is already meaningful. |
| **t-statistic** | How unlikely a result is to be luck. Roughly, above 2 means "probably real". |
| **Within category** | Large Caps compared only with Large Caps. Mixing categories measures asset class (debt vs equity), not fund choice. |
| **Point-in-time** | Using only data that existed on the decision date. Breaking this is **lookahead bias**. |
| **Survivorship bias** | Testing only funds still alive today. Dead funds were often the bad ones, so results look better than reality. |
| **Overlapping windows** | Windows that share years. They are not independent, so they overstate confidence. |
| **Control** | A fake signal run through the same machinery. A `random` ranking must score ~50% / IC ~0. A `reversed` ranking must mirror the real one. **If the controls misbehave, every other row is unreadable.** |
| **Clustering / bootstrap on dates** | Uncertainty measured on the true independent unit (dates), not on categories that share the same market. |
| **Sabotage / mutation** | Deliberately breaking code or data to prove a check turns red. |

### 22.2 The scoreboard: everything this project has measured

| Question | Answer | Where |
|---|---|---|
| Does ranking funds on past 3-year return pick winners? | **No.** 19 of 44 windows (43%), worse quartile on top by 0.9pp, IC −0.025 | §23.3 |
| Does our own early fund score pick winners? | **No.** 50% of 60 windows; top quartile +17.2% vs bottom +19.4% | §23.1 |
| Does lifetime (since-launch) return pick winners? (Manan's idea) | **No, worse than a coin.** 38% (20 of 52) | §23.4 |
| Does Bachatt's score (ported) pick winners? | **Some, unreliably.** 68% over 235 category-years, but 3 of 7 years at or below chance | §23.5 |
| Does cheaper cost predict better returns? | **Yes, the one thing that works.** 36 of 44 (82%), +2.1pp, IC +0.195. Re-measured without lookahead: smaller but still positive | §23.2, §23.6 |
| Does mixing past return into cost help? | **No, it halves the signal** (IC +0.184 → +0.091) | §23.3 |
| Does a "cheap" ₹10 NAV beat a ₹1,000 NAV? | **No.** IC +0.020: zero | §23.3 |
| Does past return tell you when to sell? | **No usable signal.** At long horizons past winners slightly *underperform* | §24 |
| Does holding period matter? | **Enormously.** Equity loses money in 16–22% of 1-year stretches, 0–2% of 5-year stretches | §25 |
| Does our stock score predict? | **Not shown.** +10.6% on NIFTY 500, −5.0% on NIFTY 50: flips sign with the universe | §26.1 |
| Does momentum predict stocks? | **Yes, modestly.** t = +2.99 (own data), t = +3.11 (32 years, IIMA). Survives costs only at low turnover. Loses badly in rebounds | §26.2–26.4 |
| Does value predict? | **Yes on IIMA data** (t = +2.39). Never tested on our own universe | §26.3 |
| Does size (small caps) predict in India? | **No, negative** (−2.8%/yr, not significant) | §26.3 |
| Does low volatility predict returns? | **No, negative in this period** (t ≈ −2.6) | §26.2 |
| Are two funds you hold really different? | **Often not.** Large Cap vs ELSS: 46.8% the same holdings | §27 |
| Is SEBI's "2.25% TER ceiling" a ceiling in the data? | **No.** 8.6% of filings sit above it; no cliff anywhere | §28.4 |
| Do the AI's numbers stay true? | **Yes, when checked.** 757 real generations, 0 invented figures | §36 |

---

## 23. Can anyone pick the better fund? Measured five ways

This is the question every Indian investing app answers with a "Top funds"
list. NexTrade measured it five separate ways before deciding what to show.

### 23.1 Our own fund score, tested (2026-07-27)

- **Scripts:** `validate_score.py` (Result 1), `validate_quartiles.py` (Result 2).
- **Write-up:** `docs/does-the-score-work.md`. The doc's opening: *"The answer is
  no, and this document exists because that needed writing down rather than
  quietly not being tested."*
- **What was tested:** the score as it was then: consistency 35%, return 25%,
  cost 20%, risk 20%.

**Method**

- NAV history from mfapi; equity categories only.
- 6 decision dates a year apart; hold for 3 years after each.
- The picker sees only NAVs up to the decision date. A fund needs ≥400 days of
  history to be offered.
- A fund that died mid-window counts as "unmeasurable", not valued at its last
  NAV.

**Result 1.** Take the score's top 2 picks per category and compare them with
the category median. 60 windows across 10 categories.

| Category | Hit rate | Spread |
|---|---|---|
| ELSS | 0% | −3.5% |
| Flexi | 83% | +0.3% |
| Focused | 33% | −1.6% |
| Large & Mid | 67% | +1.5% |
| Large | 33% | −1.3% |
| Mid | 33% | −2.5% |
| Multi | 67% | +1.2% |
| Sectoral | 17% | −1.0% |
| Small | 67% | +1.8% |
| Value | 83% | +1.8% |
| **Overall** | **50%** | **−0.4%/yr** |

**Result 2.** Top quartile vs bottom quartile, 54 windows: top **+17.2%**,
median +18.1%, bottom **+19.4%**. Top beat bottom in **25 of 54 (46%)**. The
sign is wrong.

**Caveat:** only funds alive today were in the catalogue, so this is "the
flattering version". The true numbers are worse, by an unknown margin.

**What it changed (same day, commit `a4e43bd`):**

- the score was rebuilt around cost: **cost 0.55, risk 0.25, consistency 0.20,
  past return 0**;
- the levers view started pricing "pick the best fund" at **₹0**;
- by comparison, the direct plan over the regular plan is worth a certain
  +0.64%/yr, about ₹4.2 lakh on ₹15,000/month over 15 years.

### 23.2 Cost, tested the same way (2026-07-27, re-run since)

- **Script:** `validate_cost_ranking.py`. Its docstring: cost is *"the one input
  with replicated predictive power in the literature, so before rebuilding the
  product around it, it gets the same test the score just failed."*
- **Method:** same dates and horizon. Rank funds cheapest-first by direct-plan
  TER; within category; ≥12 funds per category.

| Run | Cheapest quartile | Dearest quartile | Spread | Windows won |
|---|---|---|---|---|
| 2026-07-27 | 20.0% | 17.8% | +2.2pp | 45 of 52 (87%) |
| 2026-08-22 (scoreboard) | — | — | +2.1pp | 43 of 52 (83%) |
| Pass 148 (local NAV store, re-implemented) | 21.4% | 19.3% | +2.1pp | 43 of 52 (83%), exact match |

**Caveats:**

- It ranks on **today's** TER at past dates, a lookahead tested in §23.6.
- Some of the effect is "index funds beat active funds", which points the same
  way.
- 52 overlapping windows are not 52 independent observations, so "83%" is not
  a clean binomial.

### 23.3 Head-to-head: which visible signal predicts? (2026-07-30, re-run 2026-08-22)

- **Script:** `why_not_returns.py`.
- **Write-up:** `docs/what-actually-predicts-returns.md`.
- **Who asked:** Manan, pushing back:

  > *"Cost ka kya hai, humein toh returns matter karte hain. Ek fund ₹10 ka hai
  > 6% de raha hai, ek ₹1000 ka hai 20% de raha hai. Mere paas fixed amount hai,
  > toh mera paisa accordingly grow karega na?"*

- **The answer** was given "not by argument, but by the same harness that has
  already failed our own scoring engine once."

**Method:**

- Equity categories with ≥12 funds; 6 decision dates, 2018-06 to 2023-06; 3
  years forward.
- Four signals:
  - `past_3y`: trailing 3-year return;
  - `cost`: TER;
  - `nav_level`: lower NAV ranked "better", to test the myth;
  - `blend`: half past-return rank, half cost rank.
- Rank IC across the whole cross-section.

| Signal | 2026-07-30: spread · won · IC | 2026-08-22 (median of 3 runs): top/bottom · spread · won · IC |
|---|---|---|
| past 3y return | −1.0% · 20/44 · −0.033 | 19.4 / 20.2 · −0.9pp · 19/44 (43%) · −0.025 |
| **cost** | **+1.9% · 34/44 · +0.184** | **20.6 / 18.4 · +2.1pp · 36/44 (82%) · +0.195** |
| NAV level | +0.3% · 20/44 · +0.020 | 20.1 / 19.8 · +0.4pp · 25/44 · +0.014 |
| blend | +0.7% · 28/44 · +0.091 | 19.7 / 18.9 · +0.8pp · 30/44 · +0.105 |

The two runs differ cell by cell, because mfapi fetches at 24 threads and the
sample moves. They **agree in every direction**.

**What it settled:**

1. **Blending halves the signal.** Past return is not neutral information being
   ignored; it is noise, and adding noise degrades the one signal that works.
   That is the positive reason past return carries **0% weight**, not just a
   permitted one.
2. **NAV level is irrelevant.** A ₹10 NAV is not "cheaper" than ₹1,000; units
   are just slices. This also undercuts the NFO pitch, since new funds are
   usually sold at ₹10.
3. **Cost is not separate from returns.** TER is deducted inside the NAV every
   day. Cost *is* part of return, and the only part knowable in advance.
4. **Do not push cost above 55%.** Fees predict return but not risk (Morningstar
   found fees a weak predictor of volatility). Without a risk pillar the ranking
   would be a sorted fee list.

### 23.4 Manan's hypothesis: rank by lifetime record (2026-08-06)

- **Script:** `validate_lifetime_ranking.py`. Its docstring: *"The 3-year test
  failed. Lifetime is a different claim — a longer record, more market cycles,
  arguably a truer picture of the manager. Worth testing rather than
  dismissing."*
- **Method:** funds launched ≥5 years before each date, ranked by
  since-inception CAGR, measured over the next 3 years.
- **Result:** best lifetime record → **19.7%** next 3 years; worst → **20.9%**.
  Best beat worst in **20 of 52 (38%)**: *"worse than a coin, and pointing the
  wrong way."*

### 23.5 Bachatt's score, ported and tested (2026-08-20)

- **Script:** `measure_score_edge.py`.
- **Why:** Bachatt's own 54,586-line codebase never runs this test. All its
  backtests measure portfolio value over time; none asks whether the score ranks
  funds better than a coin.

**Method:**

- 7 formation dates, 20 Aug 2019 to 20 Aug 2025. Inputs from the 4 years before
  each date; the full ported `universe.run()`; 1 year forward.
- Within (category, sub-category). 235 category-years with ≥8 funds each.
- A **random** and a **reversed** control run through the identical pipeline.
  The script exits with an error if the random control is ever "significant".

| Column | Top quartile beat bottom | Rank IC | z |
|---|---|---|---|
| Ported score | **159/235 = 68%** | +0.170 | +5.4 |
| Random (control) | 116/235 = 49% | −0.006 | −0.2 |
| Reversed (control) | 76/235 = 32% | −0.170 | −5.4 |

| Formation year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|
| Hit rate | 68% | **44%** | **56%** | 91% | 94% | **40%** | 78% |
| Rank IC | +0.164 | +0.059 | +0.051 | +0.332 | +0.354 | +0.006 | +0.209 |

**Three of seven years were at or below chance.** Two good years carry the
average. Anyone acting on it in August 2024 did slightly worse than random.

**Caveats:**

- survivorship;
- the 1-year horizon (27% of the score is a two-week momentum window);
- category-years are not independent, so z overstates.

**Rule:** never show the 68% without the year-by-year table beside it.

### 23.6 The lookahead in the cost result, tested (passes 148–152, 2026-08-28)

The cost studies rank on **today's** TER at past dates. Was that harmless?

- **Groww's history of daily TER** made the question testable. Rank correlation
  between the TER filed back then and today's: +0.34 (2018-07), +0.47 (2020-07),
  +0.56 (2023-07). The median fund moved ~6 places. **TER is stable as a number,
  not as a rank.**
- **Pass 150 pooled every fund** into one ranking and got a confounded answer:
  "cheap" became liquid and overnight debt funds (TER ~0.16%), so it measured
  debt against equity.
- **Pass 152 re-ran within category** (263 AMFI requests, 10 fund houses, 6
  dates):

| Ranked on | Spread | Cheap won |
|---|---|---|
| Today's TER | +12.0pp | 6 of 6 |
| **The TER filed that month** | **+3.6pp** | 2 of 4 |

**Reading:** the cost effect survives the lookahead, and the lookahead roughly
triples it. The sample is tiny (4–6 windows), so **the honest size is not yet
known**. The proper run is Groww's TER history across all buyable funds.

### 23.7 What it adds up to

| Way of picking | Measured | Verdict |
|---|---|---|
| Past 3-year return | 43–50% | coin flip, sign often wrong |
| Lifetime return | 38% | worse than a coin |
| Our early composite score | 46–50% | coin flip |
| Bachatt's ported score | 68%, unstable by year | some edge, not reliable |
| **Cost** | **82–87%** (smaller after lookahead fix) | **works** |

**The product consequence:**

- Research ranks on cost.
- Past return is shown but never used to rank.
- "Pick the best fund" is priced at ₹0 among the levers.
- The Screener keeps Bachatt's ranking, labelled for what it is.

### 23.8 Mistakes made and caught in these studies

- **"A number was explained rather than traced."** The plan mislabelled the same
  table three times. Scorer figures (60/54 windows, `validate_score.py`) were
  mixed into the signal table (44 windows, `why_not_returns.py`). The first
  "correction" then invented a false source for them. Rule since: **every
  number names the script that produced it.**
- **Hand-copied numbers drift.** The cost result was written down as 34/44, 35,
  36 and 37 of 44 in different places. The scoreboard is now **recomputed by
  `build_track_record.py`**, which parses the validators' output strictly and
  refuses to write if any figure is implausible.
- **A self-report that could not be wrong.** `track_record.json`'s `why_ranges`
  text described "five runs" while the script ran three. It was a hardcoded
  string. It was fixed in code on 2026-08-28, but the committed JSON still
  carries the old text until the next rebuild.

---

## 24. When to leave a fund: the exit-signal study

- **Who asked:** Manan, 2026-08-27: *"kab mujhee pata lag jaye kei investment
  mai rok laga denaa chaoyee yaa kisi ek fund stock mai"*.
- **Script:** `validate_exit_signal.py`. Written up in the plan's §1.1 (the
  "fourth measurement").

**Method (version 5, after four wrong versions):**

- Reads the **untrimmed** NAV store (5.19M rows, 4,939 schemes, about 63% dead
  funds included). It refuses the trimmed store.
- A **cohort** is one category on one 1-January date, with ≥20 funds alive at
  both ends.
- "Losers" and "winners" are the bottom and top fifth by past return.
- Score = average forward percentile rank inside the cohort, where 0.500 means
  no information.
- **Control:** 200 random subsets per cohort. Each row reports *group minus its
  own control*.
- **Uncertainty:** bootstrap clustered on **formation dates** (2,000 draws). No
  interval is printed with fewer than 4 dates.

**Results (overlapping windows):**

| Look-back → forward | Dates | Losers − control | Winners − control [95% CI] |
|---|---|---|---|
| 1y → 1y | 12 | −0.028 | +0.033 [−0.051, +0.102] |
| 3y → 3y | 8 | +0.040 | **−0.052 [−0.101, −0.005]** |
| 5y → 3y | 6 | +0.039 | **−0.106 [−0.132, −0.082]** |
| 3y → 1y, 1y → 3y, 3y → 5y | 6–10 | ~0 | ~0 |

Every control lands between 0.497 and 0.503, so the instrument is sound.

**Reading:**

- At a 1-year look-back, nothing.
- At 3–5 years, past **winners** later *underperform* slightly: the De Bondt &
  Thaler "long-run reversal" shape. There is no sign that selling losers helps.

**The four wrong versions, kept because they taught the method:**

1. **The median of a fifth** gave the *random* control 59%, which is
   impossible. A "median" of 2–3 right-skewed values sits high. Fixed with
   average percentile ranks.
2. **Reading rows against 0.500** while the controls sat at 0.477–0.539. Fixed
   by subtracting each row's own control.
3. **Calling that drift "bias".** It was variance: a 3,000-run simulation gave
   0.4999. One control draw per cohort swings ±0.10. Fixed with 200 draws.
   **Widening the pass band until it went green was refused**: that would turn a
   gate into decoration.
4. **Bootstrapping cohorts instead of dates.** Five categories measured on the
   same day are not five independent observations of the market.

**Caveats:**

- Survivorship creeps back in through category labels. Dead funds mostly carry
  old labels (Income 1,601, IDF 792), so 541 of the 582 equity funds measured
  are still alive.
- 2 of 12 intervals exclude zero, with no correction for testing 12 things.

**Product decisions:**

- **No "Underperforming — consider exiting" badge.**
- **No "sell the winner" rule** either: "recorded as a finding, not shipped as a
  feature".
- What the app watches instead is **mechanical**:
  - a cost rise or a cheaper fund in the same category;
  - drift from the fund's mandate;
  - overlap and look-through concentration;
  - category risk vs your horizon;
  - a manager change, flagged but never acted on.

---

## 25. Base rates: holding period decides the outcome

- **Script:** `build_base_rates.py` → `app/data/base_rates.json` →
  `screener/base_rates.py`. Built 2026-08-21.
- **Question:** *how often has each kind of fund lost money, and how badly, since
  2006?* It replaces prediction with history.

**Method:**

- The whole NAV store: 5,183,632 rows, 3,992 funds, 47 categories.
- One entry point on the 1st of every month each fund was alive. Horizons of 1,
  3, 5, 7 and 10 years.
- Windows **deliberately overlap**, because a base rate is "what happened to
  people who invested", not a statistical test. The window counts are shown.
- Thresholds: ≥8 funds per category, ≥200 windows per horizon, >300 NAVs per
  fund.
- **Dead funds are included:** 2,429 of 3,992 (61%) were wound up. The screen
  says so: *"34 funds, 4 of which no longer exist… a floor and not a brochure."*

**Results by category:**

| Category | Funds | Lost money, 1-yr windows | 5-yr | 10-yr | Worst 1 year | Worst fall |
|---|---|---|---|---|---|---|
| Sectoral/Thematic | 212 | 22% | 1% | 0 | −47% | −74% |
| Small Cap | 34 | 20% | 2% | 0 | −43% | −57% |
| Value | 24 | 20% | 1% | 0 | −48% | −57% |
| ELSS | 47 | 19% | 0 | 0 | −35% | −52% |
| Flexi Cap | 38 | 18% | 0.4% | 0 | −33% | −42% |
| Focused | 31 | 17% | 0 | 0 | −33% | −46% |
| Multi Cap | 36 | 17% | 1% | 0 | −35% | −43% |
| Large Cap | 37 | 17% | 0.1% | 0 | −32% | −41% |
| Mid Cap | 35 | 17% | 0 | 0 | −34% | −45% |
| Large & Mid Cap | 33 | 16% | 0 | 0 | −35% | −46% |
| Index Funds | 295 | 16% | 0 | 0 | −33% | −44% |
| Aggressive Hybrid | 35 | 14% | 0 | 0 | −36% | −42% |
| Dynamic Asset Allocation | 39 | 9% | 0 | 0 | −25% | −34% |
| Equity Savings | 26 | 5% | 0 | 0 | −28% | −32% |
| Gilt | 28 | 5% | 0 | 0 | −5% | −13% |

**Small Cap, step by step:**

| Horizon | Windows | Lost money | Worst | Median |
|---|---|---|---|---|
| 1 year | 2,882 | 20.3% | −43.3% | +15.2% |
| 3 years | 2,117 | 6.1% | −16.6%/yr | +22.4%/yr |
| 5 years | 1,520 | 1.8% | −5.5%/yr | +20.4%/yr |
| 7 years | 1,002 | 0.2% | −1.7%/yr | +19.1%/yr |
| 10 years | 473 | 0.0% | +12.0%/yr | +19.3%/yr |

- **Worst fall −57.4%**, which is **₹4,59,280 lost on ₹8,00,000**.
- Median recovery 275 days (~9 months); worst 533 days.
- **First "safe" horizon:** about 3 years for Large Cap, 5 for Small Cap.
- *"Larger and more certain than anything fund selection produces, and it is on
  no other Indian app."*

**Data cleaning, and the rule behind it:**

- **48 "segregated portfolio" side pockets** made Credit Risk look like it lost
  70%. The real worst fall is −34%.
- **One bad NAV row** in Invesco Gold ETF FoF (₹11.86 → ₹0.19 → ₹12.00 in Oct
  2019) made its category's worst fall −98%.
- **The rule:** *a fall that comes straight back is a data error; a fall that
  stays is history.* Remove a one-day drop of more than 50% that recovers to
  ≥80% within 5 rows. DHFL Pramerica's ₹15.30 → ₹7.19 **stays**: it really
  happened.

**Mistake caught:** the first "canary" (sanity check) only covered categories the
cleaning did not touch, so it could not detect a cleaning failure. *The canary
must cover what the filter is for.* It now includes Credit Risk and FoF
Domestic. The build refuses to write if any equity category shows a 5-year loss
share above its 1-year share.

**How it is shown:**

- "20 of every 100", not 20.3%. 0.4% becomes "fewer than 1 of every 100", never
  0.
- The **reference class comes first**, before the fund's own story (Kahneman &
  Lovallo).
- A class is never widened: "equity lost 18% of years" is not "Small Cap did".

---

## 26. Stocks: the stock score, factors, and 32 years of Indian data

### 26.1 Does our stock score predict? (2026-07-29)

- **Script:** `validate_stock_score.py`; ledger `app/data/stock_score_ledger.csv`.
- **Write-up:** `docs/does-the-stock-score-work.md`.
- **Method:**
  - each company is rebuilt as of past fiscal year-ends;
  - **sector medians from that same year**, never today's table ("marking the
    exam with the answer sheet");
  - 250 trading days forward; rank IC per year.
- **No conclusion is printed below 5 years of results.**

**The result, attacked three times:**

1. The first run, NIFTY 500 with no lag: **+15.1%/yr, 3 of 3 years**. "Far too
   good."
2. **Attack 1, lookahead.** Results are published months after year-end. With a
   6-month lag: **+10.6%**. The lookahead was worth ~4.5pp/yr.
3. **Attack 2, sample.** That left 2 observations. A score with no skill lands
   two the same way 25% of the time.
4. **Attack 3, universe.** On NIFTY 50: **−5.0%, IC −0.084**. A result that
   flips sign when you change the index is not a signal. NIFTY 500's result is
   most likely the 2023–24 small/mid-cap run.

**Caveats:**

- 2 of the 5 inputs were never exercised (dividend yield came back empty;
  promoter history was empty), so the test covers only 87 of 100 points.
- The direction of survivorship bias is "genuinely unsigned": Yes Bank, DHFL,
  IL&FS and Reliance Capital all scored well and then collapsed.

**Mistakes caught:**

- The script declared success on **2 observations**: "the exact self-flattery
  this app exists to prevent, produced by the app".
- Its default settings were the discredited ones.
- A Yahoo rate-limit was reported as "not enough history".
- One claimed bug (split-adjusted prices against unadjusted EPS) was checked and
  did **not** reproduce. Nestlé P/E reads 66.7 / 76.1 / 85.3 across its split.

**Product:** Research says the stock score is "not shown to predict", with what
was measured beside it. yfinance keeps only ~5 rolling years, so every run is
appended to the ledger until 5 years accumulate.

### 26.2 Factors on our own stock universe (2026-08-06)

- **Script:** `validate_factors.py`.
- **Write-up:** `docs/do-factors-work-here.md`.
- **Who asked:** Manan, rejecting "tax and cost" as table stakes: *"jispe apne 0
  rate karaa, yehi toh humme build karna hai — tax aur cost toh koi bhi bata
  dega."*

**Method:**

- 220 NIFTY 500 stocks, 15 years of prices.
- **Factors:**
  - **momentum:** 12-month return, skipping the latest month;
  - **low volatility:** calmer stocks ranked higher;
  - **fundamentals** (ROE, earnings growth, low debt), with a 180-day filing
    lag.
- **Non-overlapping windows**: quarterly (60 of them) and annual (15).
- **Benchmark = the same universe, equally weighted.**
- **Costs charged:** 0.5% each way per rebalance (4%/yr quarterly, 1%/yr
  annual).
- **Controls:** `random` (must be 0) and `reversal` (must mirror momentum).

| Quarterly (60 windows) | vs universe | after costs | IC | t |
|---|---|---|---|---|
| **Momentum** | **+2.1%** | −1.9% | **+0.073** | **+2.99** |
| Low volatility | −2.0% | −6.0% | −0.020 | −2.67 |
| Reversal (control) | −1.2% | −5.2% | −0.073 | −1.36 |
| Random (control) | +0.0% | −4.0% | −0.009 | +0.07 |

| Annual (15 windows) | vs universe | after costs | IC | t |
|---|---|---|---|---|
| **Momentum** | **+8.2%** | **+7.2%** | +0.070 | +1.60 |
| Low volatility | −13.5% | −14.5% | −0.058 | −2.56 |
| Reversal (control) | +1.2% | +0.2% | −0.070 | +0.20 |
| Random (control) | +2.3% | +1.3% | +0.025 | +0.52 |

**Reading:**

- Momentum is one real signal (same IC at both horizons). The quarterly run
  proves it exists; the annual run shows it survives costs, but only when traded
  rarely.
- Fundamentals: none reached significance (ROE t = +1.89), because yfinance
  gives only 4–5 years of statements. Screener.in has 12 years and parses, but
  is not wired yet.

**The two mistakes the controls caught:**

1. **Version 1** used 8 yearly windows against an external index. The *random*
   control beat momentum (+3.7% vs +0.8%): noise bigger than the effect.
2. **Benchmarking NIFTY 500 stocks against the NIFTY 50** made *random* show
   **+4.2% at t = +4.13**. That was mid caps outrunning large caps, not skill.
   *"Measuring a factor against a different universe measures the universe."*
   Without the controls, that +4.2% would have been reported as a finding.

### 26.3 Thirty-two years of Indian factor data (IIMA)

- **Script:** `build_factor_evidence.py` → `app/data/factor_evidence.json`.
- **Source:** IIM Ahmedabad's survivorship-adjusted Indian Fama-French-Momentum
  library, monthly, Oct 1993 to Dec 2025 (386 months).

| Factor | Return per year | t |
|---|---|---|
| **Momentum (winners minus losers)** | **+13.41%** | **+3.11** |
| **Value (cheap minus expensive)** | **+8.56%** | **+2.39** |
| Market minus risk-free | +8.61% | +1.99 |
| **Size (small minus big)** | **−2.82%** | −0.96, negative in India, the opposite of the US |

Momentum's curve: ₹1 in 1993 grows to about ₹28 by 2025. It is long-short, so a
long-only investor gets roughly half; that is the +8.2% in §26.2.

### 26.4 Momentum fails in rebounds, not crashes

| Episode | Market | Momentum |
|---|---|---|
| 2008 crash (Jan 2008 – Mar 2009) | −64.7% | **+5.3%** |
| 2009 rebound | +91.6% | **−53.5%** |
| COVID crash | −31.0% | +35.8% |
| COVID rebound | +66.7% | −33.9% |

The worst single month was May 2009: momentum −25.0% while the market rose
+33.6%. The losers it avoided bounce hardest.

**So momentum is a return enhancer correlated with good times, never a hedge.**
The app shows the crash *and* rebound rows side by side, and puts this risk
**above** the momentum table.

**Mistake caught:** the first "2008 crash" window ran Jan 2007 to Dec 2009. It
included the 2007 rally and the 2009 rebound, so the market came out +12.7% for
the period. That produced "momentum pays nothing in a crash" (−0.4%), *the
opposite of the truth*.

🔴 **`docs/do-factors-work-here.md` still carries that retracted sentence.** The
correction lives in commit `0790cab`, the builder's docstring and the JSON. The
doc needs a fix.

### 26.5 The bar for any machine-learning model

Qlib, Chronos, TimesFM and Alpha158/101 were all considered. The bar is now
defined and low:

> **beat rank IC +0.073 at a quarterly horizon, with turnover low enough that
> costs do not eat it.**

Most published results quietly fail the second half. Never judge a model on a
harness that cannot separate momentum from a coin flip.

### 26.6 Bachatt's stock scorer, audited while porting (2026-08-21)

A 62-test differential harness ran against Bachatt's real source.

**Weights:**

| Group | Factors | Points |
|---|---|---|
| Fundamental | P/E 15 · EPS growth 12 · ROE 10 · P/B 8 · dividend 5 | 50 |
| Momentum | RSI 12 · MACD 12 · EMA trend 10 · support 7 | 41 |
| Flow | delivery | 9 |

**Findings:**

- **A newly listed company scored 100/100 "Strong Buy".** With exactly 14 days
  of prices, RSI is NaN, and the clamp `max(0, min(100, NaN))` returns 100. Now
  refused by name below 15 closes.
- **ROE can score negative** (−10 on a 10-point factor).
- **Growth measured off a loss takes full marks.** EPS −10 → +5 reads as +150%.
- **A loss-making company gets half marks on P/E**, while a profitable one at 10×
  the sector median gets zero.
- **All inputs missing scores 47.5, "Hold".**
- **Delivery % is dead upstream.** NSE's quote API returns 403, so every stock
  silently gets 4.5 of 9 points. NexTrade feeds real delivery from NSE's archive
  instead. On the NIFTY 50, **35 of 50 companies changed rank and 7 changed
  bucket** (Adani Ports went 15th → 5th, Hold → Buy).

**Manan's decision:** keep a faithful port, with a `method_note` on screen saying
41 points are momentum indicators. NexTrade's own score deliberately excludes
them.

---

## 27. Overlap and look-through: what you really own

### 27.1 Two ways to measure "are these funds different?"

| Method | Strength | Weakness |
|---|---|---|
| **Correlation of returns** (monthly) | Works for every fund, needs only NAVs | Daily returns are useless here: any two Indian equity funds correlate ≈1.0 daily |
| **Real holdings overlap** (ISIN-level) | Says *which* companies you hold twice | Needs portfolio disclosures; compare only the same month |

**Decided 2026-07-30: use both, and say which signal fired.**

They disagree, and both disagreements matter:

- **SBI Small Cap vs PPFAS Flexi Cap:** correlation 0.78, but holdings overlap
  only 0.7%. Holdings alone would call this pair "diversified"; in a crash they
  move together.
- **Axis Large Cap vs ICICI Large Cap:** **57.1%** holdings overlap: *"the same
  shares, twice"*.
- **A real 4-fund portfolio:** three equity funds correlated 0.80–0.85 with each
  other, and the bond fund 0.25–0.29. Four holdings were really about **2.4
  independent bets**.
- **Sector allocation is not a substitute.** Tested on 21 pairs, it overstates
  true holdings overlap by about 1.75× and ranks pairs wrongly.

### 27.2 Look-through on five plausible funds (2026-08-27)

**The test set:** five funds from five AMCs in five categories, the largest in
each. Real holdings came from Groww: PPFAS Flexi Cap (61 lines), ICICI Large Cap
(85), HDFC Mid Cap (79), Nippon Small Cap (251), Axis ELSS (67).

| Pair | Common names | Overlap |
|---|---|---|
| **Large Cap vs ELSS** | 29 | **46.8%** |
| Flexi vs Large Cap | 31 | 34.4% |
| Flexi vs ELSS | 23 | 28.0% |
| Small vs ELSS | — | 12.6% |
| Mid vs ELSS | — | 12.5% |
| Mid vs Small | — | 10.2% |
| Large vs Small | — | 8.8% |
| Flexi vs Small | — | 5.3% |
| Large vs Mid | — | 4.0% |
| Flexi vs Mid | — | 1.1% |

**₹1,00,000 split equally across the five:** only **₹90,945** actually reaches
equity (the rest sits in cash, debt and similar). The largest look-through
positions:

| Company | Amount | Share of equity | Held through |
|---|---|---|---|
| HDFC Bank | ₹4,704 | 5.2% | 4 of the 5 funds |
| ICICI Bank | ₹4,418 | 4.9% | 3 funds |

Then Airtel ₹2,391, Axis Bank ₹1,950, M&M ₹1,849, Kotak ₹1,716, Infosys
₹1,641, Reliance ₹1,600.

### 27.3 What "high overlap" means: measured, not assumed

Across 595 fund pairs:

| Pair type | Median overlap | 90th percentile |
|---|---|---|
| All pairs | 12.3% | 32.4% (max 99.8%) |
| Same category | 20.4% | 36.4% |
| Different categories | 11.4% | 31.0% |

So **no flat "30% = too similar" rule**; the threshold depends on the pair.

The 99.8% pair was SBI vs UTI "Large Cap": both are Nifty 50 index funds.

**That exposed a bigger fact:** **86 of 123 "Large Cap" funds on Groww are
index trackers (70%).** The cheapest 8 are all passive (0.05–0.13% TER) against
0.84–1.23% for active funds. **Active and passive are never ranked as peers.**

**The refusal:** concentration is shown as a **fact**, never as "too
concentrated, exit". High-conviction, concentrated funds have *outperformed* in
the literature (Kacperczyk, Sialm & Zheng 2005; Cremers & Petajisto 2009).
Unmeasured overlap shows **"n/a", never "0%"**, because 0% reads as "perfectly
diversified".

---

## 28. Data investigations: what each source really contains

Every source was probed live before being trusted, and several turned out to
contain something nobody expected.

### 28.1 Groww's endpoints (2026-08-27)

- **How they were found:** Groww's web app bundles were read: 25 route types →
  144 JavaScript chunks → **760 API paths**.
- **Classified:**

  | Class | Count | Use |
  |---|---|---|
  | Data, no auth | 131 | the only kind used, and only two of them |
  | Read-only portfolio (auth) | 198 | unused |
  | Order / money | 258 | **never touched** |
  | Other | 173 | unused |

- **robots.txt says `Disallow: /v1/api/*`.** No login is needed, but *"reachable
  is not permitted"*. Treated as personal-use research only.

**The two endpoints the app uses:**

- **`st_filter` listing** (5.3 MB): 3,410 rows, every one Direct and available.
  It carries TER, AUM, manager, minimum investment, exit load, sub-category,
  risk, Groww rating and returns.
- **`v5/scheme/search/{id}`**, "the best single endpoint on Groww". It returns:
  - ISIN, benchmark, launch date;
  - **full holdings with sector and weight**;
  - **manager tenure dates**;
  - **11+ years of daily TER history**;
  - exit-load history;
  - Sharpe, beta and standard deviation that Groww's own UI never shows;
  - a PROS/CONS array it fetches but never renders.

**Traps found in Groww's data:**

- A guessed URL slug returns **HTTP 200 with every field null**. Guard: `isin`
  must not be null.
- `category_info.sub_type` is garbage: 0 of 60 agreed with the listing.
- `groww_rating` contradicts itself ("2/10" in one place, "out of 5" in
  another). **Stored, never shown as a rating.**
- Two fields, `sip_return3y` and `sipReturn3y`, carry different numbers (43.44
  vs 27.43 on SBI Gold). Neither is read.
- `groww_scheme_code` actually holds an ISIN.
- Joining Groww to AMFI **by name returns zero matches** with no error. Join on
  the AMFI scheme code.

**Universe counts that do not reconcile, so all three are shown:**

- Groww's filter page: 1,741.
- The API: 1,686 unique codes, later **1,659** after excluding 30 "Specialised
  Investment Funds" (₹10 lakh minimum, no AMFI data).
- Manan's own count on 2026-08-25: 1,792.
- Zerodha's instrument list: 1,658, a useful cross-check.

### 28.2 Zerodha's endpoints

- **154 paths** found the same way.
- **Free and useful:**
  - **NPS fund performance** for every scheme (6m to since-inception);
  - NPS scheme list;
  - 247 days of NIFTY closes;
  - the MF instrument list (7,600 rows, 1,658 direct-growth buyable).
- **Trap:** a wrong-host path returns the app's HTML shell with **HTTP 200**.
  Check the content type.
- None of these is used in code yet.

### 28.3 NSE's archive

- `nsearchives.nseindia.com` serves **every trading day since 2000**: prices,
  volume, delivery %, ISIN. No auth, no cookie, no rate limit; just a browser
  User-Agent.
- Today's file: 2,632 equity names (vs 751 in the old universe).
- Backfill benchmark: ~0.05 s per file, so ~6,500 files ≈ 5 minutes ≈ 9.3M rows.
  This is an **estimate**, not built yet.
- **Traps:**
  - Eight non-equity series (government bonds, SME…) print delivery %, bonds at
    100%. Use an **`SERIES == 'EQ'` allowlist**; a blocklist would have let 51
    bad rows in.
  - A missing date can be a holiday (2012-08-20 was Ramzan Id), not a gap.
  - Prices are **unadjusted**: a 1:10 split reads as −90%. Corporate actions
    come from NSE's API. Demergers carry no ratio, so they are marked "cannot be
    adjusted".
  - `DUMMYTRVN`, an NSE dummy scrip, sat in the committed universe. The universe
    should come from the exchange's own file, not from index lists.

### 28.4 Expense ratios (TER): three discoveries

1. **A hardcoded number deleted 297 funds' cost data.**
   - `build_expense_ratios.py` walked AMFI's fund-house ids up to `_MAX_MF_ID =
     55`. Ids 56–86 hold at least 24 live houses: 63 Groww, 64 Parag Parikh, 77
     Zerodha, 82 JioBlackRock.
   - **297 live funds had no TER.** 151 of them were ranked anyway with a
     made-up "average" cost (`_NEUTRAL = 0.5`), on the one pillar that predicts.
     That is 9% of the ranked universe. Liquid (13 of 37) and ELSS (10 of 37)
     were worst hit.
   - **Fix (slice 0.2):** walk ids until **eight consecutive empty ones**, four
     times the largest real gap. *Stop on evidence, not on a number.*
   - **A second bug** surfaced in the rebuild: the builder replaced the file
     instead of merging it, losing 112 funds. Now 1,606 of 1,659 buyable funds
     (97%) carry a cost.
2. **"SEBI's 2.25% ceiling" is not a ceiling in the data.**
   - Of 2,793 AMFI values: median 0.88%, max 3.46%, and **241 (8.6%) above
     2.25%, with no cliff at 2.25% or anywhere else** from 1.00% to 2.50%.
   - SEBI's limit is slab-based by AUM and scheme type, plus add-ons. The slab
     table could not be sourced.
   - By plan: 229 of 1,396 regular plans exceed 2.25%, against 12 of 1,397
     direct plans.
   - **So the app says "unusually high for a direct plan", shows the number, and
     never claims a breach.**
3. **Two sources, compared.** Groww and AMFI agree within 0.10pp for **94.2%**
   of the 1,233 funds in both (later 94.4%). Rule:
   - require agreement;
   - where they disagree, show both and do not rank on cost;
   - "one source" gets its own label;
   - missing cost is neutral, never dropped.

### 28.5 Fund categories are messy free text

- AMFI writes the same category in **singular and plural at once**. 24 buyable
  funds vanished until commit `208f396`.
- **59% of catalogue schemes** carry a label that is not a SEBI category at
  all: "Income" (1,640), "IDF" (870), "1099 Days"… These are mostly old or
  closed schemes.
- **785 live funds** carry pre-2018 labels (the first estimate was 96). The
  inherited blocklist missed 185 of them, and "Income" with 110 live funds was
  big enough to look like a real peer group. **Fixed with an allowlist of the
  five SEBI scheme types.**
- **37 open-ended buyable funds** were missing from their real category,
  because the label follows each AMC's own spelling ("Thematic Fund" vs
  "Sectoral/ Thematic"). Mapping these needs a human: an automatic
  nearest-name match filed "Thematic" under "Contra".
- The passive-fund regex had **3 false positives** (inflation-*index*ed bond
  funds). The fixed regex agrees with AMFI's own classification **98.4%**, with
  zero misses. A better signal was found: a passive fund's name contains its
  whole benchmark (overlap 1.00 vs ~0.05 for active funds).

### 28.6 Holdings you type can lie

- **Name vs code.** Holding 119533 was typed "ICICI Prudential Corporate Bond
  Fund"; AMFI publishes that code as **Aditya Birla Sun Life**. Every number was
  right, but about a different fund.
  - **Fix:** `misnamed_as` compares the **fund house**, not the name string.
  - Plain name comparison was rejected: it fires on "PPFAS".
  - Shared-word matching was rejected: both names contain "Corporate Bond
    Fund".
- **Plan type.** Cost review first ran only for people who did not need it:
  plan type was read from the typed name, while TER is filed under the direct
  code. Now plan type comes from the AMFI code.
  - 3,762 of 4,136 regular plans paired with their direct twin (91%).
  - 1,489 of 1,500 resolved, with **0 resolved to the wrong fund**.
- **Dead funds in rankings.** Before the fix, 4–6 dead funds sat in every major
  category. Sundaram Multi Asset ranked #6 of 23 **while closed for 7.6 years**.
  Now anything with no NAV for 30+ days is excluded and named.
- **The biggest risk in the whole app** (plan §11.7): every rupee rests on
  hand-typed transactions that nothing checks against reality. Planned checks:
  - rebuild each purchase from that day's real NAV;
  - read plan type from the code, not the name;
  - reconcile against Groww's read-only portfolio once Manan allows it.

### 28.7 Smaller source findings

- **mfapi** mirrors AMFI to 4 decimals but lags by a day, or by 4 days on
  2026-09-23. Its list endpoint once returned half the schemes.
- **AMFI's daily file** carries each fund's *latest* NAV, not today's: 5,407
  rows were over a year old. It has zero-NAV placeholder rows before launch.
  Bachatt's own AMFI loader parses **0 of 14,283 rows** silently.
- **The holdings feed** was never really missing; only the *API* was. AMC
  monthly spreadsheets exist for every AMC.
- **No free source** exists for the SEBI Potential Risk Class, YTM or duration
  (debt fund risk), the G-Sec yield, or CPI (needs a key). This is why debt
  funds cannot be ranked properly (§16.3).

---

## 29. The Bachatt teardown

**Sources:** `docs/bachatt-teardown.md` (2026-07-27) and a code-level read on
2026-08-10.

**What Bachatt is:** a Flask app on Postgres (AWS RDS, ~22M NAV rows) with
Redis, 77 endpoints and 54,586 lines. There is **no machine learning**. The only
optimiser is scipy's SLSQP. "AI" is Gemini writing text. One summary: *"their
plumbing is better than ours, their evidence is worse."*

### 29.1 How Bachatt scores a fund (ported exactly into `screener/scoring.py`)

```
consistency = 0.50·roll1y + 0.25·roll6m + 0.15·roll3m + 0.10·roll1m   (rolling means)
performance = 0.55·ret3y  + 0.30·ret1y  + 0.15·ret3m                  (point to point)
quality     = 0.45·consistency + 0.40·performance + 0.15·(1 − volatility)
final       = 0.73·quality + 0.15·momentum(14 days) + 0.12·(1 − drawdown(14 days))
```

**Normalisation** blends percentile rank with magnitude, weighted by horizon:

| Metric | Rank weight | Magnitude weight |
|---|---|---|
| roll 1y | 0.70 | 0.30 |
| roll 1m | 0.90 | 0.10 |
| ret 3y | 0.70 | 0.30 |

Magnitude is capped at 0.95. Days with a >25% move are neutralised first.

**Grades:** ≥p90 Very Good, ≥p65 Good, ≥p30 Average, else Bad.

**About 85% of the score is trailing record, 27% comes from a two-week window,
and cost has zero weight.**

**Risk tier**, "the best thing in the repo":

| Input | Weight |
|---|---|
| Volatility | 55% |
| Drawdown | 25% |
| Sortino | 15% |
| Momentum | 5% |

It was built because SEBI's riskometer calls 100% of equity funds "Very High".

### 29.2 How Bachatt builds a basket (ported into `screener/basket*.py`)

1. Templates.
2. Minimum-investment filter.
3. Rank the curated ~180-fund pool.
4. Swap toward six **preferred AMCs** (ICICI, Axis, ABSL, Nippon, UTI, Invesco)
   within a 0.03 score gap.
5. SLSQP: maximise score minus 0.05×volatility, with a soft "worst 30-day
   return" floor.
6. A repair loop.
7. Round to ₹10.

**Market regime:** Nifty vs its 50- and 200-day averages, P/E vs its 5-year
average, and India VIX, with crash-recovery phases.

**What porting it uncovered** (100 differential tests, all confirmed by running):

- **The strategy and regime settings do nothing.** All nine combinations agree
  to 2.11e-15, because the constraint is soft and always violated.
- **The "smooth minimum" is far more pessimistic** than the true worst month
  (−18.1% vs −12.6%).
- **The final weights breach the caps the solver respected.** A 0.40 cap comes
  back as 0.48; a 15% gold cap as 16%. The overlay always runs and tilts toward
  the last fortnight.
- **The bounds check rewrites the caller's caps.** A 15% commodity limit becomes
  25.02%.
- **It crashes under pandas 3**; ours does not.
- **Under 30 days of history** silently produces duplicate windows.

**NexTrade returns both the solver's in-bounds answer and the adjusted one.**

### 29.3 Where NexTrade was behind ("and it is not close")

From the teardown's 14-row table. Status as of today:

| Gap | Status |
|---|---|
| Minimum investment per fund | closed via Groww data |
| Expense ratio synced | closed (and scored, which Bachatt does not) |
| AUM | closed |
| Rolling returns, hybrid normalisation, nightly precompute | closed in the Screener port |
| Risk tier, return windows | ported in the Screener; not in our own score |
| Market regime (Nifty vs moving averages, P/E, VIX) | **not ported**. Only the optimiser's regime *setting* exists, and it changes nothing (§29.2) |
| Diversification rules (max 2 per sub-category, AMC spread) | **still absent** |
| Claim discipline (a reason is shown only if the fund is top 15% AND rank ≤5 with ≥5 peers) | adopted in `screener/reasons.py` |

### 29.4 Where NexTrade is ahead

- Tax under both regimes.
- Goal-specific inflation.
- The whole balance sheet (EPF, PPF, FD, ESOP).
- Real XIRR from real transactions (Bachatt simulates a ₹1 SIP).
- Honest benchmark caveats.
- Free data.
- **Direct plans only.** Every fund Bachatt distributes is a Regular plan: 125
  matched, regular median TER 1.42% vs direct 0.63%. On ₹15,000/month for 15
  years at 12%, that drag is **₹4,20,560**.

### 29.5 Deliberately not copied

- **`PREFERRED_AMCS`:** "distribution economics wearing a quality ranking's
  clothes".
- **Leaving cost unscored.**
- **Survivorship in backtests.**
- **Mean-variance optimisation for a retail SIP.**
- **LLM-written reasons over numbers.**
- **Bachatt's name in the product:** a test forbids it.

---

## 30. Competitor research

*Four research agents, live fetches, 2026-08-21. Anything unverifiable is marked
as such in the vault note `traa-competitors.md`.*

### 30.1 Univest (Manan asked for this one)

Manan: *"univest ui ux was a boom this was like really next level designing"*.

**Verdict:** the design craft is real and the substance is thin. *"Craft copy
karo, claims nahi."*

**Registrations**, confirmed on SEBI's database:

| Registration | Entity | Number |
|---|---|---|
| Research Analyst | Uniresearch Global | INH000013776 |
| Investment Adviser | Uniapps Investment Adviser | INA000017639 |
| Broker | Univest Stock Broking | INZ000317437 |

The app company itself is not registered.

**Design worth taking:**

- **Type:** Inter Tight display, Inter body, a 3.4× body-to-headline scale
  (NexTrade was 1.7×).
- **Named checks with dots** ("PE ratio — Company PE is lower than the sector
  PE").
- **A near-term / long-term toggle** and inline "what is this?".
- **The best thing on it:** *"Price moved −196.70 (21.23%) since then"*. It
  marks its own past call to market, and is the only app in the survey that
  does. *"Humein isse behtar karna chahiye."*

**What is missing:**

- the sector median number;
- thresholds and downside;
- cost;
- position sizing (refused in their own words);
- conviction and per-call risk;
- invalidation criteria;
- a defined track record. The "86% accuracy" claim has no definition, and their
  own terms say performance is *not* verified by PaRRVA.

**Trust signals:**

- a flat 5.0 Play Store rating across ~47k reviews (implausible);
- Trustpilot 2.8 (auto-renew complaints);
- inconsistent pricing;
- a "GET 3 FREE TRADE PICKS" marquee. Do not copy.

### 30.2 The Indian field: 15 apps

The apps: Groww, Zerodha, Tickertape, Screener.in, INDmoney, Smallcase, ET
Money, Dhan, Trendlyne, Value Research, MarketsMojo, Finology, Angel One,
Upstox, Paytm Money.

**Seven gaps every one of them leaves:**

1. No rupee total cost on the buy screen.
2. No audited track record.
3. Ratings don't say whether they are relative or absolute (Value Research stars
   are a forced curve: top 10% = 5★).
4. The decisive output is paywalled.
5. No volatility-to-rupee-loss conversion.
6. No confidence or sample size on calls.
7. No automatic drawdown stop.

**Ideas worth taking, ranked:**

1. **Zerodha Nudge's trigger list:** illiquid stocks, promoter pledges,
   surveillance lists, >50% in one stock or sector. Friction, not blocks.
2. **ET Money's plain-English ratio translations.** NexTrade's `plain_words.py`
   is the same idea.
3. **Screener.in** labels its pros and cons as "machine generated".
4. **Value Research's data-sufficiency rules:** 3 years of history, ≥10 funds,
   ≥₹5 cr AUM, otherwise "Unrated".
5. **Zerodha Console's MF look-through.**
6. **Dhan's worked rupee brokerage example.**
7. **Upstox's two-layer risk** (category vs fund).
8. **Trendlyne's expectation-setting line.**
9. **Finology's "not investment advice" at the point of use.**
10. **Zerodha Kill Switch:** *"trading frequency is usually inversely
    proportional to profitability."*

**Named failures:**

- **Groww** shows a bare "Rating: 5" while the same fund ranks 30th on 3-year
  return, and its AUM figure is 14× off (it shows the AMC total).
- **Paytm Money** shows a dial reading "moderate" beside text saying "very high
  risk".

### 30.3 Global references

- **Morningstar Medalist:** People 45 / Process 45 / Parent 10, with **no
  performance pillar**.
- **Simply Wall St Snowflake:** 5 axes × 6 binary checks.
- **Vanguard, Wealthfront, Betterment:** Monte Carlo ranges, never a point
  estimate.
- **Koyfin and Kubera:** dense, calm dashboards.
- **Ghostfolio X-ray:** take the pattern, not the AGPL code.

---

## 31. The outside evidence base, graded

Manan asked *"yeh logic apne kahan se seekha"* (where did this logic come
from?). The answer is recorded with a grade, and with one rule: **do not quote
weak evidence as if it were strong, and do not cite what was not actually
read.**

### 31.1 Strong, replicated, load-bearing

- **Morningstar, *Predictive Power of Fees* (Kinnel, 2016).**
  - "Success" = survived **and** beat its category, with dead funds included.
  - Success rate by cost quintile, cheapest to dearest, US equity: **62 / 48 /
    39 / 30 / 20**.
  - The pattern is monotonic in all six asset classes (bonds: 59 → 17).
  - Expensive funds lose *more* than their fee.
  - Fees were a **weak** predictor of volatility.
  - ⚠️ The primary PDF was read on 2026-07-30. A later review (2026-08-27)
    could not re-verify the quintile figures and marked them "do not quote on
    screen". The direction stands.
- **Carhart (1997):** fund performance does not persist once momentum is
  accounted for. Only the bad tail persists, largely because of cost.
- **Brinson, Hood & Beebower (1986, 1991):** asset allocation explains ~93–95%
  of return variation across pension plans.
- **Berk & Green (2004):** skill is real but mostly absorbed by fees.
- **Barras, Scaillet & Wermers (2010):** ~75% of funds have zero net alpha.
- **Bessembinder (2018):** 57.4% of US stocks lost to T-bills over their
  lifetime; the best 4% created all the net wealth. Concentration's *typical*
  outcome is underperformance.
- **Volatility is forecastable, returns are not.** Volatility R² is 0.4–0.73,
  about 100× more forecastable than returns. The best machine-learning
  out-of-sample R² on monthly stock returns is 0.33–0.40% (Gu, Kelly & Xiu
  2020).

**The product rule that follows:** **predict risk, cost and tax; refuse to
predict return.**

### 31.2 India-specific

| Source | Finding |
|---|---|
| **SPIVA India** (Mid-Year 2025) | Large-cap active funds behind the index: 75.0% (1y), 74.2% (3y), **84.4% (5y)**, 76.3% (10y). 98.5% of Indian bond funds trail over 10 years. |
| **SEBI F&O study** (Sep 2024) | **93% of individual F&O traders lost money** (FY22–FY24); aggregate losses above ₹1.8 lakh crore; average loss ₹1.2 lakh; 75% earned under ₹5 lakh. One note says 91%, likely FY24 alone. |
| **SEBI small-cap stress test** | The ten largest small-cap funds need 27–44 days to sell half their portfolios. |
| **AMFI SIP stoppage ratio** | 109% in Jan 2025, but it counts matured SIPs as stopped. |
| **India 2024–25 correction** | Lumpsum inflows fell 40% while SIP flows fell only 2%. |
| **IIM-A** | In India only profitability and safety carry alpha; growth and payout do not. |
| **Guha Deb (2019)** | Indian losing funds keep losing. NexTrade's own data disagrees, and both are shown. |
| **A 19-year NSE momentum study** | Low-turnover momentum 19.43% CAGR vs high-turnover 8.51% (Nifty 50: 10.41%). Mostly an illiquidity premium, not a free edge. |

### 31.3 Disputed: never quoted as settled

- **The "behaviour gap"** (investors earn less than their funds because of bad
  timing):

  | Source | Gap |
  |---|---|
  | Morningstar *Mind the Gap 2025* | 1.2%/yr |
  | Fulkerson et al. (FAJ 2026) re-analysis | 0.10%/yr (one note says 0.03%) |
  | DALBAR | 0.72pp in 2025, 8.48pp in 2024 (a 12× swing) |

  **Direction strong, size unknown**, so the app puts **no number** on "staying
  invested".
- **The FCA trading-app experiment:** push notifications +11% trading,
  gamification +12%. The paper could not be re-located, so the design stands
  and the numbers do not go on screen.
- **Barber & Odean turnover:** the direction is solid; exact quintile figures
  differ across notes.

### 31.4 Unread, and therefore not cited

*Machine learning and fund characteristics help to select mutual funds with
positive alpha* (JFE 2023). It argues *against* this project's thesis. It
returned 403 twice, so it is flagged as unread: "so nobody treats the gap as
agreement".

### 31.5 What famous investors claim, graded

Grades: **A** replicated, **B** suggestive, **C** narrative, **D** contradicted.

| Claim | Grade | Note |
|---|---|---|
| F&O losses (SEBI) | A | The single most useful fact for an Indian retail user. |
| "Concentration is not free" (Bessembinder; Goetzmann & Kumar) | A | |
| Concentration pays given real edge (Cohen, Polk & Silli) | B | The base rate is against you having that edge. |
| Buffett's record | A | Explained by cheap, safe, high-quality stocks held with leverage (Frazzini et al. 2018); alpha vanishes after those factors. |
| Howard Marks: *calibrate*, don't predict cycles | B | The right voice for the app. |
| Munger's misjudgement tendencies | A (individual biases), C ("lollapalooza") | |
| Dalio's "Holy Grail" (15–20 uncorrelated streams) | A as arithmetic, D in practice | Correlations go to 1 in crises. |
| India's main risk is governance (pledged promoters: Satyam, DHFL, Yes Bank) | B | Marcellus' forensic screen. |
| Inference from one investor's success | D | |
| Market-cycle timing | D | |
| "Circle of competence" as a rule | D | Unfalsifiable. |

---

## 32. Behaviour and decision clarity

Manan, 2026-08-21: *"it should be like bringing 99 percent clarity in
decision… you are the dev pm tester analyser and everything for this, make it
the best."*

**The reframe:** **99% clarity about the decision is achievable; 99% confidence
in the outcome is not.** The project's own harnesses disproved the second three
times.

**The biggest clarity failure in Indian apps** is making the ₹0 decision (which
fund) look like the important one. For a reference user the important ones
were:

| Decision | Worth over the horizon |
|---|---|
| Tax regime | ₹27.6L |
| Save ₹5,000/month more | ₹25.2L |
| Direct plan | ₹11.1L |
| Harvest the LTCG exemption | ₹5.8L |
| Best fund | **₹0** |

**What a "clear" answer must contain (the seven-item definition):**

1. the action in rupees, with a date;
2. why not the alternative;
3. cost over my horizon;
4. worst fall on my amount;
5. a measured hit rate;
6. when the answer changes;
7. what is not shown.

**Research that shaped the screens:**

- **Disclosure "nutrition labels" are unproven.** No outcome study shows
  PRIIPs-KID-style labels work. The FCA reviewed 172 documents: 6% met
  plain-English standards. So the planned **"Decision Card" was dropped**.
- **Named checks instead.** Simply Wall St's Snowflake, Ghostfolio's X-ray and
  Kahneman's Mediating Assessments Protocol converge on decomposed checks. This
  became the `<Check>` primitive (done / todo / fact / unknown, deliberately not
  good/bad).
- **Algorithm aversion.** People abandon an algorithm after seeing it err once
  (Dietvorst 2015), but rely on it again if allowed a *bounded* adjustment
  (Dietvorst 2018). This is why the return-assumption slider exists and is
  bounded to 4–16%.
- **Reference class first** (Kahneman & Lovallo 1993; the UK Treasury Green Book
  mandates it). Base rates come **before** the fund's own story.
- **Selling is where people lose.** Akepanidtaworn et al. (*Journal of Finance*
  2023, verified from the abstract): professional sells underperform random
  sells. The "~80bps" size is not in the abstract and is not quoted. So any
  sell prompt must be mechanical and pre-committed, never a reaction to a price
  move.
- **Regulators fine gamification.** Massachusetts fined Robinhood $7.5M (Jan
  2024) for "celebratory imagery tied to the frequency of trading"; FINRA fined
  it $70M (2021). Hence: no confetti, streaks or price alerts, and daily P&L one
  tap away, not on the home screen.

**The unanswered problem.** Choi, Laibson & Madrian (2010): people choosing
between four *identical* S&P 500 index funds that differed only in fee **still
did not pick the cheapest**, even when fees were made obvious. NexTrade's whole
thesis is "cost matters". This says displaying cost clearly may not be enough.
It needs an experiment, not a layout.

---

## 33. Advisor methodology and planning numbers (researched, partly built)

These were researched on 2026-07-21 for the advisor. **Most are not yet in the
code**; they are the reference for future work.

### 33.1 Debt funds need a different framework

- Rank on **cost, the SEBI Potential Risk Class, and duration fit**, not on
  Sortino or returns.
- **Modified duration** is the sensitivity number: duration 3.2 means a 1% rate
  rise costs about 3.2% of NAV. Match it to the goal's horizon.
- **A yield more than ~1.5% above the category median is "not skill, it is worse
  paper".**
- **Franklin Templeton's 2020 wind-up was visible months ahead** in public data:
  - yields far above peers;
  - ~88% of the credit fund rated below AA;
  - heavy unlisted debt;
  - past side-pockets.
- **Warning-sign screen: flag a fund if any two of these hit.**

  | # | Sign |
  |---|---|
  | 1 | Yield > category median + 1.5% |
  | 2 | Below-AA+ holdings > 20% |
  | 3 | Unrated + unlisted > 10% |
  | 4 | Top issuer > 8% |
  | 5 | Any past side-pocket |
  | 6 | Duration outside the category band |
  | 7 | Direct-plan TER > 0.75% |

- **Never recommend a credit-risk fund.**
- **Blocked:** yield, duration and the risk class exist only in AMC PDF
  factsheets. Today the app ranks debt on cost and category fit, and **says on
  screen** that credit risk is not measured.

### 33.2 Equity screens that survive scrutiny

- Gross profit over assets is the cleanest profitability measure.
- **Beneish M-Score** catches 76% of manipulators at a 17.5% false-positive
  rate. Use it as one input, never a verdict.
- Use the **Altman Z''** emerging-market version.
- Exclude banks and NBFCs from both scores.
- **Cheapest red flag:** cash from operations below net profit for three years
  running.
- **No DCF point estimates.** A reverse DCF ("the price implies X% growth") is
  honest.

### 33.3 Planning numbers for India

- **Priority waterfall:**
  1. emergency fund;
  2. insurance;
  3. any debt above ~12% (credit cards run 36–48%);
  4. tax-advantaged investing;
  5. goal SIPs.

  An 8–9% home loan is not a blocker.
- **Emergency fund:** 6 months of expenses; 9–12 for single or unstable income.
- **Term cover:** 10–15× income. **Health cover:** ₹15–25L for a metro family
  (medical inflation 13–14%), as a base policy plus a super top-up.
- **Endowment policies** return 3–5% IRR; flag them if held.
- **Retirement:** 30–40× annual expenses (a 3–3.5% withdrawal rate, not the US
  4%). No rigorous Indian study exists, so 3% is a prudent convention, not
  evidence.
- **Instruments:**

  | Instrument | Rule |
  |---|---|
  | EPF | 8.25% |
  | PPF | 7.1%, fully tax-free |
  | Sukanya Samriddhi | 8.2%; beats PPF for a daughter's education |
  | NPS | mainly worth it via employer 80CCD(2) |
  | Sovereign Gold Bonds | **discontinued** (none since Feb 2024) |
  | International funds | mostly closed to new money |

- **Nomination is not succession.** The Supreme Court settled in 2023 that a
  nominee is a trustee for the legal heirs, so a nomination without a will
  invites a dispute.
- **Gain harvesting:** India has no wash-sale rule. Selling and rebuying ~₹1.25L
  of long-term equity gains each year resets the cost basis, saving ~₹15,600 of
  tax. Do it by mid-March.

---

## 34. Tax research

**Verified for FY 2026-27 on 2026-08-27, against the Income Tax Department's
own portal where possible.**

### 34.1 What did and did not change

- **No rate or limit changed** in the 1 Feb 2026 Budget:

  | Item | New regime | Old regime |
  |---|---|---|
  | Slabs | nil to ₹4L, then 5/10/15/20/25/30% in ₹4L steps to ₹24L | nil to ₹2.5L, 5% to ₹5L, 20% to ₹10L, 30% above |
  | Standard deduction | ₹75,000 | ₹50,000 |
  | 87A rebate | to ₹12L | to ₹5L |
  | 80CCD(2) | 14% | 10% |

  Also unchanged: 4% cess; 80C ₹1.5L; 80CCD(1B) ₹50k; equity STCG 20%, LTCG
  12.5% above ₹1.25L.
- **The law itself changed.** The **Income-tax Act 2025 replaced the 1961 Act on
  1 April 2026**.
  - 80C is now **Section 123** (three sources).
  - Other renumberings have a single source each and are not hardcoded.
  - Returns for FY 2025-26 still use the old numbers. New-Act forms are expected
    around April 2027.
  - **So the app shows both:** "80C (now Section 123, Income-tax Act 2025)".
- **A guard test** fails when the financial year passes the one named in
  `tax_regime.py`. Its first version was inert and was caught by mutation.

### 34.2 Defects found by checking code against the statute

1. **No surcharge at all** in `tax_regime.py`, since the start. It biased the
   regime comparison toward the new regime exactly where the money is largest.
   - Rates: 10% from ₹50L; 15% from ₹1cr; 25% from ₹2cr; above ₹5cr, 25% (new)
     vs 37% (old).
   - **Marginal relief:** without it, earning ₹1 over ₹50L adds about ₹1.4L of
     tax. Acceptance: *one rupee more income, at most one rupee more tax*.
     Measured at exactly ₹1.0000 before cess (₹1.04 after cess) at all four
     thresholds in both regimes.
   - **Capital gains carry surcharge of at most 15%**, verbatim from the ITD
     portal. That means `min(slab surcharge, 15%)`, **not** a flat 15%, which
     would overcharge the ₹50L–1cr band (they owe 10%).
   - **Fixed in slice 1.3.**
2. **Long-term vs short-term was counted in days (365), but the law counts
   months.** Section 2(42A) says short-term is "not more than twelve months".
   - The two disagree whenever 29 February is spanned: about one purchase date
     in four. The app showed 12.5% tax where 20% was owed.
   - **Fixed with calendar-month arithmetic.** On the boundary day itself, the
     app says "one more day removes all doubt".
3. **The ₹1.25L LTCG exemption is Section 112A, equity only.** It must never be
   applied to gold, debt or international funds (Section 112).
4. **Premature SGB redemption** became taxable from 1 April 2026.

### 34.3 The tax lever is priced from where you are

The new regime is the default, so most salaried people already have its saving.
The app once showed ₹2,45,700/yr (₹36.8L lifetime) to everyone, which is
"jhooth" (a lie).

Now:

- already on the cheaper regime → **₹0, "Already done"**;
- on the dearer one → full amount and which way to move;
- equal → no lever.

### 34.4 When to re-check

- Small-savings rates: quarterly.
- EPF: February–June.
- The Budget: every 1 February.
- New-Act ITR forms: around April 2027.

---

## 35. Regulation research

**In plain words** (from the plan's §8):

- **One person using it alone** is outside SEBI's Investment Adviser definition:
  nobody else receives advice, there is no fee, and there is no business.
- **Free use by a few friends** is a grey zone. Every enforcement action found
  involved a fee or a sales funnel, but no regulation has a client-count
  exemption.
- **Publishing it publicly is where real risk starts**, through two routes:
  - "holding out" as an adviser, which needs no fee;
  - SEBI's post-2023 test, which treats specific buy/sell calls as advice "however
    labelled".
- **SEBI's AI/ML guidelines** are a consultation paper (June 2025), not a
  circular, and they apply to registered entities. Two "circulars" quoted by
  secondary sites could not be found and are treated as fabricated.
- **DPDP Act (data protection):** the substantive duties start **14 May 2027**.
  They apply the moment the app stores another person's data.

**What keeps the app on the right side:**

- no fee;
- not public;
- never places orders;
- no specific "sell X" calls (the refusals in §11 remove that surface);
- analysis rather than advice.

**What would change it:** a fee, going public, issuing buy/sell calls, storing
others' data, or SEBI turning the AI paper into a rule.

**Credential finding** (plan §8.1): Google login used to request an *offline*
refresh token that was never used and was stored in plain text (on Turso in
production). **It was removed**; the auth router now says so in a comment.
Lesson: *"Client count is the wrong axis for this risk."*

**Product-level rules researched:**

- SEBI's riskometer wording.
- The past-performance disclaimer must sit right after the returns, in the same
  font.
- The adviser vs distributor split.
- **PaRRVA** (SEBI's past-performance verification agency) is real. No Indian
  app's track record is verified by it.

---

## 36. AI research

- **The model is pinned by Manan:** *"hum sirf only and only yeh model use
  karnege — gemini-3.1-flash-lite."*
- **Checked live (2026-08-27):**
  - 38 models are listed; `gemini-2.5-*` returns 404 for new keys.
  - The `thinkingBudget` setting is rejected by 3.x models; use `thinkingLevel`
    or omit it.
  - 3.x replies carry a `thoughtSignature`, so read `parts[0].text`.
  - Structured JSON output works (schema, enums, arrays).
- **Why grounding is non-negotiable:**
  - Asked about "TER 0.63 vs median 1.02" with no context, the model explained
    *Translation Error Rate*.
  - On FinanceBench, a model answering from memory scored 9%; grounded, 85%.
  - So every prompt states the domain and the units.
- **Why tools take names, not ids:**
  - The model filled a fund's scheme code from memory (correct that time).
  - For a fake fund it put the whole fund **name** into the code field, and a
    prompt instruction forbidding this failed in both modes.
  - A `resolve_fund` tool fixed it. **Rule: no tool takes an opaque identifier;
    resolvers are the only source; the backend validates.**
- **Rate limits:**
  - One run hit a 429 at request 16 (~15/minute).
  - A later key handled 40 in 41 s and 60 in 4.8 s.
  - Google no longer publishes free-tier limits, so the design assumes the
    lowest ever seen.
  - Narration is **on demand** (about 50 calls on a heavy day), never for all
    1,686 funds (that would take 113 minutes).
  - Batch and explicit caching are unavailable on the free tier.
- **The narration contract** (plan §17):
  1. Every figure comes from the tool output.
  2. Digits, never spelled-out numbers.
  3. Every figure names its source field.
  4. A row from a list names its subject in the same or the previous sentence.
  5. If the data does not answer, say so and stop.

  The model returns sentences **plus** a list of claims. `check_all` validates
  them. On a failure it retries **once**, with the failure message appended;
  after that the screen falls back to a template with a visible "computed" chip.

  Cache key = hash of (tool data + normalised question + model + prompt
  version), 30-day TTL. **The screen must be correct with AI switched off.**
- **Grounding's own history**, where every fix once caused the next bug:
  - It compared claims to the data and never to the text. Now the subject must
    appear in the sentence.
  - Its path-ambiguity rule rejected **95.7%** of correct citations and caught
    nothing. Now 0.2%.
  - A Unicode minus sign parsed as positive.
  - A plural key (`isins`) reopened an ISIN hole.
  - **Tested on 757 real goal explanations: 0 invented figures.** 46 flags were
    all the user's own goal names quoted back, now exempt.

---

## 37. Design research

**Manan's brief:** *"visually dekh kar maza aana chahiye, lagna chahiye
financial site"*, *"UI/UX 0 hai"*, *"lively sa hona chahiye, 3D design jaisa"*,
*"ek dum clear navigation"*, *"dekh kar samajh aa jaye"*.

**Five research agents reached one verdict:** *"Token system galat nahi hai.
Composition galat hai."* The colour tokens were fine; the layout was the
problem.

**Four measured defects, and their status on 2026-10-02:**

1. **The Screener was a 32,456-pixel page** (~1,700 rows). **Resolved
   differently:** 100-row pagination, a deliberate decision not to add
   virtualisation.
2. **Loss red is 53% more saturated than gain green** (chroma 0.196 vs 0.128).
   The spec says lower it to 0.145 and add ▲/▼ glyphs so colour never carries
   meaning alone (~8% of men have red-green colour blindness; WCAG 1.4.1).
   **Not applied yet:** `index.css` still has 0.196, and no ▲/▼ appears in the
   source. (The claim that "red distorts judgement" did not replicate.)
3. **The headline number is in a code font.** The spec says Inter Tight.
   **Partly applied:** headings use Inter Tight, but the Portfolio hero figure
   still uses the monospace `.num` class.
4. **Recharts on defaults**, and heavy. Kept for hero charts only; sparklines are
   hand-drawn SVG (built).

**References studied:** Koyfin (dense tiles), Kubera (zero shadows), Linear
("structure should be felt, not seen"), Vercel Geist ("default to stillness"),
Simply Wall St, Univest's type scale, and Groww's page layout (copied for the
fund and stock pages, then improved: every ratio carries its sector median).

**The system that came out of it** (plan §13):

- "An instrument, not a dashboard."
- Elevation by tint, not shadow.
- Eleven UI states. The cold-start "waking" state is the most frequent.
- Eight chart devices.
- A badge grammar: only the money badge is tinted.
- Motion only in response to a user action, never counting numbers up.
- **Forbidden:** decorative gradients, glows, glass, badges for metadata, a
  sparkline on every card, a progress bar with no denominator ("Portfolio Health
  78%"), and showing `groww_rating` as a rating.
- Self-rated on a 0–10 scale per dimension (direction 9, states 9…). It is "not
  a 10 until there is a screenshot of the built thing".

---

## 38. Research inventory, open questions, and where the sources disagree

### 38.1 Every research question asked so far

- **Measurements (§22–§27):**
  - fund picking, five ways;
  - cost and its lookahead;
  - the exit signal;
  - base rates;
  - the stock score;
  - factors on our own universe;
  - IIMA factors;
  - momentum in crashes vs rebounds;
  - correlation of a real portfolio;
  - holdings overlap and look-through;
  - the overlap distribution;
  - dead funds in rankings;
  - the effect of real delivery %;
  - peer-line correctness on the fund page (it once showed +133.5% where the
    truth was −29.5%);
  - NAV store size and backfill time.
- **Data probes (§28):**
  - mfapi, AMFI (NAV, TER, AUM);
  - Groww (760 endpoints);
  - Zerodha (154);
  - NSE archive, filings and corporate actions;
  - yfinance quirks;
  - Screener.in;
  - the IIMA library;
  - AMC spreadsheets;
  - free macro data (none);
  - the SEBI risk class (not free).
- **Competitors and design (§30, §37):** Univest; 15 Indian apps; global apps;
  open-source prior art; Groww's page layout; visual references; table
  libraries.
- **Regulatory (§35):**
  - SEBI adviser rules;
  - the AI/ML paper;
  - DPDP;
  - riskometer and disclaimer rules;
  - PaRRVA;
  - Univest's registrations;
  - Robinhood and FINRA enforcement;
  - the Feb 2026 SEBI recategorisation;
  - TER limits.
- **Tax (§34):**
  - FY 2026-27 values;
  - the new Act's renumbering;
  - surcharge and marginal relief;
  - the capital-gains cap;
  - SGB changes;
  - LTCG scope;
  - holding period in months.
- **AI (§36):**
  - model availability and traps;
  - structured output;
  - function calling and resolvers;
  - rate limits;
  - grounding accuracy;
  - the ML-model bar.
- **Literature (§31–§32):**
  - fees;
  - persistence;
  - behaviour gap;
  - selling;
  - gamification;
  - disclosure labels;
  - algorithm aversion;
  - reference classes;
  - concentration;
  - AUM size;
  - trailing stops;
  - Choi/Laibson/Madrian.

### 38.2 Open research questions

1. **The honest size of the cost effect without lookahead.** Run it on Groww's
   TER history for every buyable fund.
2. **Value (HML) on our own universe.** It works on IIMA data (t = +2.39) and has
   never been tested here.
3. **Fundamentals with 12 years of Screener.in data.** yfinance's 4–5 years
   cannot answer this.
4. **Does manager tenure predict anything?** The data now exists; the evidence
   does not.
5. **Debt-fund credit risk.** Needs PDF factsheet parsing.
6. **Choi, Laibson & Madrian.** Does showing cost clearly change behaviour? Needs
   an experiment.
7. **Momentum on 26 years of NSE archive data** (Phase 2).
8. **The stock score ledger** reaching 5 years.

### 38.3 Where the sources disagree (check before quoting)

| Topic | Disagreement |
|---|---|
| Cost result | 45/52 (87%, Jul 27) vs 43/52 (83%) vs 36/44 (82%): different runs and window sets. Quote the one with its script and date. |
| Behaviour gap after correction | 0.10% vs 0.03% (two notes on the same paper). |
| SEBI F&O losers | 93% vs 91%. |
| Kinnel fee quintiles | Read from the PDF on Jul 30, marked unverifiable on Aug 27. |
| Momentum in crashes | `docs/do-factors-work-here.md` still has the retracted "pays nothing" claim. |
| `track_record.json` → `why_ranges` | Still the old hardcoded sentence until the next rebuild. |
| `docs/why-there-is-no-fund-manager-screen.md` | Attributes 38% and 68% to the wrong document (they come from `validate_lifetime_ranking.py` and `measure_score_edge.py`). |
| NAV store size | 5,181,932 / 5,183,632 / 5,187,035 / 5,309,004 rows on different dates. It grows nightly. |
| AMC holdings coverage | Notes say 6 or 7 AMCs for the spreadsheet parser. Groww now covers all. |
| Plan `phase-1-redesign.md` | Its contents line says 5,426 lines (it is 6,608); §0 says 82 log entries; §1.8 keeps a stale "changes the sign" sentence. |
| `BUILD.md` | Says 1,624 tests; the suite now collects 2,094. Still prices 34 sessions after slice 1, which was meant to re-price everything. |

---

# Part III: how we work

The project is built by **Manan** (owner, only user; he writes in Hinglish and
sets direction) working with **AI coding agents**, mainly Claude Code. The
plan is written so that other engines (Codex, Cursor, Antigravity) can check it.

The standard, in his words: *"koi itna sa bhi minute to inute flaw bhi ni hoi"*.
Not even a tiny flaw.

---

## 39. The loop: from a sentence in Hinglish to a shipped, checked number

```
 1. Manan asks something, in his own words
 2. The request is written down VERBATIM, with the date, in the doc it shapes
 3. Research: repo docs, live probes of real endpoints, papers whose abstracts
    were actually fetched (never cited from memory)
 4. A MEASUREMENT with CONTROLS, before any opinion
 5. A plan section "written to be attacked"
 6. Adversarial review passes, each using a NEW method (§40)
 7. A build SLICE with an acceptance criterion that CAN FAIL (§41)
 8. Test first → code → mutation/sabotage → harnesses → check.sh green
 9. A commit whose body says what broke, how it was found, what was not done
10. Plan doc, memory notes and the Obsidian vault updated. Counts re-totalled
    by tests, never by hand.
```

### 39.1 Worked chain 1: the cost data that silently went missing

1. **Passes 117–123 of the plan review found it step by step:**
   - the "live funds" proxy was hiding 353 funds;
   - 23 whole fund houses had no TER;
   - probing AMFI directly showed id 63 = Groww, 64 = PPFAS, 77 = Zerodha,
     82 = JioBlackRock;
   - the scorer gave these a made-up average cost;
   - 9% of the ranked universe was affected.
2. **Pass 131:** *"the fix is a rule, not a number."*
3. **`BUILD.md` §0:** *"Fix this first; it is one function."*
4. **Commit `2c4393f`** (slice 0.2/0.3):
   - walk until 8 consecutive empty ids;
   - print coverage on every run;
   - replace a docstring that had wrongly said the missing funds were "mostly
     ETFs and closed-ended".
   - The guard test itself turned out to be a false negative (it matched the
     defect string inside a comment). Rewritten and confirmed by mutation.
5. **Commit `6b55bbf`:** the rebuild exposed a second bug. The builder
   *replaced* the file instead of merging it, losing 112 funds. Fixed. 97% of
   buyable funds now carry a cost.

### 39.2 Worked chain 2: the badge that could never fire

1. **Pass 136:** the catalogue holds **zero** regular plans (on purpose: it is
   the recommendation universe). So "Regular plan: Direct saves ₹X/yr", the
   largest number the app would ever show, could never fire for the person it
   exists for.
2. **Pass 137** checked the fix pass 136 had just proposed (a shared AMFI code
   stem) and found **it does not exist**. The real link is the normalised scheme
   name.
3. **Pass 151:** Manan said *"app groww random koi apni marzi se portfolio bana
   kei karlo"*, so a realistic portfolio was invented (5 real funds, ₹2,47,827).
   It confirmed the gap.
4. **Commits `b02350a` and `816ef9a`:**
   - 3,762 of 4,136 regular plans paired with their direct twin (91%);
   - 1,489 of 1,500 resolved, **0 to the wrong fund**;
   - 4 mutations run, 3 survived, so 3 tests were added.
5. **Commit `cc50d48`:** the badge's four numbers:

   | Line | Example | Meaning |
   |---|---|---|
   | saves | ₹5,000/yr | 1.0pp on ₹5,00,000 |
   | exit load | ₹0 | a true cost, gone for good |
   | tax brought forward | ₹9,375 | **not a cost**: the cost basis resets |
   | its real cost | ₹1,125/yr | the return forgone by paying the tax early |
   | breakeven | — | against the user's own horizon |

   The distinction is in the code because it **flips verdicts**. With a ₹4,000
   exit load over two years, the honest maths pays back in about a year. Treating
   the ₹9,375 as money spent would push breakeven past the horizon and tell the
   user to "leave it" in an expensive fund.

   Three things the arithmetic refuses to assume:
   - the ₹1.25L exemption is shared across all equity gains, so each holding gets
     its allocated slice;
   - it is equity-only;
   - short-term gains are taxed at 20%, not 12.5%.

   It is **`grounding.py`'s first real caller**, shown failing against a
   fabricated tenfold overstatement. Six mutations, six caught.

---

## 40. Adversarial review: the method behind 152 review passes

**The principle** (plan §18): *"Every pass used a method the previous one had
not. That was the whole technique, and the rate below is the only real evidence
about readiness."*

The plan's front page says 148 passes; that count, pinned by a test, covers
numbered rows 5–152 only. The log itself ends at pass 152.

### 40.1 The methods, and what each found

| Pass(es) | Method | What it found |
|---|---|---|
| 1–4 | Reading the document (2 engineering, 1 product/design, 1 build-readiness) | 41 findings |
| 5 | Document vs **filesystem** | `.holdings/` not gitignored: a live risk |
| 6 | Document vs fresh **measurement** | 2 findings; 3 of 5 checks clean |
| 7, 10 | Document vs **itself** | a slice table summing to 31 against a stated 32; 95.7% written as 95%; all introduced by the previous edits |
| 8 | **"Could someone BUILD from this?"** | 13 of 16 steps had no way to know they were done |
| 9 | Unverified claims, unused tools | the tax portal changed the spec (capital-gains surcharge = min(slab, 15%)) |
| 11 | Plan vs project **memory** | 5 recorded defects missing from the plan |
| 12 | Plan vs **git history** | the deploy architecture had changed 3 days earlier; the largest finding at the time |
| 13 | Plan vs **deploy budget** | free-tier RAM rested on one undocumented in-function import |
| 14 | Plan vs **free-tier UX** | cold start is the commonest state; the API client had no timeout |
| 15 | **Code vs the statute** it cites | 365 days vs 12 months: tax owed understated |
| 16 | A claimed **threshold vs real data** | the 2.25% "ceiling" is not one |
| 17–18 | Re-counting every "zero" / "all N" | "zero false positives" was 3; a sum that was right on the wrong sample |
| 19–21 | The scoreboard vs itself; **run the code instead of reading it** | pass 19 was confidently wrong; reading the producing scripts settled it |
| 22 | A whole **defect class** checked mechanically | undeclared dependencies; the class is now closed by a test |
| 24–27 | Reproduce from retained data; inventory **every payload field** and **every DB column** | 11 years of TER history already shipped by Groww; 757 real AI generations with 0 invented numbers |
| 28–29 | The auth path; migrations and dependencies | an unused refresh token stored in plain text; migrations clean |
| 30–35 | Count what was "already built"; the plan vs the **API that exists** | 0 of 8 chart devices; 49 endpoints, none named in the plan; rules already enforced 24 times in schemas |
| 36–46 | Usability of the document; schedule; user journey; on-ramp step count; design 0–10 rating | the first screen a user meets shipped last; 23 steps to enter five funds |
| 49–57 | **Mutation-test the test suite**; "named by a test" vs "actually called" | own new tests that were decoration |
| 59–75 | The plan vs **the other documents in its own folder** | the 2,330-line PRD had never been opened; two "defects" were the PRD's own spec |
| 76 | Verify the verifier | 8 false alarms, all one off-by-one in the checker |
| 77–97 | Grouping by regex vs reading each row; same fact in two places; Manan's words vs what is written | counts wrong by pattern-matching; the Groww instruction recorded nowhere |
| 98–110 | Repo files vs plan (surface-to-page map) | grep traps: "sidebar" matched a top nav, "trail" matched "trailing returns" |
| 113–130 | Harnesses vs plan; every hardcoded bound; downstream impact; data-file ages; mutate every guard | the AMC-id ceiling that dropped 297 funds |
| 131–152 | Which blocks are real; can each badge fire; reproduce the pivot from the store; lookahead test | the badge that could not fire; the cost effect re-sized |

### 40.2 The finding rate never really fell

```
passes 1-4    41      61-70   18      121-130  27
5-10          12      71-80    9      131-140   7
11-20         11      81-90   17      141-152   7
21-30         20      91-100  16
31-40         12      101-110 12
41-50         12      111-120  9
51-60         13
```

That is about 240 findings across about 151 log rows. After pass 7 the plan
claimed it had "stopped yielding latent defects". Passes 11 and 12 disproved
that. The front page now says:

> *"The rate of finding has not fallen, and a readiness verdict reporting
> otherwise is the one claim here that flatters the document."*

### 40.3 The lessons, quoted

- **"A number in prose is a claim … every one that has been re-counted has
  moved."**
- **"Every confident wrong answer in this whole exercise has come from stopping
  at the artefact instead of going to what produces it."** Read the producer,
  or run it.
- **Read the newest commits before trusting any document.** *"The deployment
  lives in a commit message and a deploy/ folder that no check had a reason to
  open."*
- *"A plan can be internally perfect and still contradict what the project
  already learned."*
- *"Three times now … confidence has been the thing that was wrong."*
- *"A number can be exactly right and still be wrong."* Verify the sample, not
  only the sum.
- *"An off-by-one that lands on every row at once is not eight errors, it is one
  — in the instrument."*
- *"Reading a guard tells you what it intends; running it against the change it
  claims to catch tells you whether it does."*
- *"A finding that names a defect and stops is half a finding."*
- *"Ek aadmi apne hi kaam mein wo galti nahi dekh sakta jo us galti ki wajah se
  hai."* One person cannot see the mistake their own blind spot causes. That is
  why other engines are invited to review.
- **Wrong corrections stay visible.** *"A plan that quietly deletes what it got
  wrong is a plan nobody can calibrate against."*
- **The honest ceiling:** *"Is this plan perfect? No document is … Is it good to
  build from? Yes, and that is a testable claim rather than a feeling."*

---

## 41. Build discipline

**Vertical slices, not layers.** An early order put every screen last, so every
schema, badge and harness decision would have surfaced "in week nine instead of
week one". It became five slices:

| Slice | What | Priced | Built |
|---|---|---|---|
| 0 | The instrument and one-command fixes | 3 sessions | 2026-08-29 |
| 1 | One holding, end to end | 6 | 2026-08-29 |
| 2 | Widen the universe | 6 | 2026-08-29 |
| 3 | The AI layer | 8 | 2026-08-29 |
| 4 | The screens | 11 | 2026-08-29 |

All 32 commits landed between 10:44 and 15:56 IST. **"Session" was never
defined**, so the plan itself says: *treat the numbers as an ordering, not a
schedule.*

**Every step has an acceptance criterion that can fail.** Examples:

- **Tax:** one rupee above each surcharge threshold costs at most one rupee more
  (before cess).
- **Waking state:** tested against a **stopped server**, not a mocked delay.
- **Universe:** *"not 'it ingested' but 'it re-prints the four figures'"*.
- **Backup:** delete the holdings store, restore from the committed dump, get the
  same store. It was run, and it found a backup that erased itself (SQLite's
  `iterdump` drops `user_version`).
- **Gates:** break one document claim and one code behaviour separately; the two
  `check.sh` steps must go red separately.
- **AI:** remove the grounding check in a test and prove a fabricated figure
  **does** reach the screen.
- **Refusals:** *"A refusal set with no test is a paragraph."*

**Show the guard failing.**

- *"A guard that is never seen to fail is a guard nobody knows works."*
- *"A new test is not evidence until something has been broken against it."*
- Commit bodies tally mutations ("Five mutations run, five caught"; "Four
  mutations … three not"), and survivors get new tests.

**Habits named in commits:**

- **Check first, build second.** One commit reverted an overwrite of good sector
  medians with a worse duplicate: *"The rule is check first, build second, and I
  did not."*
- **Delete, don't deprecate.** Old scorers and the pie chart were deleted; a test
  asserts they stay gone.
- **Allowlist over blocklist.** *"A blocklist only excludes what somebody
  remembered to name."*
- **Stop on evidence, not on a constant.**
- **`n/a`, never `0`.** A silent zero "encourages the purchase it should have
  questioned".
- **Validate contracts against real engine output, not hand-written examples.**
  *"A contract validated only against fixtures you chose is a contract validated
  against your own assumptions."*
- **Test the route, not just the engine.** Look-through returned a 500 for
  anyone who actually held something, while every engine test passed.
- **Live smoke test after each data service.** Mocked tests miss wrong response
  shapes. *"A client that passes against a MockTransport and has never spoken to
  Google is a client nobody has watched work."*
- **Fix what you see, now.** Several review passes fixed things on the spot
  instead of filing them.

---

## 42. Verification culture and the 24 rules of measurement

### 42.1 The times a tool said yes while measuring nothing

1. **`shots.mjs`** logged into a *different app*, screenshotted its login page
   14 times, and reported success.
2. **Six scripts** pointed at other projects' ports.
3. **`check.sh` could never fail.** It hid a 119×16 px button, an isolation
   "LEAK" that was really a rate limit, and a consistency harness crashing under
   "All clear".
4. **`why_ranges`** was a constant posing as a measurement. *"A caveat that is a
   constant is decoration."*
5. **The grounding path rule** rejected 95.7% of correct citations and caught
   nothing.
6. **A TER test** used an unknown scheme code, so `None` short-circuited the
   very conversion it tested.
7. **The TER coverage test** matched the defect string inside a comment.
8. **The tax-year guard** scanned the wrong text and was inert.
9. **`test_llm_explainer`** had "never been testing a model": the API key was
   empty.
10. **A stale `.pyc` file:** a same-length mutation left Python's bytecode cache
    "fresh", so tests ran the old code.

**Response:**

- `check.sh` now proves it can fail before anything else.
- Harnesses keep "could not test" separate from "passed".
- Rate-limited calls wait honestly via `PatientClient`.
- A harness whose coverage count drifts (148 → 136) is treated as a failure.

### 42.2 Document tests

Numbers written in the plan are pinned by tests that read the plan:

- the open/closed counts match their tables;
- the stated suite size equals `pytest --collect-only` (*"this test counts
  itself"*);
- headings are in order;
- the nine refusals stay in order;
- the endpoint counts, category variants, TER coverage, data-file dates and
  slider bounds hold.

They run as their own `check.sh` step, so a stale doc never reds the code gate.

### 42.3 The 24 rules of measurement (each born from an incident)

1. **Point-in-time data only.** The stock-score lookahead was worth 4.5pp.
2. **Controls first; they must behave before any row is read.** The NIFTY 50
   benchmark made random look like +4.2%.
3. **A check that cannot fail is decoration.**
4. **Measure within category.** The pooled cost run measured debt vs equity.
5. **Benchmark against the same universe.**
6. **Non-overlapping windows, or say they overlap.**
7. **Cluster on the true independent unit (dates).**
8. **Minimum sample before any claim:** 5 years (stocks), 5 windows (factors),
   4 dates (exit intervals).
9. **Rank IC over the whole cross-section**, not just top vs bottom.
10. **Charge costs.** Quarterly momentum is +2.1% before costs and −1.9% after.
11. **Run universes separately; key results by experiment.**
12. **Include dead funds and state survivorship honestly.**
13. **Attack any suspiciously good number** (the first +15.1%).
14. **Regenerate; don't quote. Quote ranges.**
15. **Cite the producing script for every number. Trace, don't explain.**
16. **Keep "could not test" apart from "wrong".**
17. **Do not flag correct data.** A permanently red gate stops being read.
18. **Builders refuse to write when a canary fails.**
19. **Sabotage proves each check can go red.**
20. **Seeded and reproducible.**
21. **Validators never change what they validate.**
22. **Never show a headline without its variance.**
23. **Unread or unverified sources are not cited.**
24. **Predict risk, cost and tax; refuse to predict return.**

---

## 43. How we write: commits, comments, documents, memory

**Commit subject:** `type: a plain sentence about the outcome or the failure, in
user terms`.

- **Types:** feat, fix, build, test, docs, review, design, rename, revert, perf,
  chore.
- **Examples:**
  - `fix: a fund that failed to load took every other fund's score with it`
  - `test: the stock score's edge inverts when you change the index`
  - `fix: the gate could not fail, and it was hiding three real failures`
- Slice work carries the slice id: `(slice 1.3)`.

**Commit body:**

- the concrete failure first, with numbers;
- how it was found ("found by loading a realistic 14-holding account");
- cause, fix, and the alternatives rejected, with reasons;
- section heads in capitals;
- the author's own mistakes owned ("FOUR THINGS THE CHECKS CAUGHT, ALL MINE");
- what is not done, "stated rather than implied";
- a closing `Checked:` line.

Session trailers (`Co-Authored-By`, later `Claude-Session:`) record who wrote
it.

**Code comments** carry the *reason* and the *incident*, not a restatement of
the code. Examples:

- `check.sh`: *"Without the flag here, seven of the nine checks could not fail."*
- `dev.sh`: *"Failing loudly here costs a second; the silent version cost an
  hour."*
- Comments warn against "fixing" deliberate behaviour (the Research/Screener
  disagreement).

**Documents:**

- Manan's words are quoted verbatim, with a date.
- Closed items are never deleted.
- Every number carries where it was measured.
- Unverified things say so in the same sentence.

**Memory, kept in three places:**

| Store | What goes there |
|---|---|
| The repo's `docs/` | The plan and the research write-ups. |
| The Obsidian vault (`manan-memory/Projects/traa/`) | Measurements, decisions, gotchas, competitors, running notes. The index (`traa.md`) names what to read first. |
| Claude's project memory (`~/.claude/projects/…/memory/`) | One fact per file: lessons, defects, decisions. Indexed by `MEMORY.md`. |

---

## 44. How decisions with Manan are made and recorded

**Mechanics:**

- His request goes in the section it shapes, verbatim and dated.
- Open questions are tagged `decide` (his call) or `Manan` (blocked on him).
- `BUILD.md` lists his pending decisions, marking each DECIDED with a date once
  made.
- **A newer instruction beats an older document.** For example, the free,
  no-card deploy overrides the PRD's ₹500–2,000/month budget.

**Overriding a written rule:** surface it once, then follow his call and update
**both** the rule and its test. *"i m the only user... humare rules hai."* Two
examples:

- Holdings shows a donut because he asked: *"he asked for the donut anyway, so it
  is a second VIEW of the same data"*.
- "Today" was renamed "Portfolio".

**His words that set direction:**

| When | What he said | What it caused |
|---|---|---|
| 2026-07-17 | *"not even 0.1 percent"* | The calculator became a real advisor |
| 2026-07-21 | *"yeh saare mutual funds kyu ni aa rha… stocks ka kuch ni dikh rha"* | The full fund and stock universe |
| 2026-07-29 | *"Mirae Asset Flexi Cap top pe kyun? Kis basis pe, kya logic?"* | Score explanations (§47.3) |
| 2026-07-30 | *"cost ka kya hai, returns matter karte hain"* | The head-to-head study (§23.3) |
| Aug | *"jispe apne 0 rate karaa, yehi toh humme build karna hai"* | The prediction research (§26) |
| Aug | *"mujhe abhi bhi kuch nahi samajh aa rha kya kar rha hai"* | Plain language first, everywhere |
| 2026-08-20 | *"jab tak hum unse ek strong logic nahi dhundte, hum unka ranking system copy karte"* | The Bachatt port |
| 2026-08-21 | *"bringing 99 percent clarity in decision"* | Levers 3 → 8, the decision-clarity work |
| 2026-08-21 | *"proper screen mai funds ka analysis… jaise grow mai"* | Fund and stock pages |
| 2026-08-27 | *"just 1 percent of what i want"* | The Phase 1 redesign plan |
| 2026-08-27 | *"buss tumara goal advisory tak ka hai"* | Scope: advisory only |
| 2026-08-27 | *"groww is the platform we use to invest"* | The universe = Groww-buyable |
| 2026-08-27 | *"kab mujhee pata lag jaye kei investment mai rok laga denaa chaoyee"* | The exit-signal study (§24) |
| 2026-08-27 | *"hum sirf only and only yeh model use karnege — gemini-3.1-flash-lite"* | The AI model pin |
| 2026-08-28 | *"app groww random koi apni marzi se portfolio bana kei karlo"* | The invented test portfolio |
| 2026-09-23 | *"bachatt se humara kuch lena dena ni hai"* | Bachatt as reference only |

He also says *"audit pehle, phir fix"* (audit first, then fix) for UI work, and
asks that no Artifacts be used.

**Decisions he made explicitly** (the Screener plan, 2026-08-20):

- copy the reference method until something better is found;
- backfill all 4,957 funds;
- show every category's top;
- no minimum-investment filter;
- keep delivery neutral and disclose it;
- drop the Fund Manager screen unless its source can be matched;
- "Fund Score" as the label;
- funds before stocks;
- finish one thing before the next;
- one Screener tab with URL sub-views;
- a resumable backfill;
- on 2026-08-21, a faithful stock-scorer port plus a method note.

---

## 45. The tools we use, and the ones that failed us

**What worked:**

| Tool | Used for |
|---|---|
| **Claude Code**, with the shared "manan hub" config (`claude-transfer/.claude`, symlinked into every project) and its tool router | Building, reviewing, research |
| **Parallel research subagents** | Competitors, Groww/Zerodha endpoints, visual direction, evidence base. Told explicitly to return plain text, never Artifacts. |
| **Review lenses**: plan-eng-review, plan-design-review (0–10 per dimension), the security-review skill (caught the public JWT secret), the **Code Reviewer** agent (3 defects), the **Model QA Specialist** agent (4 methodology bugs, plus 1 false claim it rejected) | Adversarial review |
| **Firecrawl** | Mapping AMC disclosure archives, reading Groww's page layout |
| **Local Playwright** + `frontend/scripts/*.mjs` | Every page, both themes, phone sizes, accessibility, screenshots |
| **pm2** | Keeping `traa-api`, `traa-web` and a Cloudflare `traa-tunnel` alive (`nohup` died three times) |
| **The Obsidian vault + Claude memory** | Durable knowledge across sessions |
| **Codex / Cursor / Antigravity** | Named as independent reviewers of the plan; `AGENTS.md` (added 2026-10-02) points Codex at Manan's own tool catalog |

**What failed:**

- **Chrome-extension and Puppeteer screenshots:** repeated errors, so three
  rounds of UI shipped unlooked-at until local Playwright replaced them.
- **The vibe-trading skill:** needed installs and used the same yfinance.
- **Some router suggestions** were irrelevant (perl-security,
  defi-amm-security, flutter).
- **The Obsidian MCP** is misconfigured (wrong port, missing key), so the vault
  is written as plain files.
- **Several web sources** blocked automated reading (SEBI PDFs, FCA papers,
  S&P/SPIVA PDFs), which is why some figures are marked "unverified".

---

## 46. How much to trust each part of the app

Manan asked: *"ek investor ke taur pe, jise zyada knowledge nahi — is app ke
analysis ko kaise rate karoge aur kitna bharosa karke invest karoge?"* (As an
investor without much knowledge, how would you rate this app's analysis, and how
far would you trust it with money?)

The honest answer, recorded in the vault (2026-08-08):

| Part | Rating | Trust |
|---|---|---|
| Arithmetic: tax regimes, direct vs regular cost, XIRR | **9/10** | Full |
| Cost-based fund ranking | 7/10 | Partial: cheap beats expensive, but #1 vs #5 is noise (live #1 at 0.67%, #5 at 0.66%). The real decision is to avoid #34 at 2.72%. |
| Fund overlap (real holdings) | 7/10 | Partial |
| Momentum | 7/10 | Partial: real, and it lost 53% in the 2009 rebound |
| "Which fund will do better" | **0/10** | None |
| Stock timing / signals | **0/10** | None, until the 5-year ledger fills |
| **Overall** | **about 7/10** | Not 9: one builder-tester, and a wrong number has already escaped (0.01% shown for 0.67%). Not 4: the app says what it does not know. |

**What a person should actually do with it:**

1. Use the tax answer today.
2. Switch regular plans to direct.
3. Take any of the 5 cheapest funds in a category.
4. Put only a small slice in momentum.
5. Ignore stock signals for now.
6. Verify one number yourself before any big decision.

---

## 47. Worked examples: what the app tells a real person, in rupees

### 47.1 The levers for a reference user

The reference user has ₹8L invested, adds ₹25,000/month, and has 15 years to go.

| Kind | Decision | Worth over 15 years |
|---|---|---|
| Gate | Clear the credit card at 42% first | priced per year carried (₹30,000/yr), not as a scary lifetime number |
| Gate | Build the emergency fund first | — |
| Lever | Move to the cheaper tax regime | **₹27,60,000** |
| Lever | Save ₹5,000/month more | **₹25,22,880** (range ₹14.6L–₹30.6L) |
| Lever | Move regular plans to direct | **₹11,06,705** |
| Lever | Use the ₹1.25L tax-free gain every year | **₹5,82,496** |
| Behaviour | Not selling when it falls | **no number**: two studies disagree twelvefold |
| Lever | Pick the best-performing fund | **₹0** |
| Trade (kept apart) | Hold more equity | ₹34,84,847: *"arithmetically true and it is not free money"* |

**Why "save more" is a range:** it depends on the assumed return.

| Assumed return | 6% | 8% | 10% | 12% | 14% |
|---|---|---|---|---|---|
| Value of +₹5,000/month | ₹14,61,364 | ₹17,41,726 | ₹20,89,621 | ₹25,22,880 | ₹30,64,269 |

*"Aath decisions ₹6L–₹50L ke, kisi screen pe nahi the — jabki ₹0 wale ke liye
chaar screens."* Eight decisions worth ₹6L–₹50L were on no screen, while the ₹0
one had four.

### 47.2 Tax, two salaries

| Salary (no deductions) | New regime | Old regime | Gap per year |
|---|---|---|---|
| ₹15L | ₹97,500 | ₹2,57,400 | ₹1,59,900 (old wins only above ₹5,43,750 of deductions) |
| ₹24L | ₹2,92,500 | ₹5,38,200 | ₹2,45,700 |

Someone already on the new regime sees **₹0, "Already done"**.

### 47.3 Why a fund is #1 on Research (Manan's question, 2026-07-29)

*"Mirae Asset Flexi Cap top pe kyun? Kis basis pe, kya logic?"*

| Rank | Fund | TER | Score | Record | Worst 3 years |
|---|---|---|---|---|---|
| #1 | Mirae Asset Flexi Cap | 0.67% | 88 | 3.4 years, flagged "thin record" | +12.6% |
| #2 | Nippon | 0.67% | 86 | 4.9 years | — |
| #5 | Kotak | 0.66% | 72 | 13.6 years | −4.3% |
| #34 | Taurus | 2.72% | 6 | — | −10.6% |

#1's breakdown: cost 1.00, risk 0.90, consistency forced to neutral 0.50
because the record is short (evidence strength 0.07).

**What #1 means:** *"sabse sasta, aur uske record ke against koi cheez nahi"*:
the cheapest, with nothing in its record against it. It does **not** mean it
will do best. The real decision is **avoiding #34**: four times the cost.

**An open question for Manan** from that day: should a ranking be shown at all,
or simply "5 cheap funds, koi bhi le lo" (take any)?

### 47.4 Regular vs direct, over a working life

On ₹15,000/month for 15 years at 12%:

| Plan | Ends at |
|---|---|
| Direct | ₹75,68,640 |
| Regular | ₹71,48,080 |
| **Difference** | **₹4,20,560** |

That is the price of the distributor's commission, measured on 125 real fund
pairs (regular median TER 1.42% vs direct 0.63%).

### 47.5 What a Small Cap fund has done to people before

On ₹8,00,000:

- the worst fall was **₹4,59,280** (−57.4%), and the median recovery was about
  9 months;
- 20 in 100 one-year stretches lost money, 2 in 100 five-year stretches, and
  none of the ten-year stretches.

*Keep this guide honest: when you change something it describes, change the
guide in the same commit. When you quote a number, add the date and the command
that re-measures it.*
