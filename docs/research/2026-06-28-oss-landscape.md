# NexTrade — Open-Source Landscape & Stack Research

**Date:** 2026-06-28
**Mode:** Optimize / research (pre-build)
**Decisions locked:** Hybrid build (build core + adopt OSS + glue) · Stack open to better free tools · Research both modules · Goal = real practical, deployable edge.

> This is a living research doc. We keep finding + analysing repos and append here before build.

---

## 0. TL;DR — biggest changes vs PRD v1

| Area | PRD v1 | Research says | Why |
|------|--------|---------------|-----|
| Broker/execution | Hand-code Angel One SmartAPI | **Adopt OpenAlgo** (unified layer for 20+ Indian brokers) | One API, broker-agnostic, has order mgmt + paper + many brokers free. Don't lock to Angel. |
| Backtest engine | vectorbt with a per-bar Python loop | **backtesting.py** for v1 strategy + **quantstats** for reports; vectorbt only for param sweeps | PRD's loop is O(n²) and fights vectorbt's vectorized design. Event-driven matches the regime+signal-per-bar logic. |
| Historical data | raw yfinance | **jugaad-data / openchart** primary, yfinance fallback | yfinance breaks/rate-limits on NSE; jugaad-data pulls official NSE bhavcopy. |
| Agent framework | LangGraph from day 1 | Plain Python rules in v1; **LangGraph only when adding real multi-agent reasoning** | Deterministic rules don't need a graph engine. Add it when you add LLM "analyst" agents (see TradingAgents). |
| Validation | single 10y backtest + pass criteria | Add **walk-forward / out-of-sample** (gold standard) | Single backtest = overfitting trap. WFO is how you trust the edge. |

---

## 1. Trading engine / backtest layer

