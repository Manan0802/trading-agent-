# 🚀 NexTrade — START HERE (Master Context & Onboarding)

**Read this first.** If you know nothing about this project, this file + the PRD + the research doc = full understanding of *what* we're building and *how*. Written so a total beginner (or a fresh AI agent) can get up to speed in 15 minutes.

**Last updated:** 2026-08-28 · **Phase:** Part A (Financial Advisor) is built and running. Part B (Trading Agent) is not started.

> ⚠️ **This line said "no app code yet" until 2026-08-28, which was true when it
> was written on 2026-06-29 and wrong for the 158 commits that followed.** It is
> the first thing anyone is told to read, so it is the worst place in the repo
> for a stale status. What actually exists today:
>
> | | |
> |---|---|
> | Backend | FastAPI, **49 endpoints**, 92 response schemas, 7 Alembic migrations |
> | Tests | **1,603**, plus `./check.sh` — **11 checks in 10 groups**: pytest, NAV-store integrity, scoring parity across library versions, the frontend typecheck+build, adversarial inputs, cross-view consistency, account isolation, a page sweep (seeded and brand-new), mobile, and accessibility |
> | Data | 5.2M-row NAV store, AMFI expense ratios, a 1,686-fund Groww universe |
> | Frontend | React + Vite, 49 `.tsx` files, four Playwright harnesses |
> | Advisor | goals, SIP, allocation, tax (both regimes), levers, look-through, cost review — **600 users and 757 goals in the dev database**, each with an LLM explanation |
> | Deployed | **no.** `gh release list` is empty; `deploy/FREE-NO-CARD.md` is the route to a public URL at ₹0/month |
>
> **Where to go next:** `docs/phase-1-redesign.md` is the current plan and is
> **an extension of Part A, not a rebuild of it** — it adds fund selection and
> portfolio analysis on top of the calculator described below. Its §0 says what
> it does and does not cover; its §9.1 is what is still open.

---

## 0. The 30-second version

NexTrade is a **personal AI fintech web app** with two parts:
- **Part A — Financial Advisor:** you enter a money goal (retirement, house, etc.); it calculates how much to invest monthly (SIP), how to split it (equity/debt/gold), tax savings, and explains it in simple Hinglish using an LLM.
- **Part B — AI Trading Agent:** an emotion-free, rule-based system that swing-trades one Indian index ETF (**NIFTYBEES**). It backtests on 10 years of data, paper-trades with fake money, and only touches real money *after* fake-money results prove it works. Alerts via WhatsApp.

Built for **Manan + 4-5 friends/family**. Budget tiny (~₹0–800/month). Goal = a disciplined, deployable system, **not** a get-rich bot.

---

## 1. Read these documents in this order

| # | File | What it is |
|---|------|-----------|
| 1 | `START_HERE.md` (this) | Master map + decisions + repo strategy + glossary |
| 2 | `NexTrade_PRD_v1.md` | Full product spec (features, formulas, DB schema, API, roadmap). The master reference. See §18 for build deltas. |
| 3 | `docs/research/2026-06-28-oss-landscape.md` | All open-source tools/repos researched + verdicts + the BUILD/REUSE/MODIFY blueprint |
| 4 | `docs/superpowers/specs/2026-06-29-nextrade-build-spec.md` | Consolidated build spec (PRD + deltas + v1 scope) |
| 5 | `docs/superpowers/plans/2026-06-29-phase1-financial-advisor.md` | Step-by-step Phase 1 implementation plan (12 tasks, TDD, copy-paste code) |

**To build:** open doc #5 and execute tasks 1→12 in order. Each task has tests + exact commands.

---

## 2. What's decided (locked)

