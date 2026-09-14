#!/bin/bash

set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "Creating Python virtual environment..."
    python3.13 -m venv .venv # backend requires Python 3.13
fi

source .venv/bin/activate
echo "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet --requirement requirements.txt

if [ ! -d frontend/node_modules ]; then
    echo "Installing frontend dependencies..."
    (cd frontend && npm install)
fi

echo "Starting backend on http://localhost:8000 ..."
(cd backend && uvicorn main:app --reload) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:5173 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap 'echo "Shutting down..."; kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null' EXIT INT TERM

wait