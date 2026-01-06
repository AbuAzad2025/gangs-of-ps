import os
import sys
from sqlalchemy import text, inspect

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db

app = create_app()

def add_columns():
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        try:
            columns = [c['name'] for c in inspector.get_columns('user')]
        except Exception as e:
            # Fallback for some drivers if 'user' table case sensitivity is an issue
            columns = [c['name'] for c in inspector.get_columns('User')]

        with engine.connect() as conn:
            # SQLite transaction handling might be implicit or explicit depending on driver
            # We try to use a transaction
            try:
                # We don't use 'with conn.begin()' here because some drivers (like SQLite) 
                # might not support nested transactions if one is already open or behave differently.
                # Simple execute is often safer for simple migrations.
                
                if 'last_energy_update' not in columns:
                    print("Adding last_energy_update...")
                    conn.execute(text('ALTER TABLE "user" ADD COLUMN last_energy_update TIMESTAMP'))
                    print("Added last_energy_update.")
                else:
                    print("last_energy_update already exists.")

                if 'last_health_update' not in columns:
                    print("Adding last_health_update...")
                    conn.execute(text('ALTER TABLE "user" ADD COLUMN last_health_update TIMESTAMP'))
                    print("Added last_health_update.")
                else:
                    print("last_health_update already exists.")
                
                # Explicit commit for drivers that require it (like psycopg2)
                conn.commit()
                print("Migration complete.")
            except Exception as e:
                print(f"Error: {e}")
                # Try rollback if supported
                try:
                    conn.rollback()
                except:
                    pass

if __name__ == "__main__":
    add_columns()
