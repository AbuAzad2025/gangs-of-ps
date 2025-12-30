import os
import sys

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from flask import url_for

def check_endpoints():
    print("--- Checking Flask Endpoints ---")
    
    # Ensure DB URL is set for app creation
    if not os.environ.get('DATABASE_URL'):
        os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/gangsofpalestine'

    try:
        app = create_app()
    except Exception as e:
        print(f"CRITICAL: Failed to create app. This usually means a Blueprint conflict or Import error.\nError: {e}")
        return

    print("✓ App created successfully. Listing routes...\n")
    
    routes = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods))
        routes.append((rule.endpoint, methods, str(rule)))

    # Sort by endpoint name
    routes.sort(key=lambda x: x[0])

    print(f"{'Endpoint':<40} | {'Methods':<30} | {'Rule'}")
    print("-" * 100)
    
    error_count = 0
    warning_count = 0
    
    # Define all expected blueprints based on factory.py registration
    expected_blueprints = [
        'main',         # routes/__init__.py
        'gang',         # routes/gang.py
        'combat',       # routes/combat.py
        'gym',          # routes/gym.py
        'bank',         # routes/bank.py
        'hospital',     # routes/hospital.py
        'jail',         # routes/jail.py
        'market',       # routes/market.py
        'police_chase', # routes/police_chase.py
        'travel',       # routes/travel.py
        'bounties',     # routes/bounties.py
        'casino',       # routes/casino.py
        'black_market', # routes/black_market.py
        'news',         # routes/news.py
        'forum',        # routes/forum.py
        'economy',      # routes/economy.py
        'inventory',    # routes/inventory.py
        'graveyard',    # routes/graveyard.py
        'racing',       # routes/racing.py
        'jasmin',       # routes/hostesses/jasmin.py
        'layla',        # routes/hostesses/layla.py
        'sarah',        # routes/hostesses/sarah.py
        'ruby'          # routes/hostesses/ruby.py
    ]
    
    found_blueprints = {bp: False for bp in expected_blueprints}

    for endpoint, methods, rule in routes:
        # Check against expected blueprints
        # Endpoint format is usually "blueprint_name.function_name"
        if '.' in endpoint:
            bp_name = endpoint.split('.')[0]
            if bp_name in found_blueprints:
                found_blueprints[bp_name] = True

    print("-" * 100)
    print("\n--- Comprehensive Blueprint Verification Report ---")
    
    all_passed = True
    
    # Verify all expected blueprints are present
    print(f"{'Blueprint':<20} | {'Status':<10}")
    print("-" * 35)
    
    for bp in sorted(expected_blueprints):
        status = "✅ FOUND" if found_blueprints[bp] else "❌ MISSING"
        print(f"{bp:<20} | {status}")
        if not found_blueprints[bp]:
            all_passed = False
            error_count += 1

    print("-" * 35)
            
    print(f"\nTotal Registered Routes: {len(routes)}")
    if all_passed and error_count == 0:
        print("\n✅ SUCCESS: All expected system blueprints are correctly registered and active.")
        print("   The system structure reorganization has NOT broken any core route registrations.")
    else:
        print(f"\n⚠️ WARNING: {error_count} expected blueprints are missing!")

if __name__ == "__main__":
    check_endpoints()
