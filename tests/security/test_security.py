import pytest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import MagicMock
from werkzeug.wrappers import Response

from models.user import UserRole
from services.chat_security import (
    MAX_CHAT_UPLOAD_BYTES,
    chat_send_block_reason,
    contains_prohibited_content,
    is_safe_chat_upload_rel_path,
    moderator_can_act,
    normalize_room,
    scan_upload_file,
    user_is_online,
    validate_message_attachments,
)
from tests.support.factories import (
    make_admin,
    make_developer,
    make_gym_user,
    make_hospitalized_user,
    make_jailed_user,
    make_moderator,
    make_user,
    utc_now,
)
from utils.resource_audit import (
    allow_resource_mutation,
    disallow_resource_mutation,
    is_resource_mutation_allowed,
)


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

def _invoke(app, user, decorator, *, session_data=None):
    @decorator
    def view():
        return 'ok', 200

    with app.test_request_context('/'):
        from flask_login import login_user
        if user is not None:
            login_user(user)
        if session_data:
            from flask import session
            session.update(session_data)
        return view()


def _is_redirect(result) -> bool:
    return isinstance(result, Response) and result.status_code in (301, 302, 303, 307, 308)


class TestCheckPlayerStatus:
    def test_allows_free_player(self, app, db):
        from utils.decorators import check_player_status
        user = make_user(db, username='free1')
        result = _invoke(app, user, check_player_status)
        assert result == ('ok', 200)

    def test_blocks_jailed_player(self, app, db):
        from utils.decorators import check_player_status
        user = make_jailed_user(db, username='jailed1')
        result = _invoke(app, user, check_player_status)
        assert _is_redirect(result)

    def test_blocks_hospitalized_player(self, app, db):
        from utils.decorators import check_player_status
        user = make_hospitalized_user(db, username='hosp1')
        result = _invoke(app, user, check_player_status)
        assert _is_redirect(result)

    def test_blocks_gym_training_player(self, app, db):
        from utils.decorators import check_player_status
        user = make_gym_user(db, username='gym1')
        result = _invoke(app, user, check_player_status)
        assert _is_redirect(result)

    def test_allows_expired_jail(self, app, db):
        from utils.decorators import check_player_status
        past = utc_now() - timedelta(minutes=5)
        user = make_user(db, username='freed1', jail_until=past.replace(tzinfo=None))
        result = _invoke(app, user, check_player_status)
        assert result == ('ok', 200)


class TestRoleRequired:
    def test_redirects_anonymous(self, app):
        from utils.decorators import role_required
        result = _invoke(app, None, role_required(UserRole.ADMIN))
        assert _is_redirect(result)

    def test_blocks_regular_user(self, app, db):
        from utils.decorators import role_required
        user = make_user(db, username='norm1')
        result = _invoke(app, user, role_required(UserRole.ADMIN))
        assert _is_redirect(result)

    def test_allows_admin(self, app, db):
        from utils.decorators import role_required
        user = make_admin(db, username='boss1')
        result = _invoke(app, user, role_required(UserRole.ADMIN))
        assert result == ('ok', 200)


class TestPlayerOnly:
    def test_blocks_moderator(self, app, db):
        from utils.decorators import player_only
        user = make_moderator(db, username='modplay1')
        result = _invoke(app, user, player_only)
        assert _is_redirect(result)

    def test_allows_developer(self, app, db):
        from utils.decorators import player_only
        user = make_developer(db, username='devplay1')
        result = _invoke(app, user, player_only)
        assert result == ('ok', 200)


class TestMaintenance:
    def test_blocks_player_when_feature_disabled(self, app, db):
        from models.system import SystemConfig
        from utils.decorators import check_maintenance
        with app.app_context():
            SystemConfig.set_value('maintenance_casino', 'true')
        user = make_user(db, username='maint1')
        result = _invoke(app, user, check_maintenance('casino'))
        assert _is_redirect(result)

    def test_allows_admin_during_feature_maintenance(self, app, db):
        from models.system import SystemConfig
        from utils.decorators import check_maintenance
        with app.app_context():
            SystemConfig.set_value('maintenance_casino', 'true')
        user = make_admin(db, username='maintadmin')
        result = _invoke(app, user, check_maintenance('casino'))
        assert result == ('ok', 200)


class TestDoubleVerification:
    def test_redirects_without_session(self, app, db):
        from utils.decorators import double_verification_required
        user = make_admin(db, username='dv1')
        result = _invoke(app, user, double_verification_required)
        assert _is_redirect(result)

    def test_allows_recent_verification(self, app, db):
        from utils.decorators import double_verification_required
        user = make_admin(db, username='dv2')
        result = _invoke(
            app, user, double_verification_required,
            session_data={'admin_verified_at': datetime.now(timezone.utc).isoformat()},
        )
        assert result == ('ok', 200)


class TestProhibitedContent:
    def test_blocks_urls(self):
        assert contains_prohibited_content('visit https://evil.com now') is True
        assert contains_prohibited_content('www.spam.test') is True

    def test_blocks_email(self):
        assert contains_prohibited_content('mail me at a@b.co') is True

    def test_blocks_phone(self):
        assert contains_prohibited_content('call 0598953362') is True

    def test_allows_clean_text(self):
        assert contains_prohibited_content('مرحبا يا شباب') is False
        assert contains_prohibited_content('') is False


