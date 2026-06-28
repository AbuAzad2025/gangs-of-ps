import logging
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

import pytest

from extensions import db
from models.log import UserLog
from models.user import User, UserRole
from services.economy import calculate_bank_fee, get_bank_fee_config
from services.economy_integrity import (
    ABSOLUTE_MAX_DIAMOND_DELTA,
    ABSOLUTE_MAX_MONEY_DELTA,
    ABSOLUTE_MAX_STAKE,
    SecurityBoundaryViolation,
    log_suspicious,
    parse_positive_int,
    parse_bank_amount,
    resolve_manual_diamond_purchase,
    validate_resource_changes,
    validate_stripe_webhook_credit,
)
from services.economy_policy import (
    SUPPORT_WHATSAPP_DISPLAY,
    SUPPORT_WHATSAPP_NUMBER,
    get_whatsapp_diamond_purchase_url,
    whatsapp_diamond_message,
)
from services.resource_service import ResourceService
from services.stripe_service import (
    DIAMOND_PACKAGES,
    create_checkout_session,
    get_publishable_key,
    handle_webhook_payload,
    stripe_enabled,
)
from services.staff_access import (
    is_staff,
    role_label,
    selectable_admin_roles,
    staff_capabilities,
    staff_hub_links,
)
from services.vip_service import expire_vip_if_needed, grant_vip, user_has_active_vip
from services.world_event_service import apply_world_event_money_bonus, get_active_world_event
from tests.support.factories import (
    make_admin,
    make_developer,
    make_moderator,
    make_user,
    make_vip_user,
)


class TestRequirementsService:
    def test_tier_for_level(self):
        from services.requirements import tier_for_level
        assert tier_for_level(1) == 't1'
        assert tier_for_level(10) == 't2'
        assert tier_for_level(20) == 't3'
        assert tier_for_level(40) == 't4'
        assert tier_for_level(99) == 't5'

    def test_tier_rank(self):
        from services.requirements import tier_rank
        assert tier_rank('t1') == 1
        assert tier_rank('t5') == 5

    def test_effective_level_with_rank_points(self, app, db):
        from services.requirements import effective_level
        from tests.support.factories import make_user
        user = make_user(db, username='eff1', level=5)
        with app.app_context():
            user.add_rank_points(100)
            db.session.commit()
            assert effective_level(user) == 7

    def test_check_requirements_passes(self, db):
        from services.requirements import check_requirements
        from tests.support.factories import make_user
        user = make_user(db, username='req1', level=20, exp=500)
        result = check_requirements(user, {'min_level': 10, 'min_exp': 100})
        assert result['ok'] is True
        assert result['missing'] == []

    def test_check_requirements_fails_level(self, db):
        from services.requirements import check_requirements
        from tests.support.factories import make_user
        user = make_user(db, username='req2', level=1)
        result = check_requirements(user, {'min_level': 50})
        assert result['ok'] is False
        assert 'level' in result['missing']
        assert result['hint_key'] == 'daily_tasks'

    def test_check_requirements_fails_strength(self, db):
        from services.requirements import check_requirements
        from tests.support.factories import make_user
        user = make_user(db, username='req3', strength=2)
        result = check_requirements(user, {'min_strength': 10})
        assert result['ok'] is False
        assert result['hint_key'] == 'gym'


class TestSecurityBoundary:
    def test_manual_catalog_resolves(self):
        assert resolve_manual_diamond_purchase(10) == 250

    def test_manual_catalog_rejects_unknown(self):
        with pytest.raises(SecurityBoundaryViolation):
            resolve_manual_diamond_purchase(99)

    def test_webhook_rejects_unknown_user(self, app, db):
        with app.app_context():
            with pytest.raises(SecurityBoundaryViolation):
                validate_stripe_webhook_credit(99999, 100)

    def test_webhook_rejects_catalog_mismatch(self, app, db):
        user = make_user(db, username='bound1')
        with app.app_context():
            with pytest.raises(SecurityBoundaryViolation):
                validate_stripe_webhook_credit(user.id, 99999)


