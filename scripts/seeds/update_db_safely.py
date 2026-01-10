import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from factory import create_app
from extensions import db
from sqlalchemy import text, inspect

app = create_app()

def update_db():
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)

        def get_tables():
            try:
                return set(inspector.get_table_names())
            except Exception:
                return set()

        def get_columns(table_name):
            try:
                return {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                return set()

        def ensure_column(conn, table_name, column_name, ddl):
            cols = get_columns(table_name)
            if column_name in cols:
                print(f"{table_name}.{column_name} already exists.")
                return
            conn.execute(text(ddl))
            print(f"Added {table_name}.{column_name}")

        def ensure_index(conn, ddl, name):
            try:
                conn.execute(text(ddl))
                print(f"Ensured index {name}")
            except Exception as e:
                print(f"Index {name} not ensured: {e}")

        def ensure_table(conn, table_name, ddl):
            tables = get_tables()
            if table_name in tables:
                print(f"Table {table_name} already exists.")
                return
            conn.execute(text(ddl))
            print(f"Created table {table_name}")

        required_tables = {"user", "hostesses", "market_asset"}
        existing_tables = get_tables()
        if not required_tables.issubset(existing_tables):
            print("Missing core tables detected. Creating missing tables via SQLAlchemy...")
            db.create_all()
            inspector = inspect(engine)
            existing_tables = get_tables()

        with engine.connect() as conn:
            trans = conn.begin()
            try:
                if "user" in existing_tables:
                    print("Checking user table columns...")
                    ensure_column(
                        conn,
                        "user",
                        "intelligence",
                        'ALTER TABLE "user" ADD COLUMN intelligence INTEGER DEFAULT 10',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "gym_until",
                        'ALTER TABLE "user" ADD COLUMN gym_until TIMESTAMP WITHOUT TIME ZONE',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "failed_login_attempts",
                        'ALTER TABLE "user" ADD COLUMN failed_login_attempts INTEGER DEFAULT 0',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "locked_until",
                        'ALTER TABLE "user" ADD COLUMN locked_until TIMESTAMP WITHOUT TIME ZONE',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "driving_skill",
                        'ALTER TABLE "user" ADD COLUMN driving_skill INTEGER DEFAULT 1',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "gym_activity",
                        'ALTER TABLE "user" ADD COLUMN gym_activity VARCHAR(512)',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "is_ghost_mode",
                        'ALTER TABLE "user" ADD COLUMN is_ghost_mode BOOLEAN DEFAULT FALSE',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "banned_until",
                        'ALTER TABLE "user" ADD COLUMN banned_until TIMESTAMP WITHOUT TIME ZONE',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "ban_reason",
                        'ALTER TABLE "user" ADD COLUMN ban_reason VARCHAR(255)',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "is_suspicious",
                        'ALTER TABLE "user" ADD COLUMN is_suspicious BOOLEAN DEFAULT FALSE',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "referral_code",
                        'ALTER TABLE "user" ADD COLUMN referral_code VARCHAR(16)',
                    )
                    ensure_column(
                        conn,
                        "user",
                        "referred_by_id",
                        'ALTER TABLE "user" ADD COLUMN referred_by_id INTEGER REFERENCES "user"(id)',
                    )
                    
                    ensure_index(
                        conn,
                        'CREATE UNIQUE INDEX IF NOT EXISTS ix_user_referral_code ON "user" (referral_code)',
                        "ix_user_referral_code",
                    )

                if "game_rooms" in existing_tables:
                    print("Checking game_rooms table columns...")
                    ensure_column(
                        conn,
                        "game_rooms",
                        "currency_type",
                        "ALTER TABLE game_rooms ADD COLUMN currency_type VARCHAR(20) DEFAULT 'money'",
                    )
                    ensure_column(
                        conn,
                        "game_rooms",
                        "stake_amount",
                        "ALTER TABLE game_rooms ADD COLUMN stake_amount BIGINT DEFAULT 0",
                    )
                    ensure_column(
                        conn,
                        "game_rooms",
                        "pot_amount",
                        "ALTER TABLE game_rooms ADD COLUMN pot_amount BIGINT DEFAULT 0",
                    )

                if "hostesses" in existing_tables:
                    print("Checking hostesses table columns...")
                    ensure_column(
                        conn,
                        "hostesses",
                        "is_avatar_active",
                        "ALTER TABLE hostesses ADD COLUMN is_avatar_active BOOLEAN DEFAULT FALSE",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "self_learning_enabled",
                        "ALTER TABLE hostesses ADD COLUMN self_learning_enabled BOOLEAN DEFAULT TRUE",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "memory_enabled",
                        "ALTER TABLE hostesses ADD COLUMN memory_enabled BOOLEAN DEFAULT TRUE",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "last_trained_at",
                        "ALTER TABLE hostesses ADD COLUMN last_trained_at TIMESTAMP",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "level",
                        "ALTER TABLE hostesses ADD COLUMN level INTEGER DEFAULT 1",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "exp",
                        "ALTER TABLE hostesses ADD COLUMN exp INTEGER DEFAULT 0",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "charm",
                        "ALTER TABLE hostesses ADD COLUMN charm INTEGER DEFAULT 10",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "intelligence",
                        "ALTER TABLE hostesses ADD COLUMN intelligence INTEGER DEFAULT 10",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "combat_skill",
                        "ALTER TABLE hostesses ADD COLUMN combat_skill INTEGER DEFAULT 0",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "loyalty",
                        "ALTER TABLE hostesses ADD COLUMN loyalty INTEGER DEFAULT 50",
                    )
                    ensure_column(
                        conn,
                        "hostesses",
                        "special_move_cooldown",
                        "ALTER TABLE hostesses ADD COLUMN special_move_cooldown TIMESTAMP",
                    )

                ensure_table(
                    conn,
                    "hostess_chat_messages",
                    """
                    CREATE TABLE IF NOT EXISTS hostess_chat_messages (
                        id SERIAL PRIMARY KEY,
                        hostess_id INTEGER NOT NULL REFERENCES hostesses(id),
                        user_id INTEGER NULL,
                        role VARCHAR(16) NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """,
                )
                ensure_index(
                    conn,
                    "CREATE INDEX IF NOT EXISTS ix_hostess_chat_messages_hostess_id ON hostess_chat_messages (hostess_id)",
                    "ix_hostess_chat_messages_hostess_id",
                )
                ensure_index(
                    conn,
                    "CREATE INDEX IF NOT EXISTS ix_hostess_chat_messages_user_id ON hostess_chat_messages (user_id)",
                    "ix_hostess_chat_messages_user_id",
                )

                ensure_table(
                    conn,
                    "hostess_memories",
                    """
                    CREATE TABLE IF NOT EXISTS hostess_memories (
                        id SERIAL PRIMARY KEY,
                        hostess_id INTEGER NOT NULL REFERENCES hostesses(id),
                        user_id INTEGER NOT NULL,
                        key VARCHAR(64) NOT NULL,
                        value TEXT NOT NULL,
                        importance INTEGER DEFAULT 1,
                        source VARCHAR(16) DEFAULT 'auto',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """,
                )
                ensure_index(
                    conn,
                    "CREATE INDEX IF NOT EXISTS ix_hostess_memories_hostess_id ON hostess_memories (hostess_id)",
                    "ix_hostess_memories_hostess_id",
                )
                ensure_index(
                    conn,
                    "CREATE INDEX IF NOT EXISTS ix_hostess_memories_user_id ON hostess_memories (user_id)",
                    "ix_hostess_memories_user_id",
                )
                ensure_index(
                    conn,
                    "CREATE INDEX IF NOT EXISTS ix_hostess_memories_key ON hostess_memories (key)",
                    "ix_hostess_memories_key",
                )

                if "market_asset" in existing_tables:
                    print("Checking market_asset table columns...")
                    ensure_column(
                        conn,
                        "market_asset",
                        "high_24h",
                        "ALTER TABLE market_asset ADD COLUMN high_24h DOUBLE PRECISION DEFAULT 0.0",
                    )
                    ensure_column(
                        conn,
                        "market_asset",
                        "low_24h",
                        "ALTER TABLE market_asset ADD COLUMN low_24h DOUBLE PRECISION DEFAULT 0.0",
                    )
                    ensure_column(
                        conn,
                        "market_asset",
                        "volume_24h",
                        "ALTER TABLE market_asset ADD COLUMN volume_24h DOUBLE PRECISION DEFAULT 0.0",
                    )

                trans.commit()
                print("Database schema check completed.")
            except Exception as e:
                trans.rollback()
                print(f"Schema update failed: {e}")
                raise

if __name__ == "__main__":
    update_db()
