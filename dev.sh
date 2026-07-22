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

(cd backend && exec venv/bin/uvicorn app.main:app --port 8000 --reload) &
pids+=($!)

(cd frontend && exec npm run dev) &
pids+=($!)

echo
echo "  API   http://127.0.0.1:8000/docs"
echo "  App   http://localhost:5173/portfolio"
echo
echo "Ctrl-C stops both."

wait
