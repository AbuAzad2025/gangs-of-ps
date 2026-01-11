import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
from flask_migrate import upgrade


def main():
    app = create_app()
    with app.app_context():
        upgrade(revision="heads")
        db.session.commit()


if __name__ == "__main__":
    main()
