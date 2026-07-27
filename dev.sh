#!/usr/bin/env bash
# Starts the API and the web app together and stops both on Ctrl-C.
#
#   ./dev.sh
#
# Then open http://localhost:5173/portfolio
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x backend/venv/bin/uvicorn ]; then
  echo "backend/venv is missing. Create it with:" >&2
  echo "  python3.12 -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

# Kill both halves when this script exits, so a stray API process does not keep
# port 8000 and make the next run fail with a confusing bind error.
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
(cd backend && exec venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
pids+=($!)

(cd frontend && exec npm run dev) &
pids+=($!)

echo
echo "  API   http://127.0.0.1:8000/docs"
echo "  App   http://localhost:5173/portfolio"
echo
echo "Ctrl-C stops both."

wait
