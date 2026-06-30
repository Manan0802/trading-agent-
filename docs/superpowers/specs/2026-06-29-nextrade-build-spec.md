# NexTrade — Build Spec v1 (consolidated)

**Date:** 2026-06-29
**Owner:** Manan (idea/direction) · Claude (head PM / build lead)
**Status:** For approval → then implementation plan → build
**References:** `NexTrade_PRD_v1.md` (full PRD) · `docs/research/2026-06-28-oss-landscape.md` (OSS research)

This spec = PRD **deltas** + **v1 scope** + **Phase-1 (Financial Advisor) design** + **verifiable build order**. PRD stays the master doc; where this spec differs, this spec wins.

---

## 1. Vision (one line)
A personal AI fintech platform: **(A) Financial Advisor** (goal-based SIP/allocation/tax planning, explained in Hinglish) + **(B) AI swing-trading agent** (NIFTYBEES, paper-first, risk-managed). Built for Manan + 4-5 friends/family.

## 2. Locked decisions (from brainstorming)
1. **v1 instrument:** NIFTYBEES only.
2. **AI layer:** v1 = deterministic rules + Groq LLM for *explanation only*. v2 = TradingAgents/AutoHedge-style analyst layer that *advises* the risk manager, never overrides.
3. **Backtest:** `backtesting.py` + `quantstats` (NOT vectorbt-loop). Strategy decoupled → walk-forward later.
4. **Money:** paper/fake money first. **ZERO real money until paper results prove it.** Real execution via OpenAlgo only at Phase 5.
5. **Alerts:** **WhatsApp via Twilio** (PRD §12). (Not Telegram.)
6. **Build order:** **Financial Advisor first (Phase 1)**, then trading agent.

## 3. Stack — PRD + deltas
| Layer | PRD | Delta / decision |
|-------|-----|------------------|
| Backend | Python + FastAPI | keep |
| DB | PostgreSQL (Railway) | **Dev: SQLite (zero-setup), models written portably; Deploy: Postgres (Neon/Supabase free).** |
| ORM/migrations | SQLAlchemy 2 + Alembic | keep |
| LLM | Groq Llama 3.3 + langchain-groq | keep |
| Trading data | yfinance | **jugaad-data primary (accurate NSE), yfinance fallback** |
| Backtest | vectorbt | **backtesting.py + quantstats** |
| Execution (real) | Angel One SmartAPI | **OpenAlgo (broker-agnostic), Phase 5 only** |
| Alerts | Twilio WhatsApp | keep |
| Scheduler | APScheduler | keep |
| Frontend | React+Vite+TS+Tailwind+shadcn | keep; **chart = TradingView Lightweight Charts (MIT)** |
| Allocation (FA) | fixed matrix | matrix v1; Riskfolio-Lib optional v2 |
| Skeleton reference | — | **Vibe-Trading (FastAPI+React patterns)**; `vibe-trading` skill for backtest/alpha ideas |

## 4. v1 scope (what we build now)
**In:** Financial Advisor module (full) → then Trading agent (data→indicators→signal→risk→backtest→paper). NIFTYBEES. WhatsApp alerts. Web dashboard.
**Out (defer):** real-money execution, multi-asset, AI multi-agent analyst, options/F&O, public multi-user SaaS.

---

## 5. Phase 1 — Financial Advisor (design)

**Goal:** User creates a financial goal → sees required SIP + asset allocation + tax plan → gets a plain-Hinglish LLM explanation → receives a WhatsApp test alert.

### Components (isolated, single-purpose)
- **`services/advisor/sip_calculator.py`** — pure FV/PMT math (PRD §5.3). Deterministic, fully unit-tested.
- **`services/advisor/asset_allocator.py`** — risk questionnaire scorer + timeline×risk allocation matrix (PRD §5.4). Returns equity/debt/gold + recommended products.
- **`services/advisor/tax_advisor.py`** — 80C/80D/NPS plan (PRD §5.5).
- **`services/advisor/rebalancer.py`** — drift detection vs target (PRD §5.6).
- **`services/llm/client.py` + `advisor_prompts.py`** — Groq explainer (PRD §5.7), Hinglish, "projected" not "guaranteed".
- **`services/alerts/whatsapp.py` + `templates.py`** — Twilio send + message templates (PRD §12).
- **`models/`** — `user`, `goal` (PRD §9 subset, portable types).
- **`routers/advisor.py`** — goals CRUD + calc endpoints + risk-score + rebalancing (PRD §11.1).
- **`jobs/scheduler.py`** — Sunday rebalancing cron (APScheduler).
- **Frontend** — goal wizard (4-step), goals list, goal detail (SIP + allocation pie + LLM panel), tax advisor page. api client (axios) + React Query.

### Data model (Phase 1 only)
`users` (id, name, phone, risk_score, risk_profile, annual_income, monthly_expenses) · `goals` (id, user_id, type, name, target_amount, current_savings, target_date, years, required_sip, equity/debt/gold alloc, llm_explanation, status). Portable types (string UUID, JSON) so SQLite-dev ↔ Postgres-deploy.

### Testing
Deterministic services (SIP, allocation, tax, rebalance) → **TDD**: write tests with known values first, then implement. LLM/alerts → integration smoke tests (mock external calls).

---

## 6. Build order — Phase 1 (each step has a verify gate)
1. **Scaffold** backend (FastAPI) + frontend (Vite+TS+Tailwind+shadcn) → verify: `GET /health` ok + Vite page loads.
2. **DB + models + Alembic** (users, goals) → verify: migration applies, tables exist.
3. **SIP calculator + tests** → verify: pytest green on known FV/PMT values.
4. **Asset allocator + risk scorer + tests** → verify: pytest green, matrix correct.
5. **Tax advisor + tests** → verify: pytest green.
6. **Rebalancer + tests** → verify: drift cases pass.
7. **Goal CRUD + calc API** → verify: via `/docs` create+list goal end-to-end.
8. **Groq LLM explainer** → verify: goal returns warm Hinglish explanation < 3s.
9. **Frontend wizard + detail (pie + explainer)** → verify: create goal in UI → see SIP + allocation + explanation.
10. **WhatsApp (Twilio) test send** → verify: test alert received on phone.
11. **Rebalancing + Sunday cron** → verify: drift unit test + manual trigger sends WhatsApp.

**✅ Phase 1 done when:** create goal → SIP → allocation → LLM explanation → WhatsApp test all work.

(Phase 2+ = trading data pipeline → indicators → signal → risk → backtest → paper → [Phase 5] real. Detailed in PRD §13; re-spec before starting Phase 2.)

---

## 7. Non-negotiables
- Risk manager (Phase 2+) hardcoded, never overridable.
- No real money until paper proves it.
- Every LLM output says "projected", never "guaranteed".
- Deterministic FA math = 100% reproducible + tested.
