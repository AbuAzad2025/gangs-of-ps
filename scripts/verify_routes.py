import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app

def verify_routes():
    app = create_app()
    with app.app_context():
        # Check if developer routes are registered
        routes = [rule.endpoint for rule in app.url_map.iter_rules()]
        required_routes = [
            'main.dev_dashboard',
            'main.dev_action',
            'main.dev_vehicles',
            'main.dev_vehicle_edit',
            'main.dev_items',
            'main.dev_item_edit',
            'main.dev_crimes',
            'main.dev_crime_edit',
            'main.dev_assets',
            'main.dev_asset_edit',
            'main.dev_tasks',
            'main.dev_task_edit',
            'main.dev_users',
            'main.dev_user_edit',
            'main.dev_logs',
            'main.dev_announcements',
            'main.dev_announcement_edit',
            'main.dev_announcement_delete'
        ]
        
        missing_routes = [r for r in required_routes if r not in routes]
        
        if missing_routes:
            print(f"Missing routes: {missing_routes}")
            return False
        
        print("All developer routes verified successfully.")
        return True

if __name__ == '__main__':
    if verify_routes():
        sys.exit(0)
    else:
        sys.exit(1)
