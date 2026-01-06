from flask import Blueprint, request, jsonify, session, current_app
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models.hostess import Hostess
from models.combat import CombatLog
from models.log import UserLog
from services.ai_hostess_service import AIHostessService
from datetime import datetime, timezone, timedelta
from sqlalchemy import or_

bp = Blueprint('jasmin', __name__, url_prefix='/hostesses/jasmin')

@bp.route('/chat', methods=['POST'])
def chat():
    # 1. Validation
    msg = request.form.get('message')
    if not msg:
        return jsonify({'response': _('لم اسمعك جيدا؟')})

    # Ensure this is actually Jasmin
    jasmin = Hostess.query.filter(
        (Hostess.name == 'ياسمين') | 
        (Hostess.name.ilike('%Jasmin%')) | 
        (Hostess.name.ilike('%Jasmine%'))
    ).first()
    if not jasmin:
        return jsonify({'response': _('Error: Jasmin not found in system.')})

    # Concierge Mode: No hiring required, Open to Public (Guest & Users)
    
    # 2. Prepare Context (Specific to Jasmin)
    hostess_context = jasmin.to_dict()
    
    if current_user.is_authenticated:
        # Check Status
        now = datetime.now(timezone.utc)
        is_in_jail = current_user.jail_until and current_user.jail_until > now
        is_in_hospital = current_user.hospital_until and current_user.hospital_until > now
        
        # Check Last Battle (Last 1 hour)
        last_battle = CombatLog.query.filter(
            or_(CombatLog.attacker_id == current_user.id, CombatLog.defender_id == current_user.id),
            CombatLog.timestamp >= now - timedelta(hours=1)
        ).order_by(CombatLog.timestamp.desc()).first()
        
        last_battle_info = None
        if last_battle:
            if last_battle.winner_id == current_user.id:
                last_battle_info = "won"
            else:
                last_battle_info = "lost"

        # Check Last Crime (Last 10 minutes)
        last_crime = UserLog.query.filter_by(
            user_id=current_user.id, 
            action='CRIME'
        ).filter(
            UserLog.timestamp >= now - timedelta(minutes=10)
        ).order_by(UserLog.timestamp.desc()).first()

        last_crime_result = last_crime.result if last_crime else None

        user_context = {
            'id': current_user.id,
            'name': current_user.username,
            'money': current_user.money,
            'level': current_user.level,
            'health': current_user.health,
            'energy': current_user.energy,
            'bullets': current_user.bullets,
            'diamonds': current_user.diamonds,
            'rank': current_user.rank_title,
            'is_voice': request.form.get('is_voice') == 'true',
            'is_in_jail': is_in_jail,
            'is_in_hospital': is_in_hospital,
            'last_battle_result': last_battle_info,
            'last_crime_result': last_crime_result
        }
    else:
        user_context = {
            'id': 0,
            'name': 'Guest',
            'money': 0,
            'level': 0,
            'health': 100,
            'energy': 100,
            'rank': 'Visitor',
            'is_voice': request.form.get('is_voice') == 'true'
        }
    
    # 3. Chat History
    chat_history = session.get(f'chat_history_{jasmin.id}', [])
    
    # 4. AI Service
    service = AIHostessService()
    response_text = service.get_response(msg, hostess_context, user_context, chat_history)
    
    # 5. Update History
    chat_history.append({'role': 'user', 'content': msg})
    chat_history.append({'role': 'assistant', 'content': response_text})
    session[f'chat_history_{jasmin.id}'] = chat_history[-10:]
    
    return jsonify({
        'response': response_text,
        'voice_config': jasmin.voice_config,
        'personality_config': jasmin.personality_config
    })
