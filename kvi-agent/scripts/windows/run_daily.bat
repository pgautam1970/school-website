@echo off
REM Generates and sends today's report (Asia/Kathmandu date). Safe to run repeatedly:
REM a report already accepted by the mail provider is never resent.
setlocal
cd /d "%~dp0\..\.."
call .venv\Scripts\activate.bat || exit /b 1
python scripts\kvi.py run-daily
exit /b %errorlevel%
