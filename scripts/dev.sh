#!/usr/bin/env bash

# MATRIOSHAI Core - Development Startup Script
echo "=================================================="
echo " Starting MATRIOSHAI Core (Phase 1)"
echo "=================================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/2] Starting Python FastAPI Backend on http://127.0.0.1:8000 ..."
cd "$ROOT_DIR/apps/backend"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

PYTHONPATH=. python main.py &
BACKEND_PID=$!

echo "[2/2] Starting Vite Frontend on http://127.0.0.1:1420 ..."
cd "$ROOT_DIR/apps/desktop"
npm run dev &
FRONTEND_PID=$!

cleanup() {
    echo "Shutting down MATRIOSHAI processes..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

wait
