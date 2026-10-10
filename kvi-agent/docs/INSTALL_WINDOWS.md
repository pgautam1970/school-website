# Installation on Windows (development and single-school deployment)

Requirements: Windows 10/11, Python 3.11 or newer (from python.org, tick "Add to PATH"), and the
project folder. No Docker or Node is required.

## 1. Setup
```
cd C:\KVI\school-website\kvi-agent
scripts\windows\setup.bat
```
The script creates `.venv`, installs `requirements.txt`, creates `.env` from `.env.example` (if missing),
runs `alembic upgrade head`, and prints the configuration checklist.

## 2. Configure `.env` (never commit this file)
Generate the secret key and paste it into `KVI_SECRET_KEY`:
```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Set `KVI_ADMIN_PASSWORD` (used only when the user table is empty; change the password after first login).
Fill SMTP and Meta values when you have them. Leave them empty until then. The system reports what is
missing rather than pretending it is connected.

## 3. Create the first admin
If `KVI_ADMIN_PASSWORD` was set before the first start, the admin account `admin` exists. Otherwise run
`python scripts\kvi.py init` after setting it.

## 4. Start
```
scripts\windows\run_server.bat
```
Open `http://localhost:8000` on this PC, or `http://<PC-IP>:8000` from the school LAN.
For internet-facing use, read `SECURITY_CHECKLIST.md` first. HTTPS through a reverse proxy is mandatory.

## 5. Schedule the 19:00 report
Option A (recommended): `KVI_SCHEDULER_ENABLED=true` in `.env`. The server process then runs the job
at 19:00 Asia/Kathmandu regardless of the PC's time zone. Keep the server running (install as a service
with NSSM or Windows Task Scheduler "At startup").

Option B: `powershell -ExecutionPolicy Bypass -File scripts\windows\register_daily_task.ps1`
(uses the PC clock, so set the time zone to Kathmandu, or use Option A). Use one option, not both.

## 6. Verify
```
python scripts\kvi.py check-config
python scripts\kvi.py test-email        # only after SMTP is set
python -m pytest -q                     # runs the automated test suite
```
