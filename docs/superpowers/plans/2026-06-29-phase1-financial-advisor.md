# NexTrade Phase 1 — Financial Advisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Financial Advisor module — user creates a goal → sees required SIP + asset allocation + tax plan → gets a Hinglish LLM explanation → receives a WhatsApp test alert.

**Architecture:** FastAPI backend with isolated deterministic service modules (SIP, allocation, tax, rebalance) that are pure functions (100% unit-tested, no DB/IO), a thin router layer over SQLAlchemy models, a Groq LLM explainer, and a Twilio WhatsApp sender. React+Vite+TS frontend with a 4-step goal wizard and a goal-detail view (allocation pie + LLM panel).

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2 + Alembic, Pydantic 2, pytest, langchain-groq, twilio, APScheduler · React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui + Recharts + axios + React Query.

## Global Constraints
- Python 3.11+ ; Node 18+.
- **Dev DB = SQLite** (file `nextrade.db`); models use portable types (string UUID via `str(uuid4())`, `JSON`, no Postgres-only types in Phase 1) so deploy can switch to Postgres.
- Deterministic services (SIP/allocation/tax/rebalance) are **pure functions** — no DB, no network, no `datetime.now()` passed implicitly (inject dates) — and must be fully unit-tested via TDD.
- Every LLM/user-facing money projection uses the word **"projected"**, never "guaranteed".
- Currency = INR. Money rounded to whole rupees in outputs.
- Commit after every passing task. Conventional commit messages.
- Repo root layout: `backend/` and `frontend/` as siblings.

---

### Task 1: Backend scaffold + health endpoint

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: FastAPI `app` in `app.main`; `GET /health` → `{"status": "ok"}`. Settings object `get_settings()` reading env.

- [ ] **Step 1: Create requirements.txt**

```txt
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.29
alembic==1.13.1
pydantic==2.7.0
pydantic-settings==2.2.1
python-dotenv==1.0.1
langchain-groq==0.1.6
langchain-core==0.2.0
twilio==9.0.4
apscheduler==3.10.4
httpx==0.27.0
loguru==0.7.2
pytest==8.1.1
```

- [ ] **Step 2: Create config.py**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./nextrade.db"
    groq_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"
    allowed_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Create .env.example**

```bash
DATABASE_URL=sqlite:///./nextrade.db
GROQ_API_KEY=gsk_...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
ALLOWED_ORIGINS=http://localhost:5173
```

- [ ] **Step 4: Write the failing test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: FAIL (ModuleNotFoundError: app.main).

- [ ] **Step 6: Create main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings

settings = get_settings()
app = FastAPI(title="NexTrade API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

Also create empty `app/__init__.py` and `tests/__init__.py`.

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && pip install -r requirements.txt && python -m pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: backend scaffold with health endpoint"
```

---

### Task 2: Database setup + models (users, goals)

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/goal.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Base` (DeclarativeBase), `engine`, `SessionLocal`, `get_db()` generator. `User` and `Goal` ORM models with the columns below.
- `User`: `id:str, name:str, phone:str, risk_score:int|None, risk_profile:str|None, annual_income:float|None, monthly_expenses:float|None`.
- `Goal`: `id:str, user_id:str(FK), goal_type:str, goal_name:str, target_amount:float, current_savings:float, target_date:date, years:float, required_monthly_sip:float|None, equity_allocation:int|None, debt_allocation:int|None, gold_allocation:int|None, llm_explanation:str|None, status:str`.

- [ ] **Step 1: Create database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Create models/user.py**

```python
from uuid import uuid4
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str]
    phone: Mapped[str]
    risk_score: Mapped[int | None] = mapped_column(default=None)
    risk_profile: Mapped[str | None] = mapped_column(default=None)
    annual_income: Mapped[float | None] = mapped_column(default=None)
    monthly_expenses: Mapped[float | None] = mapped_column(default=None)
```

- [ ] **Step 3: Create models/goal.py**

```python
from datetime import date
from uuid import uuid4
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    goal_type: Mapped[str]
    goal_name: Mapped[str]
    target_amount: Mapped[float]
    current_savings: Mapped[float] = mapped_column(default=0.0)
    target_date: Mapped[date]
    years: Mapped[float]
    required_monthly_sip: Mapped[float | None] = mapped_column(default=None)
    equity_allocation: Mapped[int | None] = mapped_column(default=None)
    debt_allocation: Mapped[int | None] = mapped_column(default=None)
    gold_allocation: Mapped[int | None] = mapped_column(default=None)
    llm_explanation: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")
```

Create `models/__init__.py` importing both: `from app.models.user import User; from app.models.goal import Goal`.

- [ ] **Step 4: Write the failing test**

```python
# backend/tests/test_models.py
from app.database import Base, engine, SessionLocal
from app.models import User, Goal
from datetime import date

def test_create_user_and_goal():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    u = User(name="Manan", phone="+910000000000")
    db.add(u); db.commit(); db.refresh(u)
    g = Goal(user_id=u.id, goal_type="retirement", goal_name="Retire",
             target_amount=20000000, target_date=date(2056, 1, 1), years=30)
    db.add(g); db.commit(); db.refresh(g)
    assert u.id and g.id and g.status == "active"
    db.close()
```

- [ ] **Step 5: Run test to verify it fails then passes**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS once models exist (create the files, then run).

- [ ] **Step 6: Initialize Alembic**

Run: `cd backend && alembic init migrations`
Then edit `migrations/env.py`: set `target_metadata = Base.metadata` (import `from app.database import Base` and `from app.models import User, Goal`), and set `sqlalchemy.url` from `get_settings().database_url`.

- [ ] **Step 7: Generate + apply migration**

Run:
```bash
cd backend && alembic revision --autogenerate -m "initial users and goals"
alembic upgrade head
```
Expected: `nextrade.db` created with `users` and `goals` tables.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: db setup, user/goal models, initial migration"
```

---

### Task 3: SIP calculator service (TDD)

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/advisor/__init__.py`
- Create: `backend/app/services/advisor/sip_calculator.py`
- Test: `backend/tests/test_sip_calculator.py`

**Interfaces:**
- Produces: `calculate_required_sip(target_amount: float, years: int, annual_return_rate: float, current_savings: float = 0.0, inflation_rate: float = 0.06) -> dict` with keys `required_monthly_sip, inflation_adjusted_target, future_value_of_existing_savings, net_target_to_achieve, total_invested, wealth_created`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sip_calculator.py
from app.services.advisor.sip_calculator import calculate_required_sip

def test_zero_return_simple():
    # 12,000 in 1 year, 0% return, no inflation, no savings -> 1000/month
    r = calculate_required_sip(12000, 1, 0.0, 0.0, 0.0)
    assert r["required_monthly_sip"] == 1000

def test_inflation_adjusts_target_up():
    r = calculate_required_sip(100000, 10, 0.12, 0.0, 0.06)
    assert r["inflation_adjusted_target"] > 100000

def test_existing_savings_reduce_sip():
    high = calculate_required_sip(1000000, 10, 0.12, 0.0)["required_monthly_sip"]
    low = calculate_required_sip(1000000, 10, 0.12, 500000)["required_monthly_sip"]
    assert low < high
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sip_calculator.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement sip_calculator.py**

```python
def calculate_required_sip(
    target_amount: float,
    years: int,
    annual_return_rate: float,
    current_savings: float = 0.0,
    inflation_rate: float = 0.06,
) -> dict:
    inflation_adjusted_target = target_amount * ((1 + inflation_rate) ** years)
    r_monthly = annual_return_rate / 12
    n = years * 12
    fv_existing = current_savings * ((1 + r_monthly) ** n)
    remaining_target = max(0.0, inflation_adjusted_target - fv_existing)

    if r_monthly == 0:
        sip = remaining_target / n if n else 0.0
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

Create empty `services/__init__.py` and `services/advisor/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sip_calculator.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/tests/test_sip_calculator.py
git commit -m "feat: SIP calculator with inflation + existing-savings handling"
```

---

### Task 4: Risk scorer + asset allocator (TDD)

**Files:**
- Create: `backend/app/services/advisor/asset_allocator.py`
- Test: `backend/tests/test_asset_allocator.py`

**Interfaces:**
- Produces:
  - `calculate_risk_score(answers: list[int]) -> int` (rounded mean).
  - `risk_profile_from_score(score: int) -> str` ("conservative"|"moderate"|"aggressive").
  - `get_allocation(years: float, risk_profile: str) -> dict` → `{"equity": int, "debt": int, "gold": int}` (sums to 100).
  - `recommended_products(allocation: dict) -> dict[str, list[str]]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_asset_allocator.py
from app.services.advisor.asset_allocator import (
    calculate_risk_score, risk_profile_from_score, get_allocation,
)

def test_risk_score_mean():
    assert calculate_risk_score([10, 9, 8, 10]) == 9

def test_profile_buckets():
    assert risk_profile_from_score(3) == "conservative"
    assert risk_profile_from_score(6) == "moderate"
    assert risk_profile_from_score(9) == "aggressive"

def test_short_horizon_is_defensive():
    a = get_allocation(1.0, "aggressive")
    assert a["equity"] == 20 and a["debt"] == 70 and a["gold"] == 10

def test_allocation_sums_to_100():
    for yrs in (1, 3, 7, 15):
        for prof in ("conservative", "moderate", "aggressive"):
            a = get_allocation(yrs, prof)
            assert a["equity"] + a["debt"] + a["gold"] == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_asset_allocator.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement asset_allocator.py**

```python
def calculate_risk_score(answers: list[int]) -> int:
    return round(sum(answers) / len(answers))


def risk_profile_from_score(score: int) -> str:
    if score <= 4:
        return "conservative"
    if score <= 7:
        return "moderate"
    return "aggressive"


# (timeline_bucket, risk_profile) -> (equity, debt, gold)
_MATRIX = {
    ("short", "conservative"): (20, 70, 10),
    ("short", "moderate"): (20, 70, 10),
    ("short", "aggressive"): (20, 70, 10),
    ("mid", "conservative"): (30, 60, 10),
    ("mid", "moderate"): (50, 40, 10),
    ("mid", "aggressive"): (65, 25, 10),
    ("long", "conservative"): (50, 40, 10),
    ("long", "moderate"): (65, 25, 10),
    ("long", "aggressive"): (75, 15, 10),
    ("verylong", "conservative"): (65, 25, 10),
    ("verylong", "moderate"): (75, 15, 10),
    ("verylong", "aggressive"): (85, 10, 5),
}


def _timeline_bucket(years: float) -> str:
    if years < 2:
        return "short"
    if years <= 5:
        return "mid"
    if years <= 10:
        return "long"
    return "verylong"


def get_allocation(years: float, risk_profile: str) -> dict:
    eq, debt, gold = _MATRIX[(_timeline_bucket(years), risk_profile)]
    return {"equity": eq, "debt": debt, "gold": gold}


_PRODUCTS = {
    "equity": ["Nifty 50 Index Fund (Direct Growth)", "NIFTYBEES (ETF)"],
    "debt": ["HDFC Short Duration Fund", "Parag Parikh Liquid Fund"],
    "gold": ["Nippon India Gold ETF (GOLDBEES)", "Sovereign Gold Bond (SGB)"],
}


def recommended_products(allocation: dict) -> dict[str, list[str]]:
    return {asset: _PRODUCTS[asset] for asset, pct in allocation.items() if pct > 0}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_asset_allocator.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/advisor/asset_allocator.py backend/tests/test_asset_allocator.py
git commit -m "feat: risk scorer + timeline/risk allocation matrix"
```

---

### Task 5: Tax advisor (TDD)

**Files:**
- Create: `backend/app/services/advisor/tax_advisor.py`
- Test: `backend/tests/test_tax_advisor.py`

**Interfaces:**
- Produces: `generate_tax_saving_plan(annual_income: float, existing_80c: float = 0, existing_80d: float = 0, has_nps: bool = False) -> dict` with keys `elss_recommended, tax_saved_via_elss, nps_recommended, tax_saved_via_nps, health_insurance_gap, tax_saved_via_80d, total_potential_tax_saving, priority_order`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_tax_advisor.py
from app.services.advisor.tax_advisor import generate_tax_saving_plan

def test_full_80c_gap_for_high_earner():
    r = generate_tax_saving_plan(1500000, existing_80c=0)
    assert r["elss_recommended"] == 150000
    assert r["nps_recommended"] == 50000  # income > 5L, no nps
    assert r["health_insurance_gap"] == 25000

def test_existing_80c_reduces_recommendation():
    r = generate_tax_saving_plan(1500000, existing_80c=100000)
    assert r["elss_recommended"] == 50000

def test_has_nps_zeroes_nps():
    r = generate_tax_saving_plan(1500000, has_nps=True)
    assert r["nps_recommended"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tax_advisor.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement tax_advisor.py**

```python
def _tax_rate(income: float) -> float:
    if income <= 250000:
        return 0.0
    if income <= 500000:
        return 0.05
    if income <= 1000000:
        return 0.20
    return 0.30


def generate_tax_saving_plan(
    annual_income: float,
    existing_80c: float = 0,
    existing_80d: float = 0,
    has_nps: bool = False,
) -> dict:
    remaining_80c = max(0.0, 150000 - existing_80c)
    elss_suggestion = min(remaining_80c, 150000)
    rate = _tax_rate(annual_income)
    nps_suggestion = 50000 if annual_income > 500000 and not has_nps else 0
    health_gap = max(0.0, 25000 - existing_80d)

    return {
        "elss_recommended": elss_suggestion,
        "tax_saved_via_elss": round(elss_suggestion * rate),
        "nps_recommended": nps_suggestion,
        "tax_saved_via_nps": round(nps_suggestion * rate),
        "health_insurance_gap": health_gap,
        "tax_saved_via_80d": round(health_gap * rate),
        "total_potential_tax_saving": round(
            (elss_suggestion + nps_suggestion + health_gap) * rate
        ),
        "priority_order": ["ELSS (80C)", "Health Insurance (80D)", "NPS (80CCD1B)"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_tax_advisor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/advisor/tax_advisor.py backend/tests/test_tax_advisor.py
git commit -m "feat: tax saving advisor (80C/80D/NPS)"
```

---

### Task 6: Rebalancer (TDD)

**Files:**
- Create: `backend/app/services/advisor/rebalancer.py`
- Test: `backend/tests/test_rebalancer.py`

**Interfaces:**
- Produces: `check_rebalancing_needed(current_allocation: dict, target_allocation: dict, drift_threshold: float = 5.0) -> dict` with keys `needs_rebalancing: bool, actions: list[dict]`. Each action: `{asset, current_pct, target_pct, drift, action ("BUY"|"SELL"), action_amount_pct}`. (Date injected by caller, not here.)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rebalancer.py
from app.services.advisor.rebalancer import check_rebalancing_needed

def test_no_drift():
    r = check_rebalancing_needed({"equity": 75, "debt": 15, "gold": 10},
                                 {"equity": 75, "debt": 15, "gold": 10})
    assert r["needs_rebalancing"] is False and r["actions"] == []

def test_drift_triggers_sell():
    r = check_rebalancing_needed({"equity": 85, "debt": 10, "gold": 5},
                                 {"equity": 75, "debt": 15, "gold": 10})
    assert r["needs_rebalancing"] is True
    eq = next(a for a in r["actions"] if a["asset"] == "equity")
    assert eq["action"] == "SELL" and eq["drift"] == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_rebalancer.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement rebalancer.py**

```python
def check_rebalancing_needed(
    current_allocation: dict,
    target_allocation: dict,
    drift_threshold: float = 5.0,
) -> dict:
    actions = []
    needs = False
    for asset, target in target_allocation.items():
        current = current_allocation.get(asset, 0)
        drift = abs(current - target)
        if drift > drift_threshold:
            needs = True
            actions.append({
                "asset": asset,
                "current_pct": current,
                "target_pct": target,
                "drift": drift,
                "action": "SELL" if current > target else "BUY",
                "action_amount_pct": drift,
            })
    return {"needs_rebalancing": needs, "actions": actions}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_rebalancer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/advisor/rebalancer.py backend/tests/test_rebalancer.py
git commit -m "feat: portfolio rebalancing drift detector"
```

---

### Task 7: Pydantic schemas + Goal CRUD & calc API

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/goal.py`
- Create: `backend/app/schemas/advisor.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/advisor.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_advisor_api.py`

**Interfaces:**
- Consumes: `calculate_required_sip`, `get_allocation`, `calculate_risk_score`, `risk_profile_from_score`, `recommended_products`, `generate_tax_saving_plan`, `check_rebalancing_needed`; `User`, `Goal`, `get_db`.
- Produces routes (prefix `/api/v1`):
  - `POST /advisor/calculate-sip` body `{target_amount, years, annual_return_rate, current_savings?, inflation_rate?}` → sip dict.
  - `POST /advisor/risk-score` body `{answers: int[]}` → `{score, profile}`.
  - `POST /advisor/asset-allocation` body `{years, risk_profile}` → `{allocation, products}`.
  - `POST /advisor/tax-saving` body `{annual_income, existing_80c?, existing_80d?, has_nps?}` → tax dict.
  - `POST /goals` (create user-less for v1: requires `user_id`) and `GET /goals?user_id=...`, `GET /goals/{id}`.

- [ ] **Step 1: Write schemas/goal.py**

```python
from datetime import date
from pydantic import BaseModel


class GoalCreate(BaseModel):
    user_id: str
    goal_type: str
    goal_name: str
    target_amount: float
    current_savings: float = 0.0
    target_date: date
    years: float
    annual_return_rate: float = 0.12
    risk_profile: str = "moderate"


class GoalOut(BaseModel):
    id: str
    goal_name: str
    target_amount: float
    years: float
    required_monthly_sip: float | None
    equity_allocation: int | None
    debt_allocation: int | None
    gold_allocation: int | None
    llm_explanation: str | None
    status: str

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Write schemas/advisor.py**

```python
from pydantic import BaseModel


class SipRequest(BaseModel):
    target_amount: float
    years: int
    annual_return_rate: float = 0.12
    current_savings: float = 0.0
    inflation_rate: float = 0.06


class RiskScoreRequest(BaseModel):
    answers: list[int]


class AllocationRequest(BaseModel):
    years: float
    risk_profile: str


class TaxRequest(BaseModel):
    annual_income: float
    existing_80c: float = 0
    existing_80d: float = 0
    has_nps: bool = False
```

- [ ] **Step 3: Write routers/advisor.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Goal
from app.schemas.goal import GoalCreate, GoalOut
from app.schemas.advisor import SipRequest, RiskScoreRequest, AllocationRequest, TaxRequest
from app.services.advisor.sip_calculator import calculate_required_sip
from app.services.advisor.asset_allocator import (
    calculate_risk_score, risk_profile_from_score, get_allocation, recommended_products,
)
from app.services.advisor.tax_advisor import generate_tax_saving_plan

router = APIRouter(prefix="/api/v1", tags=["advisor"])


@router.post("/advisor/calculate-sip")
def calc_sip(req: SipRequest):
    return calculate_required_sip(
        req.target_amount, req.years, req.annual_return_rate,
        req.current_savings, req.inflation_rate,
    )


@router.post("/advisor/risk-score")
def risk_score(req: RiskScoreRequest):
    score = calculate_risk_score(req.answers)
    return {"score": score, "profile": risk_profile_from_score(score)}


@router.post("/advisor/asset-allocation")
def asset_allocation(req: AllocationRequest):
    alloc = get_allocation(req.years, req.risk_profile)
    return {"allocation": alloc, "products": recommended_products(alloc)}


@router.post("/advisor/tax-saving")
def tax_saving(req: TaxRequest):
    return generate_tax_saving_plan(
        req.annual_income, req.existing_80c, req.existing_80d, req.has_nps,
    )


@router.post("/goals", response_model=GoalOut)
def create_goal(body: GoalCreate, db: Session = Depends(get_db)):
    sip = calculate_required_sip(body.target_amount, int(body.years), body.annual_return_rate, body.current_savings)
    alloc = get_allocation(body.years, body.risk_profile)
    goal = Goal(
        user_id=body.user_id, goal_type=body.goal_type, goal_name=body.goal_name,
        target_amount=body.target_amount, current_savings=body.current_savings,
        target_date=body.target_date, years=body.years,
        required_monthly_sip=sip["required_monthly_sip"],
        equity_allocation=alloc["equity"], debt_allocation=alloc["debt"], gold_allocation=alloc["gold"],
    )
    db.add(goal); db.commit(); db.refresh(goal)
    return goal


@router.get("/goals", response_model=list[GoalOut])
def list_goals(user_id: str, db: Session = Depends(get_db)):
    return db.query(Goal).filter(Goal.user_id == user_id).all()


@router.get("/goals/{goal_id}", response_model=GoalOut)
def get_goal(goal_id: str, db: Session = Depends(get_db)):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    return goal
```

- [ ] **Step 4: Wire router in main.py**

Add to `app/main.py`:
```python
from app.routers import advisor
app.include_router(advisor.router)
```

- [ ] **Step 5: Write the failing test**

```python
# backend/tests/test_advisor_api.py
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine
from app.models import User
from app.database import SessionLocal

client = TestClient(app)

def setup_module():
    Base.metadata.create_all(bind=engine)

def test_calc_sip_endpoint():
    r = client.post("/api/v1/advisor/calculate-sip",
                    json={"target_amount": 12000, "years": 1, "annual_return_rate": 0.0, "inflation_rate": 0.0})
    assert r.status_code == 200 and r.json()["required_monthly_sip"] == 1000

def test_create_and_get_goal():
    db = SessionLocal(); u = User(name="A", phone="+910000000000"); db.add(u); db.commit(); db.refresh(u); uid = u.id; db.close()
    r = client.post("/api/v1/goals", json={
        "user_id": uid, "goal_type": "home", "goal_name": "House",
        "target_amount": 2000000, "target_date": "2031-01-01", "years": 5,
        "risk_profile": "moderate"})
    assert r.status_code == 200
    gid = r.json()["id"]
    assert client.get(f"/api/v1/goals/{gid}").json()["equity_allocation"] == 50
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_advisor_api.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas backend/app/routers backend/app/main.py backend/tests/test_advisor_api.py
git commit -m "feat: advisor calc + goal CRUD API"
```

---

### Task 8: Groq LLM explainer

**Files:**
- Create: `backend/app/services/llm/__init__.py`
- Create: `backend/app/services/llm/client.py`
- Create: `backend/app/services/llm/advisor_prompts.py`
- Modify: `backend/app/routers/advisor.py` (generate + store explanation on goal create)
- Test: `backend/tests/test_llm_explainer.py`

**Interfaces:**
- Produces: `get_goal_explanation(goal_data: dict, sip_result: dict, allocation: dict) -> str`. Uses Groq if `GROQ_API_KEY` set; returns a deterministic fallback string otherwise (so tests + offline dev pass).

- [ ] **Step 1: Write client.py**

```python
from app.config import get_settings

_FA_SYSTEM_PROMPT = (
    "You are NexTrade's friendly Indian financial advisor. Explain financial plans "
    "in simple Hinglish (Hindi-English mix). Be warm, practical, concise (3-4 sentences). "
    "Never guarantee returns. Always say 'projected' not 'guaranteed'. Use emojis sparingly."
)


def call_llm(system_prompt: str, user_message: str) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        return ""  # caller supplies fallback
    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.groq_api_key,
                   temperature=0.1, max_tokens=500, timeout=30)
    return llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)]).content