class TestChatSendBlockReason:
    def test_not_authenticated(self):
        assert chat_send_block_reason(None) == 'not_authenticated'

    def test_banned_user(self, db):
        user = make_user(db, username='ban1', is_chat_banned=True)
        assert chat_send_block_reason(user) == 'banned'

    def test_muted_user(self, db):
        until = datetime.now(timezone.utc) + timedelta(hours=1)
        user = make_user(db, username='mute1', chat_muted_until=until.replace(tzinfo=None))
        assert chat_send_block_reason(user) == 'muted'

    def test_expired_mute_allows(self, db):
        until = datetime.now(timezone.utc) - timedelta(minutes=1)
        user = make_user(db, username='unmute1', chat_muted_until=until.replace(tzinfo=None))
        assert chat_send_block_reason(user) is None


class TestUserOnline:
    def test_recent_last_seen(self, db):
        user = make_user(db, username='on1')
        user.last_seen = datetime.now(timezone.utc)
        assert user_is_online(user, minutes=5) is True

    def test_stale_last_seen(self, db):
        user = make_user(db, username='off1')
        user.last_seen = datetime.now(timezone.utc) - timedelta(hours=1)
        assert user_is_online(user, minutes=5) is False


class TestNormalizeRoom:
    def test_known_room(self):
        assert normalize_room('trade') == 'trade'

    def test_unknown_falls_back_to_general(self):
        assert normalize_room('hacker_room') == 'general'


class TestModeratorCanAct:
    def test_mod_can_mute_player(self, db):
        mod = make_moderator(db, username='modact1')
        player = make_user(db, username='victim1')
        assert moderator_can_act(mod, player) is True

    def test_mod_cannot_mute_admin(self, db):
        from tests.support.factories import make_admin
        mod = make_moderator(db, username='modact2')
        admin = make_admin(db, username='adminact1')
        assert moderator_can_act(mod, admin) is False


class TestUploadSafety:
    def test_safe_path(self):
        assert is_safe_chat_upload_rel_path('uploads/chat/chat_1_abcd1234.png') is True

    def test_rejects_traversal(self):
        assert is_safe_chat_upload_rel_path('../etc/passwd') is False

    def test_valid_attachment_token(self):
        msg = '[[image:uploads/chat/chat_9_deadbeef.png|photo]]'
        assert validate_message_attachments(msg) is True

    def test_rejects_mixed_text_attachment(self):
        assert validate_message_attachments('hello [[image:uploads/chat/chat_1_abcd.png]]') is False

    def test_scan_upload_png(self):
        stream = BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        kind, ext, size = scan_upload_file('x.png', stream)
        assert kind == 'image'
        assert ext == 'png'
        assert size > 0

    def test_scan_rejects_unknown_type(self):
        stream = BytesIO(b'data')
        kind, err, size = scan_upload_file('x.exe', stream)
        assert kind is None
        assert err == 'unsupported_type'

    def test_scan_rejects_oversized(self):
        stream = MagicMock()
        stream.tell.return_value = MAX_CHAT_UPLOAD_BYTES + 1
        kind, err, _ = scan_upload_file('big.png', stream)
        assert err == 'too_large'


class TestResourceAudit:
    def test_default_not_allowed(self):
        assert is_resource_mutation_allowed() is False

    def test_allow_and_disallow(self):
        token = allow_resource_mutation()
        assert is_resource_mutation_allowed() is True
        disallow_resource_mutation(token)
        assert is_resource_mutation_allowed() is False


class TestConfigModule:
    def test_config_secret_key_exists(self):
        from config import Config
        assert Config.SECRET_KEY

    def test_test_config_flags(self):
        from config import TestConfig
        assert TestConfig.TESTING is True
        assert TestConfig.WTF_CSRF_ENABLED is False
        assert TestConfig.RATELIMIT_ENABLED is False

    def test_postgres_engine_options_have_pool_pre_ping(self):
        from config import Config
        opts = Config.SQLALCHEMY_ENGINE_OPTIONS
        assert opts.get('pool_pre_ping') is True


class TestExtensions:
    def test_extension_singletons_importable(self):
        from extensions import admin, babel, cache, csrf, db, limiter, login, mail, seo_manager
        assert db is not None
        assert login.login_view == 'main.login'
        assert cache is not None
        assert seo_manager is not None

    def test_admin_index_requires_admin(self, app, db):
        from extensions import MyAdminIndexView
        from tests.support.factories import make_admin, make_user
        admin_user = make_admin(db, username='extadmin')
        regular = make_user(db, username='extuser')
        view = MyAdminIndexView()
        with app.test_request_context('/'):
            from flask_login import login_user
            login_user(regular)
            assert view.is_accessible() is False
            login_user(admin_user)
            assert view.is_accessible() is True

    def test_platform_patch_on_windows(self):
        import platform
        from extensions import _patch_platform_for_restricted_windows
        _patch_platform_for_restricted_windows()
        release, version, csd, ptype = platform.win32_ver()
        assert isinstance(release, str)
        uname = platform.uname()
        assert uname.system
