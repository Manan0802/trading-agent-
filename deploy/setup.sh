#!/usr/bin/env bash
# Provision a fresh Ubuntu VM to run NexTrade. Idempotent — safe to re-run.
#
#   curl -fsSL https://raw.githubusercontent.com/Manan0802/trading-agent-/main/deploy/setup.sh | sudo bash
#
# or, from a checkout:
#
#   sudo bash deploy/setup.sh
#
# ## Why a VM and not a PaaS
#
# This app needs three things at once that free PaaS tiers deliberately do not
# combine: a writable 190 MB database, a process that never sleeps (the
# scheduler runs at 23:45 and 00:15 IST), and 628 MB of disk for the virtualenv
# alone (scipy 98 MB, pandas 70 MB, numpy 34 MB).
#
# Across all 57 sections of github.com/ripienaar/free-for-dev, exactly two free
# offers clear all three:
#
#   Oracle Cloud Always Free  Ampere A1, 2 cores / 12 GB RAM / 200 GB volume
#   Google Compute Engine     e2-micro, 1 GB RAM / 30 GB HDD
#
# Oracle by a distance — 1 GB of RAM is thin for uvicorn holding pandas, numpy
# and scipy resident. Everything else in that list sleeps, has no disk, or caps
# storage below what the virtualenv needs on its own.

set -euo pipefail

APP_USER=nextrade
APP_DIR=/opt/nextrade
DATA_DIR=$APP_DIR/data
REPO=https://github.com/Manan0802/trading-agent-.git

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo" >&2
  exit 1
fi

echo "==> packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# python3.12-venv is separate on Ubuntu and its absence only shows up later, as
# a confusing failure inside `python -m venv`.
apt-get install -y -qq python3 python3-venv python3-pip git curl ca-certificates debian-keyring debian-archive-keyring apt-transport-https

echo "==> caddy (TLS that renews itself)"
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -qq && apt-get install -y -qq caddy
fi

echo "==> user and directories"
id -u "$APP_USER" &>/dev/null || useradd --system --create-home --home-dir "$APP_DIR" "$APP_USER"
mkdir -p "$DATA_DIR/navstore" /var/log/nextrade /var/log/caddy
chown -R "$APP_USER:$APP_USER" "$APP_DIR" /var/log/nextrade

echo "==> code"
if [ -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
else
  # The directory already exists as the user's home, so clone into it rather
  # than over it.
  sudo -u "$APP_USER" git clone "$REPO" "$APP_DIR/src" 2>/dev/null || true
  [ -d "$APP_DIR/src" ] && cp -rn "$APP_DIR/src/." "$APP_DIR/" && rm -rf "$APP_DIR/src"
fi

echo "==> virtualenv (about 434 MB — scipy and pandas dominate it)"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/backend/venv"
sudo -u "$APP_USER" "$APP_DIR/backend/venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/backend/venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"

echo "==> environment"
if [ ! -f /etc/nextrade.env ]; then
  cp "$APP_DIR/deploy/nextrade.env.example" /etc/nextrade.env
  # A secret that is generated is one nobody has to remember not to commit.
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" /etc/nextrade.env
  chmod 600 /etc/nextrade.env
  echo "    wrote /etc/nextrade.env — set ALLOWED_ORIGINS and BACKEND_URL before starting"
fi

echo "==> service"
cp "$APP_DIR/deploy/nextrade-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable nextrade-api

echo "==> firewall"
# Oracle's Ubuntu images ship iptables rules that drop inbound traffic, which is
# SEPARATE from the Security List you also have to open in the OCI console. Both
# have to be right, and forgetting this one is the classic first-deploy hour.
if command -v iptables >/dev/null; then
  iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true
  iptables -I INPUT -p tcp --dport 443 -j ACCEPT || true
  command -v netfilter-persistent >/dev/null && netfilter-persistent save || true
fi

cat <<'DONE'

==> installed, not yet started.

Three things left, all of them yours because they need your own values:

  1. Edit /etc/nextrade.env — ALLOWED_ORIGINS (your Vercel URL) and BACKEND_URL.
  2. Edit /etc/caddy/Caddyfile — replace api.example.com with your hostname,
     and point that hostname's DNS A record at this machine's public IP.
  3. Build the NAV store. This is the long one:

       sudo -u nextrade /opt/nextrade/backend/venv/bin/python \
         /opt/nextrade/backend/scripts/backfill_nav_history.py

     Five to thirty minutes depending on mfapi, ~5.2M rows, and it is
     resumable — an interrupt costs at most one 100-fund chunk. Until it
     finishes the screener returns 503 with its own progress in the message
     rather than an empty ranking.

  Then:  sudo systemctl start nextrade-api && sudo systemctl reload caddy
  Check: journalctl -u nextrade-api -f

DONE