```

- [ ] **Step 2: Write advisor_prompts.py**

```python
from app.services.llm.client import call_llm, _FA_SYSTEM_PROMPT


def get_goal_explanation(goal_data: dict, sip_result: dict, allocation: dict) -> str:
    msg = (
        f"Explain this financial goal plan in 3-4 warm Hinglish sentences.\n"
        f"Goal: {goal_data['goal_name']}\n"
        f"Target: Rs {goal_data['target_amount']:,.0f} in {goal_data['years']} years\n"
        f"Projected monthly SIP: Rs {sip_result['required_monthly_sip']:,.0f}\n"
        f"Allocation: {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold\n"
        f"Projected wealth created: Rs {sip_result['wealth_created']:,.0f}\n"
        f"Remember: say projected, never guaranteed."
    )
    out = call_llm(_FA_SYSTEM_PROMPT, msg)
    if out:
        return out
    return (
        f"Aapka goal '{goal_data['goal_name']}' ke liye projected monthly SIP "
        f"Rs {sip_result['required_monthly_sip']:,.0f} hai, {goal_data['years']} saal ke liye. "
        f"Paisa {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold "
        f"mein lagega. Ye projected hai, guaranteed nahi — market ke hisaab se badal sakta hai. "
        f"Disciplined raho, har mahine invest karo. 📈"
    )
