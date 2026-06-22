"""Socket.IO helpers for public chat."""
from __future__ import annotations

from typing import Any, Dict


def chat_room_key(room: str) -> str:
    return f'chat-{(room or "general").strip().lower()}'


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
