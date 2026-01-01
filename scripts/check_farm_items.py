import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from factory import create_app
from extensions import db
from models import Item, SystemConfig

app = create_app()

with app.app_context():
    print("Checking Farm Configuration and Items...")
    
    # Check SystemConfig
    config_value = SystemConfig.get_value("farm_config_json")
    print(f"SystemConfig 'farm_config_json': {config_value}")
    if config_value:
        print(f"Length: {len(config_value)}")
    
    # Check Items expected by default config
    expected_items = [
        "زيت زيتون بلدي",
        "زعتر بلدي",
        "صابون نابلسي",
        "تمر أريحا",
        "كوفية فلسطينية",
        "فخار الخليل"
    ]
    
    missing_items = []
    for name in expected_items:
        item = Item.query.filter_by(name=name).first()
        if item:
            print(f"Item found: {name} (ID: {item.id}, Image: {item.image})")
        else:
            print(f"Item MISSING: {name}")
            missing_items.append(name)
            
    if missing_items:
        print(f"\nTotal missing items: {len(missing_items)}")
    else:
        print("\nAll items found.")
