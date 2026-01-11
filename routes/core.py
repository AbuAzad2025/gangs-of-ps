from flask import render_template, redirect, url_for, session, request, jsonify, current_app
from flask_login import current_user
from flask_babel import gettext as _
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_
from extensions import db, seo_manager, cache
from models.user import User
from models.combat import CombatLog
from models.hostess import Hostess
from . import bp

@cache.cached(timeout=300, key_prefix='dashboard_stats')
def get_dashboard_stats():
    """
    Calculates global game statistics for the public landing page.
    Cached for 5 minutes to reduce DB load.
    """
    try:
        # Date Calculations
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_24h_naive = last_24h.replace(tzinfo=None)

        # 1. Total Money (Global Economy)
        total_money = db.session.query(func.sum(User.money)).scalar() or 0

        # 2. Total Registered Users
        total_users = User.query.count()

        # 3. Active Users (Logged in within last 24h)
        # Assuming 'last_seen' or similar field exists, falling back to 'last_daily_reward' or 'updated_at' if needed.
        # User model usually has 'last_seen' or we can infer from logs. 
        # For now, let's use a rough estimate or a specific field if available.
        # Checking User model previously, we saw 'last_daily_reward', 'last_crime'. 
        # Let's use 'last_daily_reward' >= last_24h as a proxy for "Active Today" 
        # OR just a random heuristic if strict tracking isn't enabled.
        # Better: Users created > 0 (All users are "active" in marketing terms :P)
        # But let's try to be real:
        active_users = User.query.filter(User.last_daily_reward >= last_24h_naive).count()

        # 4. New Users (Joined in last 24h)
        new_users = User.query.filter(User.created_at >= last_24h_naive).count()

        # 5. Battles in last 24h
        battles_24h = CombatLog.query.filter(CombatLog.timestamp >= last_24h_naive).count()

        # 6. Top Players (Level & Exp)
        top_players = User.query.order_by(User.level.desc(), User.exp.desc()).limit(5).all()
        # Convert to simple dicts to avoid detached instance errors in template if cached
        top_players_data = []
        for p in top_players:
            top_players_data.append({
                'username': p.username,
                'level': p.level,
                'avatar': p.avatar,
                'rank_title': p.rank_title
            })

        return {
            'total_money': int(total_money),
            'total_users': total_users,
            'active_users': active_users,
            'new_users': new_users,
            'battles_24h': battles_24h,
            'top_players': top_players_data
        }
    except Exception as e:
        current_app.logger.error(f"Error calculating dashboard stats: {e}")
        return {
            'total_money': 0,
            'total_users': 0,
            'active_users': 0,
            'new_users': 0,
            'battles_24h': 0,
            'top_players': []
        }

@bp.route('/@vite/client')
def vite_client_noop():
    return "", 204

@bp.route('/@react-refresh')
def react_refresh_noop():
    return "", 204




@bp.route('/api/user/stats')
def get_user_stats():
    """API for real-time user stats update in navbar."""
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
    """Switch user language."""
    if lang in ['ar', 'en']:
        session['locale'] = lang
    return redirect(request.referrer or url_for('main.index'))

@bp.route('/')
def index():
    """Landing Page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.hara'))
    
    # Fetch cached stats
    stats = get_dashboard_stats()
    
    total_money_formatted = f"{stats['total_money']:,}"
    
    # Fetch Jasmin for Landing (Dynamic, so maybe not cached or cached separately)
    # Search for both English 'Jasmin' and Arabic 'ياسمين'
    jasmin = Hostess.query.filter(or_(Hostess.name.ilike('%Jasmin%'), Hostess.name == 'ياسمين')).first()

    # Set SEO
    seo_manager.set(
        title=_("عصابات فلسطين - لعبة المافيا والاستراتيجية العربية الأولى"),
        description=_("انضم الآن إلى عصابات فلسطين، لعبة المتصفح الاستراتيجية الأقوى. عش حياة الجريمة، ابنِ إمبراطوريتك، سيطر على المدن الفلسطينية، ونافس آلاف اللاعبين العرب. تحدى الاحتلال، شارك في حروب العصابات، وتفاعل مع شخصيات ذكية. التسجيل مجاني واللعب فوري!"),
        keywords="عصابات فلسطين, لعبة مافيا, العاب استراتيجية, العاب اونلاين, العاب متصفح, فلسطين, القدس, غزة, حرب العصابات, العاب عربية, RPG, Mafia Game, Gangs of Palestine"
    )
    seo_manager.add_breadcrumb(_("الرئيسية"), url_for('main.index'))

    return render_template('index.html', 
                           total_users=stats['total_users'],
                           active_users=stats['active_users'],
                           new_users=stats['new_users'],
                           battles_24h=stats['battles_24h'],
                           total_money=total_money_formatted,
                           top_players=stats['top_players'],
                           jasmin=jasmin)
