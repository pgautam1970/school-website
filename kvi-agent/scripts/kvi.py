"""KVI command-line interface — for Windows Task Scheduler, cron, n8n or manual operation.

Examples (run from the kvi-agent folder, with the venv active):
  python scripts/kvi.py init                       # create tables + bootstrap admin
  python scripts/kvi.py run-daily                  # generate & send today's report (NPT), idempotent
  python scripts/kvi.py generate --date 2026-10-10 --no-send
  python scripts/kvi.py test-email                 # SMTP connectivity test (no school data)
  python scripts/kvi.py watch-scan                 # import new exports from the watch folder
  python scripts/kvi.py purge --days 365           # retention purge (audited)
  python scripts/kvi.py backup --out backups/      # consistent backup of DB + generated PDFs
  python scripts/kvi.py seed-demo                  # SYNTHETIC demo data only (never in production)
  python scripts/kvi.py check-config               # configuration validation
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _app():
    from app.config import get_settings
    from app.db import SessionLocal, init_db
    return get_settings, SessionLocal, init_db


def cmd_init(_a):
    """Production path: alembic migrations. Existing dev databases created by create_all are stamped."""
    get_settings, SessionLocal, init_db = _app()
    import sqlite3
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from app.db import engine
    from app.services import ensure_bootstrap
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "users" in tables and "alembic_version" not in tables:
        command.stamp(cfg, "head")          # schema already created by an earlier start
        print("Existing schema stamped at head.")
    else:
        command.upgrade(cfg, "head")
        print("Migrations applied (alembic upgrade head).")
    with SessionLocal() as db:
        ensure_bootstrap(db)
    print("Admin bootstrap checked (created only on an empty user table with KVI_ADMIN_PASSWORD set).")


def cmd_run_daily(a):
    get_settings, SessionLocal, init_db = _app()
    from app.scheduler import run_daily_job
    init_db()
    res = run_daily_job(a.date, force=a.force)
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    return 0 if res.get("send_status") in ("accepted", "skipped_duplicate", "not_requested") else 1


def cmd_generate(a):
    get_settings, SessionLocal, init_db = _app()
    from app.services import generate_and_send
    init_db()
    day = a.date or datetime.now(ZoneInfo(get_settings().timezone)).date().isoformat()
    with SessionLocal() as db:
        res = generate_and_send(db, day, send=not a.no_send, kind="regenerate", actor="cli")
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))


def cmd_test_email(_a):
    get_settings, SessionLocal, init_db = _app()
    from app.delivery.email_sender import send_test_email
    init_db()
    with SessionLocal() as db:
        out = send_test_email(db)
    print(f"status={out.status} attempts={out.attempts} detail={out.message}")
    return 0 if out.status == "accepted" else 1


def cmd_watch_scan(_a):
    get_settings, SessionLocal, init_db = _app()
    from app.scheduler import run_watch_import
    init_db()
    print(json.dumps(run_watch_import(), indent=2, ensure_ascii=False, default=str))


def cmd_purge(a):
    get_settings, SessionLocal, init_db = _app()
    from app.services import purge_expired
    init_db()
    with SessionLocal() as db:
        print(json.dumps(purge_expired(db, retention_days=a.days, actor="cli"), indent=2))


def cmd_backup(a):
    """Consistent SQLite backup (online API) + copy of generated PDFs. PostgreSQL: use pg_dump (see docs)."""
    get_settings, _S, _i = _app()
    s = get_settings()
    if not s.database_url.startswith("sqlite"):
        print("Non-SQLite database: use pg_dump, see docs/BACKUP_RESTORE.md")
        return 1
    stamp = datetime.now(ZoneInfo(s.timezone)).strftime("%Y%m%d-%H%M%S")
    out = Path(a.out) / f"kvi-backup-{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    src_path = Path(s.database_url.replace("sqlite:///", ""))
    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(out / "kvi.db"))
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    reports_dir = src_path.parent / "reports"
    if reports_dir.is_dir():
        shutil.copytree(reports_dir, out / "reports", dirs_exist_ok=True)
    print(f"Backup written to {out}")


def cmd_seed_demo(a):
    """Loads the SYNTHETIC fixtures from tests/fixtures. Refuses to run unless --i-understand-synthetic."""
    if not a.i_understand_synthetic:
        print("Refusing: this loads invented demo conversations. Re-run with --i-understand-synthetic.")
        return 1
    import os
    pw = os.environ.get("KVI_DEMO_PASSWORD", "")
    if len(pw) < 12:
        print("Set KVI_DEMO_PASSWORD (12+ characters) for the demo leadership login.")
        return 1
    get_settings, SessionLocal, init_db = _app()
    from app.connectors.whatsapp_ingest import import_export_text
    from app.models import AppSetting, User, WhatsAppGroup
    from app.security import hash_password
    from sqlalchemy import select
    sys.path.insert(0, str(ROOT / "tests"))
    from fixture_map import FILE_FOR_GROUP, GROUPS  # synthetic fixture map (no env side effects)
    init_db()
    fixtures = ROOT / "tests" / "fixtures" / "whatsapp"
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.username == "demo_leadership")):
            db.add(User(username="demo_leadership", full_name="DEMO Leadership (synthetic)", role="leadership",
                        password_hash=hash_password(pw)))
        for name, cat, level, method in GROUPS:
            if not db.scalar(select(WhatsAppGroup).where(WhatsAppGroup.name == name)):
                db.add(WhatsAppGroup(name=name, category=cat, class_level=level, collection_method=method,
                                     group_admin="SYNTHETIC DEMO DATA", authorization_noted=False))
        db.commit()
        for name, fname in FILE_FOR_GROUP.items():
            g = db.scalar(select(WhatsAppGroup).where(WhatsAppGroup.name == name))
            import_export_text(db, g, (fixtures / fname).read_text(encoding="utf-8"), import_label="demo_synthetic")
        flag = db.get(AppSetting, "demo_data") or AppSetting(key="demo_data")
        flag.value = {"v": True}
        db.add(flag)
        db.commit()
    print("Synthetic demo data loaded. The dashboard shows a DEMO banner. Do not use this database for real school data.")


def cmd_check_config(_a):
    get_settings, _S, _i = _app()
    s = get_settings()
    bad = 0
    for c in s.validation_report():
        flag = "OK  " if c["ok"] else "TODO"
        bad += 0 if c["ok"] else 1
        print(f"[{flag}] {c['item']}: {c['detail']}")
    if s.env == "production" and not s.secret_key_is_strong:
        print("ERROR: KVI_SECRET_KEY must be a random value of at least 32 characters in production.")
        return 2
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="kvi", description="KVI School Intelligence CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    rd = sub.add_parser("run-daily"); rd.add_argument("--date"); rd.add_argument("--force", action="store_true")
    rd.set_defaults(fn=cmd_run_daily)
    g = sub.add_parser("generate"); g.add_argument("--date"); g.add_argument("--no-send", action="store_true")
    g.set_defaults(fn=cmd_generate)
    sub.add_parser("test-email").set_defaults(fn=cmd_test_email)
    sub.add_parser("watch-scan").set_defaults(fn=cmd_watch_scan)
    pg = sub.add_parser("purge"); pg.add_argument("--days", type=int, required=True); pg.set_defaults(fn=cmd_purge)
    bk = sub.add_parser("backup"); bk.add_argument("--out", default=str(ROOT / "backups")); bk.set_defaults(fn=cmd_backup)
    sd = sub.add_parser("seed-demo"); sd.add_argument("--i-understand-synthetic", action="store_true")
    sd.set_defaults(fn=cmd_seed_demo)
    sub.add_parser("check-config").set_defaults(fn=cmd_check_config)
    args = p.parse_args(argv)
    res = args.fn(args)
    return int(res or 0)


if __name__ == "__main__":
    sys.exit(main())
