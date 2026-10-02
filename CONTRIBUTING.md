# Working on NexTrade

Read this before the first task. It is short on purpose: the deep reference is
`PROJECT_GUIDE.md`, and the current task list is `docs/dev/PLAN.md`.

**If you use an AI coding tool, give it this file.** Claude Code reads it
automatically (via `CLAUDE.md`). For Cursor, Codex or Copilot, point the tool's
rules at this file — e.g. create a local `AGENTS.md` containing
`Follow CONTRIBUTING.md and docs/dev/PLAN.md.` (`AGENTS.md` is gitignored, so it
stays yours).

---

## 1. Run it

Python **3.12**, Node **22+**. No API keys are needed to run it.

```bash
# backend (terminal 1)
cd backend
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env            # defaults are fine for local work
venv/bin/python -m uvicorn app.main:app --port 8020 --reload
#   -> http://127.0.0.1:8020/docs

# frontend (terminal 2)
cd frontend
npm ci
echo "VITE_API_URL=" > .env.local   # empty = use the dev proxy to :8020
npm run dev
#   -> http://localhost:5173
```

Sign up at `/login`, then give the account a portfolio to look at:

```bash
cd backend && venv/bin/python scripts/seed_demo_portfolio.py you@example.com
```

(Four holdings with **synthetic** prices — fine for building UI, not for judging
returns. The fund screener answers 503 until a NAV store exists; that is
expected on a fresh machine.)

## 2. How work flows

1. Pick the next task in `docs/dev/PLAN.md`. **One task per PR.**
2. Branch from `main`: `feat/T4-tax-lots`, `fix/T1-equity-wording`.
3. Build it. Keep PRs small — under ~400 changed lines is easy to review well.
4. Run the checks in §3. All of them.
5. Open a PR into `main` and fill in the template. CI (`pr-checks`) must be green.
6. Review comes back as inline comments. Fix in new commits (don't force-push
   over a review), then reply on each comment.

## 3. Checks before you open a PR

| What | Command | Where |
|---|---|---|
| Backend tests | `venv/bin/python -m pytest tests/ -q` | `backend/` |
| Backend compiles | `venv/bin/python -m compileall -q app scripts` | `backend/` |
| Types | `npx tsc -b --noEmit` | `frontend/` |
| Lint | `npm run lint` (oxlint; warnings already in `main` are fine, **no new errors**) | `frontend/` |
| Everything incl. browser walks | `./check.sh` (needs both servers running) | repo root |

CI runs the first four on every PR. **The browser walks only run locally** —
`./check.sh` covers accessibility, phone layout and console errors on every page.

For any UI change, attach **screenshots in light and dark** to the PR, plus one
at phone width.

**Tests that skip on your machine are fine.** About 190 tests need data only the
owner's machine has (a 190 MB NAV store, a reference checkout) and skip
themselves. A skip is not a failure.

## 4. Rules that are not up for debate

- **Never commit secrets.** No `.env`, keys, tokens, `*.db`, or the cache
  folders. This repository is **public**.
- **Bachatt is reference only.** Bachatt is a separate company. Do not call any
  Bachatt system (`investment.bachatt.app`, its database, its APIs). Read
  `docs/bachatt-teardown.md` for ideas; write our own code against public sources.
- **No buy/sell advice and no return predictions on screen.** The app shows what
  it can measure and says where each number came from (`/why`). The reasons are
  in `PROJECT_GUIDE.md` §3.
- **Tests never touch the network or a real AI model.** `tests/conftest.py`
  blanks the AI keys; mock HTTP with `httpx.MockTransport`.
- **Database changes go through an Alembic migration** (`backend/migrations/`),
  never `create_all` or a hand-added column.
- **Match the module layout:** routes in `backend/app/routers/`, logic in
  `backend/app/services/`, shapes in `backend/app/schemas/`.

## 5. Traps this codebase has already fallen into

Each of these shipped as a bug once. A reviewer will check every one.

1. **Tailwind class names must be written out in full.** Tailwind only builds
   classes it can find as literal text in source. `` `bg-${tone}` `` or
   `cls.replace('bg-', 'text-')` compiles to **nothing** — the element just has
   no colour. See `components/ui/stat.tsx` and `components/AllocationBreakdown.tsx`.
2. **SVG strokes use `text-*`, not `bg-*`.** `stroke="currentColor"` reads
   `color`. A donut painted with a `bg-*` class renders as one dark ring.
3. **Charts go through `ChartFrame`** (loading / empty / ready states). A test
   (`test_chart_devices.py`) enforces it. Keep the legend *outside* the frame —
   the frame has a fixed height and a long legend spills out of its panel.
4. **Compare like with like.** A price's freshness is judged only against
   holdings of the same kind (funds vs funds, stocks vs stocks). Stocks close
   every day; fund NAVs land overnight.
5. **Classify a fund from its official AMFI category, never the text the user
   typed.** Regular plans are not in the catalogue: resolve them through
   `advisor/plan_pairs.direct_twin()`. See `services/portfolio/asset_class.py`.
6. **Some tests read source text.** E.g. `test_why_page.py` greps
   `Holdings.tsx` for the phrase `not current`. Don't wrap a pinned phrase
   across two JSX lines — the test sees a newline and fails.
7. **New page? Add it to all four browser harnesses:** `frontend/scripts/`
   `shots.mjs`, `a11y.mjs`, `mobile.mjs`, `sweep.mjs`.
8. **New expensive endpoint? Put it in the heavy rate-limit tier**
   (`_HEAVY_PATHS` in `backend/app/middleware/rate_limit.py`).
9. **Adding tests changes a number in the docs.** `test_plan_counts.py` checks
   that `docs/phase-1-redesign.md` states the real suite size (two places:
   `N tests green` and `N tests · a 5.2M-row`). Update both when you add tests —
   the failure message tells you the right number.
10. **Mutations must refresh every view.** After changing holdings or
    transactions, invalidate every key in `PORTFOLIO_QUERY_KEYS`
    (`frontend/src/lib/portfolio-api.ts`), not just the one you remember.

## 6. Writing the PR description

Say, in plain words: what changed, which files and what each is for, how you
tested it, and anything a reviewer should know (known gaps, follow-ups). If a
reviewer has to read the diff to learn what the PR does, the description is not
done.
