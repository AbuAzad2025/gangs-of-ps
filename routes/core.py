from flask import (
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
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
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_24h_naive = last_24h.replace(tzinfo=None)

        total_money = db.session.query(func.sum(User.money)).scalar() or 0
        total_users = User.query.count()

        active_users = User.query.filter(
            (User.last_seen.isnot(None)) & (User.last_seen >= last_24h_naive)
        ).count()

        new_users = User.query.filter(
            User.created_at >= last_24h_naive,
        ).count()

        battles_24h = CombatLog.query.filter(
            CombatLog.timestamp >= last_24h_naive,
        ).count()

        top_players = (
            User.query.order_by(User.level.desc(), User.exp.desc())
            .limit(5)
            .all()
        )
        top_players_data = []
        for p in top_players:
            top_players_data.append({
                'username': p.username,
                'level': p.level,
                'avatar': p.avatar,
                'rank_title': getattr(p, 'rank_title', '')
            })

        try:
            from models.system import SystemConfig
            from services.season_service import get_current_season
            from services.world_event_service import get_active_world_event
            season = get_current_season()
            world_event = get_active_world_event()
            game_name = SystemConfig.get_value('game_name', 'عصابات فلسطين')
            game_tagline = SystemConfig.get_value('game_tagline', 'لعبة استراتيجية الجريمة والهيمنة')
            support_email = SystemConfig.get_value('support_email', current_app.config.get('SUPPORT_EMAIL', 'support@gangsofpalestine.com'))
            game_status = SystemConfig.get_value('game_status', current_app.config.get('GAME_STATUS', 'online'))
        except Exception:
            season = {'name': 'الموسم 1', 'days_left': 0, 'active': True}
            world_event = None
            game_name = 'عصابات فلسطين'
            game_tagline = 'لعبة استراتيجية الجريمة والهيمنة'
            support_email = current_app.config.get('SUPPORT_EMAIL', 'support@gangsofpalestine.com')
            game_status = current_app.config.get('GAME_STATUS', 'online')

        return {
            'total_money': int(total_money),
            'total_users': total_users,
            'active_users': active_users,
            'new_users': new_users,
            'battles_24h': battles_24h,
            'top_players': top_players_data,
            'game_name': game_name,
            'game_tagline': game_tagline,
            'support_email': support_email,
            'game_status': game_status,
            'season': season,
            'world_event': world_event,
        }
    except Exception as e:
        current_app.logger.error(f"Error calculating dashboard stats: {e}")
        return {
            'total_money': 0,
            'total_users': 0,
            'active_users': 0,
            'new_users': 0,
            'battles_24h': 0,
            'top_players': [],
            'game_name': 'عصابات فلسطين',
            'game_tagline': 'لعبة استراتيجية الجريمة والهيمنة',
            'support_email': current_app.config.get('SUPPORT_EMAIL', 'support@gangsofpalestine.com'),
            'game_status': current_app.config.get('GAME_STATUS', 'online'),
            'season': {'name': 'الموسم 1', 'days_left': 0, 'active': True},
            'world_event': None,
        }


@bp.route('/api/game/overview')
def game_overview():
    """Public game overview for dashboards and future UI polish."""
    stats = get_dashboard_stats()
    return jsonify({
        'game_name': stats.get('game_name'),
        'game_tagline': stats.get('game_tagline'),
        'status': stats.get('game_status', current_app.config.get('GAME_STATUS', 'online')),
        'version': current_app.config.get('APP_VERSION', '1.0.0'),
        'support_email': stats.get('support_email', current_app.config.get('SUPPORT_EMAIL', 'support@gangsofpalestine.com')),
        'players': {
            'total': stats.get('total_users'),
            'active_24h': stats.get('active_users'),
            'new_24h': stats.get('new_users'),
        },
        'economy': {
            'total_money': stats.get('total_money'),
            'battles_24h': stats.get('battles_24h'),
        },
        'season': stats.get('season'),
        'world_event': stats.get('world_event'),
        'top_players': stats.get('top_players', []),
    })


@bp.route('/api/health')
def health_check():
    """Simple operational health endpoint for production monitoring."""
    try:
        from models.system import SystemConfig
        game_status = SystemConfig.get_value('game_status', current_app.config.get('GAME_STATUS', 'online'))
        db.session.execute(db.select(1))
        healthy = True
        message = 'ok'
    except Exception as exc:
        current_app.logger.warning(f"Health check failed: {exc}")
        healthy = False
        message = 'degraded'
        game_status = current_app.config.get('GAME_STATUS', 'online')

    return jsonify({
        'status': 'ok' if healthy else 'error',
        'message': message,
        'game_status': game_status,
        'app_name': current_app.config.get('APP_NAME', 'عصابات فلسطين'),
        'app_version': current_app.config.get('APP_VERSION', '1.0.0'),
        'database': 'ok' if healthy else 'unavailable',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), (200 if healthy else 503)


@bp.route('/tiktok-promo')
def tiktok_promo():
    """Renders a special animated page for recording TikTok promos."""
    return render_template('promo_tiktok.html')


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

    user = db.session.get(User, int(session.get('_user_id') or current_user.id))
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    return jsonify(
        {
            'energy': user.energy,
            'max_energy': user.max_energy,
            'money': user.money,
            'bullets': user.bullets,
            'diamonds': user.diamonds,
            'heat': user.heat_value(),
            'level': user.level,
            'exp': user.exp,
            'max_exp': user.max_exp,
            'rank_title': user.rank_title,
            'rank_progress': user.rank_progress_percent,
        }
    )


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

    # Fetch Jasmin for Landing (Dynamic, may not be cached)
    # Search for both English 'Jasmin' and Arabic 'ياسمين'
    jasmin = Hostess.query.filter(
        or_(
            Hostess.name.ilike('%Jasmin%'),
            Hostess.name == 'ياسمين',
        )
    ).first()

    # Set SEO
    description = _(
        "انضم الآن إلى عصابات فلسطين، لعبة المتصفح الاستراتيجية الأقوى. "
        "عش حياة الجريمة، ابنِ إمبراطوريتك، سيطر على المدن الفلسطينية، "
        "ونافس آلاف اللاعبين العرب. تحدى الاحتلال، شارك في حروب العصابات، "
        "وتفاعل مع شخصيات ذكية. التسجيل مجاني واللعب فوري!"
    )
    description_en = (
        "Gangs of Palestine is an Arabic mafia strategy browser game. "
        "Build your empire across Palestinian cities and compete with thousands of players."
    )
    keywords = (
        "عصابات, العصابات الفلسطينية, عصابات فلسطين, لعبة عصابات, لعبة مافيا, مافيا, "
        "لعبة فلسطين, لعبة فلسطينية, فلسطين, المدن الفلسطينية, القدس, غزة, رام الله, نابلس, الخليل, جنين, "
        "لعبة اونلاين, لعبة متصفح, العاب متصفح, العاب استراتيجية, لعبة استراتيجية, RPG, "
        "حرب العصابات, حروب العصابات, قتال, معارك, "
        "دردشة, شات, غرف دردشة, دردشة عربية, دردشة تعارف, "
        "Gangs of Palestine, Palestine Mafia Game, Arab Mafia Game, Arabic Mafia Game, "
        "Arab Strategy Game, Arabic Strategy Game, Browser Game, Online RPG, Mafia Game"
    )
    title = _("عصابات فلسطين | لعبة مافيا عربية ولعبة عصابات في فلسطين (Gangs of Palestine)")
    lang = request.args.get("lang")
    languages = current_app.config.get("LANGUAGES", ["ar", "en"])
    language_value = (
        lang
        if lang in languages
        else current_app.config.get("BABEL_DEFAULT_LOCALE", "ar")
    )
    faq_ar_1 = (
        "عصابات فلسطين هي لعبة مافيا عربية استراتيجية على المتصفح (Online RPG). "
        "تبدأ من الصفر وتبني إمبراطوريتك عبر الجرائم والاقتصاد والعصابات."
    )
    faq_ar_2 = (
        "نعم، اللعب مجاني ويمكنك اللعب مباشرة من المتصفح بدون تحميل. "
        "كما يمكنك تثبيتها كتطبيق PWA على الجوال."
    )
    faq_ar_3 = (
        "نعم، يوجد غرف دردشة عربية عامة وغرف متخصصة مثل غرفة المبتدئين والتجارة "
        "وغرف أخرى."
    )
    faq_ar_4 = (
        "تشمل مدن فلسطين داخل اللعبة: القدس، غزة، رام الله، نابلس، الخليل، جنين، "
        "أريحا، بيت لحم، طولكرم وغيرها حسب التحديثات."
    )
    faq_en_1 = (
        "Yes. Gangs of Palestine is an Arabic mafia strategy browser game where you "
        "build an empire, join gangs, and compete with other players."
    )
    seo_manager.set(
        title=title,
        description=f"{description} {description_en}",
        keywords=keywords,
        schema={
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebPage",
                    "@id": f"{request.base_url}#webpage",
                    "url": request.base_url,
                    "name": str(title),
                    "description": f"{description} {description_en}",
                    "inLanguage": language_value,
                    "about": {"@id": request.url_root.rstrip("/") + "#game"},
                    "isPartOf": {"@id": request.url_root.rstrip("/") + "#website"},
                    "primaryImageOfPage": {
                        "@type": "ImageObject",
                        "url": url_for(
                            "static",
                            filename="images/azad_logo_white_on_dark.png",
                            _external=True,
                        ),
                    },
                },
                {
                    "@type": "FAQPage",
                    "@id": f"{request.base_url}#faq",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": "ما هي لعبة عصابات فلسطين؟",
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": faq_ar_1,
                            },
                        },
                        {
                            "@type": "Question",
                            "name": "هل اللعبة مجانية وهل تحتاج تحميل؟",
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": faq_ar_2,
                            },
                        },
                        {
                            "@type": "Question",
                            "name": "هل يوجد شات ودردشة عربية داخل اللعبة؟",
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": faq_ar_3,
                            },
                        },
                        {
                            "@type": "Question",
                            "name": "ما المدن الفلسطينية الموجودة داخل اللعبة؟",
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": faq_ar_4,
                            },
                        },
                        {
                            "@type": "Question",
                            "name": "Is Gangs of Palestine an Arabic mafia browser game?",
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": faq_en_1,
                            },
                        },
                    ],
                },
            ],
        },
    )
    seo_manager.add_breadcrumb(_("الرئيسية"), url_for('main.index'))

    return render_template(
        'index.html',
        total_users=stats['total_users'],
        active_users=stats['active_users'],
        new_users=stats['new_users'],
        battles_24h=stats['battles_24h'],
        total_money=total_money_formatted,
        top_players=stats['top_players'],
        game_name=stats.get('game_name', 'عصابات فلسطين'),
        game_status=stats.get('game_status', current_app.config.get('GAME_STATUS', 'online')),
        support_email=stats.get('support_email', current_app.config.get('SUPPORT_EMAIL', 'support@gangsofpalestine.com')),
        season=stats.get('season', {'name': 'الموسم 1', 'days_left': 0, 'active': True}),
        world_event=stats.get('world_event'),
        jasmin=jasmin,
        hide_sidebar=True,
    )


@bp.route('/:')
def index_colon():
    return redirect(url_for('main.index'), code=301)
