from flask import render_template, redirect, url_for, session, request, jsonify
from flask_login import current_user
from flask_babel import gettext as _
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_
from extensions import db, seo_manager
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

@bp.route('/robots.txt')
def robots():
    """Serve robots.txt for search engines."""
    content = "User-agent: *\nAllow: /\nSitemap: " + url_for('main.sitemap', _external=True)
    return content, 200, {'Content-Type': 'text/plain'}

@bp.route('/sitemap.xsl')
def sitemap_xsl():
    xsl = '<?xml version="1.0" encoding="UTF-8"?>\n' \
          '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:s="http://www.sitemaps.org/schemas/sitemap/0.9">\n' \
          '  <xsl:output method="html" encoding="UTF-8"/>\n' \
          '  <xsl:template match="/">\n' \
          '    <html>\n' \
          '      <head>\n' \
          '        <meta charset="UTF-8"/>\n' \
          '        <title>Sitemap</title>\n' \
          '        <style>\n' \
          '          body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px;color:#222}\n' \
          '          table{border-collapse:collapse;width:100%}\n' \
          '          th,td{border:1px solid #ddd;padding:8px}\n' \
          '          th{background:#f5f5f5;text-align:left}\n' \
          '          tr:nth-child(even){background:#fafafa}\n' \
          '          a{color:#0b5ed7;text-decoration:none}\n' \
          '        </style>\n' \
          '      </head>\n' \
          '      <body>\n' \
          '        <h1>Sitemap</h1>\n' \
          '        <table>\n' \
          '          <tr><th>URL</th><th>Changefreq</th><th>Priority</th></tr>\n' \
          '          <xsl:for-each select="s:urlset/s:url">\n' \
          '            <tr>\n' \
          '              <td><a href="{s:loc}"><xsl:value-of select="s:loc"/></a></td>\n' \
          '              <td><xsl:value-of select="s:changefreq"/></td>\n' \
          '              <td><xsl:value-of select="s:priority"/></td>\n' \
          '            </tr>\n' \
          '          </xsl:for-each>\n' \
          '        </table>\n' \
          '      </body>\n' \
          '    </html>\n' \
          '  </xsl:template>\n' \
          '</xsl:stylesheet>'
    return xsl, 200, {'Content-Type': 'text/xsl'}

@bp.route('/sitemap.xml')
def sitemap():
    """Serve sitemap.xml for search engines."""
    # Base URL
    base_url = url_for('main.index', _external=True)
    
    # List of static pages
    pages = [
        {'loc': base_url, 'changefreq': 'daily', 'priority': '1.0'},
        {'loc': url_for('main.login', _external=True), 'changefreq': 'monthly', 'priority': '0.8'},
        {'loc': url_for('main.register', _external=True), 'changefreq': 'monthly', 'priority': '0.8'},
        {'loc': url_for('main.guide', _external=True), 'changefreq': 'monthly', 'priority': '0.7'},
    ]
    
    # Add Public Modules
    try:
        pages.append({'loc': url_for('main.organized_crimes', _external=True), 'changefreq': 'daily', 'priority': '0.9'})
        pages.append({'loc': url_for('gang.index', _external=True), 'changefreq': 'daily', 'priority': '0.9'})
        pages.append({'loc': url_for('graveyard.index', _external=True), 'changefreq': 'daily', 'priority': '0.8'})
        pages.append({'loc': url_for('news.index', _external=True), 'changefreq': 'daily', 'priority': '0.8'})
        pages.append({'loc': url_for('forum.index', _external=True), 'changefreq': 'always', 'priority': '0.9'})
        pages.append({'loc': url_for('social.leaderboard', _external=True), 'changefreq': 'daily', 'priority': '0.8'})
    except Exception:
        pass 

    # Dynamic Gangs (Top 10)
    try:
        from models.social import Gang
        top_gangs = Gang.query.order_by(Gang.level.desc()).limit(10).all()
        for g in top_gangs:
             pages.append({'loc': url_for('gang.view', gang_id=g.id, _external=True), 'changefreq': 'weekly', 'priority': '0.7'})
    except Exception:
        pass

    # XML Construction
    xml_sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_sitemap += f'<?xml-stylesheet type="text/xsl" href="{url_for("main.sitemap_xsl")}"?>\n'
    xml_sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        xml_sitemap += '  <url>\n'
        xml_sitemap += f'    <loc>{page["loc"]}</loc>\n'
        xml_sitemap += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        xml_sitemap += f'    <priority>{page["priority"]}</priority>\n'
        xml_sitemap += '  </url>\n'
        
    xml_sitemap += '</urlset>'
    
    return xml_sitemap, 200, {'Content-Type': 'application/xml'}

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
                           total_users=total_users,
                           active_users=active_users,
                           new_users=new_users,
                           battles_24h=battles_24h,
                           total_money=total_money_formatted,
                           top_players=top_players,
                           jasmin=jasmin)