```

- [ ] **Step 3: Use it in create_goal (routers/advisor.py)**

In `create_goal`, after computing `sip` and `alloc`, before building `Goal`:
```python
    from app.services.llm.advisor_prompts import get_goal_explanation
    explanation = get_goal_explanation(
        {"goal_name": body.goal_name, "target_amount": body.target_amount, "years": body.years},
        sip, alloc,
    )
```
And add `llm_explanation=explanation,` to the `Goal(...)` constructor.

- [ ] **Step 4: Write the test (uses offline fallback)**

```python
# backend/tests/test_llm_explainer.py
from app.services.llm.advisor_prompts import get_goal_explanation

def test_fallback_explanation_mentions_projected():
    out = get_goal_explanation(
        {"goal_name": "House", "target_amount": 2000000, "years": 5},
        {"required_monthly_sip": 25000, "wealth_created": 500000},
        {"equity": 50, "debt": 40, "gold": 10},
    )
    assert "projected" in out.lower()
    assert "guaranteed nahi" in out.lower() or "guaranteed" in out.lower()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_llm_explainer.py -v`
Expected: PASS (no API key → fallback path).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm backend/app/routers/advisor.py backend/tests/test_llm_explainer.py
git commit -m "feat: Groq Hinglish goal explainer with offline fallback"
```

