"""Pytest configuration and shared fixtures.

When ``RUN_WITH_REAL_DB=true``, tests run against the URL in ``DATABASE_URL``
with session-scoped schema creation and function-scoped transaction rollback
for isolation. Otherwise the legacy per-test SQLite/in-memory path is used.
"""
from __future__ import annotations

import os
import pytest

os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('WTF_CSRF_ENABLED', 'False')
os.environ.setdefault('USE_TEST_DB', '1')

RUN_WITH_REAL_DB = os.environ.get('RUN_WITH_REAL_DB', '').lower() in (
    'true', '1', 'yes')


def _resolve_database_uri() -> str:
    if RUN_WITH_REAL_DB:
        url = os.environ.get('DATABASE_URL')
        if not url:
            raise RuntimeError(
                'RUN_WITH_REAL_DB is set but DATABASE_URL is missing.')
        if not url.startswith('postgresql://'):
            raise RuntimeError(
                'DATABASE_URL must be postgresql:// when RUN_WITH_REAL_DB is set.')
        return url
    return os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')


def _build_test_config():
    from config import TestConfig

    db_uri = _resolve_database_uri()

    class TestConfigLocal(TestConfig):
        SQLALCHEMY_DATABASE_URI = db_uri
        # Let factory.py apply NullPool + search_path when TESTING + PostgreSQL.
        SQLALCHEMY_ENGINE_OPTIONS = {}
        TESTING = True
        WTF_CSRF_ENABLED = False
        RATELIMIT_ENABLED = False

    return TestConfigLocal


@pytest.fixture(scope='session')
def _real_db_session_app():
    """Create schema once per session when using live PostgreSQL."""
    if not RUN_WITH_REAL_DB:
        yield None
        return

    from factory import create_app
    from extensions import db
    from tests.support.postgres_session import (
        collect_enum_type_names,
        drop_enum_types,
    )

    application = create_app(_build_test_config())
    enum_types: list[str] = []

    with application.app_context():
        enum_types = collect_enum_type_names(db)
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()
        drop_enum_types(db, enum_types)


@pytest.fixture(scope='function', autouse=True)
def _isolate_real_db_transaction(_real_db_session_app):
    """Wrap each test in a rolled-back SQL transaction on live PostgreSQL."""
    if not RUN_WITH_REAL_DB or _real_db_session_app is None:
        yield
        return

    from extensions import db
    from tests.support.postgres_session import install_per_test_transaction

    app = _real_db_session_app
    with app.app_context():
        teardown = install_per_test_transaction(db)
        try:
            yield
        finally:
            teardown()


@pytest.fixture(scope='function')
def app(_real_db_session_app):
    if RUN_WITH_REAL_DB:
        assert _real_db_session_app is not None
        yield _real_db_session_app
        return

    from extensions import db
    from factory import create_app
    from sqlalchemy import text
    from tests.support.postgres_session import (
        collect_enum_type_names,
        drop_enum_types,
    )

    application = create_app(_build_test_config())

    with application.app_context():
        enum_types = collect_enum_type_names(db)
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
        drop_enum_types(db, enum_types)


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    from extensions import db as _db
    with app.app_context():
        yield _db
        if not RUN_WITH_REAL_DB:
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
    db.session.flush()
    user_id = int(user.id)
    db.session.commit()

    class _TestPlayer:
        id = user_id
        username = 'testplayer'

    return _TestPlayer()


@pytest.fixture
def auth_user_id(new_user):
    """Stable user id before HTTP requests expire ORM instances."""
    return int(new_user.id)


@pytest.fixture
def logged_in_client(client, new_user, app):
    from tests.support.client_helpers import login_client
    login_client(client, app, new_user)
    return client


@pytest.fixture
def login_as(client, app):
    from tests.support.client_helpers import login_client

    def _login(user):
        return login_client(client, app, user)

    return _login


@pytest.fixture
def admin_user(app, db):
    from tests.support.factories import make_admin
    return make_admin(db, username='admintest')


@pytest.fixture
def moderator_user(app, db):
    from tests.support.factories import make_moderator
    return make_moderator(db, username='modtest')


@pytest.fixture
def developer_user(app, db):
    from tests.support.factories import make_developer
    return make_developer(db, username='devtest')


@pytest.fixture
def rich_user(app, db):
    from tests.support.factories import make_user
    return make_user(db, username='richplayer', money=500_000, bank_balance=100_000, diamonds=50)
