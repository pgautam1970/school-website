@echo off
REM Starts the dashboard + API on port 8000 (single process: the in-app scheduler
REM must run in exactly one process). Keep this window open, or install as a service.
setlocal
cd /d "%~dp0\..\.."
call .venv\Scripts\activate.bat || (echo Run scripts\windows\setup.bat first & exit /b 1)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers
