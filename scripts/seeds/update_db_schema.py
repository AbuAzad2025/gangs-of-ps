import os
import sys


def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import models
    from extensions import db
    from factory import create_app
    from models.system import SystemConfig
    from sqlalchemy import inspect, text

    _ = models

    app = create_app()

    with app.app_context():
        print("Updating database schema...")
        db.create_all()

        with db.engine.begin() as conn:
            inspector = inspect(conn)
            cols = {c["name"] for c in inspector.get_columns("user")}
            if "gender" not in cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN gender VARCHAR(10) DEFAULT \'male\';'))
            if "birthdate" not in cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN birthdate DATE;'))

        configs = {
            'jail_enable_bribe': 'true',
            'jail_enable_breakout': 'true',
            'jail_bail_cost_diamonds': '5'
        }

        for key, val in configs.items():
            if not SystemConfig.query.filter_by(key=key).first():
                db.session.add(SystemConfig(key=key, value=val))
                print(f"Seeded config: {key}")

        db.session.commit()
        print("Database schema updated successfully.")


if __name__ == "__main__":
    main()
