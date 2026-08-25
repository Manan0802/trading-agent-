# Deploying NexTrade for free

The whole question, and the honest answer, from actually reading
[free-for-dev](https://github.com/ripienaar/free-for-dev) end to end — all 57
sections, 1,705 lines — against what this app measurably needs.

> **This page assumes you can complete Oracle's signup, which requires identity
> verification and a card.** If you cannot, read
> [`FREE-NO-CARD.md`](FREE-NO-CARD.md) instead. It does not hunt for a better
> host — it removes the two requirements that make every free always-on host
> want a card, by moving the nightly jobs to GitHub Actions and turning the NAV
> store into a downloadable artifact.

---

## What this app needs, measured not guessed

```
628 MB   minimum on disk   virtualenv 434 MB (scipy 98, pandas 70, numpy 34)
                           + NAV store 190 MB + user DB 1.2 MB + code 3.6 MB
190 MB   writable          the NAV store, 5.18M rows, rewritten nightly
23:45 + 00:15 IST          two scheduled jobs, in that order, every day
never sleeps               an in-process scheduler and a warm cache both
                           assume the process stays up
outbound HTTPS             mfapi.in, nsearchives.nseindia.com, amfiindia.com,
                           Yahoo Finance
```

The three that matter are **a writable disk, a process that never sleeps, and
enough storage for the virtualenv**. Free tiers deliberately do not combine
them — that combination is the line between free and paid.

## What the whole list actually contains

Searched across every section:

| requirement | entries in the entire repo |
|---|---|
| says "never sleeps" | **1** — gigalixir (Elixir only; its Postgres caps at 10,000 rows, we have 5.18M) |
| says "persistent storage" | **1** — Google Cloud Shell, capped at 60 hours a week |

Two offers clear all three requirements:

| | RAM | disk | always on | verdict |
|---|---|---|---|---|
| **Oracle Cloud Always Free** — Ampere A1 | **12 GB** | **200 GB** block volume | yes, it is a real VM | **use this** |
| Google Compute Engine — e2-micro | 1 GB | 30 GB HDD | yes | runner-up; 1 GB is thin for uvicorn holding pandas + numpy + scipy resident |

Oracle also gives 10 TB egress a month and 2 public IPv4 addresses. Its one
documented catch is that instances are
[reclaimed when deemed idle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm#compute__idleinstances)
— the nightly jobs are what keep this one from qualifying, but it is a real
risk to know about rather than discover.

## Why not Vercel for the backend

Vercel Hobby is the right home for the **frontend** and cannot host this API.
From Vercel's own docs:

| Hobby | limit |
|---|---|
| cron frequency | **once per day** — anything more frequent *fails at deploy* |
| cron precision | **±59 minutes** |
| function duration | 300s (this part is fine) |
| persistent filesystem | **none** |

The scheduler needs 23:45 then 00:15, in order. With ±59 minutes of jitter on
each, scoring can fire before the NAV refresh it depends on. And the 190 MB
store has nowhere to live — every invocation starts with an empty disk.

## Why not the others

- **Render** free web services cannot attach a disk at all and sleep after 15
  minutes idle; the free Postgres is **deleted** 30 days after creation.
- **Fly.io** removed its free allowance for new signups and requires a card on
  every org before you can deploy anything.
- **Koyeb** has no volumes on the free tier and scales to zero after ~1 hour.
- **PythonAnywhere** restricts outbound traffic to a proxy allowlist, which
  blocks mfapi and nseindia, and its free tier has no always-on tasks.
- **Alwaysdata** supports Python and gives 1 GB — under our 628 MB virtualenv
  plus data, with nothing left for caches or growth.
- **Cloud Run / Lambda / Workers** are serverless: no persistent process, so no
  in-process scheduler and no warm cache.

## The database, if you ever want it off the VM

Not needed on Oracle — 200 GB of block volume holds everything, and SQLite on
local disk is faster than any network database for this read pattern. Worth
knowing anyway, because the NAV store is SQLite and these speak it:

- **Turso** — 9 GB free, libSQL, no pause. The natural fit if the store ever
  needs to leave the box.
- **Layerbase** — 2 free managed databases including SQLite and libSQL.
- **Neon** — 0.5 GB Postgres, suspends after 5 minutes but wakes on connect in
  about half a second, no manual step. (Supabase pauses after 7 idle days and
  needs a **dashboard click** to come back — bad for an app that runs nightly
  and may see no human for a week.)

---

## Doing it

### 1. The VM — 10 minutes, and only you can do this part

Oracle needs identity verification and a card (it is a hold, not a charge).

1. Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
2. Create a **Compute instance**: shape `VM.Standard.A1.Flex`, **2 OCPU / 12 GB**,
   image **Canonical Ubuntu 24.04**
3. Boot volume 200 GB
4. Save the SSH private key it offers — there is no second chance
5. In **Security List** for the subnet, open ingress on **80** and **443**

### 2. Everything else is scripted

```bash
ssh ubuntu@<your-ip>
curl -fsSL https://raw.githubusercontent.com/Manan0802/trading-agent-/main/deploy/setup.sh | sudo bash
```

Installs Python and Caddy, creates the service user, clones the repo, builds
the virtualenv, generates a JWT secret, installs the systemd unit, and opens
the guest firewall — which is **separate** from the Oracle-side Security List,
and forgetting it is the classic first-deploy hour.

Then the three things that need your own values, which the script prints:

- `/etc/nextrade.env` — `ALLOWED_ORIGINS` (your Vercel URL) and `BACKEND_URL`
- `/etc/caddy/Caddyfile` — your hostname, with its DNS A record pointed at the VM
- Build the NAV store — five to thirty minutes, resumable

### 3. Frontend

```bash
cd frontend
vercel env add VITE_API_URL production    # https://api.yourdomain.com
vercel --prod
```

`VITE_API_URL` is baked in at **build** time, so changing it needs a redeploy,
not just an env edit.

### 4. If Oracle's signup rejects your card

It has a real history of that, particularly for Indian cards. The fallback is
**Hetzner CX22 at about ₹430 a month** — same architecture, same scripts,
nothing in this directory changes except who bills you. For an app holding real
holdings and goals, that is cheap insurance against Oracle's reclaim policy
anyway.

---

## Files here

| file | what it is |
|---|---|
| `setup.sh` | provisions a fresh Ubuntu VM; idempotent |
| `nextrade-api.service` | systemd unit — runs migrations, restarts on crash, survives reboot |
| `Caddyfile` | HTTPS via Let's Encrypt, auto-renewing, proxying to localhost:8020 |
| `nextrade.env.example` | every variable, with what breaks if it is wrong |

The repo's `Procfile` is Heroku syntax and a bare VM does not read it. The
systemd unit is that one line translated into something an init system keeps
alive.
