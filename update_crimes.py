from factory import create_app
from extensions import db
from models.gameplay import Crime
import json
import os

app = create_app()

def update_crimes():
    with app.app_context():
        # Load seeds
        seed_path = os.path.join('data', 'seeds', 'basic_crimes.json')
        with open(seed_path, 'r', encoding='utf-8') as f:
            crimes_data = json.load(f)
        
        updated_count = 0
        for data in crimes_data:
            crime = Crime.query.filter_by(name=data['name']).first()
            if crime:
                crime.cooldown = data['cooldown']
                updated_count += 1
                print(f"Updated {crime.name} cooldown to {crime.cooldown}")
        
        db.session.commit()
        print(f"Successfully updated {updated_count} crimes.")

if __name__ == "__main__":
    update_crimes()
