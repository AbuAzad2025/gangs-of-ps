from flask import Blueprint, make_response, url_for, request
from extensions import cache

bp = Blueprint('seo', __name__)


@bp.route('/robots.txt')
def robots():
    """
    Generate robots.txt
    """
    sitemap_url = request.url_root.rstrip("/") + url_for('seo.sitemap')
    rules = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /developer/",
        "Disallow: /api/",
        "Disallow: /socket.io/",
        "Disallow: /login",
        "Disallow: /register",
        "Disallow: /logout",
        "Disallow: /unconfirmed",
        "Disallow: /resend_confirmation",
        "Disallow: /confirm/",
        "Disallow: /captcha/",
        "Disallow: /profile/edit",
        "Disallow: /forum/create",
        "Disallow: /forum/topic/*/delete",
        "Disallow: /forum/topic/*/lock",
        "Disallow: /forum/topic/*/pin",
        "Disallow: /forum/post/*/delete",
        "",
        f"Sitemap: {sitemap_url}"
    ]
    response = make_response("\n".join(rules))
    response.headers["Content-Type"] = "text/plain"
    return response


@bp.route('/sitemap.xsl')
@cache.cached(timeout=86400)
def sitemap_xsl():
    """Styled XML Sitemap."""
    xsl_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<xsl:stylesheet version="1.0"',
        '    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"',
        '    xmlns:s="http://www.sitemaps.org/schemas/sitemap/0.9">',
        '  <xsl:output method="html" encoding="UTF-8"/>',
        '  <xsl:template match="/">',
        '    <html>',
        '      <head>',
        '        <meta charset="UTF-8"/>',
        '        <title>Sitemap</title>',
        '        <style>',
        '          body{font-family:system-ui,-apple-system,Segoe UI,',
        '          Roboto,Arial,sans-serif;',
        '          margin:24px;color:#222}',
        '          table{border-collapse:collapse;width:100%}',
        '          th,td{border:1px solid #ddd;padding:8px}',
        '          th{background:#f5f5f5;text-align:left}',
        '          tr:nth-child(even){background:#fafafa}',
        '          a{color:#0b5ed7;text-decoration:none}',
        '        </style>',
        '      </head>',
        '      <body>',
        '        <h1>Sitemap</h1>',
        '        <table>',
        '          <tr><th>URL</th><th>Changefreq</th><th>Priority</th></tr>',
        '          <xsl:for-each select="s:urlset/s:url">',
        '            <tr>',
        '              <td><a href="{s:loc}">',
        '                <xsl:value-of select="s:loc"/></a></td>',
        '              <td><xsl:value-of select="s:changefreq"/></td>',
        '              <td><xsl:value-of select="s:priority"/></td>',
        '            </tr>',
        '          </xsl:for-each>',
        '        </table>',
        '      </body>',
        '    </html>',
        '  </xsl:template>',
        '</xsl:stylesheet>',
    ]
    xsl = "\n".join(xsl_lines)
    return xsl, 200, {'Content-Type': 'text/xsl'}


@bp.route('/sitemap.xml')
@cache.cached(timeout=3600)
def sitemap():
    """Serve sitemap.xml for search engines."""
    base_root = request.url_root.rstrip("/")

    def absolute_url(path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        if not path_or_url.startswith("/"):
            path_or_url = "/" + path_or_url
        return base_root + path_or_url

    # List of static pages
    pages = []

    def add_page(
        loc,
        changefreq='monthly',
        priority='0.8',
        include_lang_variants=True,
    ):
        pages.append(
            {
                'loc': absolute_url(loc),
                'changefreq': changefreq,
                'priority': priority,
            }
        )
        if include_lang_variants:
            pages.append(
                {
                    'loc': f"{absolute_url(loc)}?lang=en",
                    'changefreq': changefreq,
                    'priority': priority,
                }
            )
            pages.append(
                {
                    'loc': f"{absolute_url(loc)}?lang=ar",
                    'changefreq': changefreq,
                    'priority': priority,
                }
            )

    add_page(url_for('main.index'), changefreq='daily', priority='1.0')
    for endpoint, changefreq, priority in [
        ('main.guide', 'monthly', '0.7'),
    ]:
        try:
            add_page(
                url_for(endpoint),
                changefreq=changefreq,
                priority=priority,
            )
        except Exception:
            pass

    # Add Public Modules
    try:
        add_page(
            url_for('main.organized_crimes'),
            changefreq='daily',
            priority='0.9',
        )
        add_page(
            url_for('graveyard.index'),
            changefreq='daily',
            priority='0.8',
        )
        add_page(
            url_for('news.index'),
            changefreq='daily',
            priority='0.8',
        )
        add_page(
            url_for('forum.index'),
            changefreq='always',
            priority='0.9',
        )
        add_page(
            url_for('main.leaderboard'),
            changefreq='daily',
            priority='0.8',
        )
    except Exception:
        pass

    # Dynamic Gangs (Top 10)
    try:
        from models.social import Gang
        top_gangs = Gang.query.order_by(Gang.level.desc()).limit(10).all()
        for gang in top_gangs:
            add_page(
                url_for('gang.view', gang_id=gang.id),
                changefreq='weekly',
                priority='0.7',
            )
    except Exception:
        pass

    try:
        from models import Announcement
        announcements = (
            Announcement.query.filter_by(is_active=True)
            .order_by(Announcement.created_at.desc())
            .limit(20)
            .all()
        )
        for a in announcements:
            add_page(
                url_for('news.detail', id=a.id),
                changefreq='weekly',
                priority='0.7',
            )
    except Exception:
        pass

    try:
        from models import ForumCategory, ForumTopic
        categories = (
            ForumCategory.query.filter_by(min_rank=0)
            .order_by(ForumCategory.order.asc())
            .limit(10)
            .all()
        )
        for c in categories:
            add_page(
                url_for('forum.category', id=c.id),
                changefreq='weekly',
                priority='0.7',
            )

        topics = (
            ForumTopic.query.join(
                ForumCategory,
                ForumTopic.category_id == ForumCategory.id,
            )
            .filter(ForumCategory.min_rank == 0)
            .order_by(ForumTopic.last_post_at.desc())
            .limit(20)
            .all()
        )
        for t in topics:
            add_page(
                url_for('forum.topic', id=t.id),
                changefreq='weekly',
                priority='0.6',
            )
    except Exception:
        pass

    # XML Construction
    xml_sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_sitemap += (
        f'<?xml-stylesheet type="text/xsl" '
        f'href="{url_for("seo.sitemap_xsl")}"?>\n'
    )
    xml_sitemap += (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    )

    for page in pages:
        xml_sitemap += '  <url>\n'
        xml_sitemap += f'    <loc>{page["loc"]}</loc>\n'
        xml_sitemap += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        xml_sitemap += f'    <priority>{page["priority"]}</priority>\n'
        xml_sitemap += '  </url>\n'

    xml_sitemap += '</urlset>'

    return xml_sitemap, 200, {'Content-Type': 'application/xml'}
