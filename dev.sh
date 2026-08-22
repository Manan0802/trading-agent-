#!/usr/bin/env bash
# Starts the API and the web app together and stops both on Ctrl-C.
#
#   ./dev.sh
#
# Then open http://localhost:5173/decide
#
# Port 8020, not 8000: 8000 is jba and 8010 is freea on this machine, and
# vite.config.ts plus all four harness scripts default to 8020. This script
# said 8000 until 2026-08-21, so following the documented entry point started
# a backend that nothing was pointed at.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x backend/venv/bin/uvicorn ]; then
  echo "backend/venv is missing. Create it with:" >&2
  echo "  python3.12 -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

# Refuse to start on top of something already holding a port. This is not
# paranoia about bind errors: binding 0.0.0.0:8020 SUCCEEDS while another
# process holds 127.0.0.1:8020, and the more specific bind then wins every
# localhost request. Both servers look healthy, the browser silently talks to
# the wrong application, and every route 404s for no visible reason. Failing
# loudly here costs a second; the silent version cost an hour.
for port in 8020 5173; do
  holders=$(lsof -ti TCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$holders" ]; then
    echo "Port $port is already taken:" >&2
    # Full command line, not lsof's 9-character COMMAND column: "Python" does
    # not tell you which project you are about to fight with.
    ps -o pid=,command= -p $(echo "$holders" | paste -sd, -) >&2
    echo >&2
    echo "Stop it first, or NexTrade will start cleanly and serve nothing:" >&2
    echo "  kill $(echo "$holders" | paste -sd' ' -)" >&2
    exit 1
  fi
done

# Kill both halves when this script exits, so a stray API process does not keep
# port 8020 and make the next run fail with a confusing bind error.
pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

# Bound to every interface rather than 127.0.0.1: the browser resolves
# "localhost" to ::1 first, and an API listening only on IPv4 answers nothing
# there, which Chrome then reports as a CORS failure rather than a refused
# connection. Same trap the Vite server hit earlier from the other side.
(cd backend && exec venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8020 --reload) &
pids+=($!)

(cd frontend && exec npm run dev) &
pids+=($!)

echo
echo "  API   http://127.0.0.1:8020/docs"
echo "  App   http://localhost:5173/portfolio"
echo
echo "Ctrl-C stops both."

wait
