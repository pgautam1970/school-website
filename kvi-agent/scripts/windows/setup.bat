@echo off
REM ===========================================================================
REM KVI School Intelligence - first-time setup on Windows (run from kvi-agent folder)
REM Creates the virtual environment, installs dependencies, creates .env from the
REM template (you then edit it with real values), applies migrations.
REM ===========================================================================
setlocal
cd /d "%~dp0\..\.."

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

if not exist .venv (
  echo Creating virtual environment...
  %PY% -m venv .venv || goto :fail
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt || goto :fail

if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example. EDIT IT NOW: set KVI_SECRET_KEY, KVI_ADMIN_PASSWORD and SMTP values.
  echo Generate a secret key with:  python -c "import secrets; print(secrets.token_urlsafe(48))"
)

python scripts\kvi.py init || goto :fail
python scripts\kvi.py check-config
echo.
echo Setup complete. Next: scripts\windows\run_server.bat
exit /b 0

:fail
echo.
echo SETUP FAILED. See docs\TROUBLESHOOTING.md
exit /b 1
