import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from extensions import db, limiter
from models import User, Hostess
from models.user import UserRole


def run_audit():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False

    if limiter:
        limiter.enabled = False

    with app.app_context():
        user = User.query.filter_by(username='SmokeBot').first()
        if not user:
            user = User(username='SmokeBot', email='smoke@example.com', role=UserRole.USER)
            user.set_password('password123')
            user.is_verified = True
            db.session.add(user)

        dev = User.query.filter_by(username='SmokeDev').first()
        if not dev:
            dev = User(username='SmokeDev', email='smokedev@example.com', role=UserRole.DEVELOPER)
            dev.set_password('password123')
            dev.is_verified = True
            db.session.add(dev)

        db.session.commit()

        hostess = Hostess.query.first()
        hostess_id = hostess.id if hostess else 1

        client = app.test_client()

        def check(route, keyword=None, follow=True):
            resp = client.get(route, follow_redirects=follow)
            ok = resp.status_code == 200
            if keyword:
                ok = ok and (keyword in resp.data.decode('utf-8'))
            print(("✅" if ok else "❌"), route, resp.status_code)
            return ok

        print("=== Live Route Audit (PostgreSQL) ===")

        check('/', 'Gangs of Palestine')
        check('/login', 'تسجيل الدخول')
        check('/register', 'إنشاء حساب جديد')

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

        user_routes = [
            '/market/',
            '/gym/',
            '/hospital/',
            '/bank/',
            '/gang/',
            '/casino/',
            '/travel/',
            '/inventory/',
            '/combat/',
            '/garage',
            '/jail/',
            '/forum/',
            '/news/',
            '/bounties/',
            '/leaderboard',
            '/search',
            f'/profile/{user.id}',
            '/messages',
            '/economy/properties',
            '/casino/roulette',
            '/casino/blackjack',
            '/casino/slots',
            '/casino/racing/',
        ]
        for r in user_routes:
            check(r, None)

        client.get('/logout', follow_redirects=True)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(dev.id)
            sess['_fresh'] = True

        dev_routes = [
            '/developer',
            '/developer/users',
            '/developer/settings',
            '/developer/announcements',
            '/developer/items',
            '/developer/crimes',
            '/developer/locations',
            '/developer/hostesses',
            f'/developer/hostess/trainer/{hostess_id}',
            '/developer/achievements',
            '/developer/gangs',
        ]
        for r in dev_routes:
            check(r, None)


if __name__ == "__main__":
    run_audit()

