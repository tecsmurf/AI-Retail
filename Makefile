# Common tasks (run from the repo root).
PY := backend/.venv/bin/python

.PHONY: dev api worker web test lint migrate seed
dev:  ## API + worker + dashboard together (Ctrl+C stops all)
	@trap 'kill 0' INT TERM; \
	(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) & \
	(cd backend && .venv/bin/python -m app.worker) & \
	(cd frontend && npm run dev) & wait
api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
worker:
	cd backend && .venv/bin/python -m app.worker
web:
	cd frontend && npm run dev
migrate:
	cd backend && .venv/bin/python -m app.migrate
seed:
	cd backend && .venv/bin/python -m app.seed --sample
test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm run lint && npx tsc --noEmit
lint:
	cd backend && .venv/bin/ruff check app tests
	cd frontend && npm run lint
