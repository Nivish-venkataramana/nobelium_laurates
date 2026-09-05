.PHONY: up down install migrate lint typecheck test test-backend test-frontend demo-a demo-b logs

PYTHON     := /opt/homebrew/bin/python3.12
VENV       := backend/.venv
PIP        := $(VENV)/bin/pip
PYVENV     := $(VENV)/bin/python
ALEMBIC    := $(VENV)/bin/alembic
PYTEST     := $(VENV)/bin/pytest
RUFF       := $(VENV)/bin/ruff
MYPY       := $(VENV)/bin/mypy
CELERY     := $(VENV)/bin/celery
UVICORN    := $(VENV)/bin/uvicorn
PG_CTL     := /opt/homebrew/opt/postgresql@16/bin/pg_ctl
PGDATA     := /opt/homebrew/var/postgresql@16
REDIS_CLI  := /opt/homebrew/bin/redis-cli
LOGS       := logs

# ── Start all services ────────────────────────────────────────────────────────
up: _ensure-db _ensure-redis _venv _playwright _migrate _npm
	@mkdir -p $(LOGS)
	@echo "Starting backend (FastAPI)..."
	@cd backend && PYTHONPATH=. $(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload \
		>> ../$(LOGS)/backend.log 2>&1 & echo $$! > ../$(LOGS)/backend.pid
	@echo "Starting worker (Celery)..."
	@cd backend && PYTHONPATH=. $(CELERY) -A app.workers.celery_app worker \
		--loglevel=info --concurrency=2 \
		>> ../$(LOGS)/worker.log 2>&1 & echo $$! > ../$(LOGS)/worker.pid
	@echo "Starting frontend (Vite)..."
	@cd frontend && npm run dev \
		>> ../$(LOGS)/frontend.log 2>&1 & echo $$! > ../$(LOGS)/frontend.pid
	@echo "Starting demo-app (Flask)..."
	@cd demo-app && LOGIN_LABEL=$${LOGIN_LABEL:-Login} PORT=5050 \
		$(PYVENV) app.py \
		>> ../$(LOGS)/demo-app.log 2>&1 & echo $$! > ../$(LOGS)/demo-app.pid
	@echo ""
	@echo "✅ All services started. Logs in ./logs/"
	@echo "   Frontend  → http://localhost:5173"
	@echo "   Backend   → http://localhost:8000/docs"
	@echo "   Demo app  → http://localhost:5050"

# ── Stop all services ─────────────────────────────────────────────────────────
down:
	@for svc in backend worker frontend demo-app; do \
		if [ -f $(LOGS)/$$svc.pid ]; then \
			kill $$(cat $(LOGS)/$$svc.pid) 2>/dev/null && echo "Stopped $$svc" || true; \
			rm -f $(LOGS)/$$svc.pid; \
		fi; \
	done
	@echo "All services stopped."

# ── Install dependencies ──────────────────────────────────────────────────────
install: _venv _playwright _npm
	@echo "✅ All dependencies installed."

# ── Database migrations ───────────────────────────────────────────────────────
migrate: _venv
	cd backend && $(ALEMBIC) upgrade head

# ── Linting ───────────────────────────────────────────────────────────────────
lint:
	cd backend && $(RUFF) check app
	cd frontend && npm run lint

# ── Type checking ─────────────────────────────────────────────────────────────
typecheck:
	cd backend && $(MYPY) app
	cd frontend && npm run typecheck

# ── Tests ─────────────────────────────────────────────────────────────────────
test-backend: _venv
	cd backend && $(PYTEST) app/tests/unit -v

test-frontend:
	cd frontend && npm run test

test: test-backend test-frontend

# ── Demo app label toggle ─────────────────────────────────────────────────────
demo-a:
	@if [ -f $(LOGS)/demo-app.pid ]; then kill $$(cat $(LOGS)/demo-app.pid) 2>/dev/null; fi
	@mkdir -p $(LOGS)
	@cd demo-app && LOGIN_LABEL=Login PORT=5050 $(PYVENV) app.py \
		>> ../$(LOGS)/demo-app.log 2>&1 & echo $$! > ../$(LOGS)/demo-app.pid
	@echo "Demo app restarted with LOGIN_LABEL=Login"

demo-b:
	@if [ -f $(LOGS)/demo-app.pid ]; then kill $$(cat $(LOGS)/demo-app.pid) 2>/dev/null; fi
	@mkdir -p $(LOGS)
	@cd demo-app && LOGIN_LABEL="Sign In" PORT=5050 $(PYVENV) app.py \
		>> ../$(LOGS)/demo-app.log 2>&1 & echo $$! > ../$(LOGS)/demo-app.pid
	@echo "Demo app restarted with LOGIN_LABEL=Sign In"

# ── Tail all logs ─────────────────────────────────────────────────────────────
logs:
	tail -f $(LOGS)/backend.log $(LOGS)/worker.log $(LOGS)/frontend.log $(LOGS)/demo-app.log

# ── Internal helpers ──────────────────────────────────────────────────────────
_venv:
	@if [ ! -d $(VENV) ]; then \
		echo "Creating Python venv..."; \
		$(PYTHON) -m venv $(VENV); \
	fi
	@$(PIP) install -q -r backend/requirements.txt

_playwright:
	@$(VENV)/bin/playwright install chromium 2>/dev/null || true

_npm:
	@cd frontend && npm install --silent
	@if [ -f demo-app/requirements.txt ]; then \
		$(PIP) install -q -r demo-app/requirements.txt; \
	fi

_ensure-db:
	@if ! $(PG_CTL) status -D $(PGDATA) > /dev/null 2>&1; then \
		echo "Starting PostgreSQL..."; \
		brew services start postgresql@16; \
		sleep 2; \
	fi
	@/opt/homebrew/opt/postgresql@16/bin/psql -U postgres -tc \
		"SELECT 1 FROM pg_roles WHERE rolname='qa_user'" | grep -q 1 || \
		/opt/homebrew/opt/postgresql@16/bin/psql -U postgres \
		-c "CREATE USER qa_user WITH PASSWORD 'qa_password';" 2>/dev/null || true
	@/opt/homebrew/opt/postgresql@16/bin/psql -U postgres -tc \
		"SELECT 1 FROM pg_database WHERE datname='autonomous_qa'" | grep -q 1 || \
		/opt/homebrew/opt/postgresql@16/bin/psql -U postgres \
		-c "CREATE DATABASE autonomous_qa OWNER qa_user;" 2>/dev/null || true

_ensure-redis:
	@if ! $(REDIS_CLI) ping > /dev/null 2>&1; then \
		echo "Starting Redis..."; \
		brew services start redis; \
		sleep 1; \
	fi
