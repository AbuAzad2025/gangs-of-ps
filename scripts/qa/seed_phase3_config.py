#!/usr/bin/env python3
"""Seed SystemConfig defaults for season, world events, and VIP plans."""
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))
os.environ.setdefault("FLASK_APP", "run.py")

from config import Config
from factory import create_app, db
from models.system import SystemConfig


DEFAULTS = {
    "current_season_id": ("1", "Current season number"),
    "current_season_name": ("الموسم 1", "Display name for active season"),
    "season_ends_at": (
        (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "Season end timestamp (ISO UTC)",
    ),
    "world_event_active": ("false", "Global world event toggle"),
    "world_event_title": ("حدث عالمي", "World event banner title"),
    "world_event_description": ("", "World event banner description"),
    "world_event_type": ("general", "World event type key"),
    "world_event_icon": ("fa-bolt", "Font Awesome icon class"),
    "world_event_money_bonus_pct": ("0", "Extra money reward percent during event"),
    "world_event_ends_at": ("", "World event end timestamp (ISO UTC)"),
    "vip_monthly_cost_diamonds": ("80", "Monthly VIP cost in diamonds"),
    "vip_lifetime_cost_diamonds": ("250", "Lifetime VIP cost in diamonds"),
}


def main():
    app = create_app(Config)
    with app.app_context():
        created = 0
        for key, (value, desc) in DEFAULTS.items():
            existing = SystemConfig.query.filter_by(key=key).first()
            if existing:
                continue
            SystemConfig.set_value(key, value, description=desc)
            created += 1
        db.session.commit()
        print(f"seed_phase3_config: created {created} keys")


if __name__ == "__main__":
    main()
