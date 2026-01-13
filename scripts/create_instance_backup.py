import os
import sys
import subprocess
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from factory import create_app
from utils.backup_manager import BackupManager


def _db_url():
    return os.environ.get("DATABASE_URL") or "postgresql://postgres:123@localhost:5432/gangsofpalestine"


def _parse_db_url(db_url):
    r = urlparse(db_url)
    return {
        "user": r.username or "postgres",
        "password": r.password or "",
        "host": r.hostname or "localhost",
        "port": int(r.port or 5432),
        "dbname": (r.path or "/").lstrip("/") or "gangsofpalestine",
    }


def create_backup():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv(env_path)
    os.environ["DATABASE_URL"] = _db_url()
    app = create_app()
    with app.app_context():
        backup_dir = os.path.join(app.instance_path, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        creds = _parse_db_url(os.environ["DATABASE_URL"])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"full_backup_{ts}.sql"
        filepath = os.path.join(backup_dir, filename)

        env = os.environ.copy()
        if creds["password"]:
            env["PGPASSWORD"] = creds["password"]

        pg_dump = BackupManager._get_pg_tool_path("pg_dump")
        cmd = [
            pg_dump,
            "-U",
            creds["user"],
            "-h",
            str(creds["host"]),
            "-p",
            str(creds["port"]),
            "-F",
            "p",
            "-f",
            filepath,
            creds["dbname"],
        ]

        subprocess.run(cmd, env=env, check=True)
        size = os.path.getsize(filepath)

        retention_days = int(os.environ.get("BACKUP_RETENTION_DAYS", "7"))
        cutoff = datetime.now().timestamp() - retention_days * 86400
        for f in os.listdir(backup_dir):
            if f.endswith((".dump", ".sql")):
                p = os.path.join(backup_dir, f)
                try:
                    if os.path.getmtime(p) < cutoff:
                        os.remove(p)
                except Exception:
                    pass

        return filepath, size


if __name__ == "__main__":
    path, size = create_backup()
    print(path)
    print(size)
