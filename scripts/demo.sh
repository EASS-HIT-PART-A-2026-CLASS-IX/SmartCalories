#!/usr/bin/env bash
#
# SmartCalories — graders' end-to-end demo (EX3).
#
# Walks through the running product without needing Firebase, Neon, or a paid LLM key:
#   1. starts the FastAPI backend on :9000 (SQLite, ENVIRONMENT=dev) if nothing is running
#   2. seeds a rich 30-day demo dataset via POST /auth/demo (returns the dev `demo-token`)
#   3. exercises the real REST surface as the demo user: profile, diary, insights, water,
#      TDEE calculator, rate-limit headers, and (if an LLM key is configured) a live AI chat turn
#
# Usage:
#   bash scripts/demo.sh                 # auto-start a bare API on :9000 and drive it
#   BASE_URL=http://localhost:9000 bash scripts/demo.sh   # drive an already-running API
#                                                          # (e.g. the `docker compose up` stack)
#
# Env knobs:
#   BASE_URL   API base URL (default http://localhost:9000). If it answers /health we reuse it;
#              otherwise we start our own and tear it down on exit.
#   GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY
#              optional — set any one to see the live AI chat reply. Without one the chat step
#              degrades gracefully (the backend returns a friendly "AI unavailable" message).
#
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:9000}"
API_PORT="${API_PORT:-9000}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKEN="demo-token"          # the dev escape-hatch token POST /auth/demo hands back
STARTED_API=""              # PID of an API we launch ourselves (empty if we reuse one)
API_LOG=""                  # logfile the launched API writes to (kept off our stdout pipe)

# --- pretty output (degrades to plain text when not a TTY) ---------------------------------
if [[ -t 1 ]]; then
  BOLD=$(printf '\033[1m'); DIM=$(printf '\033[2m'); GREEN=$(printf '\033[32m')
  BLUE=$(printf '\033[34m'); YELLOW=$(printf '\033[33m'); RESET=$(printf '\033[0m')
else
  BOLD=""; DIM=""; GREEN=""; BLUE=""; YELLOW=""; RESET=""
fi
step()  { printf '\n%s\n' "${BOLD}${BLUE}== $* ==${RESET}"; }
note()  { printf '%s\n' "${DIM}$*${RESET}"; }
ok()    { printf '%s\n' "${GREEN}✓ $*${RESET}"; }
warn()  { printf '%s\n' "${YELLOW}! $*${RESET}"; }

# Pretty-print JSON via python (always present through uv); fall back to raw text.
pp() { python3 -m json.tool 2>/dev/null || cat; }

# Authenticated curl as the demo user. Args: METHOD PATH [curl-args...]
api() {
  local method="$1" path="$2"; shift 2
  curl -fsS -X "$method" "${BASE_URL}${path}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" "$@"
}

