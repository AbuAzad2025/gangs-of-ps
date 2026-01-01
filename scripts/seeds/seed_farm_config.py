import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from factory import create_app
from extensions import db
from models.system import SystemConfig

app = create_app()

default_config = {
    "max_parallel_jobs": 1,
    "products": {
        "olive": {"item_name": "زيت زيتون بلدي"},
        "zaatar": {"item_name": "زعتر بلدي"},
        "soap": {"item_name": "صابون نابلسي"},
        "dates": {"item_name": "تمر أريحا"},
        "keffiyeh": {"item_name": "كوفية فلسطينية"},
        "pottery": {"item_name": "فخار الخليل"},
    },
    "requirements": {
        "olive": {"min_intelligence": 0},
        "zaatar": {"min_intelligence": 0},
        "dates": {"min_intelligence": 12},
        "soap": {"min_intelligence": 15},
        "pottery": {"min_intelligence": 18},
        "keffiyeh": {"min_intelligence": 25}
    },
    "tiers": {
        "t1": {
            "olive": {"diamonds": 1, "minutes": (6, 12), "out": (1, 2)},
            "zaatar": {"diamonds": 1, "minutes": (5, 10), "out": (1, 3)},
        },
        "t2": {
            "olive": {"diamonds": 2, "minutes": (8, 14), "out": (1, 3)},
            "zaatar": {"diamonds": 2, "minutes": (7, 12), "out": (2, 5)},
            "soap": {"diamonds": 3, "minutes": (12, 18), "out": (1, 2)},
        },
        "t3": {
            "olive": {"diamonds": 3, "minutes": (10, 18), "out": (2, 5)},
            "zaatar": {"diamonds": 3, "minutes": (9, 16), "out": (3, 7)},
            "soap": {"diamonds": 4, "minutes": (14, 22), "out": (2, 4)},
            "dates": {"diamonds": 5, "minutes": (16, 24), "out": (1, 3)},
        },
        "t4": {
            "olive": {"diamonds": 4, "minutes": (12, 20), "out": (3, 7)},
            "soap": {"diamonds": 6, "minutes": (18, 28), "out": (3, 6)},
            "dates": {"diamonds": 7, "minutes": (18, 28), "out": (2, 5)},
            "keffiyeh": {"diamonds": 8, "minutes": (22, 34), "out": (1, 2)},
        },
        "t5": {
            "olive": {"diamonds": 6, "minutes": (14, 26), "out": (5, 10)},
            "soap": {"diamonds": 10, "minutes": (22, 36), "out": (4, 8)},
            "dates": {"diamonds": 10, "minutes": (22, 36), "out": (4, 8)},
            "keffiyeh": {"diamonds": 12, "minutes": (28, 45), "out": (2, 4)},
            "pottery": {"diamonds": 12, "minutes": (28, 45), "out": (2, 4)},
        },
    },
    "boost": {
        "t1": {"cost_per_minute": 1, "min_cost": 1},
        "t2": {"cost_per_minute": 1, "min_cost": 2},
        "t3": {"cost_per_minute": 2, "min_cost": 3},
        "t4": {"cost_per_minute": 2, "min_cost": 4},
        "t5": {"cost_per_minute": 3, "min_cost": 5},
    }
}

with app.app_context():
    print("Seeding farm_config_json...")
    json_str = json.dumps(default_config, ensure_ascii=False)
    
    # Check current value
    curr = SystemConfig.query.filter_by(key="farm_config_json").first()
    if curr:
        print("Existing config found. Updating...")
        curr.value = json_str
    else:
        print("No existing config. Creating new...")
        new_conf = SystemConfig(key="farm_config_json", value=json_str, description="Farm Configuration")
        db.session.add(new_conf)
    
    try:
        db.session.commit()
        print("Successfully saved farm_config_json.")
    except Exception as e:
        db.session.rollback()
        print(f"Error saving config: {e}")
