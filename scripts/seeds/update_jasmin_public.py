from models.hostess import Hostess
from factory import create_app, db
import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..')))


app = create_app()
with app.app_context():
    h = db.session.get(Hostess, 34)
    if h:
        print(f"Updating Jasmin (ID 34)...")
        # Mark as public (concierge), not hireable in casino
        h.is_public = True
        h.role = 'support'  # Or whatever fits
        h.min_rank = 1  # Accessible to all on landing
        db.session.commit()
        print("Jasmin updated: is_public=True")
    else:
        print("Jasmin not found.")
