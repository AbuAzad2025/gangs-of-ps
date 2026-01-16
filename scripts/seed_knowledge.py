from extensions import db
from utils.essentials import initialize_hostess_knowledge
from factory import create_app
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


app = create_app()

with app.app_context():
    print("Seeding Hostess Knowledge...")
    initialize_hostess_knowledge()
    db.session.commit()
    print("Done!")
