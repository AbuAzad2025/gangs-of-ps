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
        user = User.query.filter_by(username='PostBot').first()
        if not user:
            user = User(username='PostBot', email='postbot@example.com', role=UserRole.USER)
            user.set_password('password123')
            user.is_verified = True
            db.session.add(user)

        db.session.commit()

        hostess = Hostess.query.filter_by(role='greeter').first() or Hostess.query.first()
        hostess_id = hostess.id if hostess else None

        client = app.test_client()

        def ok_status(resp):
            return resp.status_code < 500

        def post_form(path, data=None):
            resp = client.post(path, data=(data or {}), follow_redirects=False)
            print(("✅" if ok_status(resp) else "❌"), "POST", path, resp.status_code)
            return ok_status(resp)

        def post_json(path, payload=None):
            resp = client.post(path, json=(payload or {}), follow_redirects=False)
            print(("✅" if ok_status(resp) else "❌"), "POST", path, resp.status_code)
            return ok_status(resp)

        print("=== Live POST Audit (PostgreSQL) ===")

        post_form('/login', data={'username': 'nope', 'password': 'wrong'})
        post_form('/register', data={'username': 'x', 'email': 'x@x.com', 'password': 'x', 'captcha': 'WRONG'})

        post_json('/api/public/chat', payload={'message': 'مرحبا', 'history': [], 'hostess_id': hostess_id})

        post_form('/hostesses/jasmin/chat', data={'message': 'مرحبا'})
        post_form('/hostesses/layla/chat', data={'message': 'مرحبا'})
        post_form('/hostesses/ruby/chat', data={'message': 'مرحبا'})
        post_form('/hostesses/sarah/chat', data={'message': 'مرحبا'})

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

        post_form('/logout', data={})

        post_form('/casino/hostess/chat', data={'message': 'مرحبا'})


if __name__ == "__main__":
    run_audit()

