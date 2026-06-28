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
    resolve_manual_diamond_purchase,
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
