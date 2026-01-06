
import os
import sys

# Add the parent directory to sys.path to allow importing from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
import models

app = create_app()

with app.app_context():
    print("Updating database schema...")
    db.create_all()
    
    # Seed Jail Configs if missing
    from models.system import SystemConfig
    configs = {
        'jail_enable_bribe': 'true',
        'jail_enable_breakout': 'true',
        'jail_bail_cost_diamonds': '5'
    }
    
    for key, val in configs.items():
        if not SystemConfig.query.filter_by(key=key).first():
            db.session.add(SystemConfig(key=key, value=val))
            print(f"Seeded config: {key}")
            
    db.session.commit()
    print("Database schema updated successfully.")
