
import os
import sys
import json
import requests
from flask import Flask, url_for

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db
from models import Item, Vehicle, Location, Crime, OrganizedCrime, Hostess, User, MarketAsset

def load_seed(filename):
    path = os.path.join(os.getcwd(), 'data', 'seeds', filename)
    if not os.path.exists(path):
        print(f"❌ Seed file missing: {path}")
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error parsing {filename}: {e}")
        return []

def audit_static_files(app):
    print("\n--- Auditing Static Files ---")
    static_folder = app.static_folder
    
    # 1. AdminLTE
    adminlte_css = os.path.join(static_folder, 'adminlte', 'css', 'adminlte.min.css')
    adminlte_js = os.path.join(static_folder, 'adminlte', 'js', 'adminlte.min.js')
    
    if os.path.exists(adminlte_css):
        print(f"✅ AdminLTE CSS found: {adminlte_css}")
    else:
        print(f"❌ AdminLTE CSS MISSING: {adminlte_css}")

    if os.path.exists(adminlte_js):
        print(f"✅ AdminLTE JS found: {adminlte_js}")
    else:
        print(f"❌ AdminLTE JS MISSING: {adminlte_js}")

    # 2. Hostess Videos
    videos_dir = os.path.join(static_folder, 'videos', 'hostesses')
    if os.path.exists(videos_dir):
        videos = [f for f in os.listdir(videos_dir) if f.endswith('.mp4')]
        print(f"✅ Found {len(videos)} Hostess Videos in {videos_dir}")
        for v in videos:
            print(f"   - {v}")
    else:
        print(f"❌ Hostess Videos Directory MISSING: {videos_dir}")

    # 3. Location Images
    loc_dir = os.path.join(static_folder, 'locations')
    if os.path.exists(loc_dir):
        images = [f for f in os.listdir(loc_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        print(f"✅ Found {len(images)} Location Images")
    else:
        print(f"❌ Location Images Directory MISSING: {loc_dir}")

def audit_items(app):
    print("\n--- Auditing Items ---")
    seeds = load_seed('items.json')
    with app.app_context():
        db_items = Item.query.all()
        db_names = {i.name for i in db_items}
        
        for s in seeds:
            if s['name'] not in db_names:
                print(f"❌ Item missing in DB: {s['name']}")
        
        print(f"✅ Verified {len(seeds)} items against DB.")

def audit_vehicles(app):
    print("\n--- Auditing Vehicles ---")
    seeds = load_seed('vehicles.json')
    with app.app_context():
        db_vehicles = Vehicle.query.all()
        db_names = {v.name for v in db_vehicles}
        
        for s in seeds:
            if s['name'] not in db_names:
                print(f"❌ Vehicle missing in DB: {s['name']}")
        
        print(f"✅ Verified {len(seeds)} vehicles against DB.")

def audit_locations(app):
    print("\n--- Auditing Locations ---")
    seeds = load_seed('locations.json')
    static_loc_dir = os.path.join(app.static_folder, 'locations')
    
    with app.app_context():
        db_locs = Location.query.all()
        db_names = {l.name for l in db_locs}
        
        for s in seeds:
            if s['name'] not in db_names:
                print(f"❌ Location missing in DB: {s['name']}")
            
            # Check Image
            img_name = s.get('image')
            if img_name:
                img_path = os.path.join(static_loc_dir, img_name)
                if not os.path.exists(img_path):
                    print(f"❌ Location Image MISSING: {img_name} (for {s['name']})")
                else:
                    # print(f"✅ Found image for {s['name']}")
                    pass
        
        print(f"✅ Verified {len(seeds)} locations against DB and Filesystem.")

def ensure_audit_user(app):
    with app.app_context():
        user = User.query.filter_by(username='AuditBot').first()
        if not user:
            print("Creating AuditBot user...")
            user = User(username='AuditBot', email='audit@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
        else:
            user.set_password('password')
            db.session.commit()

def audit_content_integration(app):
    """
    Checks if seeded content actually appears in the rendered pages.
    """
    print("\n--- Auditing Content Integration (Page Scans) ---")
    
    ensure_audit_user(app)
    
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    client = app.test_client()
    
    with client:
        # Login
        login_resp = client.post('/login', data={'username': 'AuditBot', 'password': 'password'}, follow_redirects=True)
        if login_resp.status_code != 200:
            print(f"❌ Login Failed: {login_resp.status_code}")
            return

        # 1. Check Black Market for Items (Weapons/Armor)
        print(">> Scanning Black Market for Items...")
        resp = client.get('/black_market/')
        if resp.status_code == 200:
            content = resp.data.decode('utf-8')
            items = load_seed('items.json')
            found = 0
            for item in items:
                if item['name'] in content:
                    found += 1
            print(f"   Found {found}/{len(items)} items on Black Market Page.")
            if found == 0:
                print("   ⚠️ WARNING: No items found. Check 'is_black_market' flags.")
        else:
            print(f"   ❌ Black Market Page Failed: {resp.status_code}")

        # 2. Check Dealership for Vehicles
        print(">> Scanning Dealership for Vehicles...")
        resp = client.get('/market/dealership') # Route is in market blueprint? No, checked garage.py -> bp name 'garage' but url_prefix might be different?
        # Re-checking garage.py: bp = Blueprint('garage', __name__) -> NO url_prefix specified in snippet?
        # Wait, usually blueprints have url_prefix in __init__ or app registration.
        # Let's try /dealership directly first, or /garage/dealership
        
        # Checking route registration in garage.py again...
        # bp = Blueprint('garage', __name__) -> No prefix in file.
        # Likely registered in app with prefix or root.
        # Assuming '/dealership' based on route decorator @bp.route('/dealership')
        
        resp = client.get('/dealership') 
        if resp.status_code == 404:
             resp = client.get('/garage/dealership')
        
        if resp.status_code == 200:
            content = resp.data.decode('utf-8')
            vehicles = load_seed('vehicles.json')
            found = 0
            for v in vehicles:
                if v['name'] in content:
                    found += 1
            print(f"   Found {found}/{len(vehicles)} vehicles on Dealership Page.")
        else:
            print(f"   ❌ Dealership Page Failed: {resp.status_code}")
            
        # 3. Check Travel for Locations
        print(">> Scanning Travel for Locations...")
        resp = client.get('/travel/')
        if resp.status_code == 200:
            content = resp.data.decode('utf-8')
            locs = load_seed('locations.json')
            found = 0
            for l in locs:
                if l['name'] in content:
                    found += 1
            print(f"   Found {found}/{len(locs)} locations on Travel Page.")
        else:
            print(f"   ❌ Travel Page Failed: {resp.status_code}")

        # 4. Check Financial Market
        print(">> Scanning Financial Market...")
        resp = client.get('/market/')
        if resp.status_code == 200:
            content = resp.data.decode('utf-8')
            # Check for generic asset names like "Bitcoin", "Apple", "Gold"
            assets = ["Bitcoin", "Apple", "Gold", "NVIDIA", "Tesla"]
            found = 0
            for a in assets:
                if a in content:
                    found += 1
            print(f"   Found {found}/{len(assets)} key assets on Market Page.")
        else:
            print(f"   ❌ Financial Market Page Failed: {resp.status_code}")

if __name__ == '__main__':
    app = create_app()
    audit_static_files(app)
    audit_items(app)
    audit_vehicles(app)
    audit_locations(app)
    audit_content_integration(app)
