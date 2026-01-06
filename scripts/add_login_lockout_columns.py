
import os
import sys
from sqlalchemy import text

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app, db
from models.user import User

app = create_app()

def add_login_lockout_columns():
    with app.app_context():
        # Check if columns exist
        inspector = db.inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('user')]
        
        with db.engine.connect() as conn:
            if 'failed_login_attempts' not in columns:
                print("Adding failed_login_attempts column...")
                conn.execute(text('ALTER TABLE "user" ADD COLUMN failed_login_attempts INTEGER DEFAULT 0'))
            else:
                print("failed_login_attempts column already exists.")

            if 'locked_until' not in columns:
                print("Adding locked_until column...")
                conn.execute(text('ALTER TABLE "user" ADD COLUMN locked_until TIMESTAMP'))
            else:
                print("locked_until column already exists.")
                
            conn.commit()
            print("Migration completed successfully.")

if __name__ == '__main__':
    add_login_lockout_columns()
