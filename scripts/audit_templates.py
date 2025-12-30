
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db, limiter
from models.user import User, UserRole
from models.hostess import Hostess
from flask import url_for
from utils.essentials import initialize_essentials
from config import TestConfig

def run_audit():
    app = create_app(TestConfig)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False
    
    # Force disable limiter
    if limiter:
        limiter.enabled = False

    with app.app_context():
        # Create tables
        db.create_all()
        
        # Load Essentials (Hostesses, Items, etc.)
        try:
            print("Loading essential data...")
            initialize_essentials(app)
        except Exception as e:
            print(f"Error loading essential data: {e}")

        # Create Normal User
        user = User.query.filter_by(username='AuditBot').first()
        if not user:
            user = User(username='AuditBot', email='audit@example.com', role=UserRole.USER)
            user.set_password('password123')
            user.is_verified = True
            db.session.add(user)
        
        # Create Dead User
        dead_user = User.query.filter_by(username='DeadBot').first()
        if not dead_user:
            dead_user = User(username='DeadBot', email='dead@example.com', role=UserRole.USER)
            dead_user.set_password('password123')
            dead_user.is_verified = True
            dead_user.health = 0 # Dead
            db.session.add(dead_user)

        # Create Admin User
        admin = User.query.filter_by(username='AdminBot').first()
        if not admin:
            admin = User(username='AdminBot', email='admin@example.com', role=UserRole.DEVELOPER)
            admin.set_password('password123')
            admin.is_verified = True
            db.session.add(admin)
        
        db.session.commit()

        hostess = Hostess.query.first()
        hostess_id = hostess.id if hostess else 1

        client = app.test_client()

        print("=== Starting Template Audit V3 ===")
        
        # 1. Anonymous Routes
        print("\n--- Checking Anonymous Routes ---")
        anon_routes = [
            ('/', 'Gangs of Palestine'),
            ('/login', 'تسجيل الدخول'),
            ('/register', 'إنشاء حساب جديد'),
        ]
        
        for route, keyword in anon_routes:
            resp = client.get(route, follow_redirects=True)
            content = resp.data.decode('utf-8')
            if resp.status_code == 200 and keyword in content:
                print(f"✅ {route.ljust(25)} | OK")
            else:
                print(f"❌ {route.ljust(25)} | FAIL (Status: {resp.status_code})")
                if resp.status_code != 200:
                    print(f"   Error: Status {resp.status_code}")
                elif keyword not in content:
                    print(f"   Missing Keyword: '{keyword}'")

        # 2. Login as Normal User
        print("\n--- Logging in as AuditBot (User) ---")
        client.post('/login', data={'username': 'AuditBot', 'password': 'password123'}, follow_redirects=True)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

        # 3. User Protected Routes
        print("\n--- Checking User Routes ---")
        user_routes = [
            ('/market/', 'Market'), 
            ('/gym/', 'الجيم'),
            ('/hospital/', 'المستشفى'),
            ('/bank/', 'البنك'),
            ('/gang/', 'العصابة'), 
            ('/casino/', 'الكازينو'),
            ('/travel/', 'السفر'),
            ('/inventory/', 'المخزون'),
            ('/combat/', 'قتال'), 
            ('/garage', 'الكراج'), 
            ('/jail/', 'السجن'),
            ('/forum/', 'المنتدى'),
            ('/news/', 'الأخبار'),
            ('/bounties/', 'المطلوبين'), 
            ('/leaderboard', 'لوحة المتصدرين'), # Fixed: Keyword
            ('/search', 'بحث'), 
            (f'/profile/{user.id}', 'الملف الشخصي'), # Fixed: Dynamic Route
            ('/messages', 'الرسائل'),
            ('/economy/properties', 'properties-header'), # Fixed: Keyword
            # Sub-pages
            ('/casino/roulette', 'روليت'),
            ('/casino/blackjack', 'بلاك جاك'),
            ('/casino/slots', 'ماكينات الحظ'), 
            ('/casino/racing/', 'سباق'),
        ]

        for route, keyword in user_routes:
            try:
                resp = client.get(route, follow_redirects=True)
                content = resp.data.decode('utf-8')
                
                status_ok = resp.status_code == 200
                keyword_found = keyword in content
                
                # Dynamic checks
                if route == '/gang/' and 'إنشاء عصابة' in content: keyword_found = True
                
                if status_ok and keyword_found:
                    print(f"✅ {route.ljust(25)} | OK")
                else:
                    print(f"❌ {route.ljust(25)} | FAIL")
                    if not status_ok:
                        print(f"   Status: {resp.status_code}")
                    if not keyword_found:
                        print(f"   Missing: {keyword}")
            except Exception as e:
                print(f"❌ {route.ljust(25)} | EXCEPTION: {e}")

        # 4. Graveyard Check (Dead User)
        print("\n--- Logging in as DeadBot (Graveyard Check) ---")
        client.get('/logout', follow_redirects=True)
        client.post('/login', data={'username': 'DeadBot', 'password': 'password123'}, follow_redirects=True)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(dead_user.id)
            sess['_fresh'] = True
        
        resp = client.get('/graveyard/', follow_redirects=True)
        content = resp.data.decode('utf-8')
        if resp.status_code == 200 and 'graveyard-bg' in content: # Fixed: Keyword
            print(f"✅ {'/graveyard/'.ljust(25)} | OK")
        else:
             print(f"❌ {'/graveyard/'.ljust(25)} | FAIL")
             if 'graveyard-bg' not in content:
                 print("   Missing: graveyard-bg")

        # 5. Login as Admin
        print("\n--- Logging in as AdminBot (Developer) ---")
        client.get('/logout', follow_redirects=True)
        client.post('/login', data={'username': 'AdminBot', 'password': 'password123'}, follow_redirects=True)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        # 6. Developer Routes
        print("\n--- Checking Developer Routes ---")
        dev_routes = [
            ('/developer', 'لوحة التحكم'),
            ('/developer/users', 'المستخدمين'),
            ('/developer/settings', 'الإعدادات'),
            ('/developer/logs', 'Sentry'),
            ('/developer/announcements', 'إدارة الإعلانات'), 
            ('/developer/items', 'إدارة العناصر'),
            ('/developer/crimes', 'إدارة الجرائم'),
            ('/developer/locations', 'إدارة المناطق'),
            ('/developer/hostesses', 'إدارة المضيفات'),
            (f'/developer/hostess/trainer/{hostess_id}', 'لوحة التدريب'),
            ('/developer/achievements', 'الإنجازات'),
            ('/developer/gangs', 'إدارة العصابات'),
        ]

        for route, keyword in dev_routes:
            try:
                resp = client.get(route, follow_redirects=True)
                content = resp.data.decode('utf-8')
                
                if resp.status_code == 200: 
                    if keyword in content or 'Admin' in content or 'Developer' in content:
                        print(f"✅ {route.ljust(25)} | OK")
                        
                        # Extra check for hostesses
                        if route == '/developer/hostesses':
                            # Check for Arabic names as defined in profile.json
                            hostesses = ['ياسمين', 'ليلى', 'سارة', 'روبي']
                            found_hostesses = [h for h in hostesses if h in content]
                            if found_hostesses:
                                print(f"   Found Hostesses: {', '.join(found_hostesses)}")
                            else:
                                print(f"   ⚠️ No hostesses found in content (might be empty DB or pagination)")
                    else:
                        print(f"⚠️ {route.ljust(25)} | WARNING: Keyword '{keyword}' missing, but 200 OK")
                else:
                    print(f"❌ {route.ljust(25)} | FAIL (Status: {resp.status_code})")
            except Exception as e:
                print(f"❌ {route.ljust(25)} | EXCEPTION: {e}")

if __name__ == "__main__":
    run_audit()
