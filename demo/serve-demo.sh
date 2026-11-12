#!/usr/bin/env bash
# Starts an isolated, local WashMate instance for the Playwright demo (fresh SQLite DB, dedicated TEST accounts).
#   Frontend: http://127.0.0.1:4173   API: http://127.0.0.1:5055
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
mkdir -p .tmp && rm -f .tmp/demo.db
export DATABASE_URL="sqlite:///$ROOT/.tmp/demo.db"
export SECRET_KEY="demo-only-secret-key-not-for-production-0123456789"
export CRON_SECRET="demo-cron-secret"
export UPI_ID="demo.hostel@testupi"        # fake test UPI ID – no real payments happen
export FLASK_ENV=development
echo "operator@washmate.test" > .tmp/demo-operators.txt
export OPERATORS_FILE="$ROOT/.tmp/demo-operators.txt"   # demo-only allowlist
export OPERATOR_PASSWORD="${DEMO_OPERATOR_PASSWORD:-DemoOperator#2026}"
"$PY" backend/manage.py create-operator --email operator@washmate.test --name "Demo Operator"
"$PY" backend/manage.py seed-demo
PORT=5055 "$PY" backend/run.py &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
[ -d frontend/dist ] || npm --prefix frontend run build
cd frontend
API_TARGET=http://127.0.0.1:5055 npx vite preview --host 127.0.0.1 --port 4173 --strictPort
