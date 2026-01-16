from sqlalchemy import text
from extensions import db
from factory import create_app
import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..')))


app = create_app()

with app.app_context():
    try:
        with db.engine.connect() as conn:
            # Try PostgreSQL syntax first
            try:
                conn.execute(
                    text("ALTER TABLE hostesses ADD COLUMN is_avatar_active BOOLEAN DEFAULT false"))
                conn.commit()
                print("Successfully added is_avatar_active column (PostgreSQL).")
            except Exception as e:
                # If it fails, maybe it already exists or it's SQLite (though
                # the error said psycopg2)
                print(f"First attempt failed: {e}")
                # Check if it's SQLite just in case (though unlikely given the
                # error)
                if 'sqlite' in str(db.engine.url):
                    conn.execute(
                        text("ALTER TABLE hostesses ADD COLUMN is_avatar_active BOOLEAN DEFAULT 0"))
                    conn.commit()
                    print("Successfully added is_avatar_active column (SQLite).")
    except Exception as e:
        print(f"Final error: {e}")
