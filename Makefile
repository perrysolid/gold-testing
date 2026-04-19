.PHONY: up down build test lint demo seed clean

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

# ── Backend ───────────────────────────────────────────────────────────────────
backend-dev:
	cd backend && uvicorn app.main:app --reload --port 8000

backend-install:
	cd backend && pip install -e ".[dev]"

# ── Frontend ──────────────────────────────────────────────────────────────────
frontend-dev:
	cd frontend && npm run dev

frontend-install:
	cd frontend && npm ci

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	cd backend && \
	  GEMINI_MOCK=true \
	  GOLD_API_PROVIDER=mock \
	  OBJECT_STORE=local \
	  DB_URL=sqlite+aiosqlite:///./data/test.db \
	  pytest tests/ -v --tb=short -q

test-watch:
	cd backend && ptw tests/ -- -v

# ── Linting ───────────────────────────────────────────────────────────────────
lint:
	cd backend && ruff check app/ tests/ && mypy app/
	cd frontend && npm run lint

lint-fix:
	cd backend && ruff check --fix app/ tests/
	cd frontend && npm run lint -- --fix

# ── Demo ──────────────────────────────────────────────────────────────────────
seed:
	cd backend && python3 scripts/seed_demo_data.py

demo: up seed
	@echo "Opening Aurum demo at http://localhost:5173"
	@sleep 3
	@open http://localhost:5173 || xdg-open http://localhost:5173

# ── Models ────────────────────────────────────────────────────────────────────
models:
	bash backend/scripts/download_models.sh

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	cd backend && rm -rf data/test.db
	cd frontend && rm -rf dist .vite
