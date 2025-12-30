import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from factory import create_app
from sqlalchemy import text

# Force Postgres URL as per start_game.py
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/gangsofpalestine'

app = create_app()

def update_schema():
    with app.app_context():
        print(f"Connecting to: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Postgres ALTER TABLE
        try:
            with db.engine.connect() as conn:
                # Wrap in transaction
                trans = conn.begin()
                try:
                    # Check columns first
                    inspector = db.inspect(db.engine)
                    
                    if 'hostesses' not in inspector.get_table_names():
                        print("Table 'hostesses' does not exist. Creating all tables...")
                        db.create_all()
                        print("Tables created.")
                        trans.commit()
                        return

                    columns = [c['name'] for c in inspector.get_columns('hostesses')]
                    print(f"Existing columns: {columns}")
                    
                    if 'level' not in columns:
                        conn.execute(text("ALTER TABLE hostesses ADD COLUMN level INTEGER DEFAULT 1"))
                        print("Added level")
                    
                    if 'exp' not in columns:
                        conn.execute(text("ALTER TABLE hostesses ADD COLUMN exp INTEGER DEFAULT 0"))
                        print("Added exp")
                        
                    if 'charm' not in columns:
                        conn.execute(text("ALTER TABLE hostesses ADD COLUMN charm INTEGER DEFAULT 10"))
                        print("Added charm")
                        
                    if 'intelligence' not in columns:
                        conn.execute(text("ALTER TABLE hostesses ADD COLUMN intelligence INTEGER DEFAULT 10"))
                        print("Added intelligence")
                        
                    if 'combat_skill' not in columns:
                        conn.execute(text("ALTER TABLE hostesses ADD COLUMN combat_skill INTEGER DEFAULT 0"))
                        print("Added combat_skill")
                        
                    if 'loyalty' not in columns:
                        conn.execute(text("ALTER TABLE hostesses ADD COLUMN loyalty INTEGER DEFAULT 50"))
                        print("Added loyalty")
                        
                    if 'special_move_cooldown' not in columns:
                        conn.execute(text("ALTER TABLE hostesses ADD COLUMN special_move_cooldown TIMESTAMP"))
                        print("Added special_move_cooldown")

                    trans.commit()
                    print("Schema update completed successfully.")
                except Exception as e:
                    trans.rollback()
                    print(f"Error updating schema: {e}")
        except Exception as e:
            print(f"Connection error: {e}")

if __name__ == "__main__":
    update_schema()


if __name__ == "__main__":
    update_schema()
