import pytest


class TestAppFactory:
    def test_app_exists(self, app):
        assert app is not None

    def test_app_testing_mode(self, app):
        assert app.config.get('TESTING') is True

    def test_extensions_initialized(self, app):
        from extensions import db, login, babel
        assert db is not None
        assert login is not None
        assert babel is not None

    def test_blueprints_registered(self, app):
        blueprints = [bp.name for bp in app.blueprints.values()]
        assert 'main' in blueprints


class TestDatabaseIntegration:
    def test_db_uri_configured(self, app):
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        assert uri is not None

    def test_models_importable(self):
        from models import (
            User, UserRole, Crime, Item, Location, Gang, GangWar,
            Vehicle, Hostess, PaymentTransaction, CombatLog, ForumCategory,
            ForumTopic, ForumPost, MarketAsset, SystemConfig, Announcement
        )
        assert User is not None
        assert Crime is not None


class TestTemplateIntegration:
    def test_base_template_exists(self):
        from pathlib import Path
        path = Path(__file__).resolve().parents[2] / 'templates' / 'base.html'
        assert path.exists()

    def test_key_templates_exist(self):
        from pathlib import Path
        base = Path(__file__).resolve().parents[2] / 'templates'
        required = ['login.html', 'register.html', 'hara.html', 'crimes.html', 'profile.html']
        for t in required:
            assert (base / t).exists(), f"Missing template: {t}"
