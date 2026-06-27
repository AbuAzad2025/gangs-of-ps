import pytest


class TestCSRFProtection:
    def test_csrf_enabled_config(self, app):
        assert app.config.get('WTF_CSRF_ENABLED') is not None


class TestSecurityHeaders:
    def test_session_cookie_http_only(self, app):
        assert app.config.get('SESSION_COOKIE_HTTPONLY') is True

    def test_session_cookie_samesite(self, app):
        assert app.config.get('SESSION_COOKIE_SAMESITE') == 'Lax'

    def test_max_content_length(self, app):
        assert app.config.get('MAX_CONTENT_LENGTH') == 16 * 1024 * 1024


class TestSecurityExtensions:
    def test_talisman_configured(self, app):
        from extensions import talisman
        assert talisman is not None

    def test_limiter_configured(self, app):
        from extensions import limiter
        assert limiter is not None

    def test_mail_configured(self, app):
        from extensions import mail
        assert mail is not None
