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

        version_rows = []
        if "alembic_version" in tables:
            try:
                version_rows = [v for v in db.session.execute(text("select version_num from alembic_version")).scalars().all() if v]
            except Exception:
                version_rows = []

        if has_schema and not version_rows:
            stamp(revision="heads")
            db.session.commit()

        upgrade(revision="heads")
        db.session.commit()


if __name__ == "__main__":
    main()
