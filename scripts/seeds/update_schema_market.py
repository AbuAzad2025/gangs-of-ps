from sqlalchemy import text
from extensions import db
from factory import create_app
import os
import sys

# Add parent directory to path
sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..')))


def update_schema():
    app = create_app()
    with app.app_context():
        print("Updating schema for Auctions...")

        # Create tables if not exist
        try:
            db.create_all()
            print("Tables created (if not existed).")
        except Exception as e:
            print(f"Error creating tables: {e}")


if __name__ == '__main__':
    update_schema()
