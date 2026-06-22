"""Socket.IO helpers for public, private, and gang chat."""
from __future__ import annotations

from typing import Any, Dict


def chat_room_key(room: str) -> str:
    return f'chat-{(room or "general").strip().lower()}'


def dm_user_room(user_id: int) -> str:
    return f'dm-user-{int(user_id)}'


def gang_chat_room(gang_id: int) -> str:
    return f'gang-chat-{int(gang_id)}'


def emit_public_chat_message(room: str, payload: Dict[str, Any]) -> None:
    try:
        from extensions import socketio
        if not socketio:
            return
        socketio.emit('chat_message', payload, room=chat_room_key(room))
    except Exception:
        pass


def emit_public_chat_delete(room: str, msg_id: int) -> None:
    try:
        from extensions import socketio
        if not socketio:
            return
        socketio.emit(
            'chat_delete',
            {'id': int(msg_id)},
            room=chat_room_key(room))
    except Exception:
        pass


def emit_messenger_message(receiver_id: int, payload: Dict[str, Any]) -> None:
    try:
        from extensions import socketio
        if not socketio:
            return
        socketio.emit('messenger_message', payload, room=dm_user_room(receiver_id))
    except Exception:
        pass


def emit_gang_chat_message(gang_id: int, payload: Dict[str, Any]) -> None:
    try:
        from extensions import socketio
        if not socketio:
            return
        socketio.emit('gang_chat_message', payload, room=gang_chat_room(gang_id))
    except Exception:
        pass


def emit_gang_chat_delete(gang_id: int, msg_id: int) -> None:
    try:
        from extensions import socketio
        if not socketio:
            return
        socketio.emit(
            'gang_chat_delete',
            {'id': int(msg_id)},
            room=gang_chat_room(gang_id))
    except Exception:
        pass
