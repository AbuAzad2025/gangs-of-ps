import pytest
from unittest.mock import patch

from extensions import db
from models.payment import PaymentTransaction
from models.user import User
from tests.support.factories import make_user


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

    def test_profile_page(self, logged_in_client, auth_user_id):
        resp = logged_in_client.get(f'/profile/{auth_user_id}', follow_redirects=True)
        assert resp.status_code in (200, 302)


class TestErrorPages:
    def test_404(self, client):
        resp = client.get('/nonexistent-page-xyz')
        assert resp.status_code == 404

class TestBuyDiamondsPage:
    def test_requires_login(self, client):
        resp = client.get('/buy_diamonds', follow_redirects=False)
        assert resp.status_code == 302

    def test_renders_for_logged_in_user(self, logged_in_client):
        resp = logged_in_client.get('/buy_diamonds')
        assert resp.status_code == 200
        assert b'diamond' in resp.data.lower() or 'ماس' in resp.get_data(as_text=True)

    def test_stripe_success_message(self, logged_in_client):
        resp = logged_in_client.get('/buy_diamonds?stripe=success')
        assert resp.status_code == 200

    def test_stripe_cancel_message(self, logged_in_client):
        resp = logged_in_client.get('/buy_diamonds?stripe=cancel')
        assert resp.status_code == 200


class TestManualPaymentSubmit:
    def test_creates_pending_transaction(self, logged_in_client, db, auth_user_id):
        user_id = auth_user_id
        resp = logged_in_client.post('/buy_diamonds', data={
            'amount_usd': '10',
            'payment_method': 'bank',
            'payment_proof': '1234567890 transfer ref',
            'submit': 'Send',
        }, follow_redirects=False)
        assert resp.status_code in (302, 200)
        tx = PaymentTransaction.query.filter_by(user_id=user_id).first()
        assert tx is not None
        assert tx.diamonds_amount == 250
        assert tx.status == 'pending'
        assert tx.is_verified is False

    def test_rejects_short_proof(self, logged_in_client, db, auth_user_id):
        user_id = auth_user_id
        logged_in_client.post('/buy_diamonds', data={
            'amount_usd': '5',
            'payment_method': 'bank',
            'payment_proof': 'short',
            'submit': 'Send',
        })
        assert PaymentTransaction.query.filter_by(user_id=user_id).count() == 0


class TestStripeCheckout:
    def test_disabled_redirects(self, logged_in_client, monkeypatch):
        monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
        resp = logged_in_client.post('/stripe/checkout', data={
            'package': '5',
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert 'buy_diamonds' in resp.location

    @patch('routes.payment.create_checkout_session')
    def test_redirects_to_stripe(self, mock_checkout, logged_in_client, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        mock_checkout.return_value = ('https://checkout.stripe.com/pay', None)
        resp = logged_in_client.post('/stripe/checkout', data={
            'package': '10',
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.location.startswith('https://checkout.stripe.com')


class TestStripeWebhook:
    def test_rejects_when_disabled(self, client, monkeypatch):
        monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
        resp = client.post('/stripe/webhook', data=b'{}')
        assert resp.status_code == 400

    @patch('routes.payment.handle_webhook_payload')
    def test_credits_diamonds_on_success(self, mock_handler, client, app, db, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        user = make_user(db, username='payweb1', diamonds=0)
        user_id = user.id
        mock_handler.return_value = {
            'ok': True,
            'user_id': user_id,
            'diamonds': 100,
            'session_id': 'cs_test_session_1',
        }
        resp = client.post('/stripe/webhook', data=b'{}', headers={
            'Stripe-Signature': 'test',
        })
        assert resp.status_code == 200
        user = db.session.get(User, user_id)
        assert user.diamonds == 100
        tx = PaymentTransaction.query.filter_by(transaction_id='cs_test_session_1').first()
        assert tx is not None
        assert tx.is_verified is True

    @patch('routes.payment.handle_webhook_payload')
    def test_idempotent_verified_session(self, mock_handler, client, app, db, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        user = make_user(db, username='payweb2', diamonds=50)
        user_id = user.id
        tx = PaymentTransaction(
            user_id=user_id,
            amount_usd=5.0,
            diamonds_amount=100,
            transaction_id='cs_dup_1',
            status='completed',
            payment_method='stripe',
            payment_proof='stripe webhook',
            is_verified=True,
        )
        db.session.add(tx)
        db.session.commit()
        mock_handler.return_value = {
            'ok': True,
            'user_id': user_id,
            'diamonds': 100,
            'session_id': 'cs_dup_1',
        }
        resp = client.post('/stripe/webhook', data=b'{}')
        assert resp.status_code == 200
        user = db.session.get(User, user_id)
        assert user.diamonds == 50

    @patch('routes.payment.handle_webhook_payload')
    def test_rejects_catalog_boundary_violation(self, mock_handler, client, app, db, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        user = make_user(db, username='payweb3', diamonds=0)
        user_id = user.id
        mock_handler.return_value = {
            'ok': True,
            'user_id': user_id,
            'diamonds': 99999,
            'session_id': 'cs_bad_catalog',
        }
        resp = client.post('/stripe/webhook', data=b'{}')
        assert resp.status_code == 400
        user = db.session.get(User, user_id)
        assert user.diamonds == 0


class TestLoginScenarios:
    def test_login_wrong_password_stays_on_page(self, client, db):
        make_user(db, username='auth1', password='correct')
        resp = client.post('/login', data={
            'username': 'auth1',
            'password': 'wrong',
            'submit': 'Login',
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_success_redirects(self, client, db):
        make_user(db, username='auth2', password='secret99')
        resp = client.post('/login', data={
            'username': 'auth2',
            'password': 'secret99',
            'submit': 'Login',
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_logout_requires_login(self, client):
        resp = client.get('/logout', follow_redirects=False)
        assert resp.status_code == 302


class TestRegisterScenarios:
    def test_register_duplicate_username(self, client, db):
        make_user(db, username='taken1')
        resp = client.post('/register', data={
            'username': 'taken1',
            'email': 'other@example.com',
            'password': 'longpassword1',
            'password2': 'longpassword1',
            'submit': 'Register',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert User.query.filter_by(email='other@example.com').first() is None


class TestCaptcha:
    def test_captcha_image_endpoint(self, client):
        resp = client.get('/captcha/image')
        assert resp.status_code == 200
        assert resp.content_type.startswith('image/')
