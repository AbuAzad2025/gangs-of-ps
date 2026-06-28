import pytest
from unittest.mock import patch

from extensions import db
from models.payment import PaymentTransaction
from models.user import User
from tests.support.factories import make_user, make_user_id


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


class TestEconomyForms:
    def test_send_money_form_valid(self, app):
        from forms.economy import DepositForm, SendMoneyForm
        with app.app_context():
            assert SendMoneyForm(data={'username': 'player', 'amount': 100}).validate()
            assert DepositForm(data={'amount': 50}).validate()

    def test_send_money_form_rejects_zero(self, app):
        from forms.economy import SendMoneyForm
        with app.app_context():
            form = SendMoneyForm(data={'username': 'player', 'amount': 0})
            assert form.validate() is False


class TestGameplayForms:
    def test_attack_and_heal_forms(self, app):
        from forms.gameplay import AttackForm, HealForm
        with app.app_context():
            assert AttackForm().validate() is True
            assert HealForm().validate() is True


class TestEmpireAndMarketPages:
    def test_empire_page_authenticated(self, logged_in_client):
        resp = logged_in_client.get('/empire', follow_redirects=True)
        assert resp.status_code == 200

    def test_market_guide_page(self, logged_in_client):
        resp = logged_in_client.get('/market/guide', follow_redirects=True)
        assert resp.status_code == 200


class TestResourcesLedger:
    def test_my_ledger_requires_login(self, client):
        resp = client.get('/resources/ledger', follow_redirects=False)
        assert resp.status_code == 302

    def test_my_ledger_renders(self, logged_in_client):
        resp = logged_in_client.get('/resources/ledger', follow_redirects=True)
        assert resp.status_code == 200


class TestPublicHostessChat:
    @pytest.fixture
    def greeter(self, app, db):
        from models.hostess import Hostess
        hostess = Hostess(name='Jasmin', role='greeter')
        db.session.add(hostess)
        db.session.commit()
        return hostess

    def test_rejects_empty_message(self, client, greeter):
        resp = client.post('/api/public/chat', json={'message': '  '})
        assert resp.status_code == 400

    def test_guest_chat_success(self, client, greeter):
        resp = client.post('/api/public/chat', json={'message': 'مرحبا'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('response')
        assert data.get('hostess_name')


# Production Refactoring & Fixes Applied:
# - routes/__init__.py: _bind_current_user_to_session() prevents DetachedInstanceError after commits
class TestSessionRebind:
    def test_bank_deposit_survives_redirect(self, client, db, login_as):
        user_id = make_user_id(db, username='rebind1', money=500, bank_balance=0)
        login_as(user_id)
        resp = client.post('/bank/deposit', data={'amount': '100'}, follow_redirects=True)
        assert resp.status_code == 200


# Production Refactoring & Fixes Applied:
# - routes/bank.py: parse_bank_amount, transfer_bank_balance, deferred commit
# - services/resource_service.py: transfer_bank_balance, validate_resource_changes
class TestBankRoutes:
    def test_deposit_moves_cash_to_bank(self, client, db, login_as):
        user_id = make_user_id(db, username='bankdep1', money=500, bank_balance=0)
        login_as(user_id)
        resp = client.post('/bank/deposit', data={'amount': '200'}, follow_redirects=True)
        assert resp.status_code == 200
        user = db.session.get(User, user_id)
        assert user.money == 300
        assert user.bank_balance == 200

    def test_withdraw_moves_bank_to_cash(self, client, db, login_as):
        user_id = make_user_id(db, username='bankwd1', money=0, bank_balance=300)
        login_as(user_id)
        resp = client.post('/bank/withdraw', data={'amount': '100'}, follow_redirects=True)
        assert resp.status_code == 200
        user = db.session.get(User, user_id)
        assert user.money == 100
        assert user.bank_balance == 200

    def test_rejects_invalid_amount(self, client, db, login_as):
        user_id = make_user_id(db, username='bankbad1', money=500, bank_balance=0)
        login_as(user_id)
        client.post('/bank/deposit', data={'amount': '0'}, follow_redirects=True)
        user = db.session.get(User, user_id)
        assert user.money == 500
        assert user.bank_balance == 0

    def test_transfer_between_users(self, client, db, login_as):
        sender_id = make_user_id(db, username='xfer_a', bank_balance=800)
        recipient_id = make_user_id(db, username='xfer_b', bank_balance=0)
        login_as(sender_id)
        resp = client.post('/bank/transfer', data={
            'recipient': 'xfer_b',
            'amount': '250',
        }, follow_redirects=True)
        assert resp.status_code == 200
        sender = db.session.get(User, sender_id)
        recipient = db.session.get(User, recipient_id)
        assert sender.bank_balance == 550
        assert recipient.bank_balance == 250


# Production Refactoring & Fixes Applied:
# - routes/economy.py: begin_nested for collect_income, buy_property, gang flows
class TestEconomyRoutes:
    def test_academy_fee_preview_sanitizes_input(self, logged_in_client):
        resp = logged_in_client.get('/economy/academy/fee_preview?amount=not-a-number')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None

    def test_my_properties_page(self, logged_in_client):
        resp = logged_in_client.get('/economy/my_properties', follow_redirects=True)
        assert resp.status_code == 200
