import os
import sys
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config


def _mask_url(db_url: str) -> str:
    try:
        r = urlparse(db_url)
        if not r.password:
            return db_url
        safe_netloc = f"{r.username}:***@{r.hostname}"
        if r.port:
            safe_netloc += f":{r.port}"
        return r._replace(netloc=safe_netloc).geturl()
    except Exception:
        return db_url


def _parse_url(db_url: str):
    r = urlparse(db_url)
    return {
        "user": r.username or "",
        "password": r.password or "",
        "host": r.hostname or "",
        "port": int(r.port or 5432),
        "dbname": (r.path or "").lstrip("/"),
    }


def main() -> int:
    db_url = os.environ.get("DATABASE_URL") or Config.SQLALCHEMY_DATABASE_URI
    if not db_url:
        print("DATABASE_URL is not set and Config has no database uri.")
        return 2

    if not db_url.startswith("postgresql://"):
        print("Only postgresql:// is supported.")
        print(f"Got: {_mask_url(db_url)}")
        return 2

    info = _parse_url(db_url)
    print("DATABASE_URL:", _mask_url(db_url))
    print("psql:", f"psql -h {info['host']} -p {info['port']} -U {info['user']} -d {info['dbname']}")

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            server_version = conn.execute(text("select version()")).scalar()
            current_db = conn.execute(text("select current_database()")).scalar()
            current_user = conn.execute(text("select current_user")).scalar()
            schema_count = conn.execute(
                text(
                    "select count(*) from information_schema.tables "
                    "where table_schema='public'"
                )
            ).scalar()
            print("Connected OK")
            print("Server:", server_version)
            print("Database:", current_db)
            print("User:", current_user)
            print("Public tables:", int(schema_count or 0))

            has_alembic = conn.execute(
                text(
                    "select 1 from information_schema.tables "
                    "where table_schema='public' and table_name='alembic_version' limit 1"
                )
            ).scalar()
            if has_alembic:
                alembic_version = conn.execute(text("select version_num from alembic_version limit 1")).scalar()
                print("Alembic:", alembic_version)
    except Exception as e:
        print("Connection FAILED")
        print(str(e))
        return 1
    finally:
        try:
            engine.dispose()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