| Repo | What | Fit for us |
|------|------|-----------|
| [kernc/backtesting.py](https://github.com/kernc/backtesting.py) | Simple event-driven backtester (`next()` per bar) | **v1 strategy dev.** Matches regime+signal-per-bar mental model, easy, no O(n²) trap. Single-asset focus = fine (we start NIFTYBEES). |
| [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | Vectorized, ultra-fast param sweeps | **Research only** — run 1000s of param combos / walk-forward fast. Needs vectorized signals. |
| [edtechre/pybroker](https://github.com/edtechre/pybroker) | ML-first backtester, **walk-forward built in**, Numba-fast | Strong candidate if we go ML signals + want WFO out of the box. |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | Pro event-driven, **same engine backtest + live** | Later upgrade — kills backtest/live code drift. Steeper curve. |
| [stefan-jansen/machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading) | Book code: data→features→ML→execution | Reference/learning goldmine. |
| [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | Tearsheets: Sharpe/Sortino/DD/etc | **Adopt** — use for all backtest + paper reports. Replaces hand-rolled metrics. |
| [microsoft/qlib](https://github.com/microsoft/qlib) | AI quant platform (ML/RL pipelines) | Heavy; mine ideas for factor/ML later, not v1. |
| [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) | Reinforcement-learning trading | Aspirational/learning, not v1. |
| [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading) | Curated list of libs/strategies/books | Index to mine more. |
| [je-suis-tm/quant-trading](https://github.com/je-suis-tm/quant-trading) | Many strategy implementations (RSI, BB, MACD, pairs…) | Copy clean strategy patterns. |

**Crypto bots (architecture reference, not direct use):** [freqtrade](https://github.com/freqtrade/freqtrade) (best-in-class config/risk/hyperopt patterns), [jesse-ai/jesse](https://github.com/jesse-ai/jesse), [OctoBot](https://github.com/Drakkar-Software/OctoBot). Freqtrade especially worth reading for how it structures strategy + risk + dry-run.

---

## 2. India market layer (data + broker) — the part PRD under-researched

| Repo | What | Fit |
|------|------|-----|
| [marketcalls/openalgo](https://github.com/marketcalls/openalgo) | **Open algo platform, unified API for 20+ Indian brokers** (Zerodha, Angel, Dhan, Upstox, Fyers, Shoonya…), order mgmt, web UI | **Adopt as the execution layer.** Broker-agnostic = we pick/switch brokers freely. |
| [marketcalls/openalgo-python-library](https://github.com/marketcalls/openalgo-python-library) | Python client for OpenAlgo | Use from our FastAPI backend. |
| [marketcalls/historify](https://github.com/marketcalls/historify) | Historical data management app (OpenAlgo) | Reference for our market_data cache/pipeline. |
| [jugaad-py/jugaad-data](https://github.com/jugaad-py/jugaad-data) | Live + historical NSE/BSE data (official bhavcopy) | **Primary historical source.** Reliable, free, no key. |
| [aeron7/nsepython](https://github.com/aeron7/nsepython) | Unofficial NSE API wrapper | Secondary data (option chain, indices, corp data). |
| [Finance-LLMs/Indian-Markets](https://github.com/Finance-LLMs/Indian-Markets) | MCP tool wrapping nsepython | If we want NSE data as an MCP tool for the agent. |

**Broker API reality (2026):** Free APIs — Angel One SmartAPI, **Dhan** (free, WebSocket, paper trading, good docs), **Fyers** (free, good historical), Upstox (₹10/order via API until Mar-2026), Shoonya. Zerodha Kite = paid (~₹2000/mo). For a coder starting fresh: **Dhan or Fyers** are the cleanest free picks — and OpenAlgo supports all of them so we're not locked.
Sources: [AlgoTest broker guide](https://algotest.in/blog/best-brokers-for-algo-trading-in-india/) · [Pocketful free-API list](https://www.pocketful.in/blog/trading/best-brokers-offering-free-trading-api/) · [Stratzy Hinglish guide](https://stratzy.in/blog/best-broker-for-algo-trading-india-hinglish/)

---

## 3. AI / LLM agent layer (the "smart agent" ambition)

| Repo | What | Fit |
|------|------|-----|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | **Multi-agent LLM trading**: analyst + bull/bear debate + risk + trader agents | **Primary reference** for the "smart agent" layer. Architecture to borrow: specialized agents → debate → decision. |
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | Team of AI agents (Buffett/Munger-style personas) analyze stocks | Reference for persona agents + clean LangGraph use. |
| [TauricResearch — A-share forks](https://github.com/KylinMountain/TradingAgents-AShare) | Same idea adapted to one market's data sources | Blueprint for how to adapt a multi-agent system to **Indian** data. |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | Lightweight multi-agent framework | Alt to LangGraph if we want simpler orchestration. |
| [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | Type-safe agent framework | Clean structured-output agents (good with our Pydantic stack). |
| [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents) | Principles for production-grade LLM apps | Read before building agent layer. |

**Stance:** v1 = deterministic rules + LLM only for explanation (cheap, reliable). v2 "next level" = add a TradingAgents-style **analyst layer** (technical agent + news/sentiment agent + risk agent → debate → confidence) that *advises* the hardcoded risk manager. LLM never overrides risk limits.

---

## 4. Financial Advisor (Part A) layer

| Repo | What | Fit |
|------|------|-----|
| [PyPortfolio/PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) | Efficient frontier, Black-Litterman, HRP allocation | Optional upgrade over fixed allocation matrix (keep matrix for v1 — explainable). |
| [JerBouma/FinanceToolkit](https://github.com/JerBouma/FinanceToolkit) | 150+ financial ratios/metrics, transparent | Mine for goal/portfolio analytics. |
| [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | Portfolio analytics/tearsheets | Reuse here too for portfolio reporting. |

PRD's SIP/tax/rebalance math is fine and simple — **keep custom** (deterministic, explainable, Indian-specific). Don't over-engineer Part A.

---

## 5. Edge & validation (the difference between "looks good" and "makes money")

Single 10-year backtest = overfitting trap. Add:
- **Walk-forward optimization (WFO)** — rolling in-sample optimize → out-of-sample test. Gold standard. (pybroker has it built in; can also DIY with vectorbt.)
- **Parameter stability check** — if best params swing wildly across windows → overfit red flag.
- **Multiple market regimes** in test window (2015–2025 covers bull/COVID crash/sideways).
- **Honest costs** — STT + brokerage + slippage already in PRD (good).
- Benchmark vs **buy-and-hold NIFTYBEES** always (must beat it risk-adjusted, not just absolute).

Sources: [QuantInsti WFO](https://blog.quantinsti.com/walk-forward-optimization-introduction/) · [IBKR walk-forward](https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/) · [AlgoTrading101 WFO](https://algotrading101.com/learn/walk-forward-optimization/)

---

## 6. Recommended hybrid stack (proposed — needs your sign-off)

- **Build ourselves:** signal engine, risk manager (hardcoded), regime detector, FA math, FastAPI API, React UI, WhatsApp layer, trade journal. (Learning + control where it matters.)
- **Adopt OSS:** `backtesting.py` (strategy backtest) · `quantstats` (reports) · `vectorbt` (param sweeps/WFO) · `jugaad-data`+`openchart` (historical NSE) · **OpenAlgo** (live data + order execution, broker-agnostic) · `pandas-ta` (indicators, keep).
- **Defer:** LangGraph multi-agent analyst layer (v2) · PyPortfolioOpt (optional) · NautilusTrader (if/when unifying backtest+live).
- **LLM:** Groq Llama 3.3 (keep) for explanations now; analyst agents later.

---

## 7. Research / decision tasks FOR YOU (Manan)

1. **Share the trading + finance repos you already found** — we slot them into the tables above and compare.
2. **Broker choice** — open API access on **Dhan or Fyers** (free, OpenAlgo-supported). Confirm which you can get a demat + API key for fastest.
3. **OpenAlgo trial** — skim [openalgo docs](https://docs.openalgo.in/); decide adopt vs reference-only.
4. **Instruments** — beyond NIFTYBEES, list what you'd actually want to trade (the strategy/edge depends on this).
5. **Groq limits** — confirm free-tier rate/volume is enough for daily scans + summaries for ~5 users.
6. **Hosting** — Railway now charges; check Render / Fly.io / Oracle free tier / self-host as alternatives.
7. **Ambition tradeoff** — "agent as smart as big traders" needs honest scoping: do you want (a) a rock-solid disciplined rule system first, then (b) layer LLM analysts on top? (Recommended order.)

---

## 8. Open questions to resolve before writing the build spec

- Backtest engine final pick: `backtesting.py` (recommended) vs `pybroker` (if WFO+ML priority)?
- OpenAlgo: adopt as execution layer, or keep direct broker SDK?
- Agent layer: v1 rules-only (recommended) vs build multi-agent analyst now?
- One instrument (NIFTYBEES) for v1, or multi-asset from start?

---

## 9. DECISIONS LOCKED (2026-06-29)

1. **Instruments** — v1 = NIFTYBEES only. Expand later.
2. **AI layer** — v1 = deterministic rules + Groq LLM for explanation only. v2 = TradingAgents-style AI analyst layer that *advises* the risk manager, never overrides hardcoded limits.
3. **Backtest** — `backtesting.py` (v1, candle-by-candle) + `quantstats` reports. Strategy logic written decoupled so it can later run through vectorbt/pybroker for walk-forward. "basic → advance."
4. **Money/data** — `jugaad-data` (free NSE) for backtest + paper. OpenAlgo only at real-money phase. **CORE PRINCIPLE: entire system built + tested on PAPER money first. ZERO real money until paper results prove it.**

---

## 10. User's 40 repos — verdict & slotting

Legend: 🟢 ADOPT (use directly) · 🔵 PATTERN (copy code/ideas) · 🟡 LATER/LEARN · ⚪ SKIP (out of our scope)

### Cat 1 — AI multi-agent trading (→ v2 analyst layer)
| Repo | Verdict | Where it fits |
|------|---------|---------------|
| TradingAgents | 🔵🔵 | **Primary v2 blueprint** — analyst/risk/fund agents + debate→decision. |
| ai-hedge-fund (virattt) | 🔵 | v2 persona agents + clean LangGraph reference. |
| FinRL | 🟡 | RL trading — advanced/learning, overkill for v1/v2. |
| AI-Trader | 🟡 | Reference for agent-native platform layout. |
| Vibe-Trading | 🔵 | "Personal trading agent" UX + broker-integration patterns. |
| AgenticTrading | 🔵 | backtest+paper+**inspect reasoning** — reasoning-inspection UI idea is great. |
| FinMem | 🔵 | Layered memory → reuse idea for trade-journal **learning loop** (v2). |
| LLM-TradeBot | ⚪ | Crypto, auto-symbol — not our scope. |
| OctoBot (AI) | 🟡 | Plain-text strategy DSL idea only. Crypto. |
| Hummingbot (AI) | ⚪ | Market-making/HFT crypto — wrong style. |

### Cat 2 — Non-AI bots/frameworks
| Repo | Verdict | Where it fits |
|------|---------|---------------|
| Freqtrade | 🔵🔵 | **Read heavily** — best structure for strategy + risk + dry-run + hyperopt. Crypto but architecture gold. |
| Backtrader | 🟡 | Backtest-engine fallback if we outgrow backtesting.py (multi-asset). |
| Zipline / zipline-reloaded | ⚪ | Older; backtesting.py covers v1. |
| LEAN/QuantConnect | 🟡 | Heavy multi-asset engine — possible long-term "advance" engine. |
| StockSharp | ⚪ | C# — wrong stack. |
| Jesse | 🟡 | Study its **zero look-ahead-bias** principle (critical for honest backtests). |
| Superalgos | ⚪ | Visual no-code JS — not our path. |
| pykiteconnect | 🟡 | Zerodha official (paid API) — only if Zerodha picked at real money. |
| jugaad-trader | 🟢 | **Free unofficial Zerodha order placement** — pairs with jugaad-data at real money (note: unofficial = reliability risk). |
| OpenAlgo | 🟢 | **Real-money execution layer** (broker-agnostic). Already our pick. |

### Cat 3 — AI financial advisors / analysis
| Repo | Verdict | Where it fits |
|------|---------|---------------|
| FinGPT | 🔵 | v2 **news/sentiment agent** (financial LLM). |
| FinRobot | 🟡 | Agent-platform reference. |
| AI-Stock-Advisor | 🔵 | **LangChain + RAG** pattern for FA explainer + news RAG. |
| ai-powered-robo-advisor | 🔵🔵 | **Direct Part A blueprint** — full-stack robo-advisor w/ explainable AI. Study structure. |
| FinRL-Trading | 🟡 | Live layer for FinRL — later. |
| Riskfolio-Lib | 🟢 | **Part A allocation upgrade** (HRP/risk-parity, more models than PyPortfolioOpt). v2 optional. |
| PyPortfolioOpt | 🟢 | Part A allocation (optional v1.5). |
| FinanceToolkit | 🔵 | FA analytics/ratios. |
| OpenBBTerminal | 🟡 | Data aggregation + feature inspiration (heavy). Possible extra data source. |
| awesome-ai-in-finance | 🔵 | Index — mine for more. |

### Cat 4 — Non-AI finance / portfolio
| Repo | Verdict | Where it fits |
|------|---------|---------------|
| Ghostfolio | 🔵🔵 | **Part A dashboard UX blueprint** (wealth tracking). Strong reference. |
| Wealthfolio | 🔵 | Local-first portfolio tracker UX. |
| rotki | 🟡 | Portfolio + tax reference. |
| Maybe | 🔵 | Personal-finance-OS UX (net worth) — Part A inspiration. |
| Actual Budget | ⚪ | Envelope budgeting — out of scope (we're goal-based, not budgeting). |
| Firefly III | ⚪ | PFM budgeting — out of scope. |
| GnuCash | ⚪ | Accounting — out of scope. |
| jugaad-data | 🟢 | **Our primary data source.** |
| Kite-Trader | 🟡 | Unofficial Zerodha lib alt (real money). |
| ERPNext | ⚪ | ERP/GST — out of scope. |

**Parking lot — not for v1/v2, but KEEP (may help if scope grows):**
| Repo | Why not now | When it COULD help |
|------|-------------|--------------------|
| Hummingbot | Market-making/HFT crypto | If we ever add intraday/market-making or crypto |
| LLM-TradeBot | Crypto, auto-symbol | If multi-symbol auto-selection becomes a feature |
| Superalgos | Visual no-code JS | If we want a visual strategy builder for non-coders |
| StockSharp | C# stack | If we add a C#/.NET component or need its 100+ connectors |
| Zipline / zipline-reloaded | Older engine | If we need event-driven multi-asset US-style backtests |
| Actual Budget | Envelope budgeting | If FA expands into expense budgeting for the 5 users |
| Firefly III | PFM budgeting | Same — full personal-finance-manager features later |
| GnuCash | Double-entry accounting | If users want SIP/holdings ledger + tax-grade records |
| ERPNext | ERP/GST | If this ever becomes a registered biz needing GST/invoicing |

### Highest-value picks from your 40 (the keepers)
- **Execution/data:** OpenAlgo 🟢, jugaad-data 🟢, jugaad-trader 🟢
- **v1 build patterns:** Freqtrade 🔵, Edge-Swing 🔵 (see §11)
- **Part A:** ai-powered-robo-advisor 🔵, Ghostfolio 🔵, Riskfolio-Lib 🟢, FinanceToolkit 🔵
- **v2 AI brain:** TradingAgents 🔵, ai-hedge-fund 🔵, FinGPT 🔵, FinMem 🔵, AI-Stock-Advisor 🔵

---

## 11. Claude's gap-fill finds (the "kuch tum bhi dhundna")
| Repo | Verdict | Why |
|------|---------|-----|
| [weanonymous01/Edge-Swing](https://github.com/weanonymous01/Edge-Swing) | 🔵🔵 | **Python swing system for India ETFs/stocks** — backtest + trend-following + NIFTY-50 benchmark + CLI signals. Tiny but *exactly* our v1 domain. Best direct blueprint found. |
| [dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | 🟢 | Part A allocation (confirmed canonical repo). |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 🟡 | Production event-driven, unified backtest+live. Long-term "advance" engine. |
| jugaad-data + nsepython + (openchart) | 🟢 | India free data stack (from §2). |
| quantstats | 🟢 | Tearsheet reports (from §1). |

**Still to find before build (focused next pass):** a reliable free **NSE EOD data** validation (jugaad-data vs openchart vs yfinance accuracy), and 1-2 real **NIFTY swing strategy writeups** with published backtest stats to sanity-check our edge expectations.

---

## 12. Data reliability + edge reality (verified 2026-06-29)

- **Data:** `jugaad-data` more accurate than yfinance (yfinance shows price drift vs NSE; jugaad-data pulls new NSE site, cached, future-proof). **Confirmed primary source.** Caveat: index data needs dedupe/filtering. ([jugaad-data](https://github.com/jugaad-py/jugaad-data) · [Snyk health](https://snyk.io/advisor/python/jugaad-data))
- **Edge reality:** Simple 50-EMA/RSI swing systems (US data) ≈ 9–11% CAGR — often *on par with buy-and-hold on raw return* but with **far lower drawdown** (e.g. 22% vs 83%). So our system's real value = **lower drawdown + discipline + repeatability**, not magic alpha. NIFTY-specific public stats are scarce → **our own walk-forward backtest is the only honest answer.** ([QuantifiedStrategies 50-EMA](https://www.quantifiedstrategies.com/50-ema-strategy/))
- **Implication for goals:** target "beat NIFTYBEES buy-and-hold on **risk-adjusted** terms (Sharpe, max-DD)" — not "huge returns." That's the achievable, defensible bar.

---

## 13. BUILD vs REUSE vs MODIFY — the build blueprint

How we use the hybrid approach per component. **BUILD** = write ourselves (learning + control). **REUSE** = adopt OSS as-is. **MODIFY** = adopt + customize. Each REUSE/MODIFY names the source + a PATTERN ref to study.

### Part B — Trading agent
| Component | Verdict | Tool / source | Note |
|-----------|---------|---------------|------|
| Historical data fetch | REUSE | jugaad-data (thin wrapper) | + nsepython for extras |
| Data cache / pipeline → DB | BUILD | (our Postgres schema) | pattern: marketcalls/historify |
| Indicators (EMA/RSI/MACD/ATR/ADX) | REUSE | pandas-ta | keep as PRD |
| Market regime detector | BUILD | (PRD logic) | small, ours |
| Signal engine (5-condition + confidence) | BUILD | (core IP) | the thing we learn deeply |
| Risk manager (sizing, SL, daily limit) | BUILD | (hardcoded) | **must own — never outsource risk** |
| Backtest engine | REUSE | backtesting.py | wrap our strategy in it |
| Backtest reports/tearsheet | REUSE | quantstats | Sharpe/Sortino/DD/winrate |
| Walk-forward validation | BUILD (thin) | loop over backtesting.py / vectorbt | the "advance" step |
| Paper trader | BUILD | (PRD class) | pattern: Freqtrade dry-run; Edge-Swing |
| Live execution (real money) | REUSE | OpenAlgo (+ jugaad-trader fallback) | Phase 5 only |
| Trade journal | BUILD | (our DB) + LLM summary | pattern: FinMem memory (v2) |
| WhatsApp alerts | REUSE+BUILD | twilio lib + our templates | |
| Scheduler (cron scans) | REUSE | APScheduler | |

### Part A — Financial advisor
| Component | Verdict | Tool / source | Note |
|-----------|---------|---------------|------|
| SIP / tax / rebalance math | BUILD | (deterministic, India-specific) | simple, keep custom |
| Asset allocation | BUILD (v1 matrix) → MODIFY (v2) | Riskfolio-Lib / PyPortfolioOpt | matrix now, optimizer later |
| LLM explainer | BUILD prompts + REUSE | langchain-groq | pattern: AI-Stock-Advisor (RAG), ai-powered-robo-advisor |
| Portfolio/goal dashboard UX | BUILD | React+shadcn | pattern: Ghostfolio, Maybe |
| Financial ratios/analytics | REUSE (optional) | FinanceToolkit | only if needed |

### AI analyst layer — v2
| Component | Verdict | Tool / source | Note |
|-----------|---------|---------------|------|
| Multi-agent analyst (debate→confidence) | BUILD on framework | REUSE LangGraph; PATTERN TradingAgents, ai-hedge-fund | advises risk mgr, never overrides |
| News / sentiment agent | MODIFY | FinGPT | feeds confidence score |
| Trade-learning memory | PATTERN | FinMem | improves over time |

### Platform (plumbing — all REUSE)
FastAPI · React+Vite+TypeScript+Tailwind+shadcn · PostgreSQL + SQLAlchemy + Alembic · Groq LLM · Recharts/TanStack Query/Zustand (per PRD §7).

> **Rule of thumb:** we BUILD the brain (signals, risk, FA math) and REUSE the body (data, backtest, charts, execution, alerts). Risk manager is always ours.

---

## 14. Deep scan — user's 7 specific repos (READMEs read 2026-06-29)

### 🟢🔵 1. HKUDS/Vibe-Trading — TOP PICK, our closest twin
[repo](https://github.com/HKUDS/Vibe-Trading) · **MIT** (usable!)
- **Same stack as NexTrade:** Python 3.11+ **FastAPI backend + React 19 frontend**, `pip install vibe-trading-ai`, built-in **API + MCP server**.
- Personal trading agent; **event-driven + swarm** analysis runs; **standalone backtest validation** (`artifacts/validation.json`); **data-source loader registry** (currently tushare/China — we swap in jugaad-data behind same pattern).
- **"Shadow Account"** feature: extracts rules from a real account → generates a `SignalEngine` with **conditional entry (RSI / prior-return bounds)** — directly relevant to our signal engine.
- Mature engineering: LLM content-filter resilience, context micro-compaction, PIT-safe (point-in-time) data to avoid look-ahead bias.
- **Verdict:** study deeply, likely **adopt chunks directly** (loader-registry pattern, MCP server shape, backtest-validation flow, FastAPI+React skeleton). Swap China data → India. **#1 structural reference.**

### 🔵🔵 2. TauricResearch/TradingAgents — primary v2 AI-brain blueprint
[repo](https://github.com/TauricResearch/TradingAgents) · research framework, LangGraph
- Pipeline: **Fundamentals + Sentiment + News + Technical analysts → Bull/Bear researcher debate → Trader → Risk team → Portfolio Manager** (approves/rejects → simulated exchange).
- **Supports Groq** (our LLM) + India tickers (`RELIANCE.NS`, `.BO` via Yahoo). Usable as a package: `TradingAgentsGraph().propagate(ticker, date)`.
- **Decision-log memory:** fetches realised return next run, writes a reflection, injects past lessons → exactly the **trade-learning loop** idea.
- ⚠️ Research scaffold: LLM-heavy, **non-deterministic + expensive** (many agent calls), no fixed replicable returns.
- **Verdict:** **v2 blueprint** for the analyst layer that *advises* our hardcoded risk manager (never overrides). Not v1.

### 🔵 3. The-Swarm-Corporation/AutoHedge — clean simple multi-agent pattern
[repo](https://github.com/The-Swarm-Corporation/AutoHedge) · **MIT**
- Minimal 4-agent pipeline: **Director (thesis) → Quant (analysis) → Risk Manager (sizing) → Execution**. Risk-first, structured JSON output.
- ⚠️ **Solana/crypto only**, wallet private key, fully **autonomous "trades on your behalf"** — against our human-in-loop + no-real-money-till-proven rule.
- **Verdict:** copy the **4-agent pipeline structure** (simpler than TradingAgents, good starter shape for v2). Ignore the crypto/autonomous execution.

### 🟡⚠️ 4. Fincept-Corporation/FinceptTerminal — IDEAS ONLY, license landmine
[repo](https://github.com/Fincept-Corporation/FinceptTerminal)
- **C++20 / Qt6 desktop app** (wrong stack — not our Python/React web). Has 37 AI agents, 100+ data connectors, **16 Indian broker integrations** (Zerodha, Angel, Upstox, Fyers, Dhan, Groww…), paper trading, QuantLib.
- 🚨 **License trap:** dual AGPL-3.0 + commercial. Free *only* for personal/learning. **Any** business/startup/internal use needs a paid license; **liquidated damages start at USD 50,000/yr**; obligation attaches to derivative works **even if you replace their APIs**; joint liability extends to any developer/consultant. Now only monthly-maintained.
- **Verdict:** browse for **ideas** (broker list, feature menu, screen layout). **Do NOT copy code or build on it.** Wrong stack + legal risk for a multi-user/anything-commercial future.

### ⚪ 5. harry0703/MoneyPrinterTurbo — OFF-CORE (video tool, not trading)
[repo](https://github.com/harry0703/MoneyPrinterTurbo)
- Name misleads — it's an **AI short-video generator** (topic → LLM script → TTS → stock footage → subtitles → MP4). No trading/finance logic.
- **Verdict:** park under **marketing** — could make promo/social videos for NexTrade later. Not in the trading system.

### ⚪ 6. OpenBMB/VoxCPM — OFF-CORE (TTS / voice)
[repo](https://github.com/OpenBMB/VoxCPM)
- Tokenizer-free **text-to-speech** model. Voice synthesis, not trading.
- **Verdict:** park as nice-to-have **voice alerts / spoken daily summary** (v3). Not core.

### 🟡 7. jo-inc/camoufox (camofox-browser) — NICHE UTILITY
[repo](https://github.com/jo-inc/camofox-browser)
- Stealth / anti-detect Firefox for scraping. Not trading.
- **Verdict:** keep in back pocket — if NSE / news sites block scraping, camoufox = resilient **data/news fetch** feeding the v2 sentiment agent. Use only if blocked.

### Net new actions from this batch
1. **Vibe-Trading = primary skeleton reference** — clone, study loader-registry + MCP server + backtest-validation + FastAPI/React layout; adapt to India (jugaad-data).
2. **AutoHedge 4-agent shape** = simplest v2 multi-agent starter; **TradingAgents** = richer v2 blueprint + decision-log memory.
3. **Avoid FinceptTerminal code** (license). Mine only ideas.
4. **MoneyPrinterTurbo / VoxCPM / camoufox** = parked side-utilities (marketing video / voice alerts / scraping), not trading core.

### TradingView (user connecting via MCP)
- TradingView has **no official free data/order API.** An MCP server typically exposes TA rating / screener / chart links (scraped). Useful to **cross-check** our signal vs TradingView's technical rating — a confirmation input, not primary.
- **Real gold for us:** TradingView **Lightweight Charts** (free, MIT JS lib) → best-in-class candlestick chart for our React frontend (better than Recharts for OHLC). Adopt for the trading dashboard chart.
