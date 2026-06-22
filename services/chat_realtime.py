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
