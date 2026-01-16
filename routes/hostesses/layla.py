from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from flask_babel import _
from extensions import limiter
from models.hostess import Hostess
from services.ai_hostess_service import AIHostessService
from datetime import datetime, timezone

bp = Blueprint('layla', __name__, url_prefix='/hostesses/layla')


@bp.route('/chat', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def chat():
    # 1. Validation
    msg = request.form.get('message')
    if not msg:
        return jsonify({'response': _('لم اسمعك جيدا؟')})

    # Ensure this is actually Layla
    layla = Hostess.query.filter(
        (Hostess.name == 'ليلى') |
        (Hostess.name.ilike('%Layla%'))
    ).first()
    if not layla:
        return jsonify({'response': _('Error: Layla not found in system.')})

    if current_user.active_hostess_id != layla.id:
        return jsonify(
            {'response': _('عذرا، يجب عليك التعاقد معي (ليلى) اولا.')})

    # Check contract expiry
    now = datetime.now(timezone.utc)
    if not current_user.casino_luck_until:
        return jsonify({'response': _('انتهى وقتنا. ادفع اذا اردت المزيد.')})

    luck_until = current_user.casino_luck_until
    if luck_until.tzinfo is None:
        luck_until = luck_until.replace(tzinfo=timezone.utc)

    if luck_until <= now:
        return jsonify({'response': _('انتهى وقتنا. ادفع اذا اردت المزيد.')})

    # 2. Prepare Context
    hostess_context = layla.to_dict()

    user_context = {
        'id': current_user.id,
        'name': current_user.username,
        'money': current_user.money,
        'level': current_user.level,
        'health': current_user.health,
        'energy': current_user.energy,
        'rank': current_user.rank_title,
        'is_voice': request.form.get('is_voice') == 'true'
    }

    # 3. Chat History
    chat_history = session.get(f'chat_history_{layla.id}', [])

    # 4. AI Service
    service = AIHostessService()
    response_text = service.get_response(
        msg, hostess_context, user_context, chat_history)

    # 5. Update History
    chat_history.append({'role': 'user', 'content': msg})
    chat_history.append({'role': 'assistant', 'content': response_text})
    session[f'chat_history_{layla.id}'] = chat_history[-10:]

    return jsonify({
        'response': response_text,
        'voice_config': layla.voice_config,
        'personality_config': layla.personality_config
    })
