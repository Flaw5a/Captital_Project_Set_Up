@echo off
REM CBES Project Set-Up - Windows launcher
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Creating virtual environment...
  py -3 -m venv .venv
)
call .venv\Scripts\activate

echo Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

if not exist ".env" (
  echo Creating .env from .env.example ...
  copy .env.example .env >nul
)

echo Starting server on http://localhost:8000
python -m uvicorn app.main:app --reload --port 8000
