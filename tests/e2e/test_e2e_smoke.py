"""End-to-end smoke flows for the public game experience and template interactions."""

from __future__ import annotations

import subprocess
from pathlib import Path

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[2]
JS_DIR = ROOT / 'static' / 'js'
TEMPLATE_DIR = ROOT / 'templates'


@pytest.mark.e2e
def test_public_game_journey(client):
    """Exercise the public-facing flow from landing page to authenticated dashboard."""
    landing = client.get('/')
    assert landing.status_code in (200, 302)

    login_page = client.get('/login')
    assert login_page.status_code == 200

    username = 'e2e_player_01'
    password = 'StrongPass123!'
    register = client.post(
        '/register',
        data={
            'username': username,
            'email': f'{username}@example.com',
            'password': password,
            'confirm_password': password,
        },
        follow_redirects=True,
    )
    assert register.status_code == 200

    login = client.post(
        '/login',
        data={
            'username': username,
            'password': password,
            'submit': 'Login',
        },
        follow_redirects=True,
    )
    assert login.status_code == 200

    overview = client.get('/api/game/overview')
    assert overview.status_code == 200
    payload = overview.get_json()
    assert payload['game_name']
    assert payload['players'] is not None

    dashboard = client.get('/hara', follow_redirects=True)
    assert dashboard.status_code in (200, 302)

    health = client.get('/api/health')
    assert health.status_code == 200
    assert health.get_json()['status'] in {'ok', 'error'}


@pytest.mark.e2e
def test_auth_templates_expose_key_fields(client):
    """Ensure the public auth templates render the expected form widgets and inputs."""
    checks = {
        '/login': ['username', 'password', 'submit'],
        '/register': ['username', 'birthdate', 'playstyle', 'confirm_password', 'togglePasswordVisibility'],
    }

    for path, required in checks.items():
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        for token in required:
            assert token in html, f'{path} is missing expected field or interactive hook: {token}'

        if path == '/register':
            assert 'captcha' in html or 'captchaImage' in html


@pytest.mark.e2e
def test_base_template_includes_frontend_assets(client):
    """Ensure the main template loads the visual and theme assets used by the game UI."""
    response = client.get('/')
    assert response.status_code in (200, 302)

    html = response.get_data(as_text=True)
    assert 'gop-visual.js' in html
    assert 'game-flash-meta' in html
    assert 'palestine_luxury.css' in html
    assert 'adminlte.min.css' in html


@pytest.mark.e2e
def test_frontend_template_inventory_is_100_percent_valid():
    """Compile every HTML template under templates/ to enforce a 100% frontend template gate."""
    templates = sorted(TEMPLATE_DIR.rglob('*.html'))
    assert templates, 'No HTML templates were found in the project'

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)

    def number_format(value):
        try:
            return '{:,}'.format(value)
        except (TypeError, ValueError):
            return value

    def safe_message_html(value):
        if value is None:
            return ''
        value = str(value)
        if '<' not in value and '>' not in value:
            return value
        from bs4 import BeautifulSoup
        from markupsafe import Markup

        allowed_tags = {'a', 'b', 'br', 'div', 'em', 'i', 'li', 'ol', 'p', 'small', 'span', 'strong', 'ul'}
        soup = BeautifulSoup(value, 'html.parser')
        for tag in soup.find_all(['script', 'style']):
            tag.decompose()
        for tag in soup.find_all(True):
            if tag.name not in allowed_tags:
                tag.unwrap()
                continue
            if tag.name == 'a':
                href = tag.get('href')
                title = tag.get('title')
                attrs = {}
                if href:
                    href = str(href)
                    if href.startswith(('http://', 'https://', '/')):
                        attrs['href'] = href
                        attrs['rel'] = 'nofollow noopener noreferrer'
                        attrs['target'] = '_blank'
                if title:
                    attrs['title'] = str(title)
                tag.attrs = attrs
            else:
                tag.attrs = {}
        return Markup(str(soup))

    env.filters['number_format'] = number_format
    env.filters['safe_message_html'] = safe_message_html

    for template_file in templates:
        relative = template_file.relative_to(TEMPLATE_DIR).as_posix()
        try:
            env.get_template(relative)
        except Exception as exc:  # pragma: no cover - should fail clearly in CI
            raise AssertionError(f'Template syntax failed for {relative}: {exc}') from exc

    assert len(templates) > 0


@pytest.mark.e2e
def test_frontend_js_files_are_syntax_valid():
    """Validate every frontend JS file parses cleanly with Node before deployment."""
    js_files = sorted(JS_DIR.glob('*.js'))
    assert js_files, 'No frontend JavaScript files were found in static/js'

    for js_file in js_files:
        result = subprocess.run(['node', '--check', str(js_file)], capture_output=True, text=True)
        assert result.returncode == 0, f'JavaScript syntax failed in {js_file.name}: {result.stderr}'

    assert len(js_files) > 0
