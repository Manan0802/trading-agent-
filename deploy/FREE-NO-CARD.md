# Deploying NexTrade with no credit card

[`README.md`](README.md) in this directory answers "which free host is best"
and lands on Oracle Cloud Always Free. That answer stands — **if you can get
through Oracle's signup, which needs identity verification and a card.**

This is the path when you cannot, or will not, put a card anywhere. It ends
with a public HTTPS URL you can open on a phone, at ₹0/month, with no payment
method on file at any provider.

It is not the same deployment. It is a different architecture, and the
difference is the point.

---

## Why the original plan needed a card

The app used to need one host that did three things at once:

```
a writable disk      the 190 MB NAV store, rewritten nightly
a process that never sleeps   an in-process APScheduler at 23:45 and 00:15 IST
enough RAM for pandas + numpy + scipy
```

Free tiers deliberately never combine the first two. Across all 1,232 entries in
[free-for-dev](https://github.com/ripienaar/free-for-dev), exactly one says
"never sleeps" and exactly one says "persistent storage" — and they are
different services. That combination *is* the line between free and paid.

So instead of hunting for a host that clears the bar, this lowers the bar.

## What changed

**The nightly jobs moved to GitHub Actions.**
[`.github/workflows/nightly.yml`](../.github/workflows/nightly.yml) runs the NAV
refresh and the scoring pass as two sequential steps in one job. This repository
is public, so Actions minutes are unlimited and free.

Two things improved on the way:

- **The ordering is now guaranteed.** APScheduler fired the capture at 23:45 and
  the scoring at 00:15 and trusted 30 minutes to be enough. Sequential steps
  cannot invert, whatever the runner's queue does.
- **The memory-heavy work left the host.** Scoring the universe with pandas is
  the only part that ever needed real RAM, and it now happens on a 16 GB runner.

**The NAV store became a build artifact.** The workflow trims it
([`scripts/trim_nav_store.py`](../backend/scripts/trim_nav_store.py)) and
publishes it as a release asset. The app downloads it at boot
([`scripts/fetch_nav_store.py`](../backend/scripts/fetch_nav_store.py)).

    4,939 schemes -> 1,723        189 MB -> 95.8 MB -> 23.9 MB gzipped

Everything dropped is wound up — no NAV in 90 days. Verified across 11 metrics
for every fund in both stores: zero differences.

**So the disk no longer has to persist.** The store is read-only at runtime; the
thing that writes it runs on GitHub. Losing it on restart costs one 24 MB
download, not the five-to-thirty-minute mfapi re-crawl that made sleeping hosts
unusable before.

## What the app actually needs now

Measured, not estimated:

| | |
|---|---|
| API memory, serving | **46 MB RSS** |
| Store, gzipped | **23.9 MB** |
| Writable state at runtime | **the user database only, ~1.2 MB** |
| Scheduled work on the host | **none** |

Against Render's free tier that is roughly 10x RAM headroom.

---

## The stack

| Piece | Where | Card? |
|---|---|---|
| Frontend | Vercel Hobby → `*.vercel.app` | no |
| Backend API | Render free → `*.onrender.com` | **no** — see below |
| Nightly jobs | GitHub Actions | no |
| NAV store | GitHub release asset | no |
| User accounts | Turso (libSQL, SQLite-compatible) | no |
| HTTPS + domain | the platforms' own subdomains | no |

**You do not need to buy a domain.** Vercel and Render each hand you an HTTPS
subdomain. That removes Caddy, Let's Encrypt and the registrar from this path
entirely — [`Caddyfile`](Caddyfile) is for the Oracle route, not this one.

### On Render and payment methods

Render's docs do not ask for a card to sign up, and are explicit about what
happens without one:

> "If you haven't added a payment method, Render instead suspends all of your
> Free services for the remainder of the month."

Read that as a feature. With no card on file **you cannot be charged** — the
worst case is the service stopping until the month rolls over. For 3–4 users
against a 750 instance-hour allowance, you will not reach it.

The free tier's real costs are honest ones:

- **Sleeps after 15 minutes idle**, ~1 minute to wake. With the store fetched at
  boot rather than rebuilt, that is a container start, not an outage.
- **No persistent disk.** No longer relevant — which is the whole point above.
- **Free Postgres is deleted 30 days after creation.** Do not put accounts there;
  that is what Turso is for.

*(Koyeb was the alternative and is worse on every axis: 512 MB, scale-to-zero
after an hour, and a $29 pre-authorisation hold to verify you are human.)*

---

## Doing it

### 1. Turn on the nightly job

```bash
gh workflow run nightly.yml          # or the Actions tab -> nightly -> Run workflow
```

The first run builds the store from scratch and publishes the `nav-store`
release. Check it produced an asset before going further:

```bash
gh release view nav-store
```

The workflow refuses to publish a run that ranked fewer than 1,000 funds, so a
partial AMFI feed cannot quietly replace a good store with an empty screen.

### 2. User accounts on Turso

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup                    # no card
turso db create nextrade
turso db show nextrade --url
turso db tokens create nextrade
```

Set `DATABASE_URL` to the libSQL URL with the token. Everything else in
[`nextrade.env.example`](nextrade.env.example) still applies — in particular
`JWT_SECRET`, which the app refuses to start without.

### 3. Backend on Render

New → Web Service → connect the repo.

```
Root directory   backend
Build command    pip install -r requirements.txt
Start command    python scripts/fetch_nav_store.py && \
                 alembic upgrade head && \
                 uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Environment:

```bash
ENVIRONMENT=production
JWT_SECRET=<openssl rand -hex 32>
DATABASE_URL=<the Turso libSQL URL>
SCREENER_JOB_ENABLED=0        # the jobs run on Actions now, not here
ALLOWED_ORIGINS=https://<your-app>.vercel.app
FRONTEND_URL=https://<your-app>.vercel.app
BACKEND_URL=https://<your-service>.onrender.com
TRUST_PROXY_HEADER=false
```

`SCREENER_JOB_ENABLED=0` is not optional. Left on, this instance runs its own
nightly pass against a store it is supposed to be reading, and two writers
race for one file.

### 4. Frontend on Vercel

```bash
cd frontend
vercel env add VITE_API_URL production    # https://<your-service>.onrender.com
vercel --prod
```

`VITE_API_URL` is baked in at build time, so changing it needs a rebuild, not
just an env edit.

### 5. Check it

```bash
API=https://<your-service>.onrender.com APP=https://<your-app>.vercel.app ./check.sh
```

---

## What you are giving up

Say these out loud before choosing this over ₹430/month on Hetzner:

- **First request after idle takes about a minute.** Every time. For 3–4 people
  checking a portfolio a few times a day, most visits pay that cost.
- **Rate limits are per process and reset on every wake.** They already were
  in-process; sleeping makes the reset frequent. Fine at this size, not at any
  other.
- **Two providers can suspend you with no notice and no contract**, and the
  free tier is the first thing either would cut.
- **The nightly job is only as reliable as GitHub's scheduler.** Scheduled
  workflows are queued, not guaranteed, and can be dropped entirely on a
  repository with no recent pushes. `fetch_nav_store.py` warns when the newest
  NAV is more than 5 days old; nothing pages you.

None of that matters much for a screen four people read. All of it matters the
day it holds someone's real money and they expect it to be there.
