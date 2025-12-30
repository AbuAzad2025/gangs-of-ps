import os
import sys

# Add parent directory to path to import factory and extensions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
from models.hostess import Hostess
from utils.essentials import load_json_seed, initialize_hostesses

def verify():
    print("--- Starting Verification ---")
    
    # Ensure DB URL is set
    if not os.environ.get('DATABASE_URL'):
        os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/gangsofpalestine'
        print("Set default DATABASE_URL.")

    try:
        app = create_app()
        print("✓ App created successfully.")
    except Exception as e:
        print(f"✗ Failed to create app: {e}")
        return

    with app.app_context():
        # 1. Initialize Hostesses (Simulate app startup)
        print("\nChecking Hostesses...")
        try:
            # We don't want to run full initialization if it modifies DB destructively, 
            # but initialize_hostesses is idempotent (checks if exists).
            initialize_hostesses() 
            db.session.commit()
            print("✓ initialize_hostesses() ran.")
        except Exception as e:
            print(f"✗ Error running initialize_hostesses(): {e}")
            # Continue to check what we have

        # 2. Verify Hostesses in DB
        print("\nVerifying Hostesses in Database:")
        try:
            hostesses = Hostess.query.all()
            if not hostesses:
                print("✗ No hostesses found in database!")
            else:
                for h in hostesses:
                    print(f"  - {h.name} ({h.role}): Buff={h.buff_type}")
                    
                    # Check for specific correctness
                    if h.name == "ياسمين" and h.role != "greeter":
                            print("    ⚠️ Warning: Jasmin role mismatch (expected greeter)")
                    if h.name == "سارة" and h.buff_type != "hospital_recovery":
                            print("    ⚠️ Warning: Sarah buff mismatch (expected hospital_recovery)")
        except Exception as e:
            print(f"✗ Error querying hostesses: {e}")

        # 3. Verify Seed Files
        print("\nVerifying Seed Files in data/seeds:")
        seeds_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'seeds')
        seeds = ['locations.json', 'items.json', 'vehicles.json', 'basic_crimes.json', 'organized_crimes.json']
        for seed in seeds:
            path = os.path.join(seeds_dir, seed)
            if os.path.exists(path):
                try:
                    import json
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"  ✓ {seed}: Found and valid JSON ({len(data)} items)")
                except Exception as e:
                    print(f"  ✗ {seed}: Invalid JSON - {e}")
            else:
                print(f"  ✗ {seed}: File not found at {path}")

if __name__ == "__main__":
    verify()
