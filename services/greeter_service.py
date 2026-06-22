"""Greeter hostess resolution and unified assistant chat."""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from flask import session
from flask_login import current_user

from extensions import db
from models.hostess import Hostess
from services.ai_hostess_service import AIHostessService
from services.chat_security import MAX_ASSISTANT_MESSAGE_LEN


def get_greeter_hostess(hostess_id: int | None = None) -> Optional[Hostess]:
    hostess = None
    if hostess_id:
        try:
            hostess = db.session.get(Hostess, int(hostess_id))
        except Exception:
            hostess = None
    if not hostess:
        hostess = Hostess.query.filter_by(role='greeter').first()
    if not hostess:
        hostess = Hostess.query.filter(
            (Hostess.name.ilike('%Jasmin%')) | (Hostess.name.ilike('%Jasmine%'))
        ).first()
    if not hostess:
        hostess = Hostess.query.first()
    return hostess


def _guest_id() -> int:
    if 'guest_id' not in session:
        session['guest_id'] = random.randint(1_000_000_000, 2_000_000_000)
    return int(session['guest_id'])


def process_assistant_message(
    message: str,
    hostess_id: int | None = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    """Returns (payload_dict, error_message, http_status)."""
    text = (message or '').strip()
    if not text:
        return None, 'Missing message', 400
    if len(text) > MAX_ASSISTANT_MESSAGE_LEN:
        return None, 'Message too long', 400

    # Public assistant is greeter-only (ignore arbitrary hostess_id).
    hostess = get_greeter_hostess()
    if not hostess:
        return None, 'Hostess not found', 404

    is_auth = bool(
        current_user
        and getattr(current_user, 'is_authenticated', False)
        and current_user.is_authenticated
    )

    if is_auth:
        user_context = {
            'id': int(current_user.id),
            'name': str(current_user.username or ''),
            'is_guest': False,
            'money': int(getattr(current_user, 'money', 0) or 0),
            'level': int(getattr(current_user, 'level', 0) or 0),
        }
        session_key = f'user_chat_history_{hostess.id}_{current_user.id}'
    else:
        user_context = {
            'id': _guest_id(),
            'name': 'Guest Player',
            'is_guest': True,
            'money': 0,
            'level': 0,
        }
        session_key = f'guest_chat_history_{hostess.id}'

    ai_service = AIHostessService()
    chat_history: List[Dict[str, str]] = session.get(session_key, [])

    try:
        response_text = ai_service.get_response(
            user_message=text,
            hostess_context=hostess.to_dict(),
            user_context=user_context,
            chat_history=chat_history,
        )
    except Exception:
        response_text = ai_service._rule_based_response(
            text, hostess.to_dict(), user_context)

    chat_history.append({'role': 'user', 'content': text})
    chat_history.append({'role': 'assistant', 'content': response_text})
    if len(chat_history) > 20:
        chat_history = chat_history[-20:]
    session[session_key] = chat_history
    session.modified = True

    return {
        'response': response_text,
        'hostess_name': hostess.name,
        'hostess_image': hostess.image,
        'hostess_id': hostess.id,
    }, None, 200