class TestParsePositiveInt:
    def test_valid_in_range(self):
        assert parse_positive_int('100', min_value=1, max_value=500) == 100

    def test_rejects_non_numeric(self):
        assert parse_positive_int('abc') is None
        assert parse_positive_int(None) is None

    def test_rejects_below_min(self):
        assert parse_positive_int(0, min_value=1) is None

    def test_rejects_above_max(self):
        assert parse_positive_int(ABSOLUTE_MAX_MONEY_DELTA + 1) is None

    def test_custom_max(self):
        assert parse_positive_int(50, max_value=40) is None
        assert parse_positive_int(40, max_value=40) == 40

    def test_default_zero_allowed(self):
        assert parse_positive_int(0, min_value=0) == 0


# Production Refactoring & Fixes Applied:
# - services/economy_integrity.py: parse_bank_amount, validate_resource_changes
class TestParseBankAmount:
    def test_valid_amount(self):
        assert parse_bank_amount(500) == 500

    def test_rejects_zero(self):
        assert parse_bank_amount(0) is None

    def test_rejects_huge_amount(self):
        assert parse_bank_amount(ABSOLUTE_MAX_MONEY_DELTA + 1) is None


class TestValidateResourceChanges:
    def test_rejects_empty_mutation(self):
        with pytest.raises(SecurityBoundaryViolation):
            validate_resource_changes({}, set_fields=None)

    def test_allows_set_fields_only(self):
        validate_resource_changes({}, set_fields={'jail_until': None})

    def test_rejects_extreme_money_delta(self):
        with pytest.raises(SecurityBoundaryViolation):
            validate_resource_changes({'money': ABSOLUTE_MAX_MONEY_DELTA + 1})

    def test_rejects_extreme_diamond_delta(self):
        with pytest.raises(SecurityBoundaryViolation):
            validate_resource_changes({'diamonds': ABSOLUTE_MAX_DIAMOND_DELTA + 1})

    def test_constants_sane(self):
        assert ABSOLUTE_MAX_MONEY_DELTA > 0
        assert ABSOLUTE_MAX_DIAMOND_DELTA > 0
        assert ABSOLUTE_MAX_STAKE > 0


class TestLogSuspicious:
    def test_logs_warning(self, app, caplog):
        with app.app_context():
            with caplog.at_level(logging.WARNING):
                log_suspicious(42, 'overspend', 'tried 9e9')
        assert 'ECON_INTEGRITY' in caplog.text
        assert 'user=42' in caplog.text


class TestEconomyPolicy:
    def test_whatsapp_message_includes_username(self):
        msg = whatsapp_diamond_message('azad', amount_usd=10)
        assert 'azad' in msg
        assert '10$' in msg

    def test_whatsapp_message_without_amount(self):
        msg = whatsapp_diamond_message('player_x')
        assert 'player_x' in msg
        assert 'المبلغ' not in msg

    def test_purchase_url_encodes_text(self):
        url = get_whatsapp_diamond_purchase_url('testuser', 5)
        assert SUPPORT_WHATSAPP_NUMBER in url
        assert 'wa.me' in url
        assert 'testuser' in unquote(url)

    def test_display_number_matches_config(self):
        assert SUPPORT_WHATSAPP_DISPLAY.startswith('+')


class TestBankFeeConfig:
    def test_returns_defaults(self, app):
        with app.app_context():
            cfg = get_bank_fee_config()
        assert cfg['tier1_threshold'] == 50000
        assert cfg['tier2_threshold'] == 200000
        assert cfg['tier1_pct'] == 0.005
        assert cfg['tier2_pct'] == 0.012


