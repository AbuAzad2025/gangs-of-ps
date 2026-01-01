import os
import sys
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db

app = create_app()

def update_schema():
    with app.app_context():
        # 1. Create new tables (ConfigLog)
        db.create_all()
        print("Created new tables (if any).")
        
        # 2. Add is_suspicious to user table
        with db.engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user' AND column_name='is_suspicious'"))
            if not result.fetchone():
                print("Adding is_suspicious column to user table...")
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN is_suspicious BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("Column added.")
            else:
                print("is_suspicious column already exists.")

if __name__ == "__main__":
    update_schema()
