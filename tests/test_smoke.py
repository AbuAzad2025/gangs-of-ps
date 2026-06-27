"""Smoke test — verify app factory and basic imports work."""
import pytest


def test_app_factory(app):
    assert app is not None
    assert app.testing is True


def test_import_core_modules():
    from models import User, Crime, Item, Gang, Location
    assert all([User, Crime, Item, Gang, Location])


def test_extensions_loaded(app):
    from extensions import db, login, babel, csrf
    assert all([db, login, babel, csrf])
