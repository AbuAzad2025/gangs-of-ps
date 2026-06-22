from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, request, url_for
from flask_babel import _
from flask_login import current_user

from extensions import db
from models.user import UserRole

bp = Blueprint('main', __name__)

REGISTERED_ROUTE_MODULES = ()


def register_main_routes():
    from . import (
        auth,
        core,
        gameplay,
        payment,
        social,
        economy,
        garage,
        developer,
        staff,
        search,
        graveyard,
        racing,
        errors,
        trend,
        black_market,
    )

    global REGISTERED_ROUTE_MODULES
    REGISTERED_ROUTE_MODULES = (
        auth,
        core,
        gameplay,
        payment,
        social,
        economy,
        garage,
        developer,
        staff,
        search,
        graveyard,
        racing,
        errors,
        trend,
        black_market,
    )
    return REGISTERED_ROUTE_MODULES


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        # Throttle last_seen DB writes (every ~90s) — cuts load on chat/market polls
        try:
            from flask import session
            now = datetime.now(timezone.utc)
            touch = True
            prev_raw = session.get('last_seen_touch')
            if prev_raw:
                try:
                    prev = datetime.fromisoformat(prev_raw)
                    if prev.tzinfo is None:
                        prev = prev.replace(tzinfo=timezone.utc)
                    touch = (now - prev).total_seconds() >= 90
                except Exception:
                    touch = True
            if touch:
                current_user.last_seen = now
                session['last_seen_touch'] = now.isoformat()
                db.session.commit()
        except Exception:
            db.session.rollback()

        # 1. Jail Check (Integration)
        if current_user.jail_until:
            now = datetime.now(timezone.utc)
            jail_until = current_user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)

            if jail_until > now:
                # User is in jail. Restrict access.
                endpoint = request.endpoint
                if not endpoint:
                    return

                # Allowed Prefixes
                if endpoint.startswith(
                        'jail.') or endpoint.startswith('static'):
                    return

                # Allow Developer Panel Access
                if current_user.role == UserRole.DEVELOPER and (
                        request.path.startswith('/developer')
                        or endpoint.startswith('admin.')):
                    return

                # Allowed Specific Endpoints (Auth & Communication)
                allowed_endpoints = {
                    'main.logout',
                    'main.messages',
                    'main.view_message',
                    'main.notifications',
                    'main.read_notification',
                    'main.read_all_notifications',
                    'main.delete_notification',
                    'main.messenger',
                    'main.messenger_conversations',
                    'main.messenger_messages',
                    'main.messenger_send',
                    'main.messenger_mark_read',
                    'main.messenger_delete',
                    'main.chat_lobby',
                    'main.chat_room',
                    'main.get_public_chat_messages',
                    'main.send_public_chat_message',
                    'main.public_chat_upload',
                    'main.get_online_users',
                    'main.random_match',
                    'main.chat_typing_get',
                    'main.chat_typing_set',
                    'main.chat_vip_upgrade',
                    'main.chat_vip_donate'
                }

                if endpoint in allowed_endpoints:
                    return

                # Prevent redirect loop
                if endpoint == 'jail.index':
                    return

                flash(_('🚫 لا يمكنك التجول وأنت في سجن عوفر!'), 'danger')
                return redirect(url_for('jail.index'))

        # 2. Resource Regeneration
        try:
            # Check if method exists (handling potential migration lag during
            # dev)
            if hasattr(current_user, 'regenerate_resources'):
                current_user.regenerate_resources()
                db.session.commit()
        except Exception:
            db.session.rollback()
