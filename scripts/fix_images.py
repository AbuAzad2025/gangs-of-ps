import os
import sys

# Add parent directory to path to import factory and extensions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
from models.location import Location

if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/gangsofpalestine'

app = create_app()

def fix_locations():
    with app.app_context():
        locations = Location.query.all()
        count = 0
        for loc in locations:
            # Check if image is just a filename (no slash) and exists in static/images/locations
            if loc.image and '/' not in loc.image:
                possible_path = os.path.join(app.root_path, 'static', 'images', 'locations', loc.image)
                if os.path.exists(possible_path):
                    print(f"Fixing location {loc.name}: {loc.image} -> locations/{loc.image}")
                    loc.image = f"locations/{loc.image}"
                    count += 1
                elif loc.image == 'default_city.jpg':
                     # Special case for default, fix it anyway even if file missing
                     print(f"Fixing location {loc.name}: {loc.image} -> locations/{loc.image}")
                     loc.image = f"locations/{loc.image}"
                     count += 1
        
        if count > 0:
            db.session.commit()
            print(f"Updated {count} locations.")
        else:
            print("No locations needed updating.")

if __name__ == "__main__":
    fix_locations()
