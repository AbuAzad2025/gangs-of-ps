import json
from models.gameplay import Crime
from extensions import db
from factory import create_app
import os
import sys
sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..')))


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
                app.logger.info(
                    f"Updated {
                        crime.name} cooldown to {
                        crime.cooldown}")

        db.session.commit()
        app.logger.info(f"Successfully updated {updated_count} crimes.")


if __name__ == "__main__":
    update_crimes()
