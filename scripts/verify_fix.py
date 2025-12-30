import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

def verify_fix():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                print("Verifying 'driving_skill' column...")
                # Try to select the column
                conn.execute(text('SELECT driving_skill FROM "user" LIMIT 1'))
                print("[SUCCESS] Column 'driving_skill' exists and is accessible.")
                
                print("Verifying 'active_hostess_id' column...")
                conn.execute(text('SELECT active_hostess_id FROM "user" LIMIT 1'))
                print("[SUCCESS] Column 'active_hostess_id' exists and is accessible.")

        except Exception as e:
            print(f"[FAIL] Verification failed: {e}")

if __name__ == "__main__":
    verify_fix()