| Decision | Choice | Why |
|----------|--------|-----|
| Build style | **Hybrid** — build the "brain" ourselves, reuse OSS for "body" | learn + control where it matters, don't reinvent plumbing |
| v1 instrument | **NIFTYBEES only** | one thing solid first, expand later |
| AI layer | **v1 = rules + LLM explain only; v2 = multi-agent AI analyst** | reliable first, smart second; AI advises, never overrides risk |
| Backtest engine | **backtesting.py** + **quantstats** (not vectorbt) | event-driven matches our logic; PRD's vectorbt loop was O(n²) buggy |
| Market data | **jugaad-data** (NSE) primary, yfinance fallback | jugaad-data more accurate + future-proof than yfinance |
| Real execution | **OpenAlgo** (broker-agnostic), Phase 5 only | works with 20+ Indian brokers, no lock-in |
| Money | **Paper/fake money first. ZERO real money until paper proves it.** | survival > speed; non-negotiable |
| Alerts | **WhatsApp via Twilio** (NOT Telegram) | user choice |
| Build order | **Financial Advisor first**, then Trading agent | simpler, builds the platform skeleton |
| Dev DB | **SQLite** (dev) → **Postgres/Neon/Supabase** (deploy) | zero setup now, portable models |
| Frontend chart | **TradingView Lightweight Charts** (MIT) | best free candlestick chart |
| Roles | Manan = idea/direction; AI = build lead ("boss") | |

---

## 3. Final tech stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy 2 + Alembic, Pydantic 2, pytest, APScheduler, langchain-groq (Groq Llama 3.3), twilio (WhatsApp). Data: jugaad-data (+ yfinance fallback). Backtest: backtesting.py + quantstats + pandas-ta. Execution (later): OpenAlgo.
**Frontend:** React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui + Recharts + TradingView Lightweight Charts + axios + React Query + Zustand.
**Infra:** dev SQLite → deploy Postgres (Neon/Supabase free) + Render/Fly.io/Vercel.

---

## 4. The repos we studied — and what to take from each

Legend: 🟢 ADOPT (use directly) · 🔵 PATTERN (copy ideas/code) · 🟡 LATER/LEARN · ⚪ PARKED (off-core, maybe later)

