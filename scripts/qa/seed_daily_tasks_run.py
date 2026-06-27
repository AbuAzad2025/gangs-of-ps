#!/usr/bin/env python3
"""Run daily task seeding via Flask CLI."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from run import app

with app.app_context():
    from utils.essentials import initialize_daily_tasks
    initialize_daily_tasks()
    print("Daily tasks seeded.")
