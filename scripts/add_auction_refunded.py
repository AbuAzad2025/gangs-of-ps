
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from factory import create_app
from sqlalchemy import text

app = create_app()

def add_column():
    with app.app_context():
        # Use connection directly
        with db.engine.connect() as conn:
            # We need to ensure we are in a clean transaction
            trans = conn.begin()
            try:
                # Try to add column directly. 
                # If it exists, it will fail.
                # Postgres supports IF NOT EXISTS in newer versions
                conn.execute(text("ALTER TABLE auction_bid ADD COLUMN IF NOT EXISTS is_refunded BOOLEAN DEFAULT FALSE"))
                trans.commit()
                print("Column added successfully or already exists.")
            except Exception as e:
                trans.rollback()
                print(f"Error adding column: {e}")
                
if __name__ == "__main__":
    add_column()
