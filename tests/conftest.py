import os
import sys
import pytest

os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('WTF_CSRF_ENABLED', 'False')
os.environ.setdefault('USE_TEST_DB', '1')


@pytest.fixture(scope='function')
def app():
    from config import TestConfig
    from factory import create_app

    class TestConfigLocal(TestConfig):
        SQLALCHEMY_DATABASE_URI = os.environ.get(
            'TEST_DATABASE_URL',
            'sqlite:///:memory:'
        )
        SQLALCHEMY_ENGINE_OPTIONS = {}
        TESTING = True
        WTF_CSRF_ENABLED = False
        RATELIMIT_ENABLED = False

    application = create_app(TestConfigLocal)

    with application.app_context():
        from extensions import db
        from sqlalchemy import text

        enum_types = [
            c.type.name for t in db.metadata.sorted_tables
            for c in t.columns
            if hasattr(c.type, 'name') and c.type.name
        ]

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()

        for et in set(enum_types):
            try:
                db.session.execute(text(f'DROP TYPE IF EXISTS "{et}" CASCADE'))
                db.session.commit()
            except Exception:
                db.session.rollback()


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    from extensions import db as _db
    with app.app_context():
        yield _db
        _db.session.rollback()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def new_user(app, db):
    from models.user import User
    user = User(
        username='testplayer',
        email='test@example.com',
        is_verified=True,
    )
    user.set_password('password123')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def logged_in_client(client, new_user, app):
    with client:
        with app.app_context():
            from models.user import User
            from extensions import db
            from flask_login import login_user
            user = db.session.get(User, new_user.id)
            login_user(user, remember=True)
            db.session.commit()
    return client
