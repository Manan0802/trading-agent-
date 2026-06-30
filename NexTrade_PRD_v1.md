# NexTrade — Complete Product Requirements Document (PRD)

**Version:** 1.0  
**Date:** June 2026  
**Author:** Manan  
**Status:** Pre-Build — Ready for Claude Code  
**Stack Decision:** Final (see Section 7)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context & Goals](#2-business-context--goals)
3. [User Personas](#3-user-personas)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [Part A — Financial Advisor](#5-part-a--financial-advisor)
6. [Part B — AI Trading Agent](#6-part-b--ai-trading-agent)
7. [Complete Tech Stack](#7-complete-tech-stack)
8. [Data Sources & External APIs](#8-data-sources--external-apis)
9. [Database Schema](#9-database-schema)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Backend API Specification](#11-backend-api-specification)
12. [WhatsApp Alerts Integration](#12-whatsapp-alerts-integration)
13. [Phase-Wise Roadmap](#13-phase-wise-roadmap)
14. [Folder Structure](#14-folder-structure)
15. [Open Source Tools & MCPs](#15-open-source-tools--mcps)
16. [SEBI Compliance Notes](#16-sebi-compliance-notes)
17. [Success Metrics & KPIs](#17-success-metrics--kpis)

---

## 1. Executive Summary

NexTrade is a **unified personal AI-powered financial platform** with two core modules:

**Part A — Financial Advisor:** A deterministic, math-first goal-based financial planning engine. Calculates SIP requirements, asset allocation, tax-saving strategies, and rebalancing schedules for personal goals (retirement, home, education, emergency fund). LLM explains everything in plain Hinglish.

**Part B — AI Trading Agent:** An emotion-free, rule-based algorithmic swing trading system. Targets Indian index ETFs (NIFTYBEES on NSE to start). Includes full backtesting engine (vectorbt), paper trading simulation, trade journal, WhatsApp alerts, and eventually semi-automated real-money execution.

| Dimension | Details |
|-----------|---------|
| Platform | Unified web dashboard (React + Vite) + WhatsApp alerts |
| Backend | Python + FastAPI + LangGraph + Groq Llama 3.3 |
| Users | Personal use + 4-5 close friends/family |
| Timeline | 1-2 months to working MVP (Claude Code assisted) |
| Budget | ₹500–2000/month infra |
| Starting Capital (real) | ₹10–15k (only after paper trading proves system) |

---

## 2. Business Context & Goals

### 2.1 Primary Goals

1. **Side Income** — Build a disciplined, edge-based trading system that generates practical consistent returns over time
2. **Deep Learning** — Understand algo trading from scratch: signals, backtesting, risk management, live execution
3. **Financial Independence** — Long-term wealth building via passive goal-based investing (FA) + active swing trading (Agent)
4. **AI Engineering Showcase** — Demonstrates multi-agent AI architecture in a real-world fintech context

### 2.2 Non-Goals (Explicitly Out of Scope)

- ❌ Get-rich-quick bot or guaranteed profit system
- ❌ High-frequency trading (HFT) — requires colocated servers, sub-millisecond execution
- ❌ Options/Derivatives/F&O trading in Phase 1 (too complex for start)
- ❌ Multi-user public SaaS (Phase 1 is personal)
- ❌ Robo-advisor with SEBI RIA license (out of scope legally)
- ❌ Crypto trading (Phase 1 — Indian market only)

### 2.3 Core Philosophy (Non-Negotiable)

> **"100 trades → 45 losses, 55 profits = acceptable. Losses small (controlled by risk manager). Profits slightly larger (R:R ratio). Overall green over time = goal."**

- This is a **probability game**, not a prediction game
- Risk management is more important than signal quality
- Paper trading MUST prove the system before real money goes in
- One bad strategy = drawdown. Good risk control = you survive to trade another day.

---

## 3. User Personas

### 3.1 Primary User: Manan (Self)

| Attribute | Value |
|-----------|-------|
| Background | Software Engineer, AI/ML focus |
| Investing Experience | Basic — MFs via Groww, SIP started |
| Trading Experience | Zero — never actively traded |
| Technical Skill | High — Python, LangGraph, MERN, APIs |
| Goal | Learn algo trading + generate side income |
| Time Available | 5–10 hrs/week |
| Risk Appetite | Moderate-High (willing to lose testing capital) |

### 3.2 Secondary Users (4–5 People)

| Attribute | Value |
|-----------|-------|
| Who | Close friends and family |
| Module | Primarily Financial Advisor only |
| Technical Skill | Low — non-technical |
| Need | Simple goal planning, SIP calculator, alerts |
| Interface | Web UI + WhatsApp alerts only |

---

## 4. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        NexTrade Platform                         │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  React + Vite Frontend                    │   │
│  │           (Web Dashboard — TypeScript + Tailwind)         │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                             │ REST API (HTTPS)                    │
│  ┌──────────────────────────▼────────────────────────────────┐  │
│  │                   FastAPI Backend (Python)                  │  │
│  │                                                             │  │
│  │   ┌──────────────────┐    ┌──────────────────────────────┐ │  │
│  │   │   PART A:        │    │   PART B:                    │ │  │
│  │   │   Financial      │    │   AI Trading Agent           │ │  │
│  │   │   Advisor Engine │    │   (LangGraph Orchestrator)   │ │  │
│  │   │                  │    │                              │ │  │
│  │   │ • SIP Calculator │    │ • Signal Engine (pandas-ta)  │ │  │
│  │   │ • Asset Alloc.   │    │ • Risk Manager               │ │  │
│  │   │ • Tax Advisor    │    │ • Backtest Engine (vectorbt) │ │  │
│  │   │ • Rebalancer     │    │ • Paper Trader               │ │  │
│  │   │ • LLM Explainer  │    │ • Trade Journal              │ │  │
│  │   └────────┬─────────┘    └──────────────┬───────────────┘ │  │
│  │            │                              │                  │  │
│  │   ┌────────▼──────────────────────────────▼──────────────┐ │  │
│  │   │              PostgreSQL (Railway)                      │ │  │
│  │   │   users | goals | trades | signals | backtest_results  │ │  │
│  │   └───────────────────────────────────────────────────────┘ │  │
│  │            │                              │                  │  │
│  │   ┌────────▼──────────┐    ┌─────────────▼──────────────┐  │  │
│  │   │   Groq API         │    │   Data Pipeline             │  │  │
│  │   │   Llama 3.3 70B    │    │   yfinance (historical)     │  │  │
│  │   │   (LLM layer)      │    │   Angel One SmartAPI (live) │  │  │
│  │   └───────────────────┘    └─────────────────────────────┘  │  │
│  │                                                               │  │
│  │   ┌───────────────────────────────────────────────────────┐  │  │
│  │   │   APScheduler — Cron Jobs                              │  │  │
│  │   │   9:30 AM scan | 3:00 PM EOD | Sunday rebalancing     │  │  │
│  │   └───────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                             │                                        │
│  ┌──────────────────────────▼────────────────────────────────┐      │
│  │              Twilio WhatsApp Alerts                         │      │
│  │       (Signals, Trade alerts, Daily summaries)              │      │
│  └─────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Part A — Financial Advisor

### 5.1 Feature Overview

The Financial Advisor is a **deterministic math engine** (pure formulas, no guessing, 100% reproducible results) with an **LLM layer that explains results in plain Hinglish**.

| Feature | Description |
|---------|-------------|
| Goal Input System | User defines financial goals with timeline + amount |
| SIP Calculator | Calculates exact monthly SIP needed per goal |
| Asset Allocation Engine | Equity/Debt/Gold split based on risk + timeline |
| Tax Saving Advisor | 80C, 80D, NPS recommendations with amounts |
| Rebalancing Scheduler | Detects drift, alerts via WhatsApp |
| LLM Explainer | Groq Llama explains every output in simple language |

### 5.2 Supported Goal Types

| Goal Type | Example Use Case | Key Inputs |
|-----------|-----------------|------------|
| Emergency Fund | 6 months expenses buffer | Monthly expense, target months coverage |
| Home Purchase | ₹20L down payment in 5 years | Target amount, years to goal |
| Retirement | ₹2Cr corpus in 30 years | Target corpus, years, current age |
| Child Education | College fees in 12 years | Target amount, child's current age |
| Vacation | Europe trip in 2 years | Target amount, years |
| Wedding | ₹15L in 3 years | Target amount, years |
| Custom | Any user-defined goal | Target amount, years, name |

### 5.3 SIP Calculation Engine

#### Core Formula (Future Value of Monthly SIP)

```python
def calculate_required_sip(
    target_amount: float,
    years: int,
    annual_return_rate: float,
    current_savings: float = 0.0,
    inflation_rate: float = 0.06
) -> dict:
    """
    FV of existing savings + FV of monthly SIP = Inflation-adjusted target
    
    FV formula for monthly SIP:
    FV = PMT × [((1 + r)^n - 1) / r] × (1 + r)
    
    Solving for PMT:
    PMT = FV × r / [((1 + r)^n - 1) × (1 + r)]
    
    Where:
        PMT = Monthly SIP amount (what we solve for)
        r   = Monthly return rate = annual_rate / 12
        n   = Number of months = years × 12
        FV  = Inflation-adjusted target corpus
    """
    # Adjust target for inflation
    inflation_adjusted_target = target_amount * ((1 + inflation_rate) ** years)
    
    # Subtract future value of existing savings
    r_monthly = annual_return_rate / 12
    n = years * 12
    fv_existing = current_savings * ((1 + r_monthly) ** n)
    remaining_target = max(0, inflation_adjusted_target - fv_existing)
    
    # Solve for PMT
    if r_monthly == 0:
        sip = remaining_target / n
    else:
        sip = remaining_target * r_monthly / (((1 + r_monthly) ** n - 1) * (1 + r_monthly))
    
    return {
        "required_monthly_sip": round(sip, 0),
        "inflation_adjusted_target": round(inflation_adjusted_target, 0),
        "future_value_of_existing_savings": round(fv_existing, 0),
        "net_target_to_achieve": round(remaining_target, 0),
        "total_invested": round(sip * n, 0),
        "wealth_created": round(remaining_target - (sip * n), 0),
    }
```

#### Assumed Return Rates (Conservative, Configurable)

| Asset Class | Annual Return | Notes |
|-------------|---------------|-------|
| Equity — Large Cap Index | 12% | Nifty 50 historical avg |
| Equity — Mid/Small Cap | 14% | Higher risk |
| Debt Mutual Fund | 7% | Short duration |
| Gold | 8% | Long term gold avg |
| FD / RD | 6.5% | Current SBI FD |
| PPF | 7.1% | Current govt rate |
| NPS | 10% | Historical Tier 1 equity |
| Liquid Fund | 6% | For emergency fund |

> ⚠️ These are projections, not guarantees. Displayed prominently in UI.

### 5.4 Asset Allocation Engine

#### Risk Profile Scoring (0–10)

```python
RISK_QUESTIONS = [
    {
        "question": "If your investment drops 30% tomorrow, what would you do?",
        "options": {
            "Sell everything immediately": 1,
            "Sell some to limit loss": 3,
            "Hold and wait for recovery": 6,
            "Buy more at lower prices": 10
        }
    },
    {
        "question": "What is your investment experience?",
        "options": {
            "Never invested before": 1,
            "Only FDs/savings": 3,
            "Some mutual funds": 6,
            "Stocks/crypto regularly": 9
        }
    },
    {
        "question": "How stable is your income?",
        "options": {
            "Unstable/freelance": 2,
            "Somewhat stable": 5,
            "Very stable (govt/corporate job)": 8,
            "Multiple income streams": 10
        }
    },
    {
        "question": "Do you have existing financial liabilities?",
        "options": {
            "Heavy loans (>50% income)": 1,
            "Moderate loans (20-50%)": 4,
            "Light loans (<20%)": 7,
            "No loans at all": 10
        }
    }
]

def calculate_risk_score(answers: list[int]) -> int:
    return round(sum(answers) / len(answers))

# Score mapping
# 1-4 → Conservative
# 5-7 → Moderate
# 8-10 → Aggressive
```

#### Allocation Matrix

| Timeline | Risk | Equity | Debt | Gold |
|----------|------|--------|------|------|
| < 2 years | Any | 20% | 70% | 10% |
| 2–5 years | Conservative | 30% | 60% | 10% |
| 2–5 years | Moderate | 50% | 40% | 10% |
| 2–5 years | Aggressive | 65% | 25% | 10% |
| 5–10 years | Conservative | 50% | 40% | 10% |
| 5–10 years | Moderate | 65% | 25% | 10% |
| 5–10 years | Aggressive | 75% | 15% | 10% |
| > 10 years | Conservative | 65% | 25% | 10% |
| > 10 years | Moderate | 75% | 15% | 10% |
| > 10 years | Aggressive | 85% | 10% | 5% |

#### Recommended Products per Allocation

| Asset | Recommended Product | Type |
|-------|--------------------|----- |
| Equity (core) | Nifty 50 Index Fund (Direct Growth) | MF |
| Equity (ETF) | NIFTYBEES | ETF on NSE |
| Equity (mid) | Nifty Midcap 150 Index Fund | MF |
| Debt | Parag Parikh Liquid Fund / HDFC Short Duration | MF |
| Gold | Nippon India Gold ETF (GOLDBEES) | ETF |
| Gold (alt) | Sovereign Gold Bond (SGB) | Govt Bond |
| Tax saving equity | Mirae Asset ELSS Tax Saver | ELSS MF |
| Emergency | HDFC Liquid Fund / Savings account | Liquid MF |

### 5.5 Tax Saving Logic

```python
def generate_tax_saving_plan(
    annual_income: float,
    existing_80c: float = 0,
    existing_80d: float = 0,
    has_nps: bool = False
) -> dict:
    """
    Section 80C — Limit ₹1,50,000
    Section 80D — Health insurance ₹25,000 (₹50,000 for senior parents)
    Section 80CCD(1B) — NPS additional ₹50,000 (over 80C)
    """
    
    # 80C recommendations
    remaining_80c = max(0, 150000 - existing_80c)
    elss_suggestion = min(remaining_80c, 150000)
    
    # Tax rate (simplified new regime excluded — old regime calc)
    def tax_rate(income):
        if income <= 250000: return 0
        elif income <= 500000: return 0.05
        elif income <= 1000000: return 0.20
        else: return 0.30
    
    effective_rate = tax_rate(annual_income)
    
    # NPS recommendation (if income > 5L)
    nps_suggestion = 50000 if annual_income > 500000 and not has_nps else 0
    
    # Health insurance gap
    health_gap = max(0, 25000 - existing_80d)
    
    return {
        "elss_recommended": elss_suggestion,
        "tax_saved_via_elss": round(elss_suggestion * effective_rate),
        "nps_recommended": nps_suggestion,
        "tax_saved_via_nps": round(nps_suggestion * effective_rate),
        "health_insurance_gap": health_gap,
        "tax_saved_via_80d": round(health_gap * effective_rate),
        "total_potential_tax_saving": round(
            (elss_suggestion + nps_suggestion + health_gap) * effective_rate
        ),
        "priority_order": ["ELSS (80C)", "Health Insurance (80D)", "NPS (80CCD1B)"]
    }
```

### 5.6 Rebalancing Logic

**Check runs every Sunday via scheduled job:**

```python
def check_rebalancing_needed(
    current_allocation: dict,   # {"equity": 80, "debt": 15, "gold": 5}
    target_allocation: dict,    # {"equity": 75, "debt": 15, "gold": 10}
    drift_threshold: float = 5.0  # 5% absolute drift
) -> dict:
    """
    If any asset class drifts more than 5% from target → trigger rebalancing alert
    """
    rebalancing_actions = []
    needs_rebalancing = False
    
    for asset in target_allocation:
        current = current_allocation.get(asset, 0)
        target = target_allocation[asset]
        drift = abs(current - target)
        
        if drift > drift_threshold:
            needs_rebalancing = True
            direction = "SELL" if current > target else "BUY"
            rebalancing_actions.append({
                "asset": asset,
                "current_pct": current,
                "target_pct": target,
                "drift": drift,
                "action": direction,
                "action_amount_pct": drift
            })
    
    return {
        "needs_rebalancing": needs_rebalancing,
        "actions": rebalancing_actions,
        "last_checked": datetime.now().isoformat()
    }
```

### 5.7 LLM Integration in Financial Advisor

**LLM fires in 3 scenarios:**

1. After SIP calculation → plain-language goal summary
2. After asset allocation → explain WHY this split
3. After tax saving → explain each recommendation simply

```python
FA_SYSTEM_PROMPT = """
You are NexTrade's friendly Indian financial advisor. 
Explain financial plans in simple Hinglish (Hindi-English mix).
Be warm, practical, and concise (3-4 sentences max).
Never guarantee returns. Always say "projected" not "guaranteed".
Use emojis sparingly. Be encouraging but realistic.
"""

def get_goal_explanation(goal_data: dict, sip_result: dict, allocation: dict) -> str:
    user_message = f"""
Explain this financial goal plan to the user:

Goal: {goal_data['goal_name']}
Target Amount: ₹{goal_data['target_amount']:,.0f}
Timeline: {goal_data['years']} years
Required Monthly SIP: ₹{sip_result['required_monthly_sip']:,.0f}
Asset Allocation: {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold
Total to be invested: ₹{sip_result['total_invested']:,.0f}
Projected wealth created: ₹{sip_result['wealth_created']:,.0f}

Write a warm 3-4 sentence explanation in simple Hinglish.
"""
    # Call Groq API via langchain-groq
    response = llm.invoke([
        SystemMessage(content=FA_SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ])
    return response.content
```

---

## 6. Part B — AI Trading Agent

### 6.1 Architecture Overview

```
Trading Agent Pipeline (runs daily at market hours)
═══════════════════════════════════════════════════

[1] DATA PIPELINE
    └── yfinance → Historical OHLCV (backtest)
    └── Angel One SmartAPI → Live OHLCV (paper/real)
    └── Stored in PostgreSQL daily

[2] INDICATOR ENGINE (pandas-ta)
    └── EMA 20, 50, 200
    └── RSI 14
    └── MACD (12, 26, 9)
    └── Bollinger Bands (20, 2)
    └── ATR 14 (for stop-loss sizing)
    └── Volume SMA 20 + ratio

[3] MARKET REGIME DETECTOR
    └── ADX 14 (trend strength)
    └── Price vs EMA 200 (bull/bear)
    └── ATR ratio (volatility check)
    └── Output: TRENDING_BULL / TRENDING_BEAR / SIDEWAYS / VOLATILE

[4] SIGNAL ENGINE (LangGraph Node)
    └── 5 conditions → confidence score (0.0–1.0)
    └── BUY signal if confidence ≥ 0.60
    └── EXIT checks on open positions

[5] RISK MANAGER (hardcoded, cannot be overridden)
    └── Position sizing: 1% capital risk per trade
    └── Stop loss: Entry − 2×ATR
    └── Target: Entry + 2×risk (2:1 R:R)
    └── Max positions: 3
    └── Daily loss limit: 3% → auto-stop

[6] EXECUTION LAYER
    └── Backtest: vectorbt (historical simulation)
    └── Paper: Fake portfolio, live prices
    └── Real (Phase 5): Angel One order placement

[7] TRADE JOURNAL + ALERTS
    └── Every trade logged to DB with full context
    └── LLM generates trade summary
    └── WhatsApp alerts: signals, exits, daily summary
```

### 6.2 Starting Instrument

**Primary:** `NIFTYBEES.NS` — Nippon India ETF Nifty BeES (NSE)

| Property | Value |
|----------|-------|
| Tracks | Nifty 50 Index |
| Liquidity | Very High (safe for algos) |
| Price range | ~₹200–300 per unit |
| Lot size | 1 unit (no minimum lot) |
| Data availability | yfinance: 10+ years free |
| Exchange | NSE (National Stock Exchange) |
| Trading hours | 9:15 AM – 3:30 PM IST (Mon–Fri) |

**Phase 2 expansion (after 3–4 months):**
- `BANKBEES.NS` — Bank Nifty ETF
- `RELIANCE.NS`, `INFY.NS` — Large cap stocks
- Sector ETFs (IT, Pharma, Auto)

### 6.3 Trading Style: Swing Trading

| Parameter | Value |
|-----------|-------|
| Hold Duration | 2–10 trading days |
| Frequency | 3–8 trades per month |
| Data Timeframe | Daily candles (1D) |
| Analysis Timeframe | Weekly for regime, Daily for entry |
| Risk per trade | 1% of capital |
| Target R:R | 2:1 (min), 3:1 (ideal) |

**Why swing for Phase 1:**
- No sub-second execution needed
- Can check/manage once or twice daily
- Less noise than intraday
- Daily candles = cleaner signals
- Easier to backtest reliably
- No intraday margin requirements

### 6.4 Technical Indicators Engine

```python
import pandas_ta as ta
import pandas as pd

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: OHLCV DataFrame (Date, Open, High, Low, Close, Volume)
    Output: DataFrame with all indicators appended
    """
    # === TREND ===
    df['ema_20'] = ta.ema(df['Close'], length=20)    # Short-term trend
    df['ema_50'] = ta.ema(df['Close'], length=50)    # Medium-term trend
    df['ema_200'] = ta.ema(df['Close'], length=200)  # Long-term regime filter
    
    # === MOMENTUM ===
    df['rsi'] = ta.rsi(df['Close'], length=14)       # 0-100: 30=oversold, 70=overbought
    
    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']
    
    # === VOLATILITY ===
    bb = ta.bbands(df['Close'], length=20, std=2)
    df['bb_upper'] = bb['BBU_20_2.0']
    df['bb_middle'] = bb['BBM_20_2.0']
    df['bb_lower'] = bb['BBL_20_2.0']
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    
    # === TREND STRENGTH ===
    adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    df['adx'] = adx['ADX_14']
    df['dmp'] = adx['DMP_14']  # +DI (bullish)
    df['dmn'] = adx['DMN_14']  # -DI (bearish)
    
    # === VOLUME ===
    df['vol_sma_20'] = ta.sma(df['Volume'], length=20)
    df['vol_ratio'] = df['Volume'] / df['vol_sma_20']  # >1.5 = volume surge
    
    return df
```

### 6.5 Market Regime Detection

```python
def detect_market_regime(df: pd.DataFrame) -> str:
    """
    Classifies current market condition to adapt strategy.
    Uses last row of DataFrame (current bar).
    """
    latest = df.iloc[-1]
    
    adx = latest['adx']
    above_200ema = latest['Close'] > latest['ema_200']
    atr_pct = latest['atr'] / latest['Close']  # ATR as % of price
    
    if adx > 25 and above_200ema:
        return 'TRENDING_BULL'    # Strong uptrend → full position, long only
    elif adx > 25 and not above_200ema:
        return 'TRENDING_BEAR'    # Strong downtrend → NO new longs, stay cash
    elif adx < 20:
        return 'SIDEWAYS'         # Range-bound → reduce position size, tighter SL
    elif atr_pct > 0.025:
        return 'VOLATILE'         # High volatility → reduce position or skip
    else:
        return 'NEUTRAL'          # Normal conditions → moderate position

# Position size multipliers per regime
REGIME_SIZE_MULTIPLIERS = {
    'TRENDING_BULL': 1.0,    # Full position sizing
    'TRENDING_BEAR': 0.0,    # NO trades (cash only)
    'SIDEWAYS':      0.5,    # Half position
    'VOLATILE':      0.5,    # Half position
    'NEUTRAL':       0.75,   # 75% position
}

# Allowed actions per regime
REGIME_ALLOWED_ACTIONS = {
    'TRENDING_BULL': ['BUY', 'HOLD', 'EXIT'],
    'TRENDING_BEAR': ['EXIT', 'HOLD'],         # Never open new longs
    'SIDEWAYS':      ['BUY', 'HOLD', 'EXIT'],  # With reduced size
    'VOLATILE':      ['EXIT', 'HOLD'],          # Prefer to stay out
    'NEUTRAL':       ['BUY', 'HOLD', 'EXIT'],
}
```

### 6.6 Signal Generation Engine (LangGraph Node)

```python
def generate_entry_signal(df: pd.DataFrame, regime: str) -> dict:
    """
    Evaluates 5 conditions for long entry.
    Returns signal type + confidence score.
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 5 conditions for BUY signal
    conditions = {
        # Condition 1: Short-term above medium-term EMA (uptrend)
        'ema_crossover': (
            latest['ema_20'] > latest['ema_50'] and
            prev['ema_20'] <= prev['ema_50']  # Fresh crossover
        ),
        
        # Condition 2: Price above long-term EMA (bull regime)
        'above_200ema': latest['Close'] > latest['ema_200'],
        
        # Condition 3: RSI in healthy range (not overbought, not too weak)
        'rsi_healthy': 35 < latest['rsi'] < 65,
        
        # Condition 4: MACD momentum positive
        'macd_bullish': (
            latest['macd'] > latest['macd_signal'] and
            latest['macd_hist'] > 0
        ),
        
        # Condition 5: Volume confirms move
        'volume_confirms': latest['vol_ratio'] > 1.2,
    }
    
    score = sum(conditions.values())         # 0–5
    confidence = round(score / 5.0, 2)      # 0.0–1.0
    
    # Regime check
    if regime == 'TRENDING_BEAR' or regime == 'VOLATILE':
        return {'signal': 'HOLD', 'confidence': 0.0, 'conditions': conditions,
                'reason': f'Signal blocked by regime: {regime}'}
    
    if confidence >= 0.60:  # Minimum 3/5 conditions
        return {'signal': 'BUY', 'confidence': confidence, 'conditions': conditions}
    
    return {'signal': 'HOLD', 'confidence': confidence, 'conditions': conditions}


def check_exit_signal(position: dict, df: pd.DataFrame) -> dict:
    """
    Checks if open position should be exited.
    """
    latest = df.iloc[-1]
    current_price = latest['Close']
    
    # Priority 1: Stop loss hit (hardcoded, never skip)
    if current_price <= position['stop_loss']:
        return {'exit': True, 'reason': 'STOP_LOSS_HIT', 
                'exit_price': position['stop_loss']}
    
    # Priority 2: Target hit
    if current_price >= position['target']:
        return {'exit': True, 'reason': 'TARGET_REACHED', 
                'exit_price': position['target']}
    
    # Priority 3: Trend reversal (EMA crossover flips)
    if latest['ema_20'] < latest['ema_50']:
        return {'exit': True, 'reason': 'TREND_REVERSAL', 
                'exit_price': current_price}
    
    # Priority 4: RSI extreme overbought
    if latest['rsi'] > 75:
        return {'exit': True, 'reason': 'RSI_OVERBOUGHT', 
                'exit_price': current_price}
    
    # Priority 5: Max hold duration (10 days for swing)
    days_held = (datetime.now() - position['entry_time']).days
    if days_held >= 10:
        return {'exit': True, 'reason': 'MAX_HOLD_DURATION', 
                'exit_price': current_price}
    
    return {'exit': False, 'reason': None}
```

### 6.7 Risk Manager — Most Critical Component

> **Rule: Never risk more than 1% of total capital on a single trade. This is hardcoded. Not configurable. Not overridable.**

```python
# ============================================
# RISK PARAMETERS — HARDCODED, DO NOT CHANGE
# ============================================
RISK_CONFIG = {
    'max_risk_per_trade_pct': 0.01,    # 1% capital max loss per trade
    'stop_loss_atr_multiplier': 2.0,   # Stop = Entry − (2 × ATR)
    'reward_risk_ratio': 2.0,          # Target = Entry + (risk × 2)
    'max_daily_loss_pct': 0.03,        # 3% daily → STOP all trading
    'max_open_positions': 3,           # Never hold more than 3 simultaneous trades
    'max_capital_per_trade_pct': 0.30, # Never allocate > 30% capital to single trade
}

def calculate_position_size(
    total_capital: float,
    entry_price: float,
    stop_loss: float,
    regime_multiplier: float = 1.0
) -> int:
    """
    Position size based on fixed % risk.
    Formula: Shares = (Capital × Risk%) / (Entry − StopLoss)
    """
    risk_amount = total_capital * RISK_CONFIG['max_risk_per_trade_pct']
    risk_per_share = entry_price - stop_loss
    
    if risk_per_share <= 0:
        raise ValueError("Stop loss must be below entry price")
    
    # Risk-based position size
    raw_shares = risk_amount / risk_per_share
    
    # Capital constraint (max 30% of capital in one trade)
    max_by_capital = (total_capital * RISK_CONFIG['max_capital_per_trade_pct']) / entry_price
    
    # Apply regime multiplier (e.g., 0.5 in SIDEWAYS)
    shares = int(min(raw_shares, max_by_capital) * regime_multiplier)
    
    return max(0, shares)


def calculate_stop_loss(entry_price: float, atr: float) -> float:
    """Stop loss placed 2×ATR below entry."""
    return round(entry_price - (RISK_CONFIG['stop_loss_atr_multiplier'] * atr), 2)


def calculate_target(entry_price: float, stop_loss: float) -> float:
    """Target placed at 2:1 reward:risk ratio above entry."""
    risk = entry_price - stop_loss
    return round(entry_price + (risk * RISK_CONFIG['reward_risk_ratio']), 2)


def check_daily_loss_limit(daily_pnl: float, total_capital: float) -> bool:
    """Returns True if daily loss limit hit → STOP TRADING."""
    if daily_pnl < 0:
        loss_pct = abs(daily_pnl) / total_capital
        return loss_pct >= RISK_CONFIG['max_daily_loss_pct']
    return False


def validate_trade_allowed(
    current_positions: int,
    daily_pnl: float,
    total_capital: float
) -> tuple[bool, str]:
    """Master check before opening any new position."""
    if current_positions >= RISK_CONFIG['max_open_positions']:
        return False, f"Max positions ({RISK_CONFIG['max_open_positions']}) already open"
    if check_daily_loss_limit(daily_pnl, total_capital):
        return False, "Daily loss limit reached — trading halted today"
    return True, "OK"
```

### 6.8 Backtest Engine

**Library:** `vectorbt` — fastest Python backtester, vectorized operations

```python
import vectorbt as vbt
import yfinance as yf
import pandas as pd

def run_backtest(
    ticker: str = 'NIFTYBEES.NS',
    start_date: str = '2015-01-01',
    end_date: str = '2024-12-31',
    initial_capital: float = 100000,
    fees: float = 0.001,       # 0.1% = realistic India STT + brokerage
    slippage: float = 0.001    # 0.1% = realistic slippage
) -> dict:
    
    # Download historical data
    raw = yf.download(ticker, start=start_date, end=end_date, interval='1d', auto_adjust=True)
    df = raw.copy()
    
    # Calculate indicators
    df = calculate_indicators(df)
    df = df.dropna()
    
    # Generate signals (Boolean Series)
    entries = pd.Series(False, index=df.index)
    exits = pd.Series(False, index=df.index)
    
    for i in range(1, len(df)):
        slice_df = df.iloc[:i+1]
        regime = detect_market_regime(slice_df)
        signal = generate_entry_signal(slice_df, regime)
        
        if signal['signal'] == 'BUY' and not entries.iloc[i-1]:
            entries.iloc[i] = True
        
        exit_check = check_exit_signal(
            {'stop_loss': 0, 'target': float('inf'), 'entry_time': df.index[i]},
            slice_df
        )
        if exit_check['exit']:
            exits.iloc[i] = True
    
    # Run vectorbt portfolio simulation
    portfolio = vbt.Portfolio.from_signals(
        close=df['Close'],
        entries=entries,
        exits=exits,
        init_cash=initial_capital,
        fees=fees,
        slippage=slippage,
        freq='D'
    )
    
    return extract_backtest_metrics(portfolio, initial_capital)


def extract_backtest_metrics(portfolio, initial_capital: float) -> dict:
    """Extract all relevant metrics with honest assessment."""
    metrics = {
        'total_return_pct': round(portfolio.total_return() * 100, 2),
        'cagr_pct': round(portfolio.annualized_return() * 100, 2),
        'sharpe_ratio': round(portfolio.sharpe_ratio(), 3),
        'sortino_ratio': round(portfolio.sortino_ratio(), 3),
        'max_drawdown_pct': round(portfolio.max_drawdown() * 100, 2),
        'win_rate_pct': round(portfolio.trades.win_rate() * 100, 2),
        'profit_factor': round(portfolio.trades.profit_factor(), 3),
        'total_trades': int(portfolio.trades.count()),
        'avg_trade_duration_days': round(portfolio.trades.duration.mean().days, 1),
        'best_trade_pct': round(portfolio.trades.returns.max() * 100, 2),
        'worst_trade_pct': round(portfolio.trades.returns.min() * 100, 2),
        'final_capital': round(portfolio.final_value(), 2),
        'fees_paid_total': round(portfolio.fees_paid().sum(), 2),
    }
    
    # Pass/Fail criteria
    metrics['passed_criteria'] = (
        metrics['sharpe_ratio'] > 1.0 and
        metrics['max_drawdown_pct'] < 15.0 and
        metrics['win_rate_pct'] > 45.0 and
        metrics['profit_factor'] > 1.3 and
        metrics['total_trades'] >= 50
    )
    
    return metrics
```

#### Backtest Pass Criteria (Must clear to proceed to paper trading)

| Metric | Minimum Threshold | Why |
|--------|------------------|-----|
| Sharpe Ratio | > 1.0 | Risk-adjusted return is acceptable |
| Max Drawdown | < 15% | Portfolio can survive bad periods |
| Win Rate | > 45% | Strategy wins more than half the time |
| Profit Factor | > 1.3 | Total profit ÷ total loss > 1.3 |
| Total Trades | > 50 | Statistically significant sample |
| CAGR | > 12% | Beats Nifty buy-and-hold benchmark |

### 6.9 Paper Trading Engine

```python
class PaperTradingEngine:
    """
    Simulates real trading with live market data and fake money.
    Run for minimum 2-3 months before any real money.
    """
    
    def __init__(self, initial_capital: float = 100000):
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.positions: dict = {}       # Open positions
        self.trade_history: list = []   # All closed trades
        self.daily_pnl: float = 0.0
        self.total_pnl: float = 0.0
        self.is_active: bool = False
    
    def run_morning_scan(self):
        """Runs at 9:30 AM IST every weekday."""
        # 1. Fetch latest data
        df = fetch_latest_ohlcv('NIFTYBEES.NS', days=60)
        df = calculate_indicators(df)
        
        # 2. Check daily loss limit first
        if check_daily_loss_limit(self.daily_pnl, self.capital):
            self.send_whatsapp_alert('RISK_ALERT', {
                'loss': abs(self.daily_pnl),
                'loss_pct': abs(self.daily_pnl) / self.capital * 100
            })
            return
        
        # 3. Check existing positions for exits
        for pos_id, position in list(self.positions.items()):
            exit_check = check_exit_signal(position, df)
            if exit_check['exit']:
                self.close_position(pos_id, exit_check['exit_price'], exit_check['reason'], df)
        
        # 4. Generate new signal
        regime = detect_market_regime(df)
        signal = generate_entry_signal(df, regime)
        
        # 5. Open new position if signal is valid
        if signal['signal'] == 'BUY':
            allowed, reason = validate_trade_allowed(
                len(self.positions), self.daily_pnl, self.capital
            )
            if allowed:
                self.open_position(df, signal, regime)
    
    def open_position(self, df: pd.DataFrame, signal: dict, regime: str):
        entry_price = df.iloc[-1]['Close']
        atr = df.iloc[-1]['atr']
        stop_loss = calculate_stop_loss(entry_price, atr)
        target = calculate_target(entry_price, stop_loss)
        regime_mult = REGIME_SIZE_MULTIPLIERS[regime]
        qty = calculate_position_size(self.capital, entry_price, stop_loss, regime_mult)
        
        if qty == 0:
            return
        
        position = {
            'id': str(uuid4()),
            'instrument': 'NIFTYBEES.NS',
            'entry_price': entry_price,
            'quantity': qty,
            'stop_loss': stop_loss,
            'target': target,
            'regime': regime,
            'confidence': signal['confidence'],
            'signals_triggered': [k for k, v in signal['conditions'].items() if v],
            'entry_time': datetime.now(),
            'capital_at_risk': (entry_price - stop_loss) * qty,
            'trade_phase': 'PAPER'
        }
        
        self.positions[position['id']] = position
        self.send_whatsapp_alert('TRADE_SIGNAL', position)
    
    def close_position(self, pos_id: str, exit_price: float, reason: str, df: pd.DataFrame):
        position = self.positions.pop(pos_id)
        pnl = (exit_price - position['entry_price']) * position['quantity']
        pnl_pct = (exit_price - position['entry_price']) / position['entry_price'] * 100
        
        self.daily_pnl += pnl
        self.total_pnl += pnl
        self.capital += pnl
        
        trade_record = {**position, 
                       'exit_price': exit_price, 
                       'exit_reason': reason,
                       'actual_pnl': round(pnl, 2),
                       'pnl_percent': round(pnl_pct, 2),
                       'holding_days': (datetime.now() - position['entry_time']).days,
                       'exit_time': datetime.now()}
        
        # LLM generates trade summary
        trade_record['llm_summary'] = generate_trade_summary(trade_record)
        
        self.trade_history.append(trade_record)
        self.save_trade_to_db(trade_record)
        self.send_whatsapp_alert('TRADE_EXIT', trade_record)
    
    def run_eod_summary(self):
        """Runs at 3:00 PM IST — sends daily recap."""
        summary = {
            'capital': self.capital,
            'daily_pnl': self.daily_pnl,
            'total_pnl': self.total_pnl,
            'open_positions': len(self.positions),
            'total_trades': len(self.trade_history),
        }
        self.send_whatsapp_alert('DAILY_SUMMARY', summary)
        self.daily_pnl = 0.0  # Reset for next day
```

#### Paper Trading Pass Criteria (to advance to Phase 5)

| Metric | Target |
|--------|--------|
| Minimum duration | 2 months (minimum), 3 recommended |
| Sharpe Ratio (paper) | > 0.8 |
| Max drawdown (paper) | < 10% |
| Consistency | Profitable in 6 out of 8 weeks |
| System reliability | Zero critical bugs over 2 months |
| Signal quality | >45% win rate on paper trades |

### 6.10 Trade Journal

```python
# Every trade stored in DB with full context for analysis

TRADE_SCHEMA = {
    'id': 'UUID',
    'instrument': 'NIFTYBEES.NS',
    'trade_type': 'BUY / SELL',
    'entry_price': 'float',
    'exit_price': 'float',
    'quantity': 'int',
    'stop_loss': 'float',
    'target_price': 'float',
    'actual_pnl': 'float',
    'pnl_percent': 'float',
    'capital_at_risk': 'float',
    'market_regime': 'TRENDING_BULL / SIDEWAYS / etc.',
    'confidence_score': 'float (0.0–1.0)',
    'signals_triggered': 'list of strings',
    'exit_reason': 'STOP_LOSS / TARGET / REVERSAL / TIMEOUT / MANUAL',
    'holding_days': 'int',
    'trade_phase': 'PAPER / REAL',
    'llm_summary': 'string (AI-generated lesson from trade)',
    'entry_time': 'timestamp',
    'exit_time': 'timestamp',
}

def generate_trade_summary(trade: dict) -> str:
    """LLM generates lesson/insight from each trade."""
    prompt = f"""
Analyze this trade briefly (2-3 lines, simple English):

Instrument: {trade['instrument']}
Entry: ₹{trade['entry_price']} → Exit: ₹{trade['exit_price']}  
PnL: ₹{trade['actual_pnl']} ({trade['pnl_percent']}%)
Signals that triggered: {trade['signals_triggered']}
Exit reason: {trade['exit_reason']}
Market regime: {trade['market_regime']}
Confidence at entry: {trade['confidence_score']}
Held for: {trade['holding_days']} days

What went right or wrong? What should we learn from this trade?
Keep it brief and actionable.
"""
    return llm.invoke(prompt).content
```

---

## 7. Complete Tech Stack

### 7.1 Backend

| Component | Tool | Version | Purpose |
|-----------|------|---------|---------|
| Language | Python | 3.11+ | Everything backend |
| API Framework | FastAPI | 0.110+ | REST API, async, auto-docs at /docs |
| ORM | SQLAlchemy | 2.0+ | DB model definitions + queries |
| DB Migrations | Alembic | 1.13+ | Schema version control |
| Task Scheduler | APScheduler | 3.10+ | Market scan cron jobs |
| Agent Framework | LangGraph | 0.2+ | Trading agent orchestration |
| LLM | Groq (Llama 3.3 70B) | latest | FA explanations + trade summaries |
| LLM Client | langchain-groq | latest | Easy Groq API wrapper |
| Backtesting | vectorbt | 0.26+ | Vectorized backtest engine |
| Technical Analysis | pandas-ta | 0.3+ | 130+ indicators including EMA, RSI, MACD, ATR |
| Historical Data | yfinance | 0.2+ | Free NSE/BSE OHLCV data |
| Live Data/Orders | SmartApi-python | latest | Angel One API |
| 2FA (Angel One) | pyotp | latest | TOTP authentication |
| Alerts | twilio | latest | WhatsApp messaging |
| Data Validation | Pydantic | 2.0+ | Request/response models |
| HTTP Client | httpx | 0.27+ | Async HTTP calls |
| Environment | python-dotenv | latest | Secrets management |
| Data Science | pandas + numpy | latest | Data manipulation |
| WSGI Server | uvicorn | 0.29+ | Run FastAPI in prod |
| Process Manager | gunicorn | latest | Production process management |
| Testing | pytest | latest | Unit + integration tests |

### 7.2 Frontend

| Component | Tool | Version | Purpose |
|-----------|------|---------|---------|
| Framework | React | 18+ | UI layer |
| Build Tool | Vite | 5+ | Fast dev server + bundler |
| Language | TypeScript | 5+ | Type safety |
| Styling | TailwindCSS | 3+ | Utility-first CSS |
| UI Components | shadcn/ui | latest | Accessible, beautiful components |
| Charts | Recharts | 2+ | Line, area, pie, bar charts |
| Data Fetching | React Query (TanStack) | 5+ | Server state + caching |
| HTTP | Axios | 1+ | API calls with interceptors |
| Routing | React Router | 6+ | Client-side navigation |
| Global State | Zustand | 4+ | Lightweight state management |
| Date Handling | dayjs | latest | Lightweight date formatting |
| Icons | Lucide React | latest | Clean icon set |
| Form Handling | React Hook Form | 7+ | Goal input forms |
| Form Validation | Zod | 3+ | Schema validation |
| Notifications | react-hot-toast | latest | Success/error toasts |

### 7.3 Database & Infrastructure

| Component | Tool | Plan | Cost |
|-----------|------|------|------|
| Database | PostgreSQL 15+ | Railway | Free → ₹400/month |
| Backend Hosting | Railway | Starter | Free → ₹400/month |
| Frontend Hosting | Vercel | Free | ₹0 |
| LLM API | Groq | Free tier | ₹0 (very generous) |
| Market Data | yfinance | Free | ₹0 |
| Live Data | Angel One SmartAPI | Free | ₹0 (need account) |
| WhatsApp Alerts | Twilio Sandbox | Free | ₹0 (up to 5 users) |
| Domain (optional) | Namecheap | — | ~₹800/year |
| **Total Monthly** | | | **~₹0–800** |

---

## 8. Data Sources & External APIs

### 8.1 Historical Data — yfinance

```python
import yfinance as yf

# NSE stocks/ETFs use .NS suffix
# BSE stocks use .BO suffix

def fetch_historical_ohlcv(
    ticker: str,
    period: str = '10y',       # '1y', '2y', '5y', '10y', 'max'
    interval: str = '1d'       # '1d', '1wk', '1mo'
) -> pd.DataFrame:
    
    data = yf.download(ticker, period=period, interval=interval, auto_adjust=True)
    data.columns = ['Close', 'High', 'Low', 'Open', 'Volume']  # Standardize
    data.index = pd.to_datetime(data.index)
    data = data.dropna()
    
    return data

# Example usage
niftybees = fetch_historical_ohlcv('NIFTYBEES.NS', period='10y', interval='1d')
# Returns 10 years of daily OHLCV data — free, no API key needed
```

**Important limits:**
- No API key required
- Rate limits not documented — add delays in loops
- 15-minute delay on intraday data (fine for daily candles)
- Max 1min interval data: ~7 days historical

### 8.2 Live Data — Angel One SmartAPI

```python
from SmartApi.SmartConnect import SmartConnect
import pyotp

def get_angel_one_session():
    """Establishes authenticated session with Angel One."""
    obj = SmartConnect(api_key=os.getenv('ANGEL_ONE_API_KEY'))
    
    totp = pyotp.TOTP(os.getenv('ANGEL_ONE_TOTP_SECRET'))
    data = obj.generateSession(
        clientCode=os.getenv('ANGEL_ONE_CLIENT_ID'),
        password=os.getenv('ANGEL_ONE_PASSWORD'),
        totp=totp.now()
    )
    
    return obj, data['data']['jwtToken']

def fetch_live_ltp(obj: SmartConnect, symbol: str, token: str) -> float:
    """Get Last Traded Price."""
    ltp_data = obj.ltpData('NSE', symbol, token)
    return ltp_data['data']['ltp']

def fetch_live_candles(obj: SmartConnect, params: dict) -> pd.DataFrame:
    """Fetch OHLCV candles for recent period."""
    # params = {exchange, symboltoken, interval, fromdate, todate}
    candle_data = obj.getCandleData(params)
    df = pd.DataFrame(candle_data['data'],
                      columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# NIFTYBEES Angel One Token
NIFTYBEES_TOKEN = '2994'
NIFTYBEES_SYMBOL = 'NIFTYBEES-EQ'
```

**Angel One API Credentials needed:**
1. `ANGEL_ONE_API_KEY` — from https://smartapi.angelbroking.com/
2. `ANGEL_ONE_CLIENT_ID` — your Angel One login ID
3. `ANGEL_ONE_PASSWORD` — your Angel One password
4. `ANGEL_ONE_TOTP_SECRET` — from Angel One authenticator setup

### 8.3 Groq LLM API

```python
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatGroq(
    model="llama-3.3-70b-versatile",    # Best balance of speed + quality
    api_key=os.getenv('GROQ_API_KEY'),
    temperature=0.1,                     # Low = more deterministic financial advice
    max_tokens=500,                      # Keep responses concise
    timeout=30
)

def call_llm(system_prompt: str, user_message: str) -> str:
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ])
    return response.content
```

**Get Groq API key:** https://console.groq.com/ — free, very generous limits

### 8.4 Twilio WhatsApp API

```python
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'  # Twilio sandbox

def send_whatsapp_message(to_number: str, message: str) -> str:
    """
    to_number format: '+91XXXXXXXXXX' (with country code)
    Recipient must first join sandbox by messaging the Twilio sandbox number.
    """
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    msg = client.messages.create(
        from_=TWILIO_WHATSAPP_NUMBER,
        body=message,
        to=f'whatsapp:{to_number}'
    )
    return msg.sid

def broadcast_alert(message: str, user_numbers: list[str]):
    """Send same alert to all registered users."""
    for number in user_numbers:
        try:
            send_whatsapp_message(number, message)
        except Exception as e:
            logger.error(f"WhatsApp send failed for {number}: {e}")
```

**Twilio Sandbox setup:**
1. Create Twilio account at twilio.com
2. Go to Messaging → Try WhatsApp
3. Each user sends "join <keyword>" to sandbox number (+1 415 523 8886)
4. After joining → they receive your messages
5. Free for up to ~5-10 verified sandbox users

---

## 9. Database Schema

```sql
-- ================================================
-- NexTrade Database Schema
-- PostgreSQL 15+
-- ================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========== USERS ==========
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(255) UNIQUE,
    phone           VARCHAR(15) NOT NULL,   -- WhatsApp number with country code
    risk_score      INTEGER CHECK (risk_score BETWEEN 1 AND 10),
    risk_profile    VARCHAR(20),            -- 'conservative', 'moderate', 'aggressive'
    annual_income   DECIMAL(15,2),
    monthly_expenses DECIMAL(15,2),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ========== FINANCIAL GOALS ==========
CREATE TABLE goals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    goal_type           VARCHAR(50) NOT NULL,    -- 'retirement', 'home', 'education', etc.
    goal_name           VARCHAR(200) NOT NULL,
    target_amount       DECIMAL(15,2) NOT NULL,
    inflation_adjusted_target DECIMAL(15,2),
    current_savings     DECIMAL(15,2) DEFAULT 0,
    target_date         DATE NOT NULL,
    years_remaining     DECIMAL(4,1),
    required_monthly_sip DECIMAL(10,2),
    equity_allocation   INTEGER,
    debt_allocation     INTEGER,
    gold_allocation     INTEGER,
    recommended_products TEXT[],
    assumed_return_pct  DECIMAL(5,2) DEFAULT 12.0,
    inflation_rate_pct  DECIMAL(4,2) DEFAULT 6.0,
    llm_explanation     TEXT,
    status              VARCHAR(20) DEFAULT 'active',  -- 'active', 'completed', 'paused'
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ========== TRADING CONFIGURATION ==========
CREATE TABLE trading_config (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID REFERENCES users(id),
    instrument              VARCHAR(50) DEFAULT 'NIFTYBEES.NS',
    total_capital           DECIMAL(15,2) NOT NULL,
    max_risk_per_trade_pct  DECIMAL(4,3) DEFAULT 0.01,
    max_daily_loss_pct      DECIMAL(4,3) DEFAULT 0.03,
    max_open_positions      INTEGER DEFAULT 3,
    trading_phase           VARCHAR(20) DEFAULT 'paper',  -- 'backtest', 'paper', 'real'
    is_bot_active           BOOLEAN DEFAULT FALSE,
    strategy_name           VARCHAR(100) DEFAULT 'EMA_RSI_MACD_Swing_v1',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ========== MARKET DATA (OHLCV CACHE) ==========
CREATE TABLE market_data (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      VARCHAR(50) NOT NULL,
    date        DATE NOT NULL,
    open_price  DECIMAL(10,2),
    high_price  DECIMAL(10,2),
    low_price   DECIMAL(10,2),
    close_price DECIMAL(10,2),
    volume      BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, date)
);

-- ========== SIGNALS LOG ==========
CREATE TABLE signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id           UUID REFERENCES trading_config(id),
    instrument          VARCHAR(50),
    signal_type         VARCHAR(10),    -- 'BUY', 'SELL', 'HOLD'
    confidence_score    DECIMAL(4,3),
    price_at_signal     DECIMAL(10,2),
    regime              VARCHAR(30),
    indicators_snapshot JSONB,          -- {ema20, ema50, rsi, macd, atr, vol_ratio}
    conditions_met      JSONB,          -- {ema_crossover: true, rsi_ok: false, ...}
    acted_upon          BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ========== TRADES ==========
CREATE TABLE trades (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id           UUID REFERENCES trading_config(id),
    signal_id           UUID REFERENCES signals(id),
    instrument          VARCHAR(50) NOT NULL,
    trade_type          VARCHAR(10),            -- 'BUY', 'SELL' (of opening leg)
    entry_price         DECIMAL(10,2),
    exit_price          DECIMAL(10,2),
    quantity            INTEGER,
    stop_loss           DECIMAL(10,2),
    target_price        DECIMAL(10,2),
    capital_at_risk     DECIMAL(10,2),
    actual_pnl          DECIMAL(10,2),
    pnl_percent         DECIMAL(6,2),
    market_regime       VARCHAR(30),
    confidence_score    DECIMAL(4,3),
    signals_triggered   TEXT[],
    exit_reason         VARCHAR(50),    -- 'STOP_LOSS', 'TARGET', 'REVERSAL', 'TIMEOUT', 'MANUAL'
    holding_days        INTEGER,
    trade_phase         VARCHAR(20),    -- 'PAPER', 'REAL'
    llm_summary         TEXT,
    entry_time          TIMESTAMPTZ,
    exit_time           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ========== BACKTEST RESULTS ==========
CREATE TABLE backtest_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name   VARCHAR(100),
    instrument      VARCHAR(50),
    start_date      DATE,
    end_date        DATE,
    initial_capital DECIMAL(15,2),
    final_capital   DECIMAL(15,2),
    total_return_pct DECIMAL(6,2),
    cagr_pct        DECIMAL(6,2),
    sharpe_ratio    DECIMAL(5,3),
    sortino_ratio   DECIMAL(5,3),
    max_drawdown_pct DECIMAL(6,2),
    win_rate_pct    DECIMAL(5,2),
    profit_factor   DECIMAL(5,3),
    total_trades    INTEGER,
    avg_hold_days   DECIMAL(5,1),
    fees_paid       DECIMAL(10,2),
    slippage_used   DECIMAL(5,3),
    params_used     JSONB,             -- Strategy parameters
    passed_criteria BOOLEAN,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ========== PORTFOLIO SNAPSHOTS ==========
CREATE TABLE portfolio_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id           UUID REFERENCES trading_config(id),
    snapshot_date       DATE NOT NULL,
    total_capital       DECIMAL(15,2),
    positions_value     DECIMAL(15,2),
    cash_available      DECIMAL(15,2),
    daily_pnl           DECIMAL(10,2),
    total_pnl           DECIMAL(10,2),
    total_pnl_pct       DECIMAL(6,2),
    open_positions      JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(config_id, snapshot_date)
);

-- ========== INDEXES ==========
CREATE INDEX idx_trades_config_id ON trades(config_id);
CREATE INDEX idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX idx_trades_phase ON trades(trade_phase);
CREATE INDEX idx_signals_created ON signals(created_at DESC);
CREATE INDEX idx_market_data_ticker_date ON market_data(ticker, date DESC);
CREATE INDEX idx_goals_user_id ON goals(user_id);
CREATE INDEX idx_portfolio_config_date ON portfolio_snapshots(config_id, snapshot_date DESC);
```

---

## 10. Frontend Architecture

### 10.1 Page Map

```
/                           → Landing / Auth page
/dashboard                  → Main overview
  
/advisor                    → Financial Advisor module
  /advisor/goals            → All goals list
  /advisor/goals/new        → Goal creation wizard (multi-step)
  /advisor/goals/:id        → Goal detail + SIP plan + LLM explanation
  /advisor/tax              → Tax saving calculator
  /advisor/rebalancing      → Portfolio rebalancing checker

/trading                    → Trading Agent module
  /trading/overview         → Live signal + positions dashboard  
  /trading/backtest         → Run backtest + view results
  /trading/paper            → Paper trading dashboard
  /trading/journal          → Trade journal table + analytics
  /trading/settings         → Risk config + bot on/off

/alerts                     → WhatsApp alert settings
/settings                   → User profile + risk questionnaire
```

### 10.2 Key UI Components

#### Dashboard (`/dashboard`)
```
┌─────────────────────────────────────────────┐
│  NexTrade                    [🔔] [Settings] │
├──────────────────┬──────────────────────────┤
│  💰 Capital      │  📊 Today's Signal        │
│  ₹1,00,000       │  NIFTYBEES | BUY 🟢       │
│  PnL: +₹2,340    │  Confidence: 80%          │
│  (+2.34%)        │  Regime: TRENDING_BULL    │
├──────────────────┴──────────────────────────┤
│  📈 Goals Progress                           │
│  Emergency Fund  ████████░░  80% | 4 months │
│  Home Down Pymnt ████░░░░░░  40% | 3 years  │
├─────────────────────────────────────────────┤
│  📋 Recent Trades (last 5)                  │
│  NIFTYBEES | +₹1,200 | Target ✅ | 5 days  │
│  NIFTYBEES | -₹450   | StopLoss ❌| 3 days  │
└─────────────────────────────────────────────┘
```

#### Goal Creation Wizard (`/advisor/goals/new`)
```
Step 1: What's your goal?
  → [Select goal type tiles]

Step 2: Goal details
  → Goal name, Target amount, Target date, Current savings

Step 3: Risk profile
  → 4 risk questions with sliders/options

Step 4: Results
  → Monthly SIP required
  → Asset allocation pie chart
  → Recommended products
  → LLM explanation panel
  → [Save Goal] button
```

#### Trading Dashboard (`/trading/overview`)
```
┌──────────────────────────────────────────────┐
│  Market: NSE   Time: 10:32 AM   [Bot: 🟢 ON] │
├──────────────────────────────────────────────┤
│  NIFTYBEES: ₹248.40 (+0.8%)                  │
│  [Candlestick chart with EMA 20/50 overlaid] │
│                                               │
│  Regime: [🟢 TRENDING_BULL]                  │
│  Signal: [🟢 BUY | 80% confidence]           │
│                                               │
│  Indicators:                                  │
│  RSI: 54 ✅ | MACD: 0.82 ✅ | Vol: 1.4x ✅   │
├──────────────────────────────────────────────┤
│  Open Positions (1/3)                         │
│  NIFTYBEES | 40 units @ ₹245                 │
│  SL: ₹239 | Target: ₹257 | PnL: +₹136       │
├──────────────────────────────────────────────┤
│  Risk Gauge                                   │
│  Daily Loss: ₹0 / ₹3000 limit [░░░░░░░] 0%  │
└──────────────────────────────────────────────┘
```

#### Backtest Results (`/trading/backtest`)
```
┌──────────────────────────────────────────────┐
│  Strategy: EMA_RSI_MACD_Swing_v1             │
│  Period: Jan 2015 – Dec 2024 (10 years)      │
│  Instrument: NIFTYBEES.NS                    │
├──────────────┬───────────────────────────────┤
│  📈 Equity Curve (area chart)                │
│              │                               │
├──────────────┴───────────────────────────────┤
│  Total Return: +187%    CAGR: 11.2%          │
│  Sharpe:  1.24 ✅       Sortino: 1.67 ✅     │
│  Max DD:  -12.3% ✅     Win Rate: 52% ✅     │
│  Trades:  127 ✅        Profit Factor: 1.45✅ │
│                                               │
│  [✅ PASSED — Ready for Paper Trading]        │
└──────────────────────────────────────────────┘
```

### 10.3 Color System

```typescript
// tailwind.config.ts additions
const colors = {
  'nextrade-green': '#00C896',    // Profit / positive
  'nextrade-red': '#FF4757',      // Loss / negative
  'nextrade-blue': '#2196F3',     // Primary actions
  'nextrade-yellow': '#FFC107',   // Warnings / SIDEWAYS regime
  'surface': '#1A1A2E',           // Dark background
  'surface-2': '#16213E',         // Card background
  'surface-3': '#0F3460',         // Elevated elements
  'text-primary': '#EAEAEA',
  'text-secondary': '#8B8B9E',
}
```

---

## 11. Backend API Specification

### 11.1 Financial Advisor Endpoints

```
POST   /api/v1/goals                       Create new financial goal
GET    /api/v1/goals                       List all goals for user
GET    /api/v1/goals/{goal_id}             Goal detail + full SIP plan
PUT    /api/v1/goals/{goal_id}             Update goal parameters
DELETE /api/v1/goals/{goal_id}             Delete goal

POST   /api/v1/advisor/calculate-sip       Quick SIP calculation (no save)
POST   /api/v1/advisor/asset-allocation    Get allocation recommendation
POST   /api/v1/advisor/tax-saving         Get tax optimization plan
GET    /api/v1/advisor/rebalancing        Check portfolio rebalancing needed
POST   /api/v1/advisor/risk-score         Submit risk questionnaire → score
```

### 11.2 Trading Agent Endpoints

```
GET    /api/v1/trading/signal              Latest signal + confidence
GET    /api/v1/trading/regime              Current market regime
GET    /api/v1/trading/status             Bot status + active positions

POST   /api/v1/backtest/run               Start backtest job (async)
GET    /api/v1/backtest/results           All backtest runs
GET    /api/v1/backtest/results/{id}      Specific backtest detail

GET    /api/v1/paper/status              Paper trading status
POST   /api/v1/paper/start               Activate paper trading bot
POST   /api/v1/paper/stop                Pause paper trading bot
POST   /api/v1/paper/reset               Reset portfolio to initial capital
GET    /api/v1/paper/positions           Current open paper positions

GET    /api/v1/trades                    All trades (filter: phase, date, pnl)
GET    /api/v1/trades/{trade_id}         Trade detail + LLM summary
GET    /api/v1/trades/analytics/summary  Win rate, sharpe, drawdown summary
GET    /api/v1/trades/analytics/pnl-curve  Daily PnL over time

GET    /api/v1/portfolio/snapshot        Latest portfolio snapshot
GET    /api/v1/portfolio/history         Historical capital curve

POST   /api/v1/alerts/test               Send test WhatsApp alert
GET    /api/v1/alerts/settings           Get alert config
PUT    /api/v1/alerts/settings           Update alert preferences (which alerts to send)

GET    /api/v1/data/ohlcv/{ticker}       Get cached OHLCV data
POST   /api/v1/data/refresh              Force refresh market data
```

### 11.3 Scheduled Jobs (APScheduler)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone='Asia/Kolkata')

# Market morning scan — 9:30 AM IST weekdays
@scheduler.scheduled_job(CronTrigger(day_of_week='mon-fri', hour=9, minute=30))
async def morning_market_scan():
    await paper_trader.run_morning_scan()
    await send_morning_briefing()

# Midday check — 12:30 PM IST weekdays
@scheduler.scheduled_job(CronTrigger(day_of_week='mon-fri', hour=12, minute=30))
async def midday_position_check():
    await paper_trader.check_open_positions()

# EOD summary — 3:15 PM IST weekdays
@scheduler.scheduled_job(CronTrigger(day_of_week='mon-fri', hour=15, minute=15))
async def end_of_day_summary():
    await paper_trader.run_eod_summary()
    await data_pipeline.update_daily_candle()

# Weekly rebalancing check — 10 AM Sunday
@scheduler.scheduled_job(CronTrigger(day_of_week='sun', hour=10))
async def weekly_rebalancing_check():
    users = await get_all_active_users()
    for user in users:
        await check_and_alert_rebalancing(user)

# Daily data refresh — 4 PM weekdays (after market close)
@scheduler.scheduled_job(CronTrigger(day_of_week='mon-fri', hour=16, minute=0))
async def refresh_market_data():
    await data_pipeline.download_latest_candles()
```

---

## 12. WhatsApp Alerts Integration

### 12.1 Setup Process

1. Sign up at https://www.twilio.com/
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Get sandbox number and join keyword
4. Have all 4-5 users text `join <keyword>` to the Twilio sandbox number
5. Users can now receive messages from your bot
6. Add their numbers to DB

### 12.2 Alert Templates

```python
class WhatsAppTemplates:
    
    @staticmethod
    def trade_signal(trade: dict) -> str:
        emoji = "🟢" if trade['signal'] == 'BUY' else "🔴"
        return f"""
{emoji} *NexTrade Signal* | {trade['instrument']}

📊 Action: *{trade['signal']}*
💰 Entry Price: ₹{trade['entry_price']}
🛡️ Stop Loss: ₹{trade['stop_loss']}
🎯 Target: ₹{trade['target']}
📈 Confidence: {int(trade['confidence'] * 100)}%
🌡️ Market: {trade['regime']}

_Paper Trade Mode_
""".strip()

    @staticmethod
    def trade_exit(trade: dict) -> str:
        profitable = trade['actual_pnl'] > 0
        emoji = "✅" if profitable else "❌"
        return f"""
{emoji} *Trade Closed* | {trade['instrument']}

Entry: ₹{trade['entry_price']} → Exit: ₹{trade['exit_price']}
PnL: ₹{trade['actual_pnl']} ({trade['pnl_percent']:+.1f}%)
Reason: {trade['exit_reason'].replace('_', ' ').title()}
Held: {trade['holding_days']} days

💡 {trade['llm_summary'][:100]}...
""".strip()

    @staticmethod
    def daily_summary(summary: dict) -> str:
        pnl_emoji = "📈" if summary['daily_pnl'] >= 0 else "📉"
        return f"""
📊 *NexTrade Daily Recap*

💵 Capital: ₹{summary['capital']:,.0f}
{pnl_emoji} Today's PnL: ₹{summary['daily_pnl']:+,.0f}
💼 Total PnL: ₹{summary['total_pnl']:+,.0f}
📂 Open Positions: {summary['open_positions']}/3
🔄 Total Paper Trades: {summary['total_trades']}

_Next scan: Tomorrow 9:30 AM_
""".strip()

    @staticmethod
    def risk_alert(loss: float, loss_pct: float) -> str:
        return f"""
⚠️ *RISK ALERT — Bot Paused*

Daily loss limit reached!
Loss Today: ₹{abs(loss):,.0f} ({loss_pct:.1f}%)
Limit: 3% of capital

🔒 Bot PAUSED for today.
Resumes tomorrow at 9:30 AM.

_No action needed from you._
""".strip()

    @staticmethod
    def rebalancing_alert(actions: list) -> str:
        actions_text = '\n'.join([
            f"• {a['asset'].upper()}: {a['action']} {a['drift']:.1f}% (target: {a['target_pct']}%)"
            for a in actions
        ])
        return f"""
⚖️ *Portfolio Rebalancing Alert*

Your allocation has drifted from target:

{actions_text}

💡 Consider rebalancing your investments this week.

_NexTrade Financial Advisor_
""".strip()
```

---

## 13. Phase-Wise Roadmap

### Phase 1 — Financial Advisor (Week 1–2)
**Goal:** Working FA module — SIP calculator, goal tracking, LLM explanations, WhatsApp alerts

| Task | Priority | Estimated Time |
|------|----------|----------------|
| Project setup (FastAPI + React + PostgreSQL + Railway/Vercel) | P0 | 4 hrs |
| Database schema + Alembic migrations | P0 | 2 hrs |
| User creation + auth (simple JWT) | P0 | 3 hrs |
| SIP calculation engine (all formulas) | P0 | 3 hrs |
| Asset allocation engine + risk scorer | P0 | 3 hrs |
| Tax saving calculator | P1 | 2 hrs |
| Groq LLM integration (FA explanations) | P0 | 2 hrs |
| Goal CRUD API endpoints | P0 | 3 hrs |
| React — Goal creation wizard (4 steps) | P0 | 5 hrs |
| React — Goal dashboard + progress bars | P0 | 3 hrs |
| React — SIP result + allocation pie chart | P0 | 3 hrs |
| Twilio WhatsApp setup + test send | P1 | 2 hrs |
| Rebalancing check + Sunday cron alert | P1 | 2 hrs |
| Deploy: Railway backend + Vercel frontend | P0 | 2 hrs |

**✅ Phase 1 complete when:** User creates goal → sees SIP amount → gets LLM explanation → receives WhatsApp test

---

### Phase 2 — Data Pipeline (Week 2–3)
**Goal:** Reliable OHLCV data pipeline, indicators calculated, stored in DB

| Task | Priority | Estimated Time |
|------|----------|----------------|
| yfinance integration + OHLCV download script | P0 | 2 hrs |
| Bulk historical download (10 years NIFTYBEES) | P0 | 1 hr |
| Store OHLCV in PostgreSQL market_data table | P0 | 2 hrs |
| pandas-ta indicator calculation | P0 | 3 hrs |
| Angel One SmartAPI account setup + auth | P0 | 2 hrs |
| Live LTP fetch + recent candles from Angel One | P0 | 3 hrs |
| Daily data update cron job (4 PM weekdays) | P0 | 2 hrs |
| Data validation (missing dates, outliers) | P1 | 2 hrs |
| API endpoint: GET /api/v1/data/ohlcv/{ticker} | P1 | 1 hr |

**✅ Phase 2 complete when:** Fresh OHLCV + indicators in DB every market day, live LTP fetching works

---

### Phase 3 — Strategy + Backtest Engine (Week 3–5)
**Goal:** Backtest strategy on 10 years data, honest metrics, pass criteria

| Task | Priority | Estimated Time |
|------|----------|----------------|
| Signal engine (5 conditions + confidence) | P0 | 4 hrs |
| Market regime detector | P0 | 2 hrs |
| Risk manager (position sizing, SL, target) | P0 | 3 hrs |
| vectorbt backtest wrapper | P0 | 4 hrs |
| Metrics extraction (Sharpe, DD, win rate) | P0 | 2 hrs |
| Pass/fail criteria checker | P0 | 1 hr |
| Backtest results storage in DB | P0 | 2 hrs |
| API: POST /api/v1/backtest/run | P0 | 2 hrs |
| React — Backtest runner UI | P1 | 3 hrs |
| React — Equity curve + metrics display | P1 | 3 hrs |
| Strategy parameter tuning (manual grid search) | P1 | 3 hrs |

**✅ Phase 3 complete when:** 10-year backtest runs, Sharpe > 1.0, drawdown < 15%, pass criteria met

---

### Phase 4 — Paper Trading (Week 5–8+)
**Goal:** Live signals on fake money for 2–3 months minimum

| Task | Priority | Estimated Time |
|------|----------|----------------|
| PaperTradingEngine class | P0 | 5 hrs |
| Morning scan cron job (9:30 AM) | P0 | 2 hrs |
| EOD summary cron job (3:15 PM) | P0 | 2 hrs |
| Trade open/close logic | P0 | 3 hrs |
| LLM trade summary generation | P0 | 2 hrs |
| WhatsApp signal + exit alerts | P0 | 2 hrs |
| WhatsApp daily summary | P0 | 1 hr |
| Paper portfolio tracking (DB snapshots) | P0 | 2 hrs |
| API: GET /api/v1/paper/status + positions | P0 | 2 hrs |
| React — Paper trading dashboard | P1 | 4 hrs |
| React — Trade journal table + charts | P1 | 4 hrs |
| Monitoring: bot uptime, error alerts | P1 | 2 hrs |
| **2–3 months running paper trades** | P0 | — |

**✅ Phase 4 complete when:** 2 months of consistent paper trading, Sharpe > 0.8, no critical bugs

---

### Phase 5 — Real Money (After Phase 4 proven)
**Goal:** ₹10–15k real capital, semi-automated execution

| Task | Priority | Estimated Time |
|------|----------|----------------|
| Angel One order placement API | P0 | 4 hrs |
| Semi-auto flow: Signal → WhatsApp → Approve → Execute | P0 | 4 hrs |
| Real vs paper trade separation in DB | P0 | 2 hrs |
| Capital management dashboard | P0 | 3 hrs |
| Real trade monitoring + alerts | P0 | 2 hrs |
| SEBI compliance review | P0 | 1 hr |
| Emergency stop mechanism | P0 | 2 hrs |

**✅ Phase 5 complete when:** First real trade executed, risk controls verified in live environment

---

## 14. Folder Structure

```
nextrade/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                         # FastAPI app, CORS, router includes
│   │   ├── config.py                       # Settings from .env (pydantic BaseSettings)
│   │   ├── database.py                     # SQLAlchemy engine, session factory
│   │   │
│   │   ├── models/                         # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── goal.py
│   │   │   ├── trading_config.py
│   │   │   ├── market_data.py
│   │   │   ├── signal.py
│   │   │   ├── trade.py
│   │   │   ├── backtest.py
│   │   │   └── portfolio_snapshot.py
│   │   │
│   │   ├── schemas/                        # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── goal.py
│   │   │   ├── trading.py
│   │   │   ├── backtest.py
│   │   │   └── alerts.py
│   │   │
│   │   ├── routers/                        # FastAPI route handlers
│   │   │   ├── __init__.py
│   │   │   ├── advisor.py                  # /api/v1/advisor/* + /api/v1/goals/*
│   │   │   ├── trading.py                  # /api/v1/trading/*
│   │   │   ├── backtest.py                 # /api/v1/backtest/*
│   │   │   ├── paper.py                    # /api/v1/paper/*
│   │   │   ├── journal.py                  # /api/v1/trades/*
│   │   │   ├── portfolio.py                # /api/v1/portfolio/*
│   │   │   ├── data.py                     # /api/v1/data/*
│   │   │   └── alerts.py                   # /api/v1/alerts/*
│   │   │
│   │   ├── services/
│   │   │   ├── advisor/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sip_calculator.py       # All SIP math formulas
│   │   │   │   ├── asset_allocator.py      # Risk score → allocation matrix
│   │   │   │   ├── tax_advisor.py          # 80C/80D/NPS calculations
│   │   │   │   └── rebalancer.py           # Drift detection logic
│   │   │   │
│   │   │   ├── trading/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── data_pipeline.py        # yfinance + Angel One data fetch
│   │   │   │   ├── indicators.py           # pandas-ta wrapper functions
│   │   │   │   ├── regime_detector.py      # ADX-based market regime
│   │   │   │   ├── signal_engine.py        # 5-condition signal generation
│   │   │   │   ├── risk_manager.py         # Position sizing, SL, daily limit
│   │   │   │   ├── backtest_engine.py      # vectorbt wrapper + metrics
│   │   │   │   └── paper_trader.py         # PaperTradingEngine class
│   │   │   │
│   │   │   ├── llm/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── client.py               # Groq LLM client setup
│   │   │   │   ├── advisor_prompts.py      # FA explanation prompts
│   │   │   │   └── trade_summarizer.py     # Trade journal LLM summaries
│   │   │   │
│   │   │   └── alerts/
│   │   │       ├── __init__.py
│   │   │       ├── whatsapp.py             # Twilio client + send functions
│   │   │       └── templates.py            # All WhatsApp message templates
│   │   │
│   │   └── jobs/
│   │       ├── __init__.py
│   │       └── scheduler.py                # APScheduler setup + all cron jobs
│   │
│   ├── migrations/                         # Alembic migration files
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_sip_calculator.py
│   │   ├── test_signal_engine.py
│   │   ├── test_risk_manager.py
│   │   └── test_backtest_engine.py
│   │
│   ├── scripts/
│   │   ├── download_historical_data.py     # One-time bulk OHLCV download
│   │   ├── run_backtest_cli.py             # CLI backtest runner
│   │   └── seed_test_data.py               # Seed DB with test data
│   │
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── Dockerfile
│   └── railway.toml
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   │
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── advisor/
│   │   │   │   ├── Goals.tsx               # Goal list
│   │   │   │   ├── GoalNew.tsx             # 4-step wizard
│   │   │   │   ├── GoalDetail.tsx          # SIP plan + LLM
│   │   │   │   ├── TaxAdvisor.tsx
│   │   │   │   └── Rebalancing.tsx
│   │   │   └── trading/
│   │   │       ├── TradingOverview.tsx     # Live signal + positions
│   │   │       ├── Backtest.tsx
│   │   │       ├── PaperTrading.tsx
│   │   │       ├── TradeJournal.tsx
│   │   │       └── TradingSettings.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                         # shadcn/ui components
│   │   │   ├── layout/
│   │   │   │   ├── Navbar.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── charts/
│   │   │   │   ├── EquityCurve.tsx
│   │   │   │   ├── AllocationPie.tsx
│   │   │   │   ├── PnLChart.tsx
│   │   │   │   └── CandlestickChart.tsx
│   │   │   ├── trading/
│   │   │   │   ├── SignalCard.tsx
│   │   │   │   ├── RegimeBadge.tsx
│   │   │   │   ├── RiskGauge.tsx
│   │   │   │   ├── PositionsTable.tsx
│   │   │   │   └── BacktestMetrics.tsx
│   │   │   └── advisor/
│   │   │       ├── GoalCard.tsx
│   │   │       ├── SIPResult.tsx
│   │   │       ├── AllocationDisplay.tsx
│   │   │       └── LLMExplainer.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useGoals.ts
│   │   │   ├── useSignal.ts
│   │   │   ├── useTrades.ts
│   │   │   ├── usePortfolio.ts
│   │   │   └── useBacktest.ts
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                      # Axios instance + interceptors
│   │   │   ├── queryClient.ts              # React Query client
│   │   │   └── utils.ts                    # formatCurrency, formatDate, etc.
│   │   │
│   │   ├── store/
│   │   │   └── useStore.ts                 # Zustand global state
│   │   │
│   │   └── types/
│   │       ├── goal.types.ts
│   │       ├── trade.types.ts
│   │       └── signal.types.ts
│   │
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── .env.example
│
├── docs/
│   ├── PRD.md                              # This file
│   ├── API_REFERENCE.md                    # Full API docs
│   └── TRADING_STRATEGY.md                 # Strategy deep dive
│
└── README.md
```

---

## 15. Open Source Tools & MCPs

### 15.1 Python Libraries (requirements.txt)

```txt
# === WEB FRAMEWORK ===
fastapi==0.110.0
uvicorn[standard]==0.29.0
gunicorn==21.2.0

# === DATABASE ===
sqlalchemy==2.0.29
alembic==1.13.1
psycopg2-binary==2.9.9

# === DATA VALIDATION ===
pydantic==2.7.0
pydantic-settings==2.2.1
python-dotenv==1.0.1

# === AI / LLM ===
langchain-groq==0.1.6
langgraph==0.2.0
langchain-core==0.2.0

# === MARKET DATA ===
yfinance==0.2.38
smartapi-python==1.3.4
pyotp==2.9.0

# === TRADING / ANALYSIS ===
vectorbt==0.26.1
pandas-ta==0.3.14b
pandas==2.2.1
numpy==1.26.4
scipy==1.13.0

# === SCHEDULING ===
apscheduler==3.10.4

# === ALERTS ===
twilio==9.0.4

# === HTTP ===
httpx==0.27.0
requests==2.31.0

# === UTILITIES ===
python-jose[cryptography]==3.3.0   # JWT auth
passlib[bcrypt]==1.7.4             # Password hashing
python-multipart==0.0.9            # File uploads
loguru==0.7.2                      # Better logging
```

### 15.2 Relevant MCPs for Claude Code Sessions

| MCP | Connected | Use in NexTrade |
|-----|-----------|-----------------|
| GrowwMCP | ✅ Yes | Reference portfolio data, not direct integration |
| Postman MCP | ✅ Yes | API endpoint testing during build |
| GitHub MCP | Check | Code repo management, commits |
| Google Drive MCP | ✅ Yes | Store backtest result CSVs |

### 15.3 Open Source References

| Resource | URL | Why useful |
|----------|-----|-----------|
| vectorbt docs | https://vectorbt.dev/ | Backtest framework reference |
| pandas-ta GitHub | https://github.com/twopirllc/pandas-ta | All indicator signatures |
| Angel One SmartAPI | https://smartapi.angelbroking.com/docs | Broker API reference |
| Twilio WhatsApp | https://www.twilio.com/docs/whatsapp | WhatsApp integration docs |
| FastAPI docs | https://fastapi.tiangolo.com/ | API framework reference |
| shadcn/ui | https://ui.shadcn.com/ | UI component library |
| Railway deploy | https://docs.railway.app/ | Backend deployment guide |
| LangGraph docs | https://langchain-ai.github.io/langgraph/ | Agent framework |

---

## 16. SEBI Compliance Notes

> ⚠️ Read before Phase 5 (real money trading). Not legal advice.

### What Is Allowed

| Activity | Legal Status |
|----------|-------------|
| Paper trading / backtesting | ✅ 100% legal, no restrictions |
| Manual trading using bot-generated signals | ✅ Legal — you are placing orders |
| Using broker API (Angel One SmartAPI) | ✅ Legal — broker provides it for retail |
| Semi-auto (bot suggests, human approves) | ✅ Legal — human still in control |
| Full automation via broker API | ⚠️ Grey area for retail |

### Recommended Approach for Phase 5

**Use semi-automated flow:**
1. Bot generates signal → sends WhatsApp
2. You approve via WhatsApp reply (or button in dashboard)
3. Bot places the order via Angel One API
4. You get confirmation WhatsApp

This keeps a human in the loop (legally safe) while automating the heavy lifting.

### Practical Rules

- Trade only in **Cash Segment** (NSE) — no margin, no F&O in Phase 1
- Never trade with borrowed money initially
- Keep records of all trades (the journal does this automatically)
- Max loss per trade: 1% (hardcoded in risk manager)
- No intraday trading in Phase 1 (avoids additional margin regulations)

---

## 17. Success Metrics & KPIs

### Financial Advisor

| Metric | Target |
|--------|--------|
| Goal creation (time) | Under 3 minutes end-to-end |
| SIP calculation accuracy | 100% (deterministic math) |
| LLM response time | Under 3 seconds |
| Rebalancing alert delivery | Within 30 seconds of trigger |

### Trading Agent — Backtest Phase 3 (Must Pass All)

| Metric | Threshold | Status if Not Met |
|--------|-----------|------------------|
| Sharpe Ratio | > 1.0 | Refine strategy |
| Max Drawdown | < 15% | Tighten stop loss |
| Win Rate | > 45% | Improve entry filters |
| Profit Factor | > 1.3 | Improve R:R ratio |
| CAGR | > 12% | Check benchmark vs Nifty |
| Total Trades (backtest) | > 50 | More years of data |

### Paper Trading — Phase 4 (Must Pass All)

| Metric | Target |
|--------|--------|
| Duration (minimum) | 2 months |
| Paper Sharpe | > 0.8 |
| Max paper drawdown | < 10% |
| Bot uptime | > 95% |
| Critical bugs | 0 |
| Win rate (paper) | > 45% |

### System Performance

| Metric | Target |
|--------|--------|
| API response time (p95) | < 500ms |
| Signal generation time | < 5 seconds |
| WhatsApp alert delivery | < 30 seconds |
| Daily cron job success rate | > 99% |
| DB query time (p95) | < 100ms |

---

## 18. Build Decisions & OSS Strategy (added 2026-06-29)

> This section overrides the original stack where they differ. Came from a full research + brainstorming pass. Full detail: `START_HERE.md` + `docs/research/2026-06-28-oss-landscape.md` + `docs/superpowers/`.

### 18.1 Locked deltas vs PRD v1
| Area | PRD v1 | Final decision |
|------|--------|----------------|
| Build style | implied custom | **Hybrid** — build brain (signals/risk/FA math), reuse OSS for body (data/backtest/charts/execution/alerts) |
| Backtest | vectorbt + per-bar loop (O(n²) bug) | **backtesting.py + quantstats**; vectorbt only for param sweeps; walk-forward added |
| Market data | yfinance | **jugaad-data** primary (accurate NSE), yfinance fallback |
| Execution | Angel One SmartAPI hand-coded | **OpenAlgo** (broker-agnostic, 20+ Indian brokers), Phase 5 only |
| Alerts | Twilio WhatsApp | **kept** (Telegram considered, rejected) |
| AI layer | LangGraph from day 1 | **v1 rules-only + LLM explain; v2 multi-agent analyst** (TradingAgents/AutoHedge patterns) that advises risk mgr, never overrides |
| Frontend chart | Recharts | **TradingView Lightweight Charts** for candlesticks (Recharts for pies/lines) |
| Dev DB | Postgres/Railway | **SQLite dev → Postgres (Neon/Supabase) deploy**, portable models |
| Allocation (FA) | fixed matrix | matrix v1; **Riskfolio-Lib/PyPortfolioOpt** optional v2 |
| v1 scope | broad | **NIFTYBEES only, paper-money first, Financial Advisor built first** |

### 18.2 Open-source strategy — what we take from where
- **Skeleton reference:** HKUDS/Vibe-Trading (FastAPI+React twin; loader registry, MCP server, backtest validation, signal-engine gen). Also a local `vibe-trading` skill.
- **Data:** jugaad-data (+ nsepython extras). **Backtest:** backtesting.py + quantstats. **Indicators:** pandas-ta. **Execution:** OpenAlgo. **Allocation:** Riskfolio-Lib/PyPortfolioOpt.
- **Strategy blueprint:** Edge-Swing (India ETF swing). **Architecture to study:** Freqtrade (risk/dry-run/hyperopt).
- **v2 AI brain:** TradingAgents (analyst→debate→trader→risk→PM + decision-log memory), AutoHedge (simple 4-agent shape), ai-hedge-fund (personas), FinGPT (sentiment), AI-Stock-Advisor/ai-powered-robo-advisor (RAG explainer + robo structure).
- **Part A dashboard UX:** Ghostfolio, Maybe.
- **⚠️ Avoid code (license/scope):** FinceptTerminal (AGPL+commercial, $50k damages, C++ — ideas only). Parked off-core: MoneyPrinterTurbo (video), VoxCPM (TTS), camoufox (scraping), + crypto/HFT/budgeting/ERP repos.
- **Rule:** risk manager always ours, hardcoded, never overridable. Full BUILD/REUSE/MODIFY table = research doc §13.

### 18.3 Build order
Phase 1 Financial Advisor → 2 Data pipeline → 3 Strategy+Backtest → 4 Paper trading (2-3 mo) → 5 Real money (OpenAlgo, only after paper proves) → v2 AI analyst layer. Phase 1 plan: `docs/superpowers/plans/2026-06-29-phase1-financial-advisor.md`.

---

## Environment Variables Reference

```bash
# .env.example — Copy to .env and fill values

# DATABASE
DATABASE_URL=postgresql://user:password@host:5432/nextrade

# SECURITY
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# GROQ LLM
GROQ_API_KEY=gsk_...

# ANGEL ONE BROKER
ANGEL_ONE_API_KEY=...
ANGEL_ONE_CLIENT_ID=...
ANGEL_ONE_PASSWORD=...
ANGEL_ONE_TOTP_SECRET=...   # From authenticator app QR code

# TWILIO WHATSAPP
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# APP SETTINGS
APP_ENV=development           # development | production
LOG_LEVEL=INFO
ALLOWED_ORIGINS=http://localhost:5173,https://nextrade.vercel.app

# TRADING CONFIG
DEFAULT_INSTRUMENT=NIFTYBEES.NS
DEFAULT_CAPITAL=100000        # Paper trading starting capital
PAPER_TRADING_ACTIVE=false    # Set true to activate paper bot
```

---

## Quick Start for Claude Code

```bash
# 1. Clone / create repo
mkdir nextrade && cd nextrade

# 2. Backend setup
cd backend
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # Fill in credentials

# 3. Database setup
alembic upgrade head

# 4. Download historical data (one-time)
python scripts/download_historical_data.py

# 5. Run backend
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs

# 6. Frontend setup (new terminal)
cd ../frontend
npm install
cp .env.example .env         # Set VITE_API_URL=http://localhost:8000
npm run dev
# Frontend: http://localhost:5173

# 7. Run first backtest
python scripts/run_backtest_cli.py --ticker NIFTYBEES.NS --years 10
```

---

*NexTrade PRD v1.0 — Built with Claude Code*  
*Last updated: June 2026*  
*Status: Ready to build 🚀*
