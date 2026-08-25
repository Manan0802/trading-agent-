# Deploying NexTrade

> **Which host, and why:** [`deploy/README.md`](deploy/README.md) — the whole
> free-for-dev list read against this app's measured needs (628 MB on disk, a
> 190 MB writable database, two scheduled jobs a day, a process that never
> sleeps). Two free offers in the entire list clear all three. Scripts for the
> winner are in [`deploy/`](deploy/).


Two halves that deploy separately: a static React bundle, and a FastAPI process
with a database. The frontend can go anywhere that serves files. The backend
needs somewhere that keeps a disk and does not sleep.

Nothing here is done for you. This is the list of what to set and, where it
matters, what goes wrong if you don't.

---

## Before anything

The app refuses to start in production with a broken configuration rather than
starting and failing quietly later. Four things it checks:

| It refuses if | Because |
|---|---|
| `JWT_SECRET` is the example value | It is public in this repository. Anyone could sign a token for any account. |
| `JWT_SECRET` is under 32 characters | The signature becomes the weak link. |
| `DATABASE_URL` is a **relative** SQLite path | On a hosted container that is ephemeral storage. The first redeploy silently deletes every account — nothing errors, nothing logs. |
| `ALLOWED_ORIGINS` contains `*` | This API sends credentials, so a wildcard lets any site read a logged-in user's portfolio. Browsers also reject the combination, so it fails as a total CORS outage rather than a clear error. |

Generate a secret with:

```bash
openssl rand -hex 32
```

---

## Backend

Anywhere that runs a long-lived Python process with a persistent disk —
Coolify, Railway, Fly, Render, or a VPS. **Not** a serverless function: there is
a background scheduler and a warm disk cache, and both assume the process
stays up.

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Environment

```bash
ENVIRONMENT=production
JWT_SECRET=<openssl rand -hex 32>

# Postgres, or SQLite at an ABSOLUTE path on a mounted volume.
DATABASE_URL=postgresql://user:pass@host:5432/nextrade
# DATABASE_URL=sqlite:////data/nextrade.db

# The frontend's exact origin. No wildcard, no trailing slash.
ALLOWED_ORIGINS=https://nextrade.yourdomain.com
FRONTEND_URL=https://nextrade.yourdomain.com
BACKEND_URL=https://api.nextrade.yourdomain.com

# Only if a reverse proxy you control sets X-Forwarded-For. Leave false
# otherwise: the caller sets that header themselves, and believing it gives
# every request a fresh rate-limit bucket, which turns the limiter off.
TRUST_PROXY_HEADER=false

# Optional. Absent means the feature is simply off.
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GROQ_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
```

Google OAuth also needs `https://api.<your-domain>/api/v1/auth/google/callback`
added as an authorised redirect URI in the Google console, or sign-in fails at
the last step with an error the user cannot act on.

### Disk

Three caches are written next to the backend, and they are worth keeping across
restarts — a cold start is roughly 40 seconds against 3 warm.

```
backend/.navcache/        NAV history
backend/.stockcache/      stock fundamentals
backend/.holdingscache/   AMC monthly portfolios (multi-MB downloads)
backend/.newscache/       NSE filings
```

Point them elsewhere with `NEXTRADE_CACHE_DIR`, `NEXTRADE_STOCK_CACHE_DIR`,
`NEXTRADE_HOLDINGS_CACHE_DIR`, `NEXTRADE_NEWS_CACHE_DIR`. Losing them costs
speed, never correctness.

### The NAV store is different, and needs real disk

```
backend/.navstore/nav.db   5.2M NAV rows across 4,939 funds, ~175 MB
```

`NEXTRADE_NAV_DB` moves it. **Losing this one is not free.** It is what the
whole fund screener reads, and rebuilding it takes **five to thirty minutes**
of crawling mfapi for all 4,957 funds — during which `/api/v1/screener/*`
returns **503 with the rebuild progress in the message**, not an empty ranking.
Put it on a persistent volume, or accept that outage after every redeploy.

