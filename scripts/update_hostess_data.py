import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from models import Hostess, HostessKnowledge
from extensions import db

app = create_app()

with app.app_context():
    # 1. Update Jasmin
    jasmin = Hostess.query.filter(Hostess.name.ilike('%Jasmin%')).first()
    if jasmin:
        jasmin.is_public = True
        jasmin.min_rank = 0 # No rank needed for concierge
        print(f"Updated Jasmin: is_public={jasmin.is_public}")

    # 2. Update others
    # Layla (Spy) - Mid tier
    layla = Hostess.query.filter(Hostess.name.ilike('%Layla%')).first()
    if layla:
        layla.min_rank = 5 # Rank 5 (e.g., Lieutenant)
        layla.price = 50000 # Expensive
        print(f"Updated Layla: min_rank={layla.min_rank}")

    # Ruby (Luck) - High tier
    ruby = Hostess.query.filter(Hostess.name.ilike('%Ruby%')).first()
    if ruby:
        ruby.min_rank = 3
        ruby.price = 25000
        print(f"Updated Ruby: min_rank={ruby.min_rank}")

    # Sarah (Support) - Low tier
    sarah = Hostess.query.filter(Hostess.name.ilike('%Sarah%')).first()
    if sarah:
        sarah.min_rank = 1
        sarah.price = 5000
        print(f"Updated Sarah: min_rank={sarah.min_rank}")

    db.session.commit()
    print("Hostess data updated.")
