"""Socket.IO handlers for live public chat."""
from __future__ import annotations

from flask_login import current_user

from extensions import socketio
from services.chat_security import PUBLIC_CHAT_ROOMS, normalize_room
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
