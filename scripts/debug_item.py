import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from run import app
from models import Item

with app.app_context():
    item = db.session.get(Item, 20)
    if item:
        print(f"Item 20: {item.name}, {item.type}")
    else:
        print("Item 20 not found")
