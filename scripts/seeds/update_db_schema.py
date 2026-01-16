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

    def _ensure_column(conn, inspector, table_name, column_name, ddl_sql):
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        if column_name not in cols:
            conn.execute(text(ddl_sql))

    app = create_app()

    with app.app_context():
        print("Updating database schema...")
        db.create_all()

        with db.engine.begin() as conn:
            inspector = inspect(conn)
            _ensure_column(
                conn, inspector, "user", "gender",
                'ALTER TABLE "user" ADD COLUMN gender VARCHAR(10) DEFAULT \'male\';',
            )
            _ensure_column(
                conn, inspector, "user", "birthdate",
                'ALTER TABLE "user" ADD COLUMN birthdate DATE;',
            )
            _ensure_column(
                conn, inspector, "user", "last_seen",
                'ALTER TABLE "user" ADD COLUMN last_seen TIMESTAMP;',
            )
            _ensure_column(
                conn, inspector, "user", "chat_muted_until",
                'ALTER TABLE "user" ADD COLUMN chat_muted_until TIMESTAMP;',
            )
            _ensure_column(
                conn, inspector, "public_chat", "room",
                "ALTER TABLE public_chat ADD COLUMN room VARCHAR(50) DEFAULT 'general';",
            )

            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_user_last_seen ON "user" (last_seen);'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_public_chat_room ON public_chat (room);'))

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
