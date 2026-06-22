#!/usr/bin/env python3
"""Run Alembic upgrade via Flask-Migrate (Windows-safe)."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))
os.environ.setdefault("FLASK_APP", "run.py")

from config import Config
from factory import create_app
from flask_migrate import upgrade


def main():
    app = create_app(Config)
    with app.app_context():
        upgrade()
        print("upgrade: OK")


if __name__ == "__main__":
    main()
