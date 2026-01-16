from sqlalchemy import text
from factory import create_app
from extensions import db
import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..')))


os.environ.setdefault(
    'DATABASE_URL',
    'postgresql://postgres:123@localhost:5432/gangsofpalestine')

app = create_app()


def update_schema():
    with app.app_context():
        print(f"Connecting to: {app.config['SQLALCHEMY_DATABASE_URI']}")

        inspector = db.inspect(db.engine)
        tables = set(inspector.get_table_names())

        with db.engine.connect() as conn:
            trans = conn.begin()
            try:
                if 'hostesses' not in tables:
                    print("Table 'hostesses' missing, creating all tables...")
                    db.create_all()
                    trans.commit()
                    return

                columns = {c['name']
                           for c in inspector.get_columns('hostesses')}

                if 'self_learning_enabled' not in columns:
                    conn.execute(
                        text("ALTER TABLE hostesses ADD COLUMN self_learning_enabled BOOLEAN DEFAULT TRUE"))
                    print("Added hostesses.self_learning_enabled")
                if 'memory_enabled' not in columns:
                    conn.execute(
                        text("ALTER TABLE hostesses ADD COLUMN memory_enabled BOOLEAN DEFAULT TRUE"))
                    print("Added hostesses.memory_enabled")
                if 'last_trained_at' not in columns:
                    conn.execute(
                        text("ALTER TABLE hostesses ADD COLUMN last_trained_at TIMESTAMP"))
                    print("Added hostesses.last_trained_at")

                tables = set(db.inspect(db.engine).get_table_names())

                if 'hostess_chat_messages' not in tables:
                    conn.execute(text("""
                        CREATE TABLE hostess_chat_messages (
                            id SERIAL PRIMARY KEY,
                            hostess_id INTEGER NOT NULL REFERENCES hostesses(id),
                            user_id INTEGER NULL,
                            role VARCHAR(16) NOT NULL,
                            content TEXT NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        )
                    """))
                    conn.execute(
                        text("CREATE INDEX ix_hostess_chat_messages_hostess_id ON hostess_chat_messages (hostess_id)"))
                    conn.execute(
                        text("CREATE INDEX ix_hostess_chat_messages_user_id ON hostess_chat_messages (user_id)"))
                    print("Created hostess_chat_messages")

                if 'hostess_memories' not in tables:
                    conn.execute(text("""
                        CREATE TABLE hostess_memories (
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
                    """))
                    conn.execute(
                        text("CREATE INDEX ix_hostess_memories_hostess_id ON hostess_memories (hostess_id)"))
                    conn.execute(
                        text("CREATE INDEX ix_hostess_memories_user_id ON hostess_memories (user_id)"))
                    conn.execute(
                        text("CREATE INDEX ix_hostess_memories_key ON hostess_memories (key)"))
                    print("Created hostess_memories")

                trans.commit()
                print("Schema update completed successfully.")
            except Exception as e:
                trans.rollback()
                print(f"Error updating schema: {e}")
                raise


if __name__ == "__main__":
    update_schema()
