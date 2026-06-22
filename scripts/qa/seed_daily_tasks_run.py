#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv()

from config import Config
from factory import create_app, db
from utils.essentials import initialize_daily_tasks

app = create_app(Config)
with app.app_context():
    initialize_daily_tasks()
    db.session.commit()
    from models.gameplay import DailyTask
    n = DailyTask.query.filter(DailyTask.description.like("مدرسة الحارة - يوم %")).count()
    total = DailyTask.query.filter_by(is_active=True).count()
    print(f"Seeded. Economy academy tasks: {n}/5, active daily tasks total: {total}")
