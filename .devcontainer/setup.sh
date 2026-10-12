#!/usr/bin/env bash
# One-time setup for Codespaces / Dev Containers.
set -euo pipefail
sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg postgresql-client >/dev/null
cd backend
python -m venv .venv
.venv/bin/pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 torchvision==0.20.1
.venv/bin/pip install -q -r requirements-dev.txt
until pg_isready -h db -U purplesol -q; do sleep 1; done
PGPASSWORD=purplesol psql -h db -U purplesol -tc "SELECT 1 FROM pg_database WHERE datname='purplesol_test'" | grep -q 1 \
  || PGPASSWORD=purplesol createdb -h db -U purplesol purplesol_test
.venv/bin/python -m app.migrate
.venv/bin/python -m app.seed
cd ../frontend && npm ci --no-audit --no-fund
echo "Ready. Run: make dev   (API :8000, worker, dashboard :3000)"