class TestCalculateBankFee:
    def test_no_fee_below_tier1(self):
        cfg = get_bank_fee_config.__wrapped__() if hasattr(get_bank_fee_config, '__wrapped__') else {
            'tier1_threshold': 50000,
            'tier2_threshold': 200000,
            'tier1_pct': 0.005,
            'tier2_pct': 0.012,
        }
        fee, reason = calculate_bank_fee(10_000, cfg)
        assert fee == 0
        assert reason == 'No Fee'

    def test_tier1_fee(self):
        cfg = {
            'tier1_threshold': 50000,
            'tier2_threshold': 200000,
            'tier1_pct': 0.005,
            'tier2_pct': 0.012,
        }
        fee, reason = calculate_bank_fee(100_000, cfg)
        assert fee == 500
        assert 'Tier 1' in reason

    def test_tier2_fee(self):
        cfg = {
            'tier1_threshold': 50000,
            'tier2_threshold': 200000,
            'tier1_pct': 0.005,
            'tier2_pct': 0.012,
        }
        fee, reason = calculate_bank_fee(500_000, cfg)
        assert fee == 6000
        assert 'Tier 2' in reason


class TestResourceService:
    def test_adds_money_and_logs(self, app, db):
        user = make_user(db, username='res1', money=100)
        user_id = user.id
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user_id, {'money': 250}, 'test_reward',
            )
        assert ok is True
        user = db.session.get(User, user_id)
        assert user.money == 350
        log = UserLog.query.filter_by(user_id=user.id).order_by(UserLog.id.desc()).first()
        assert log is not None
        assert log.action == 'TEST_REWARD'

    def test_rejects_insufficient_funds(self, app, db):
        user = make_user(db, username='res2', money=50)
        user_id = user.id
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user_id, {'money': -100}, 'test_spend', check_balance=True,
            )
        assert ok is False
        user = db.session.get(User, user_id)
        assert user.money == 50

    def test_unknown_user_returns_false(self, app, db):
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(99999, {'money': 10}, 'ghost')
        assert ok is False

    def test_invalid_resource_raises_and_rolls_back(self, app, db):
        user = make_user(db, username='res3')
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user.id, {'not_a_field': 5}, 'bad_field',
            )
        assert ok is False

    def test_version_mismatch_fails(self, app, db):
        user = make_user(db, username='res4', money=100)
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user.id, {'money': 10}, 'versioned',
                expected_version=user.version + 99,
            )
        assert ok is False

    def test_daily_money_cap_for_crime_reward(self, app, db):
        from models.system import SystemConfig
        user = make_user(db, username='res5', money=0)
        user_id = user.id
        with app.app_context():
            SystemConfig.set_value('economy_daily_money_limit', '100')
        with app.test_request_context('/'):
            assert ResourceService.modify_resources(
                user_id, {'money': 60}, 'crime_reward',
            )
            assert ResourceService.modify_resources(
                user_id, {'money': 60}, 'crime_reward',
            )
        user = db.session.get(User, user_id)
        assert user.money == 100
        assert user.daily_money_earned == 100

    def test_stripe_checkout_not_capped(self, app, db):
        user = make_user(db, username='res6', money=0)
        user_id = user.id
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user_id, {'diamonds': 500}, 'stripe_checkout',
            )
        assert ok is True
        user = db.session.get(User, user_id)
        assert user.diamonds == 500

    def test_set_fields_updates_status(self, app, db):
        from datetime import datetime, timezone
        user = make_user(db, username='res7')
        user_id = user.id
        until = datetime.now(timezone.utc).replace(tzinfo=None)
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user_id, {}, 'status_set',
                set_fields={'jail_until': until},
            )
        assert ok is True
        user = db.session.get(User, user_id)
        assert user.jail_until == until

    def test_resets_daily_counter_on_new_day(self, app, db):
        from datetime import timedelta
        user = make_user(db, username='res8', money=0, daily_money_earned=90)
        user_id = user.id
        user.daily_money_date = date.today() - timedelta(days=1)
        db.session.commit()
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user_id, {'money': 50}, 'crime_reward',
            )
        assert ok is True
        user = db.session.get(User, user_id)
        assert user.daily_money_earned == 50

    def test_rejects_extreme_money_delta(self, app, db):
        user = make_user(db, username='res9', money=100)
        with app.test_request_context('/'):
            ok = ResourceService.modify_resources(
                user.id,
                {'money': ABSOLUTE_MAX_MONEY_DELTA + 1},
                'exploit',
            )
        assert ok is False


