#!/usr/bin/env bash
# Everything that has to be true before this is worth showing anyone.
#
#   ./check.sh            against a server you already have running on :8000
#   API=http://127.0.0.1:8010 ./check.sh
#
# The unit tests assert what the code is meant to do. The three harnesses after
# them ask the questions tests do not: does anything 500 on input a form never
# showed it, does the app tell the same story in every place it tells it, and
# can one account reach another's money.
set -uo pipefail

cd "$(dirname "$0")"
API="${API:-http://127.0.0.1:8000}"
APP="${APP:-http://localhost:5173}"
FAILED=()

step() {
  echo
  echo "── $1 ─────────────────────────────────────────"
}

run() {
  local name="$1"; shift
  if "$@"; then
    echo "   ✓ $name"
  else
    echo "   ✗ $name"
    FAILED+=("$name")
  fi
}

step "unit tests"
run "pytest" bash -c "cd backend && venv/bin/python -m pytest -q 2>&1 | tail -3"

step "frontend build"
run "typecheck and build" bash -c "cd frontend && npm run build 2>&1 | grep -E 'error|✓ built'"

if ! curl -sf -o /dev/null "$API/docs"; then
  echo
  echo "No API on $API — skipping the live harnesses."
  echo "Start one, or pass API=... , then run this again."
else
  step "adversarial inputs"
  run "no 500s, no NaN" bash -c "cd backend && venv/bin/python scripts/edge_cases.py --api '$API' | tail -4"

  step "cross-view consistency"
  run "the same fact agrees with itself" bash -c "cd backend && venv/bin/python scripts/consistency.py --api '$API' | tail -4"

  step "account isolation"
  run "nothing crosses between accounts" bash -c "cd backend && venv/bin/python scripts/isolation.py --api '$API' | tail -4"

  if curl -sf -o /dev/null "$APP"; then
    step "every page, both themes"
    run "seeded" bash -c "cd frontend && API_URL='$API' APP_URL='$APP' node scripts/sweep.mjs"
    run "brand new account" bash -c "cd frontend && API_URL='$API' APP_URL='$APP' node scripts/sweep.mjs --empty"

    step "every page on a phone"
    run "fits, and every control is thumb-sized" bash -c "cd frontend && API_URL='$API' APP_URL='$APP' node scripts/mobile.mjs | tail -3"
  else
    echo
    echo "No web app on $APP — skipping the page sweep."
  fi
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "All clear."
  exit 0
fi
echo "${#FAILED[@]} failed:"
for f in "${FAILED[@]}"; do echo "  - $f"; done
exit 1
