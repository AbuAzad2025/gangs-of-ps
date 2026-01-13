from flask import Blueprint, make_response, url_for, current_app, render_template
from datetime import datetime, timedelta
from extensions import cache

bp = Blueprint('seo', __name__)

@bp.route('/robots.txt')
def robots():
    """
    Generate robots.txt
    """
    rules = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /developer/",
        "Disallow: /auth/logout",
        "Disallow: /profile/edit",
        "",
        f"Sitemap: {url_for('seo.sitemap', _external=True)}"
    ]
    response = make_response("\n".join(rules))
    response.headers["Content-Type"] = "text/plain"
    return response

@bp.route('/sitemap.xsl')
@cache.cached(timeout=86400)
def sitemap_xsl():
    """Styled XML Sitemap."""
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
@cache.cached(timeout=3600)
def sitemap():
    """Serve sitemap.xml for search engines."""
    # Base URL
    base_url = url_for('main.index', _external=True)
    base_url_en = f"{base_url}?lang=en"
    base_url_ar = f"{base_url}?lang=ar"
    
    # List of static pages
    pages = []
    def add_page(loc, changefreq='monthly', priority='0.8', include_lang_variants=True):
        pages.append({'loc': loc, 'changefreq': changefreq, 'priority': priority})
        if include_lang_variants:
            pages.append({'loc': f"{loc}?lang=en", 'changefreq': changefreq, 'priority': priority})
            pages.append({'loc': f"{loc}?lang=ar", 'changefreq': changefreq, 'priority': priority})
    
    add_page(base_url, changefreq='daily', priority='1.0')
    add_page(url_for('main.login', _external=True))
    add_page(url_for('main.register', _external=True))
    add_page(url_for('main.guide', _external=True), changefreq='monthly', priority='0.7')
    
    # Add Public Modules
    try:
        add_page(url_for('main.organized_crimes', _external=True), changefreq='daily', priority='0.9')
        add_page(url_for('gang.index', _external=True), changefreq='daily', priority='0.9')
        add_page(url_for('graveyard.index', _external=True), changefreq='daily', priority='0.8')
        add_page(url_for('news.index', _external=True), changefreq='daily', priority='0.8')
        add_page(url_for('forum.index', _external=True), changefreq='always', priority='0.9')
        add_page(url_for('social.leaderboard', _external=True), changefreq='daily', priority='0.8')
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
    xml_sitemap += f'<?xml-stylesheet type="text/xsl" href="{url_for("seo.sitemap_xsl")}"?>\n'
    xml_sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        xml_sitemap += '  <url>\n'
        xml_sitemap += f'    <loc>{page["loc"]}</loc>\n'
        xml_sitemap += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        xml_sitemap += f'    <priority>{page["priority"]}</priority>\n'
        xml_sitemap += '  </url>\n'
        
    xml_sitemap += '</urlset>'
    
    return xml_sitemap, 200, {'Content-Type': 'application/xml'}
