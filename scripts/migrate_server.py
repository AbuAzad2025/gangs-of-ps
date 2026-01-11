import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
from flask_migrate import upgrade, stamp
from sqlalchemy import inspect, text


def main():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        has_schema = bool(tables - {"alembic_version"})

        current_version = None
        if "alembic_version" in tables:
            try:
                current_version = db.session.execute(text("select version_num from alembic_version")).scalar()
            except Exception:
                current_version = None

        if has_schema and not current_version:
            with db.engine.begin() as conn:
                conn.execute(text("create table if not exists alembic_version (version_num varchar(32) not null)"))
                row = conn.execute(text("select version_num from alembic_version limit 1")).fetchone()
                if not row:
                    conn.execute(text("insert into alembic_version (version_num) values (:v)"), {"v": "380a7cb143ee"})
                else:
                    v = row[0]
                    if not v:
                        conn.execute(text("update alembic_version set version_num = :v"), {"v": "380a7cb143ee"})

        upgrade(revision="heads")
        db.session.commit()


if __name__ == "__main__":
    main()
