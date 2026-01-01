import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        print("Checking if gym_activity column exists in user table...")
        # Check if column exists
        # Note: user is a reserved word, so we might need to handle quotes, but information_schema stores as 'user' usually
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user' AND column_name='gym_activity'"))
        
        if not result.fetchone():
            print("Adding gym_activity column...")
            try:
                conn.commit() 
                
                with conn.begin():
                    # Using double quotes for "user" table name just in case
                    conn.execute(text('ALTER TABLE "user" ADD COLUMN gym_activity VARCHAR(512)'))
                
                print("Column gym_activity added successfully.")
            except Exception as e:
                print(f"Error adding column: {e}")
                # Try without quotes if it failed (sqlite vs postgres differences sometimes)
                try:
                    conn.rollback()
                    with conn.begin():
                         conn.execute(text("ALTER TABLE user ADD COLUMN gym_activity VARCHAR(512)"))
                    print("Column gym_activity added successfully (retry).")
                except Exception as e2:
                    print(f"Retry failed: {e2}")

        else:
            print("Column gym_activity already exists.")
