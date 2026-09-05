.PHONY: up down build logs migrate lint typecheck test test-backend test-frontend demo-a demo-b

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

lint:
	docker compose exec backend ruff check app
	cd frontend && npm run lint

typecheck:
	docker compose exec backend mypy app
	cd frontend && npm run typecheck

test-backend:
	docker compose exec backend pytest app/tests -v

test-frontend:
	cd frontend && npm run test

test: test-backend test-frontend

# Restart the demo app with the login button reading "Login" (version A)
demo-a:
	LOGIN_LABEL="Login" docker compose up -d --force-recreate demo-app

# Restart the demo app with the login button reading "Sign In" (version B),
# used to demonstrate self-healing.
demo-b:
	LOGIN_LABEL="Sign In" docker compose up -d --force-recreate demo-app
