from sqlalchemy import text
from factory import create_app, db
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
            # Try to add the column. If it fails, it likely exists.
            try:
                conn.execute(
                    text('ALTER TABLE "user" ADD COLUMN intelligence INTEGER DEFAULT 10'))
                conn.commit()
                print("Added 'intelligence' column to User table.")
            except Exception as e:
                print(f"Could not add column (might exist): {e}")
    except Exception as e:
        print(f"General error: {e}")