# Production Refactoring & Fixes Applied:
# - services/resource_service.py: transfer_bank_balance with begin_nested savepoint
class TestBankTransferAtomic:
    def test_transfer_moves_bank_balance(self, app, db):
        sender = make_user(db, username='banksend', bank_balance=1000, money=0)
        recipient = make_user(db, username='bankrecv', bank_balance=0, money=0)
        sender_id, recipient_id = int(sender.id), int(recipient.id)
        with app.test_request_context('/'):
            ok = ResourceService.transfer_bank_balance(sender_id, recipient_id, 400)
        assert ok is True
        sender = db.session.get(User, sender_id)
        recipient = db.session.get(User, recipient_id)
        assert sender.bank_balance == 600
        assert recipient.bank_balance == 400

    def test_transfer_rolls_back_on_insufficient_funds(self, app, db):
        sender = make_user(db, username='bankpoor', bank_balance=50)
        recipient = make_user(db, username='bankrich', bank_balance=0)
        sender_id, recipient_id = int(sender.id), int(recipient.id)
        with app.test_request_context('/'):
            ok = ResourceService.transfer_bank_balance(sender_id, recipient_id, 100)
        assert ok is False
        sender = db.session.get(User, sender_id)
        recipient = db.session.get(User, recipient_id)
        assert sender.bank_balance == 50
        assert recipient.bank_balance == 0

    def test_transfer_rejects_self(self, app, db):
        user = make_user(db, username='bankself', bank_balance=100)
        with app.test_request_context('/'):
            assert ResourceService.transfer_bank_balance(int(user.id), int(user.id), 10) is False


# Production Refactoring & Fixes Applied:
# - services/market_trading.py: parse_bank_amount boundary sanitization
class TestMarketTradingPay:
    def test_rejects_negative_amount(self, app, db):
        from services.market_trading import pay_from_game_balance
        user = make_user(db, username='trader1', money=1000)
        with app.app_context():
            ok, err, _ = pay_from_game_balance(user.id, -5, 'market_buy')
        assert ok is False
        assert err is not None

    def test_pays_from_cash(self, app, db):
        from services.market_trading import pay_from_game_balance
        user = make_user(db, username='trader2', money=500, bank_balance=200)
        user_id = int(user.id)
        with app.test_request_context('/'):
            ok, err, breakdown = pay_from_game_balance(user_id, 100, 'market_buy')
        assert ok is True
        assert err is None
        assert breakdown['from_cash'] == 100
        user = db.session.get(User, user_id)
        assert user.money == 400


