from sqlalchemy import text
from extensions import db
from factory import create_app
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # Check columns via information_schema to avoid transaction errors
        print("Checking if columns exist...")
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='market_asset' AND column_name='high_24h'"))

        if not result.fetchone():
            print("Adding columns...")
            try:
                conn.commit()
                # In Postgres, DDL must be committed.
                # using .begin() context manager
                with conn.begin():
                    conn.execute(
                        text("ALTER TABLE market_asset ADD COLUMN high_24h FLOAT DEFAULT 0.0"))
                    conn.execute(
                        text("ALTER TABLE market_asset ADD COLUMN low_24h FLOAT DEFAULT 0.0"))
                    conn.execute(
                        text("ALTER TABLE market_asset ADD COLUMN volume_24h FLOAT DEFAULT 0.0"))
                print("Columns added successfully.")
            except Exception as e:
                print(f"Error adding columns: {e}")
        else:
            print("Columns already exist.")
