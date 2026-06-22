"""Socket.IO handlers for live chat (public, private, gang)."""
from __future__ import annotations

from flask_login import current_user

from extensions import socketio
from services.chat_security import PUBLIC_CHAT_ROOMS, normalize_room
from services.chat_realtime import dm_user_room, gang_chat_room
from services.vip_service import user_has_active_vip

if socketio:
    from flask_socketio import join_room, leave_room

    @socketio.on('chat_subscribe')
    def _chat_subscribe(data):
        data = data or {}
        room = normalize_room(data.get('room') or 'general')
        if room == 'vip':
            if not current_user.is_authenticated or not user_has_active_vip(current_user):
                return {'ok': False, 'error': 'vip_required'}
        if room == 'dating' and not current_user.is_authenticated:
            return {'ok': False, 'error': 'login_required'}
        if room == 'strangers' and current_user.is_authenticated:
            return {'ok': False, 'error': 'guests_only'}
        join_room(f'chat-{room}')
        return {'ok': True, 'room': room}

    @socketio.on('chat_unsubscribe')
    def _chat_unsubscribe(data):
        data = data or {}
        room = normalize_room(data.get('room') or 'general')
        leave_room(f'chat-{room}')
        return {'ok': True}

    @socketio.on('messenger_subscribe')
    def _messenger_subscribe(_data):
        if not current_user.is_authenticated:
            return {'ok': False, 'error': 'login_required'}
        join_room(dm_user_room(current_user.id))
        return {'ok': True}

    @socketio.on('messenger_unsubscribe')
    def _messenger_unsubscribe(_data):
        if not current_user.is_authenticated:
            return {'ok': False, 'error': 'login_required'}
        leave_room(dm_user_room(current_user.id))
        return {'ok': True}

    @socketio.on('gang_chat_subscribe')
    def _gang_chat_subscribe(data):
        if not current_user.is_authenticated:
            return {'ok': False, 'error': 'login_required'}
        data = data or {}
        try:
            gang_id = int(data.get('gang_id') or 0)
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'invalid_gang'}
        if not gang_id or int(current_user.gang_id or 0) != gang_id:
            return {'ok': False, 'error': 'forbidden'}
        join_room(gang_chat_room(gang_id))
        return {'ok': True, 'gang_id': gang_id}

    @socketio.on('gang_chat_unsubscribe')
    def _gang_chat_unsubscribe(data):
        if not current_user.is_authenticated:
            return {'ok': False, 'error': 'login_required'}
        data = data or {}
        try:
            gang_id = int(data.get('gang_id') or 0)
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'invalid_gang'}
        if gang_id:
            leave_room(gang_chat_room(gang_id))
        return {'ok': True}