### Use now / soon
| Repo | Verdict | What to extract |
|------|---------|-----------------|
| [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | 🟢🔵 #1 | **Our closest twin** (FastAPI+React, MIT). Copy: data-source loader registry, MCP server shape, backtest-validation flow, signal-engine generation, FastAPI/React skeleton. Swap China data → jugaad-data. Also available as local `vibe-trading` skill. |
| [marketcalls/openalgo](https://github.com/marketcalls/openalgo) | 🟢 | Broker-agnostic execution layer for 20+ Indian brokers (real-money phase). |
| [jugaad-py/jugaad-data](https://github.com/jugaad-py/jugaad-data) | 🟢 | Primary NSE historical data (accurate, free). |
| [kernc/backtesting.py](https://github.com/kernc/backtesting.py) | 🟢 | v1 backtest engine (event-driven). |
| [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | 🟢 | Backtest tearsheets (Sharpe/Sortino/drawdown). |
| [twopirllc/pandas-ta] | 🟢 | Indicators (EMA/RSI/MACD/ATR/ADX). |
| [weanonymous01/Edge-Swing](https://github.com/weanonymous01/Edge-Swing) | 🔵 | India ETF swing system w/ NIFTY benchmark — closest small blueprint for our strategy. |
| [dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) / [PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) | 🟢 | Better allocation for Part A (v2 optional). |

### v2 AI brain (after rules are solid)
| Repo | Verdict | What to extract |
|------|---------|-----------------|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | 🔵🔵 | Multi-agent blueprint: analysts → bull/bear debate → trader → risk → PM. Groq + `.NS` support. Decision-log memory = trade-learning loop. |
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | 🔵 | Persona agents + clean LangGraph use. |
| [The-Swarm-Corporation/AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge) | 🔵 | Simple 4-agent shape (Director→Quant→Risk→Execution). Copy structure; ignore its crypto/autonomous execution. |
| [FinGPT] | 🔵 | News/sentiment agent (v2). |
| [AI-Stock-Advisor / ai-powered-robo-advisor] | 🔵 | LangChain+RAG explainer + robo-advisor structure for Part A. |

### Learn from (don't depend on)
- [Freqtrade](https://github.com/freqtrade/freqtrade) 🔵 — best reference for strategy + risk + dry-run + hyperopt structure (crypto, but architecture gold).
- [Backtrader] 🟡 — backtest engine fallback if we outgrow backtesting.py.
- [microsoft/qlib], [FinRL] 🟡 — advanced AI/ML quant ideas, later.
- [Ghostfolio](https://github.com/ghostfolio/ghostfolio) / Maybe 🔵 — Part A dashboard UX inspiration.

### ⚠️ Avoid / off-core (important honesty)
- **FinceptTerminal** 🟡⚠️ — great ideas (broker list, screens) BUT **AGPL + commercial license, $50k+ damages, attaches to derivatives**. C++/Qt (wrong stack). **Mine ideas only; never copy code or build on it.**
- **MoneyPrinterTurbo** ⚪ — AI video generator (name misleads). Not trading. Park for marketing/promo videos.
- **VoxCPM** ⚪ — text-to-speech. Park for voice alerts (v3).
- **camoufox** 🟡 — stealth browser. Only if NSE/news scraping gets blocked.
- Hummingbot, LLM-TradeBot, Superalgos, StockSharp, Zipline, Actual Budget, Firefly III, GnuCash, ERPNext — ⚪ parked (crypto-HFT / market-making / wrong language / budgeting / accounting / ERP). See research doc §10 "Parking lot" for *when* each could matter.

> **The rule:** we BUILD the brain (signal engine, risk manager, FA math) and REUSE the body (data, backtest, charts, execution, alerts). **Risk manager is always ours, hardcoded, never overridable.** Full BUILD/REUSE/MODIFY table = research doc §13.

---

## 5. Build roadmap (phases)

- **Phase 1 — Financial Advisor** (plan ready, doc #5): SIP + allocation + tax + rebalance + LLM explainer + WhatsApp + web UI.
- **Phase 2 — Data pipeline:** jugaad-data → NIFTYBEES OHLCV → DB → pandas-ta indicators.
- **Phase 3 — Strategy + backtest:** signal engine + regime detector + risk manager + backtesting.py + quantstats; pass criteria (Sharpe>1, DD<15%, win>45%, PF>1.3). Add walk-forward.
- **Phase 4 — Paper trading:** live signals on fake money, 2-3 months, WhatsApp alerts, trade journal.
- **Phase 5 — Real money:** OpenAlgo, semi-auto (human approves), ₹10-15k, only after Phase 4 proves it.
- **v2 — AI analyst layer:** TradingAgents/AutoHedge-style agents that advise the risk manager.

Each phase: build → test → verify → next. Re-spec before Phase 2.

---

## 6. How to start building (on your machine)

```bash
git clone <this-repo>
cd <repo>
# Backend
cd backend && python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m pytest -v            # run tests as you build each task
uvicorn app.main:app --reload  # API at http://localhost:8000/docs
# Frontend (new terminal)
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```
Then open `docs/superpowers/plans/2026-06-29-phase1-financial-advisor.md` and do Task 1 → Task 12. Each task: write test → see it fail → write code → see it pass → commit.

Secrets: copy `backend/.env.example` → `backend/.env`, fill Groq + Twilio keys (free).

---

## 7. Non-negotiables (never break these)
1. Risk manager (Phase 3+) hardcoded — never overridable, not even by AI.
2. No real money until paper trading proves it.
3. Every money projection says "**projected**", never "guaranteed".
4. Deterministic FA math = 100% reproducible + unit-tested.
5. Trade only NSE cash segment in v1 (no F&O, no intraday, no margin).

---

## 8. Glossary (for total beginners)
- **SIP** — Systematic Investment Plan: fixed amount invested every month.
- **ETF / NIFTYBEES** — a tradable "basket"; NIFTYBEES tracks India's top-50 companies (Nifty 50).
- **Equity/Debt/Gold** — stocks / bonds-FDs / gold; we split money across them by risk + timeline.
- **Swing trading** — holding 2-10 days (not seconds, not years).
- **Backtest** — run the strategy on past data to see if it would've made money.
- **Paper trading** — practice with fake money on live prices.
- **Indicator (EMA/RSI/MACD/ATR/ADX)** — math on price/volume that hints at trend/momentum/volatility.
- **Signal** — the rule output: BUY / HOLD / EXIT.
- **Risk manager** — decides position size, stop-loss, daily loss limit; protects capital.
- **Stop-loss / Target** — auto-exit at a loss cap / profit goal.
- **Sharpe ratio** — return per unit of risk (higher = better; >1 good).
- **Max drawdown** — biggest peak-to-bottom fall (smaller = safer).
- **Walk-forward** — optimize on old data, test on unseen newer data, repeatedly — the honest way to trust a strategy.
- **Regime** — market mood: trending-bull / bear / sideways / volatile.
- **LLM (Groq Llama)** — the AI that explains things in Hinglish; in v2 also analyzes/debates.

---

*This file is the front door. Keep it updated as the project evolves.*
