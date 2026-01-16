from models.social import PublicChat
from extensions import db
from factory import create_app
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
    db.create_all()
    print("Database tables updated successfully.")
