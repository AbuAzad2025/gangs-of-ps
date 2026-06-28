"""PostgreSQL session schema + per-test transaction isolation for pytest."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import scoped_session, sessionmaker


def collect_enum_type_names(db) -> list[str]:
    enum_types = []
    for table in db.metadata.sorted_tables:
        for column in table.columns:
            type_name = getattr(column.type, 'name', None)
            if type_name:
                enum_types.append(type_name)
    return list(set(enum_types))


def drop_enum_types(db, enum_types: list[str]) -> None:
    for enum_name in enum_types:
        try:
            db.session.execute(text(f'DROP TYPE IF EXISTS "{enum_name}" CASCADE'))
            db.session.commit()
        except Exception:
            db.session.rollback()


def install_per_test_transaction(db):
    """Bind scoped session to a rolled-back connection transaction.

    Uses SQLAlchemy savepoints so tests may call ``db.session.commit()`` without
    persisting rows after the test function completes.
    """
    connection = db.engine.connect()
    outer = connection.begin()

    db.session.close()
    db.session.remove()

    original_scoped = db.session
    factory = sessionmaker(
        bind=connection,
        join_transaction_mode='create_savepoint',
    )
    test_scoped = scoped_session(factory)
    db.session = test_scoped

    def teardown():
        test_scoped.remove()
        db.session = original_scoped
        original_scoped.remove()
        if not connection.closed:
            outer.rollback()
            connection.close()

    return teardown
