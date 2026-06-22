#!/usr/bin/env python3
"""Quick PostgreSQL + Alembic health check."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

def main():
    url = os.environ.get("DATABASE_URL", "")
    print("DATABASE_URL:", url[:50] + "..." if len(url) > 50 else url)
    if not url.startswith("postgresql"):
        print("WARN: Not using PostgreSQL — AI_INSTRUCTIONS require PostgreSQL for production.")
        return 1

    try:
        import psycopg2
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        print("PostgreSQL:", cur.fetchone()[0].split(",")[0])
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='alembic_version')"
        )
        has_alembic = cur.fetchone()[0]
        print("alembic_version table:", "yes" if has_alembic else "NO")
        if has_alembic:
            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
            print("DB revision:", row[0] if row else "empty")
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE'"
        )
        print("Public tables:", cur.fetchone()[0])
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables = [r[0] for r in cur.fetchall()]
        for key in ("user", "daily_task", "crime", "gang", "market_asset"):
            print(f"  - {key}:", "OK" if key in tables else "MISSING")
        conn.close()
    except Exception as e:
        print("PostgreSQL connection FAILED:", e)
        return 1

    os.environ.setdefault("FLASK_APP", "run.py")
    from factory import create_app, db
    from config import Config
    from flask_migrate import Migrate
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext

    app = create_app(Config)
    migrate = Migrate(app, db)

    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            db_rev = ctx.get_current_revision()
            print("Flask-Migrate current:", db_rev or "(none)")

        cfg = app.extensions["migrate"].migrate.get_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        print("Migration heads:", heads)
        if len(heads) > 1:
            print("ERROR: Multiple migration heads — branch conflict!")
            return 1
        head = heads[0] if heads else None
        if db_rev != head:
            print("MISMATCH: DB at", db_rev, "but head is", head)
            return 1
        print("Migrations: OK (DB at head)")

        # Economy academy tasks
        from models.gameplay import DailyTask
        count = DailyTask.query.filter(
            DailyTask.description.like("مدرسة الحارة - يوم %")
        ).count()
        print("Economy academy tasks in DB:", count, "(expected 5)")
        if count < 5:
            print("WARN: Run `flask seed_daily_tasks` to seed academy tasks.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