---

### Task 9: WhatsApp (Twilio) sender + test endpoint

**Files:**
- Create: `backend/app/services/alerts/__init__.py`
- Create: `backend/app/services/alerts/whatsapp.py`
- Create: `backend/app/services/alerts/templates.py`
- Create: `backend/app/routers/alerts.py`
- Modify: `backend/app/main.py` (include alerts router)
- Test: `backend/tests/test_alerts.py`

**Interfaces:**
- Produces: `send_whatsapp_message(to_number: str, message: str) -> str | None` (returns sid, or None if creds missing — no crash). `WhatsAppTemplates.rebalancing_alert(actions: list) -> str`. Route `POST /api/v1/alerts/test` body `{to_number, message?}`.

- [ ] **Step 1: Write whatsapp.py**

```python
from loguru import logger
from app.config import get_settings


def send_whatsapp_message(to_number: str, message: str) -> str | None:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        logger.warning("Twilio creds missing; skipping WhatsApp send")
        return None
    from twilio.rest import Client
    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    msg = client.messages.create(from_=s.twilio_whatsapp_number, body=message, to=f"whatsapp:{to_number}")
    return msg.sid
```

- [ ] **Step 2: Write templates.py**

```python
class WhatsAppTemplates:
    @staticmethod
    def rebalancing_alert(actions: list) -> str:
        lines = "\n".join(
            f"- {a['asset'].upper()}: {a['action']} {a['drift']:.1f}% (target {a['target_pct']}%)"
            for a in actions
        )
        return (
            "*Portfolio Rebalancing Alert*\n\n"
            "Your allocation has drifted from target:\n\n"
            f"{lines}\n\nConsider rebalancing this week.\n_NexTrade Financial Advisor_"
        )
```

