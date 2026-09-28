#!/usr/bin/env bash
# CBES Project Set-Up - macOS/Linux launcher
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "Creating .env from .env.example ..."
  cp .env.example .env
fi

echo "Starting server on http://localhost:8000"
python -m uvicorn app.main:app --reload --port 8000
