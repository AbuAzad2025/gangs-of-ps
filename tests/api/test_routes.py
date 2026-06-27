import pytest


class TestPublicRoutes:
    def test_index_page(self, client):
        resp = client.get('/')
        assert resp.status_code in (200, 302)

    def test_login_page(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200

    def test_register_page(self, client):
        resp = client.get('/register')
        assert resp.status_code == 200


class TestAuthRoutes:
    def test_login_post_invalid(self, client):
        resp = client.post('/login', data={
            'username': 'nonexistent',
            'password': 'wrong',
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_register_post(self, client):
        resp = client.post('/register', data={
            'username': 'newplayer',
            'email': 'new@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestAuthenticatedRoutes:
    def test_hara_page_authenticated(self, logged_in_client):
        resp = logged_in_client.get('/hara', follow_redirects=True)
        assert resp.status_code in (200, 302)

    def test_crimes_page(self, logged_in_client):
        resp = logged_in_client.get('/crimes', follow_redirects=True)
        assert resp.status_code in (200, 302)

    def test_profile_page(self, logged_in_client):
        resp = logged_in_client.get('/profile', follow_redirects=True)
        assert resp.status_code in (200, 302)


class TestErrorPages:
    def test_404(self, client):
        resp = client.get('/nonexistent-page-xyz')
        assert resp.status_code == 404