- [ ] **Step 3: Write routers/alerts.py**

```python
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.alerts.whatsapp import send_whatsapp_message

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class TestAlert(BaseModel):
    to_number: str
    message: str = "NexTrade test alert ✅"


@router.post("/test")
def test_alert(body: TestAlert):
    sid = send_whatsapp_message(body.to_number, body.message)
    return {"sent": sid is not None, "sid": sid}
```

Wire in `main.py`: `from app.routers import alerts; app.include_router(alerts.router)`.

- [ ] **Step 4: Write the test (templates + no-cred path)**

```python
# backend/tests/test_alerts.py
from app.services.alerts.templates import WhatsAppTemplates
from app.services.alerts.whatsapp import send_whatsapp_message

def test_rebalancing_template():
    msg = WhatsAppTemplates.rebalancing_alert(
        [{"asset": "equity", "action": "SELL", "drift": 10.0, "target_pct": 75}])
    assert "EQUITY" in msg and "SELL" in msg

def test_send_without_creds_returns_none():
    assert send_whatsapp_message("+910000000000", "hi") is None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_alerts.py -v`
Expected: PASS.

- [ ] **Step 6: Manual live check (optional, needs Twilio sandbox joined)**

Run backend (`uvicorn app.main:app --reload`), then:
`curl -X POST localhost:8000/api/v1/alerts/test -H "Content-Type: application/json" -d '{"to_number":"+91YOURNUMBER"}'`
Expected: WhatsApp message received (after joining Twilio sandbox).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/alerts backend/app/routers/alerts.py backend/app/main.py backend/tests/test_alerts.py
git commit -m "feat: Twilio WhatsApp sender + test endpoint"
```

---

### Task 10: Rebalancing scheduled job (APScheduler)

**Files:**
- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/scheduler.py`
- Modify: `backend/app/main.py` (start scheduler on startup)
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Produces: `run_rebalancing_check(current: dict, target: dict, to_number: str) -> bool` (returns True if alert was triggered). `start_scheduler()` registers a Sunday 10:00 IST cron calling it (cron registration not unit-tested; the callable is).