(This line said "2-3 minutes" until 2026-08-22, which contradicted
`scripts/backfill_nav_history.py`'s own docstring in the same repository and
understated the real downtime by roughly an order of magnitude. mfapi has no
SLA and has already served half a universe once; the script's number is the
one to trust because it is the thing doing the crawling.)

It is deliberately a separate SQLite file rather than a table in
`DATABASE_URL`. That database is under a megabyte; this is 175 MB of public,
rederivable, nightly-rewritten data, and sharing a durability class with
accounts and goals would put it in every backup and every free-tier quota.
`alembic upgrade head` also runs on every deploy, and a migration against 5.2M
rows is not something to do on a boot.

Build it with:

```bash
venv/bin/python scripts/backfill_nav_history.py     # resumable; safe to interrupt
```

### Two scheduled jobs, and one switch you must set on multi-instance

| job | when (IST) | what |
|---|---|---|
| `nav_refresh` | 23:45 | Capture the day's NAVs from AMFI, then gap-fill from mfapi |
| `screener_score` | 00:15 | Score the whole universe and publish the run (~8 s) |

Split on purpose: AMFI's file carries only each scheme's **latest** NAV, so a
missed capture is recoverable only through mfapi's one-day-lagged mirror, while
scoring can be re-run any time from NAVs already stored. A scorer bug must not
cost a day of history.

**`SCREENER_JOB_ENABLED=0` on every instance but one.** APScheduler's
`max_instances=1` is per *process*, so `--workers N` or a second container means
N concurrent nightly runs against one store. The pipeline has its own in-flight
guard as well, but the switch is the one that costs nothing.

---

## Frontend

Static output. Vercel, Cloudflare Pages, Netlify, or any bucket.

```bash
cd frontend
VITE_API_URL=https://api.nextrade.yourdomain.com npm run build
# -> dist/
```

`VITE_API_URL` is baked in at build time, not read at runtime. Changing it
means rebuilding.

Serve `dist/` with SPA fallback — every unknown path rewrites to `index.html`,
or a refresh on `/portfolio` returns 404.

---

## Rate limits

In-process, so they are per worker: **N workers allow N times the limit**, and a
restart forgets everything.

```
auth       10/min   login, register, password reset   per IP
heavy      20/min   overlap, cost review, research    per user
default   120/min   everything else                   per user
/health   exempt
```

For one instance this is the right trade — no Redis to run, no operational
story to get wrong. Behind more than one worker it becomes decorative, and the
fix is to move `_Bucket` in `app/middleware/rate_limit.py` behind Redis.

---

## Verifying a deployment

```bash
curl https://api.<your-domain>/health
# {"status":"ok"}

# Security headers present
curl -sD- -o /dev/null https://api.<your-domain>/health | grep -i x-frame-options

# Rate limiter alive: the 11th should be 429
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code} " -X POST \
    https://api.<your-domain>/api/v1/auth/jwt/login \
    -d "username=nobody@example.com&password=wrong"
done
```

Then run the full gate against it:

```bash
API=https://api.<your-domain> APP=https://<your-domain> ./check.sh
```

---

## What this app does not do

It never places an order. There is no broker integration and no API key that
could move money. Recommendations are read, and executed by hand on Groww or
Zerodha. Nothing in a deployment changes that, and nothing should.

---

## Known limits worth deploying with your eyes open

- **Rate limits are per worker.** See above.
- **Holdings cover 7 AMCs** — PPFAS, SBI, Nippon, Axis, Kotak, ICICI, HDFC — and
  HDFC only partially. Anything else reports "holdings n/a", never zero.
- **The stock score is unproven.** It won on NIFTY 500 and lost on NIFTY 50, and
  the screen says so. See `docs/does-the-stock-score-work.md`.
- **Fund ranking is mostly a cost ranking**, because that is the only input that
  survived testing. See `docs/what-actually-predicts-returns.md`.
- **Market data comes from public endpoints** — mfapi, AMFI, NSE archives,
  yfinance — with no contract and no SLA. Each has a cache and a stated
  fallback; none has a guarantee.
