#!/usr/bin/env bash
# Everything that has to be true before this is worth showing anyone.
#
#   ./check.sh            against a server you already have running on :8020
#   API=http://127.0.0.1:9000 ./check.sh    (if it is somewhere else)
#
# The unit tests assert what the code is meant to do. The three harnesses after
# them ask the questions tests do not: does anything 500 on input a form never
# showed it, does the app tell the same story in every place it tells it, and
# can one account reach another's money.
set -uo pipefail

cd "$(dirname "$0")"
# 8000 and 8010 are other projects on this machine. Pointing the gate at
# one of them does not fail -- it runs every check against a different app.
API="${API:-http://127.0.0.1:8020}"
APP="${APP:-http://localhost:5173}"
FAILED=()

step() {
  echo
  echo "── $1 ─────────────────────────────────────────"
}

# Every harness below is `harness | tail`, so the pipeline's exit status is
# tail's unless pipefail is set -- and `set -o pipefail` at the top of this file
# does NOT reach a child `bash -c`. Without the flag here, seven of the nine
# checks could not fail: this script printed "All clear" on a run where
# mobile.mjs had exited 1 and had said so on the line above the green tick.
sh() {
  bash -o pipefail -c "$1"
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

# The gate's own control, in the spirit of the `random` and `reversal` columns
# in the factor harness: prove the instrument can register a failure before
# trusting anything it says. A green run means nothing if a red one is
# impossible.
if sh "false | tail -1"; then
  echo "BROKEN: this script cannot detect a failing check, so every result"
  echo "below would be meaningless. Fix sh()/run() before trusting it."
  exit 2
fi

# Two steps, not one. Eighteen of the suite's tests assert things about the
# DOCUMENTATION -- that §9.1's headline matches its own table, that a file:line
# citation still lands on the line it quotes, that the plan's stated suite size
# is the real one. They belong in the suite: §11's whole argument is that a
# claim nothing checks is a claim that goes wrong quietly, and the front page
# said "thirty-six review passes" for dozens of passes while the log held
# eighty-four. But run under one label, a stale count in a document turns the
# CODE gate red, and a builder who touched no code cannot tell which broke.
_DOC_TESTS="tests/test_plan_counts.py tests/test_plan_structure.py \
tests/test_plan_refusals.py tests/test_plan_endpoint_counts.py \
tests/test_data_built.py tests/test_category_names.py tests/test_ter_coverage.py \
tests/test_return_bounds_agree.py"

step "unit tests"
run "pytest" sh "cd backend && venv/bin/python -m pytest -q \
  $(for t in $_DOC_TESTS; do printf -- '--ignore=%s ' \"\$t\"; done) 2>&1 | tail -3"

step "the document still matches the repo"
# Not code. These fail when a number in the plan stops being true of the repo --
# a count, a line citation, a file that lost its build date.
run "counts, citations, and dated data" sh "cd backend && venv/bin/python -m pytest -q $_DOC_TESTS 2>&1 | tail -3"

# The tests run against fixtures, so they cannot ask whether the NAVs already on
# disk are the ones AMFI published. Inserts are ON CONFLICT DO NOTHING, which
# means a stored date is never corrected -- sampling stored-against-mfapi is the
# only thing in this repo that can notice a restatement. Green on an empty store.
step "nav store integrity"
run "the stored NAVs are still true" sh "cd backend && venv/bin/python scripts/validate_nav_integrity.py --api '$API' | tail -4"

# The scoring engine is a transcription of another codebase's arithmetic, so the
# question is not "does it run" but "does it still equal the thing it copied" --
# under a different pandas major, which is where a silent drift would hide.
# Needs a pinned oracle interpreter; absent one, say so rather than pass quietly.
PARITY_PY="backend/.parity-venv/bin/python"
if [ -x "$PARITY_PY" ]; then
  step "scoring parity across library versions"
  run "our numbers still equal the reference" sh "
    $PARITY_PY backend/scripts/verify_scoring_parity.py --mode oracle --out /tmp/_o.json >/dev/null &&
    backend/venv/bin/python backend/scripts/verify_scoring_parity.py --mode port --out /tmp/_p.json >/dev/null &&
    backend/venv/bin/python backend/scripts/verify_scoring_parity.py --compare /tmp/_o.json /tmp/_p.json | tail -3"
else
  echo
  echo "No parity interpreter at $PARITY_PY - skipping the cross-version scoring check."
  echo "Create it with:  python3.12 -m venv backend/.parity-venv && backend/.parity-venv/bin/pip install 'numpy==1.26.4' 'pandas==2.2.2'"
fi

step "frontend build"
# Filtered with tail, not grep: `grep -E 'error|✓ built'` matched the word
# "error" too, so a build that failed loudly satisfied its own success check.
run "typecheck and build" sh "cd frontend && npm run build 2>&1 | tail -3"

if ! curl -sf -o /dev/null "$API/docs"; then
  echo
  echo "No API on $API — skipping the live harnesses."
  echo "Start one, or pass API=... , then run this again."
else
  step "adversarial inputs"
  run "no 500s, no NaN" sh "cd backend && venv/bin/python scripts/edge_cases.py --api '$API' | tail -4"

  step "cross-view consistency"
  run "the same fact agrees with itself" sh "cd backend && venv/bin/python scripts/consistency.py --api '$API' | tail -4"

  step "account isolation"
  run "nothing crosses between accounts" sh "cd backend && venv/bin/python scripts/isolation.py --api '$API' | tail -4"

  if curl -sf -o /dev/null "$APP"; then
    step "every page, both themes"
    run "seeded" sh "cd frontend && API_URL='$API' APP_URL='$APP' node scripts/sweep.mjs"
    run "brand new account" sh "cd frontend && API_URL='$API' APP_URL='$APP' node scripts/sweep.mjs --empty"

    step "every page on a phone"
    run "fits, and every control is thumb-sized" sh "cd frontend && API_URL='$API' APP_URL='$APP' node scripts/mobile.mjs | tail -3"

    step "without a mouse, without sight"
    run "labels, headings, contrast, tab order" sh "cd frontend && API_URL='$API' APP_URL='$APP' node scripts/a11y.mjs | tail -3"
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
