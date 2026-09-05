#!/usr/bin/env bash
# start.sh — Native macOS startup for Autonomous QA Platform
# Usage: ./start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$ROOT/logs"
VENV="$ROOT/backend/.venv"
PYTHON=/opt/homebrew/bin/python3.12
PG_BIN=/opt/homebrew/opt/postgresql@16/bin

mkdir -p "$LOGS"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}▶ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
error() { echo -e "${RED}✖ $*${NC}"; exit 1; }

# ── Check / start PostgreSQL ──────────────────────────────────────────────────
info "Checking PostgreSQL..."
if ! brew services list | grep -q "postgresql@16.*started"; then
  info "Starting PostgreSQL 16 via Homebrew..."
  brew services start postgresql@16
  sleep 3
fi

# Create role + DB if missing
"$PG_BIN/psql" -U "$(whoami)" postgres -tc \
  "SELECT 1 FROM pg_roles WHERE rolname='qa_user'" | grep -q 1 \
  || "$PG_BIN/psql" -U "$(whoami)" postgres \
     -c "CREATE USER qa_user WITH PASSWORD 'qa_password';" 2>/dev/null || true

"$PG_BIN/psql" -U "$(whoami)" postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname='autonomous_qa'" | grep -q 1 \
  || "$PG_BIN/psql" -U "$(whoami)" postgres \
     -c "CREATE DATABASE autonomous_qa OWNER qa_user;" 2>/dev/null || true

info "PostgreSQL ready ✓"

# ── Check / start Redis ───────────────────────────────────────────────────────
info "Checking Redis..."
if ! /opt/homebrew/bin/redis-cli ping &>/dev/null; then
  info "Starting Redis via Homebrew..."
  brew services start redis
  sleep 2
fi
info "Redis ready ✓"

# ── Python venv + deps ────────────────────────────────────────────────────────
info "Setting up Python venv..."
if [ ! -d "$VENV" ]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
# Demo-app deps
"$VENV/bin/pip" install -q -r "$ROOT/demo-app/requirements.txt"
info "Python deps installed ✓"

# ── Playwright chromium ───────────────────────────────────────────────────────
info "Installing Playwright Chromium (skip if cached)..."
"$VENV/bin/playwright" install chromium 2>/dev/null || warn "Playwright install skipped (may already be cached)"

# ── Frontend npm deps ─────────────────────────────────────────────────────────
info "Installing frontend npm deps..."
cd "$ROOT/frontend" && npm install --silent
cd "$ROOT"
info "npm deps installed ✓"

# ── Alembic migrations ────────────────────────────────────────────────────────
info "Running database migrations..."
cd "$ROOT/backend" && PYTHONPATH=. "$VENV/bin/alembic" upgrade head
cd "$ROOT"
info "Migrations complete ✓"

# ── Stop any stale processes ──────────────────────────────────────────────────
for svc in backend worker frontend demo-app; do
  if [ -f "$LOGS/$svc.pid" ]; then
    kill "$(cat "$LOGS/$svc.pid")" 2>/dev/null || true
    rm -f "$LOGS/$svc.pid"
  fi
done

# ── Start services ────────────────────────────────────────────────────────────
info "Starting backend (FastAPI on :8000)..."
cd "$ROOT/backend"
PYTHONPATH=. "$VENV/bin/uvicorn" app.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  >> "$LOGS/backend.log" 2>&1 &
echo $! > "$LOGS/backend.pid"
cd "$ROOT"

info "Starting Celery worker..."
cd "$ROOT/backend"
PYTHONPATH=. "$VENV/bin/celery" -A app.workers.celery_app worker \
  --loglevel=info --concurrency=2 \
  >> "$LOGS/worker.log" 2>&1 &
echo $! > "$LOGS/worker.pid"
cd "$ROOT"

info "Starting frontend (Vite on :5173)..."
cd "$ROOT/frontend"
npm run dev >> "$LOGS/frontend.log" 2>&1 &
echo $! > "$LOGS/frontend.pid"
cd "$ROOT"

info "Starting demo-app (Flask on :5050)..."
cd "$ROOT/demo-app"
LOGIN_LABEL="${LOGIN_LABEL:-Login}" PORT=5050 "$VENV/bin/python" app.py \
  >> "$LOGS/demo-app.log" 2>&1 &
echo $! > "$LOGS/demo-app.pid"
cd "$ROOT"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅  Autonomous QA Platform is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  🖥  Dashboard   → ${YELLOW}http://localhost:5173${NC}"
echo -e "  ⚡  Backend API → ${YELLOW}http://localhost:8000/docs${NC}"
echo -e "  🎭  Demo app   → ${YELLOW}http://localhost:5050${NC}"
echo ""
echo -e "  Logs: ${YELLOW}./logs/{backend,worker,frontend,demo-app}.log${NC}"
echo -e "  Stop: ${YELLOW}./stop.sh${NC}"
echo ""
