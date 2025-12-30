from flask import render_template, redirect, url_for, session, request, jsonify
from flask_login import current_user
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_
from extensions import db
from models.user import User
from models.combat import CombatLog
from models.hostess import Hostess
from . import bp

@bp.route('/@vite/client')
def vite_client_noop():
    return "", 204

@bp.route('/@react-refresh')
def react_refresh_noop():
    return "", 204

@bp.route('/api/user/stats')
def get_user_stats():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'energy': current_user.energy,
        'max_energy': current_user.max_energy,
        'money': current_user.money,
        'bullets': current_user.bullets,
        'diamonds': current_user.diamonds,
        'heat': current_user.heat_value(),
        'level': current_user.level,
        'exp': current_user.exp,
        'max_exp': current_user.max_exp,
        'rank_title': current_user.rank_title,
        'rank_progress': current_user.rank_progress_percent
    })

@bp.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['ar', 'en']:
        session['locale'] = lang
    return redirect(request.referrer or url_for('main.index'))

@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.hara'))
    
    # Calculate Stats
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)
    
    total_users = User.query.count()
    
    # Active Users (using last_daily_reward or last_crime or last_travel as proxy)
    active_users = User.query.filter(
        or_(
            User.last_daily_reward >= yesterday,
            User.last_crime >= yesterday,
            User.last_travel >= yesterday
        )
    ).count()
    
    new_users = User.query.filter(User.created_at >= yesterday).count()
    
    # Combat stats (Attacks in last 24h)
    battles_24h = CombatLog.query.filter(CombatLog.timestamp >= yesterday).count()
    
    # Economy
    total_money = db.session.query(func.sum(User.money)).scalar() or 0
    total_money_formatted = f"{total_money:,}"
    
    # Top Players
    top_players = User.query.order_by(User.level.desc(), User.exp.desc()).limit(5).all()
    
    # Fetch Jasmin for Landing
    jasmin = Hostess.query.filter(Hostess.name.ilike('%Jasmin%')).first()

    return render_template('index.html', 
                           total_users=total_users,
                           active_users=active_users,
                           new_users=new_users,
                           battles_24h=battles_24h,
                           total_money=total_money_formatted,
                           top_players=top_players,
                           jasmin=jasmin)
