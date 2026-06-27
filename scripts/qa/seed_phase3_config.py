#!/usr/bin/env python3
"""Seed Phase 3 configuration values into SystemConfig."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extensions import db
from models.system import SystemConfig
from run import app

CONFIG_DEFAULTS = {
    "global_data_cache_seconds": "5",
    "elite_sync_interval_seconds": "60",
    "maintenance_mode": "false",
    "registration_open": "true",
}

with app.app_context():
    for key, value in CONFIG_DEFAULTS.items():
        existing = SystemConfig.query.filter_by(key=key).first()
        if not existing:
            db.session.add(SystemConfig(key=key, value=value, description=f"Auto-seeded: {key}"))
    db.session.commit()
    print("Phase 3 config seeded.")