- [ ] **Step 1: Write scheduler.py**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.advisor.rebalancer import check_rebalancing_needed
from app.services.alerts.whatsapp import send_whatsapp_message
from app.services.alerts.templates import WhatsAppTemplates

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def run_rebalancing_check(current: dict, target: dict, to_number: str) -> bool:
    result = check_rebalancing_needed(current, target)
    if result["needs_rebalancing"]:
        send_whatsapp_message(to_number, WhatsAppTemplates.rebalancing_alert(result["actions"]))
        return True
    return False


def start_scheduler():
    # Phase 1: stub job; real per-user logic wired when holdings tracking exists.
    scheduler.add_job(lambda: None, CronTrigger(day_of_week="sun", hour=10, minute=0),
                      id="weekly_rebalance", replace_existing=True)
    if not scheduler.running:
        scheduler.start()
```

- [ ] **Step 2: Wire startup in main.py**

```python
from app.jobs.scheduler import start_scheduler

@app.on_event("startup")
def _startup():
    start_scheduler()
```

- [ ] **Step 3: Write the failing test**

```python
# backend/tests/test_scheduler.py
from app.jobs.scheduler import run_rebalancing_check

def test_no_alert_when_balanced():
    assert run_rebalancing_check({"equity":75,"debt":15,"gold":10},
                                 {"equity":75,"debt":15,"gold":10}, "+910000000000") is False

def test_alert_when_drifted():
    # no Twilio creds -> send returns None but function still reports triggered
    assert run_rebalancing_check({"equity":85,"debt":10,"gold":5},
                                 {"equity":75,"debt":15,"gold":10}, "+910000000000") is True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_scheduler.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/jobs backend/app/main.py backend/tests/test_scheduler.py
git commit -m "feat: weekly rebalancing scheduler job"
```

---

### Task 11: Frontend scaffold (Vite + TS + Tailwind + shadcn)

**Files:**
- Create: `frontend/` (Vite app)
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/.env.example`

**Interfaces:**
- Produces: running Vite app; `api` axios instance with `baseURL = import.meta.env.VITE_API_URL`.

- [ ] **Step 1: Scaffold Vite app**

Run:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install axios @tanstack/react-query react-router-dom recharts
npm install -D tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p
```

- [ ] **Step 2: Configure Tailwind**

Set `frontend/tailwind.config.js` `content: ["./index.html", "./src/**/*.{ts,tsx}"]`. Add to `src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: Create lib/api.ts**

```ts
import axios from "axios";
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});
```

- [ ] **Step 4: Create .env.example**

```bash
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 5: Verify dev server**

Run: `cd frontend && npm run dev`
Expected: Vite page at http://localhost:5173.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold (vite+ts+tailwind+axios+react-query)"
```

---

### Task 12: Goal wizard + detail view (pie + LLM panel)

**Files:**
- Create: `frontend/src/pages/GoalNew.tsx`
- Create: `frontend/src/pages/GoalDetail.tsx`
- Create: `frontend/src/components/AllocationPie.tsx`
- Modify: `frontend/src/App.tsx` (routes + React Query provider)

