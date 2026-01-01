import os
import sys
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db

def add_maintenance_column():
    app = create_app()
    with app.app_context():
        print("Adding maintenance_cost column to asset table...")
        
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE asset ADD COLUMN maintenance_cost INTEGER DEFAULT 0"))
                conn.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error (maybe column exists): {e}")

if __name__ == '__main__':
    add_maintenance_column()
