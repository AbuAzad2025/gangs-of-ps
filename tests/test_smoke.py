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


def test_game_defaults_are_initialized(app):
    from models.system import SystemConfig
    assert SystemConfig.get_value('game_name', 'عصابات فلسطين') == 'عصابات فلسطين'
    assert SystemConfig.get_value('game_status', 'online') == 'online'
    assert SystemConfig.get_value('organized_crimes_enabled', 'true') in {'true', 'false'}


def test_game_overview_endpoint(client):
    response = client.get('/api/game/overview')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'game_name' in payload
    assert 'support_email' in payload
    assert payload['support_email']
    assert 'players' in payload
    assert 'season' in payload


def test_game_stats_page_requires_login(client):
    response = client.get('/game-stats', follow_redirects=False)
    assert response.status_code == 302


def test_game_stats_page_renders_for_logged_in_user(logged_in_client):
    response = logged_in_client.get('/game-stats')
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'لوحة إحصائيات اللعبة' in page or 'Game Stats' in page


def test_health_endpoint(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] in {'ok', 'error'}
    assert payload['database'] in {'ok', 'unavailable'}
    assert 'app_name' in payload
    assert 'app_version' in payload
