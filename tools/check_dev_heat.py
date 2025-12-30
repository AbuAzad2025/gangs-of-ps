import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from factory import create_app
from extensions import db
from models import User, UserRole


def main():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)

    with app.app_context():
        user = User.query.filter_by(username="Azad").first()
        if not user:
            user = User(username="Azad", email="azad@master.key")
            user.set_password("x")
            db.session.add(user)
            db.session.commit()

        user.role = UserRole.DEVELOPER
        user.is_verified = True
        db.session.commit()
        uid = user.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True

    resp = client.get("/developer/heat")
    print("status", resp.status_code)
    print(resp.data[:800])


if __name__ == "__main__":
    main()