class TestStripeEnabled:
    def test_disabled_without_secret(self, monkeypatch):
        monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
        assert stripe_enabled() is False

    def test_enabled_with_secret(self, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_abc')
        assert stripe_enabled() is True

    def test_publishable_key(self, monkeypatch):
        monkeypatch.setenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_xyz')
        assert get_publishable_key() == 'pk_test_xyz'


class TestCreateCheckoutSession:
    def test_not_configured(self, monkeypatch):
        monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
        url, err = create_checkout_session(1, '5', 'http://ok', 'http://cancel')
        assert url is None
        assert 'not configured' in err.lower()

    def test_invalid_package(self, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        url, err = create_checkout_session(1, '999', 'http://ok', 'http://cancel')
        assert url is None
        assert err == 'Invalid package'

    @patch('stripe.checkout.Session.create')
    def test_success_returns_url(self, mock_create, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        mock_create.return_value = MagicMock(url='https://checkout.stripe.com/x')
        url, err = create_checkout_session(7, '10', 'http://ok', 'http://cancel')
        assert err is None
        assert url.startswith('https://checkout')
        meta = mock_create.call_args.kwargs['metadata']
        assert meta['user_id'] == '7'
        assert meta['diamonds'] == str(DIAMOND_PACKAGES['10']['diamonds'])


class TestHandleWebhookPayload:
    def test_not_configured(self, monkeypatch):
        monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
        result = handle_webhook_payload(b'{}', 'sig')
        assert result['ok'] is False

    @patch('stripe.Webhook.construct_event')
    def test_ignores_non_checkout_events(self, mock_construct, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')
        mock_construct.return_value = {'type': 'payment_intent.succeeded', 'data': {'object': {}}}
        result = handle_webhook_payload(b'{}', 'sig')
        assert result['ok'] is True
        assert result.get('ignored') is True

    @patch('stripe.Webhook.construct_event')
    def test_parses_completed_checkout(self, mock_construct, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test')
        monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')
        mock_construct.return_value = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_1',
                    'metadata': {'user_id': '3', 'diamonds': '250'},
                },
            },
        }
        result = handle_webhook_payload(b'{}', 'sig')
        assert result['ok'] is True
        assert result['user_id'] == 3
        assert result['diamonds'] == 250
        assert result['session_id'] == 'cs_test_1'


class TestRoleLabel:
    def test_user_label(self):
        assert role_label(UserRole.USER)

    def test_none_defaults(self):
        text = role_label(None)
        assert text


class TestSelectableRoles:
    def test_includes_moderator_and_developer(self):
        roles = selectable_admin_roles()
        assert UserRole.MODERATOR in roles
        assert UserRole.DEVELOPER in roles


class TestIsStaff:
    def test_player_not_staff(self, db):
        user = make_user(db, username='pl1')
        assert is_staff(user) is False

    def test_moderator_is_staff(self, db):
        user = make_moderator(db, username='st1')
        assert is_staff(user) is True


class TestStaffHubLinks:
    def test_player_gets_no_links(self, db):
        user = make_user(db, username='pl2')
        assert staff_hub_links(user) == []

    def test_moderator_gets_chat_links(self, db):
        user = make_moderator(db, username='st2')
        links = staff_hub_links(user)
        endpoints = [l.get('endpoint') for l in links]
        assert 'main.staff_chat' in endpoints

    def test_developer_gets_dev_panel(self, db):
        user = make_developer(db, username='st3')
        endpoints = [l.get('endpoint') for l in staff_hub_links(user)]
        assert 'main.dev_dashboard' in endpoints


class TestStaffCapabilities:
    def test_moderator_capabilities(self, db):
        user = make_moderator(db, username='cap1')
        caps = staff_capabilities(user)
        assert len(caps) >= 2

    def test_developer_has_extra_caps(self, db):
        dev = make_developer(db, username='cap2')
        admin = make_admin(db, username='cap3')
        assert len(staff_capabilities(dev)) > len(staff_capabilities(admin))


class TestUserHasActiveVip:
    def test_regular_user_not_vip(self, db):
        user = make_user(db, username='vip0')
        assert user_has_active_vip(user) is False

    def test_lifetime_vip(self, db):
        user = make_vip_user(db, username='vip1', lifetime=True)
        assert user_has_active_vip(user) is True

    def test_expired_vip(self, db):
        user = make_vip_user(db, username='vip2', days=30)
        past = datetime.now(timezone.utc) - timedelta(days=1)
        user.vip_until = past.replace(tzinfo=None)
        assert user_has_active_vip(user) is False


class TestGrantVip:
    def test_grants_subscriber_role(self, app, db):
        user = make_user(db, username='grant1')
        user_id = user.id
        with app.app_context():
            assert grant_vip(user_id, days=7) is True
            db.session.commit()
        user = db.session.get(User, user_id)
        assert user.role == UserRole.SUBSCRIBER
        assert user.vip_until is not None

    def test_lifetime_clears_until(self, app, db):
        user = make_user(db, username='grant2')
        user_id = user.id
        with app.app_context():
            grant_vip(user_id, lifetime=True)
            db.session.commit()
        user = db.session.get(User, user_id)
        assert user.vip_until is None


class TestExpireVip:
    def test_downgrades_expired(self, app, db):
        user = make_vip_user(db, username='exp1', days=1)
        user_id = user.id
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        user.vip_until = past.replace(tzinfo=None)
        db.session.commit()
        with app.app_context():
            fresh = db.session.get(User, user_id)
            still = expire_vip_if_needed(fresh, now=datetime.now(timezone.utc))
            db.session.commit()
        assert still is False
        user = db.session.get(User, user_id)
        assert user.role == UserRole.USER


class TestWorldEvent:
    def test_inactive_by_default(self, app):
        with app.app_context():
            assert get_active_world_event() is None

    def test_active_event_with_bonus(self, app):
        from models.system import SystemConfig
        ends = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        with app.app_context():
            SystemConfig.set_value('world_event_active', 'true')
            SystemConfig.set_value('world_event_ends_at', ends)
            SystemConfig.set_value('world_event_money_bonus_pct', '20')
            SystemConfig.set_value('world_event_title', 'Bonus Week')
            ev = get_active_world_event()
        assert ev is not None
        assert ev['title'] == 'Bonus Week'
        assert ev['money_bonus_pct'] == 20.0

    def test_expired_event_returns_none(self, app):
        from models.system import SystemConfig
        ends = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with app.app_context():
            SystemConfig.set_value('world_event_active', 'true')
            SystemConfig.set_value('world_event_ends_at', ends)
            assert get_active_world_event() is None

    def test_apply_bonus(self, app):
        from models.system import SystemConfig
        ends = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        with app.app_context():
            SystemConfig.set_value('world_event_active', 'true')
            SystemConfig.set_value('world_event_ends_at', ends)
            SystemConfig.set_value('world_event_money_bonus_pct', '10')
            result = apply_world_event_money_bonus(1000)
        assert result == 1100

    def test_no_bonus_when_inactive(self, app):
        with app.app_context():
            assert apply_world_event_money_bonus(500) == 500


@pytest.fixture
def gang_with_upgrades(app, db):
    import json
    from models.social import Gang

    leader = make_user(db, username='ganglead1')
    gang = Gang(name='TestGang', leader_id=leader.id, upgrades=json.dumps({'gym_rat': 1}))
    db.session.add(gang)
    db.session.commit()
    return gang


class TestGangService:
    def test_no_gang_returns_zero(self, app):
        from services.gang_service import GangService
        with app.app_context():
            assert GangService.get_gang_buff(None, 'gym_rat') == 0

    def test_empty_upgrades_returns_zero(self, app, db):
        from models.social import Gang
        from services.gang_service import GangService
        leader = make_user(db, username='ganglead2')
        gang = Gang(name='EmptyGang', leader_id=leader.id, upgrades='{}')
        db.session.add(gang)
        db.session.commit()
        with app.app_context():
            assert GangService.get_gang_buff(gang.id, 'gym_rat') == 0

    def test_reads_buff_from_seed_data(self, app, gang_with_upgrades):
        from services.gang_service import GangService
        with app.app_context():
            buff = GangService.get_gang_buff(gang_with_upgrades.id, 'gym_rat')
        assert isinstance(buff, (int, float))
        assert buff >= 0

    def test_unknown_buff_type_returns_zero(self, app, gang_with_upgrades):
        from services.gang_service import GangService
        with app.app_context():
            assert GangService.get_gang_buff(gang_with_upgrades.id, 'nonexistent_buff') == 0


class TestEmpireService:
    def test_dashboard_wealth_and_score(self, app, db):
        from services.empire_service import get_empire_dashboard
        user = make_user(db, username='empire1', money=50_000, bank_balance=25_000, level=5)
        with app.app_context():
            dash = get_empire_dashboard(user, heat=3, gang=None)
        assert dash['wealth'] == 75_000
        assert dash['cash'] == 50_000
        assert dash['bank'] == 25_000
        assert 5 <= dash['empire_score'] <= 100
        assert len(dash['quick_actions']) >= 4
        assert dash['economy_health']['score'] >= 0

    def test_dashboard_with_gang_boosts_score(self, app, db, gang_with_upgrades):
        from services.empire_service import get_empire_dashboard
        user = make_user(db, username='empire2', money=10_000, level=3)
        with app.app_context():
            no_gang = get_empire_dashboard(user, heat=0, gang=None)['empire_score']
            with_gang = get_empire_dashboard(
                user, heat=0, gang=gang_with_upgrades)['empire_score']
        assert with_gang >= no_gang


class TestMarketEducation:
    def test_concepts_list_not_empty(self, app):
        from services.market_education import get_market_concepts
        with app.app_context():
            concepts = get_market_concepts()
        assert len(concepts) >= 5
        assert all('title' in c and 'body' in c for c in concepts)

    def test_empty_portfolio_tips(self, app):
        from services.market_education import analyze_portfolio
        with app.app_context():
            result = analyze_portfolio([], cash=1000, bank=500)
        assert result['diversification_score'] == 0
        assert result['asset_count'] == 0
        assert len(result['tips']) >= 1

    def test_concentrated_portfolio_warning(self, app, db):
        from models.market import MarketAsset, UserInvestment
        from services.market_education import analyze_portfolio
        user = make_user(db, username='investor1', money=5000)
        stock = MarketAsset(symbol='TST', name='Test Co', asset_type='stock', current_price=10.0)
        db.session.add(stock)
        db.session.flush()
        inv = UserInvestment(
            user_id=user.id,
            asset_id=stock.id,
            quantity=100.0,
            average_buy_price=8.0,
        )
        db.session.add(inv)
        db.session.commit()
        with app.app_context():
            result = analyze_portfolio([inv], assets_by_id={stock.id: stock}, cash=100)
        assert result['asset_count'] == 1
        assert result['largest_weight_pct'] == 100
        assert result['diversification_score'] < 50

    def test_diversified_portfolio_scores_higher(self, app, db):
        from models.market import MarketAsset, UserInvestment
        from services.market_education import analyze_portfolio
        user = make_user(db, username='investor2')
        assets = [
            MarketAsset(symbol='AAA', name='Alpha', asset_type='stock', current_price=10.0),
            MarketAsset(symbol='BBB', name='Beta', asset_type='crypto', current_price=5.0),
        ]
        db.session.add_all(assets)
        db.session.flush()
        invs = [
            UserInvestment(user_id=user.id, asset_id=assets[0].id, quantity=50.0, average_buy_price=9.0),
            UserInvestment(user_id=user.id, asset_id=assets[1].id, quantity=40.0, average_buy_price=4.0),
        ]
        db.session.add_all(invs)
        db.session.commit()
        assets_by_id = {a.id: a for a in assets}
        with app.app_context():
            result = analyze_portfolio(invs, assets_by_id=assets_by_id, cash=500)
        assert result['asset_count'] == 2
        assert result['diversification_score'] >= 45


class TestHostessTrainingService:
    def test_build_greeter_prompt(self, app):
        from services.hostess_training_service import build_greeter_leader_prompt
        hostess = type('H', (), {'name': 'Jasmin', 'dialogue_style': 'friendly'})()
        with app.app_context():
            prompt = build_greeter_leader_prompt(hostess)
        assert 'Jasmin' in prompt or len(prompt) > 20

    def test_training_examples_json(self, app):
        import json
        from services.hostess_training_service import (
            build_greeter_leader_examples,
            build_greeter_leader_training_json,
        )
        hostess = type('H', (), {'name': 'Greeter'})()
        with app.app_context():
            examples = build_greeter_leader_examples()
            payload = build_greeter_leader_training_json(hostess)
        assert len(examples) >= 3
        parsed = json.loads(payload)
        assert isinstance(parsed, list)


class TestGreeterService:
    @pytest.fixture
    def greeter_hostess(self, app, db):
        from models.hostess import Hostess
        hostess = Hostess(name='Jasmin', role='greeter', dialogue_style='friendly')
        db.session.add(hostess)
        db.session.commit()
        return hostess

    def test_get_greeter_by_role(self, app, greeter_hostess):
        from services.greeter_service import get_greeter_hostess
        with app.app_context():
            found = get_greeter_hostess()
        assert found is not None
        assert found.role == 'greeter'

    def test_process_empty_message_rejected(self, app, greeter_hostess):
        from services.greeter_service import process_assistant_message
        with app.app_context():
            payload, err, status = process_assistant_message('   ')
        assert payload is None
        assert status == 400

    def test_process_message_rule_based_fallback(self, app, greeter_hostess, client):
        from services.greeter_service import process_assistant_message
        with app.app_context():
            with client.session_transaction() as sess:
                sess['_user_id'] = None
            payload, err, status = process_assistant_message('كيف أبدأ؟')
        assert status == 200
        assert payload is not None
        assert 'response' in payload