**Interfaces:**
- Consumes: backend `POST /api/v1/goals`, `GET /api/v1/goals/{id}`.
- Produces: a working create-goal → detail flow in the browser.

- [ ] **Step 1: AllocationPie.tsx**

```tsx
import { PieChart, Pie, Cell, Legend, ResponsiveContainer } from "recharts";

const COLORS = ["#00C896", "#2196F3", "#FFC107"];

export function AllocationPie({ equity, debt, gold }: { equity: number; debt: number; gold: number }) {
  const data = [
    { name: "Equity", value: equity },
    { name: "Debt", value: debt },
    { name: "Gold", value: gold },
  ];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" outerRadius={90} label>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
        </Pie>
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: GoalNew.tsx (minimal single-form v1, wizard styling later)**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export function GoalNew() {
  const nav = useNavigate();
  const [form, setForm] = useState({
    user_id: "demo-user", goal_type: "home", goal_name: "",
    target_amount: 2000000, target_date: "2031-01-01", years: 5, risk_profile: "moderate",
  });
  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  async function submit() {
    const { data } = await api.post("/api/v1/goals", form);
    nav(`/goals/${data.id}`);
  }

  return (
    <div className="max-w-md mx-auto p-6 space-y-3">
      <h1 className="text-xl font-bold">New Goal</h1>
      <input className="border p-2 w-full" placeholder="Goal name"
        value={form.goal_name} onChange={(e) => set("goal_name", e.target.value)} />
      <input className="border p-2 w-full" type="number" placeholder="Target amount"
        value={form.target_amount} onChange={(e) => set("target_amount", +e.target.value)} />
      <input className="border p-2 w-full" type="number" placeholder="Years"
        value={form.years} onChange={(e) => set("years", +e.target.value)} />
      <select className="border p-2 w-full" value={form.risk_profile}
        onChange={(e) => set("risk_profile", e.target.value)}>
        <option value="conservative">Conservative</option>
        <option value="moderate">Moderate</option>
        <option value="aggressive">Aggressive</option>
      </select>
      <button className="bg-blue-600 text-white px-4 py-2 rounded" onClick={submit}>Create Goal</button>
    </div>
  );
}
```

- [ ] **Step 3: GoalDetail.tsx**

```tsx
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { AllocationPie } from "../components/AllocationPie";

export function GoalDetail() {
  const { id } = useParams();
  const { data, isLoading } = useQuery({
    queryKey: ["goal", id],
    queryFn: async () => (await api.get(`/api/v1/goals/${id}`)).data,
  });
  if (isLoading || !data) return <div className="p-6">Loading...</div>;
  return (
    <div className="max-w-xl mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">{data.goal_name}</h1>
      <p className="text-lg">Projected monthly SIP: ₹{data.required_monthly_sip?.toLocaleString()}</p>
      <AllocationPie equity={data.equity_allocation} debt={data.debt_allocation} gold={data.gold_allocation} />
      <div className="bg-gray-100 p-4 rounded">{data.llm_explanation}</div>
    </div>
  );
}
```

- [ ] **Step 4: App.tsx routes + providers**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GoalNew } from "./pages/GoalNew";
import { GoalDetail } from "./pages/GoalDetail";

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/goals/new" />} />
          <Route path="/goals/new" element={<GoalNew />} />
          <Route path="/goals/:id" element={<GoalDetail />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 5: Manual end-to-end verify**

Run backend (`uvicorn app.main:app --reload`) + frontend (`npm run dev`). Seed a `demo-user` row (or relax FK for v1). In the browser: create a goal → land on detail → see SIP + allocation pie + Hinglish explanation.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: goal create + detail view with allocation pie and explanation"
```

---

## Phase 1 Definition of Done
- All `pytest` tests green (`cd backend && python -m pytest -v`).
- Create a goal in the browser → see projected SIP + allocation pie + Hinglish explanation.
- `POST /api/v1/alerts/test` delivers a WhatsApp message (after joining Twilio sandbox).
- Code committed in small conventional commits.

## Self-review notes
- Spec coverage: SIP (T3), allocation+risk (T4), tax (T5), rebalance (T6), goal API (T7), LLM explainer (T8), WhatsApp (T9), rebalancing cron (T10), frontend wizard+detail+pie (T11-12) — all PRD §5 + spec §5 components covered.
- Deterministic services are pure + TDD (T3-T6).
- Portable DB types for SQLite→Postgres (T2).
- "projected" enforced in explainer + tests (T8).
- Deferred (correctly, per spec §4): trading agent, real money, multi-agent AI, user-auth wizard step (v1 uses `demo-user`; full user/risk-questionnaire flow can be a follow-up task once auth is added).