cleanup() {
  if [[ -n "$STARTED_API" ]]; then
    note "Stopping the demo API…"
    # `uv run` forks the real uvicorn child, so killing $STARTED_API (the uv launcher) alone
    # leaves an orphan. Kill the launcher AND any uvicorn we started on our port.
    kill "$STARTED_API" 2>/dev/null || true
    pkill -f "uvicorn calorie_tracker.main:app .*--port ${API_PORT}" 2>/dev/null || true
    wait "$STARTED_API" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# --- preconditions --------------------------------------------------------------------------
command -v curl >/dev/null || { echo "curl is required"; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }

printf '%s\n' "${BOLD}SmartCalories — EX3 demo${RESET}"
note "Target API: ${BASE_URL}"

# --- start the API if needed ----------------------------------------------------------------
if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
  ok "An API is already answering at ${BASE_URL} — reusing it."
else
  command -v uv >/dev/null || { echo "uv is required to auto-start the API (https://docs.astral.sh/uv/)"; exit 1; }
  step "Starting the backend (SQLite, ENVIRONMENT=dev) on :${API_PORT}"
  note "tables auto-create on startup; no Alembic/Neon needed for the demo"
  API_LOG="$(mktemp -t smartcal-demo-api.XXXXXX)"
  note "API logs → ${API_LOG}"
  # Redirect the API's stdout/stderr to a logfile, NOT this script's stdout — otherwise the
  # backgrounded server keeps the pipe open and anything reading our output blocks on EOF.
  (
    cd "${REPO_ROOT}/backend"
    ENVIRONMENT=dev DATABASE_URL="sqlite:///./data/demo.db" \
      uv run uvicorn calorie_tracker.main:app --port "${API_PORT}" --log-level warning
  ) >"${API_LOG}" 2>&1 &
  STARTED_API=$!

  note "Waiting for /health (first run compiles deps, can take ~30s)…"
  for _ in $(seq 1 90); do
    if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then break; fi
    if ! kill -0 "$STARTED_API" 2>/dev/null; then
      echo "API process died on startup. Last log lines:"; tail -20 "${API_LOG}" 2>/dev/null; exit 1
    fi
    sleep 1
  done
  curl -fsS "${BASE_URL}/health" >/dev/null 2>&1 || {
    echo "API did not become healthy in time. Last log lines:"; tail -20 "${API_LOG}" 2>/dev/null; exit 1
  }
  ok "Backend is up."
fi

# --- 1. seed the demo dataset ---------------------------------------------------------------
step "1. Seed the demo dataset  (POST /auth/demo — dev only)"
note "wipes + rebuilds 30 days of meals, water logs, goals, and sample chats for 'demo-uid'"
SEED_JSON="$(curl -fsS -X POST "${BASE_URL}/auth/demo" -H 'Content-Type: application/json' || true)"
if [[ -z "$SEED_JSON" ]]; then
  warn "POST /auth/demo failed — the target API is probably not in ENVIRONMENT=dev."
  warn "Restart it with ENVIRONMENT=dev (the auto-start path below does this for you)."
  exit 1
fi
echo "$SEED_JSON" | pp
ok "Seeded. The dev token 'demo-token' authenticates every call below."

# --- 2. profile -----------------------------------------------------------------------------
step "2. Who am I?  (GET /users/me — auto-created from the verified token)"
api GET /users/me | pp

# --- 3. diary -------------------------------------------------------------------------------
step "3. Today's diary  (GET /diary/today)"
COUNT="$(api GET /diary/today | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')"
ok "${COUNT} entries already logged for today."

step "   Log a new food  (POST /diary)"
api POST /diary -d '{"name":"Demo apple","calories":95,"meal":"snack","protein_g":0,"carb_g":25,"fat_g":0}' | pp
ok "Entry created and scoped to the demo user."

# --- 4. insights ----------------------------------------------------------------------------
step "4. Macros today vs. goal  (GET /insights/macros/today)"
api GET /insights/macros/today | pp

step "   Logging streak  (GET /insights/streak)"
api GET /insights/streak | pp

step "   TDEE calculator  (POST /insights/tdee)"
api POST /insights/tdee -d '{"weight_kg":75,"height_cm":178,"age_years":30,"sex":"male","activity_level":"moderate"}' | pp

# --- 5. quick logs --------------------------------------------------------------------------
step "5. Log water  (POST /logs/water) then summarize  (GET /logs/range)"
api POST /logs/water -d '{"ml":300}' | pp
api GET "/logs/range?days=7" | pp

# --- 6. security: rate-limit headers --------------------------------------------------------
step "6. Rate-limit headers  (Session 11 baseline)"
# GET with header dump (-D -); /health only allows GET, so a HEAD (-I) would 405.
HEADERS="$(curl -fsS -D - -o /dev/null "${BASE_URL}/health" || true)"
if echo "$HEADERS" | grep -qi 'x-ratelimit'; then
  echo "$HEADERS" | grep -i 'x-ratelimit\|retry-after' || true
  ok "X-RateLimit-* headers present (Redis-backed token bucket)."
else
  warn "No X-RateLimit-* headers — the limiter falls open when Redis is unreachable."
  warn "Run the full stack ('cd backend && docker compose up') to see them (Redis runs there)."
fi

# --- 7. the AI agent (optional live turn) ---------------------------------------------------
step "7. AI chat turn  (POST /chat/messages → smolagents agent + diary tools)"
if [[ -n "${GEMINI_API_KEY:-}${GROQ_API_KEY:-}${OPENROUTER_API_KEY:-}" ]]; then
  note "an LLM provider key is set — running a live turn (this calls the model)…"
  CHAT_OUT="$(api POST /chat/messages -d '{"content":"/log a medium banana, then tell me my remaining calories today"}' || true)"
  if [[ -n "$CHAT_OUT" ]]; then echo "$CHAT_OUT" | pp; ok "The agent replied and logged via its tools."; \
  else warn "Chat call failed — check the provider key / quota."; fi
else
  warn "No LLM key set (GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY)."
  warn "Skipping the live AI turn. Set one and re-run to watch the agent log food and answer."
  note "The chat endpoint is exercised regardless by 'cd backend && uv run pytest' (TestModel)."
fi

# --- wrap up --------------------------------------------------------------------------------
step "Done — explore the rest interactively"
cat <<EOF
${BOLD}Next steps:${RESET}
  • Swagger UI ........ ${BASE_URL}/docs   (every endpoint, "Try it out")
  • Frontend (Chat + Diary, en/he RTL):
        cd frontend && npm install && npm run dev      # http://localhost:5173
    then click "Continue as guest" and type:  /log oatmeal 300
  • Full stack (db + api + redis + web, all local) in one shot:
        cd backend && docker compose up --build
  • Tests:  cd backend && uv run pytest        (41 tests)
EOF
ok "Demo complete."
