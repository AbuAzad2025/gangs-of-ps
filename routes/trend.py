from flask import render_template, url_for
from extensions import seo_manager
from models import User, Gang, CombatLog
from flask_babel import _
from . import bp


@bp.route('/trend')
def trend():
    # 1. Recent Big Battles (Last 24h)
    recent_battles = CombatLog.query.order_by(
        CombatLog.timestamp.desc()).limit(10).all()

    # 2. Top Gangs
    top_gangs = Gang.query.order_by(
        Gang.level.desc(),
        Gang.exp.desc()).limit(5).all()

    # 3. Recent Level Ups (Simulated by high level users for now or UserLog if we tracked it)
    # We'll just show top players
    top_players = User.query.order_by(User.level.desc()).limit(10).all()

    # 4. Total Stats
    total_users = User.query.count()
    total_gangs = Gang.query.count()

    # Set SEO
    seo_manager.set(
        title=_("الترند - أحداث عصابات فلسطين المباشرة"),
        description=_("تابع آخر المعارك، أقوى العصابات، وأخطر المجرمين في القدس وغزة والضفة. هل أنت مستعد للمنافسة؟"),
        keywords="ترند, عصابات فلسطين, معارك, ترتيب, ألعاب",
        image=url_for(
            'static',
            filename='images/trend_share.jpg',
            _external=True))
    seo_manager.add_breadcrumb(
        _("الترند"), url_for(
            'main.trend', _external=True))

    return render_template('trend.html',
                           battles=recent_battles,
                           top_gangs=top_gangs,
                           top_players=top_players,
                           total_users=total_users,
                           total_gangs=total_gangs)
