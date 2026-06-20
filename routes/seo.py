from flask import Blueprint, make_response, url_for, request
from extensions import cache

bp = Blueprint('seo', __name__)


@bp.route('/robots.txt')
@cache.cached(timeout=3600)
def robots():
    """
    Generate robots.txt
    """
    sitemap_url = url_for("seo.sitemap", _external=True)
    rules = [
        "User-agent: *",
        "Allow: /",
        "Allow: /gang/",
        "Allow: /gang/view",
        "Allow: /gang/view/",
        "Disallow: /gang/dashboard",
        "Disallow: /gang/create",
        "Disallow: /gang/edit",
        "Disallow: /gang/invites",
        "Disallow: /gang/accept_invite",
        "Disallow: /gang/reject_invite",
        "Disallow: /gang/leave",
        "Disallow: /admin/",
        "Disallow: /developer/",
        "Disallow: /api/",
        "Disallow: /socket.io/",
        "Disallow: /chat/room/",
        "Disallow: /chat/vip/",
        "Disallow: /hara",
        "Disallow: /bank/",
        "Disallow: /black_market/",
        "Disallow: /casino/",
        "Disallow: /combat/",
        "Disallow: /farm/",
        "Disallow: /factory/",
        "Disallow: /garage/",
        "Disallow: /inventory/",
        "Disallow: /market/",
        "Disallow: /police_chase/",
        "Disallow: /resources/",
        "Disallow: /travel/",
        "Disallow: /entertainment/",
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
    from datetime import date, datetime, timezone
    from flask import current_app
    from xml.sax.saxutils import escape as xml_escape

    base_root = request.url_root.rstrip("/")

    def absolute_url(path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        if not path_or_url.startswith("/"):
            path_or_url = "/" + path_or_url
        return base_root + path_or_url

    def _with_lang(loc: str, lang: str) -> str:
        sep = "&" if "?" in loc else "?"
        return f"{loc}{sep}lang={lang}"

    def _lastmod_iso(value):
        if not value:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None:
                try:
                    value = value.replace(tzinfo=timezone.utc)
                except Exception:
                    pass
            try:
                return value.date().isoformat()
            except Exception:
                return None
        if isinstance(value, date):
            try:
                return value.isoformat()
            except Exception:
                return None
        return None

    langs = list(current_app.config.get("LANGUAGES", ["ar", "en"]))
    langs = [lang_code for lang_code in langs if lang_code]
    if "ar" not in langs:
        langs.insert(0, "ar")
    if "en" not in langs:
        langs.append("en")
    langs = langs[:6]

    pages_by_loc = {}

    def add_page(
        loc,
        changefreq="monthly",
        priority="0.8",
        lastmod=None,
        include_lang_variants=True,
    ):
        abs_loc = absolute_url(loc)
        item = pages_by_loc.get(abs_loc) or {}
        item["loc"] = abs_loc
        item["changefreq"] = changefreq
        item["priority"] = priority
        item["include_lang_variants"] = bool(include_lang_variants)

        new_lastmod = _lastmod_iso(lastmod)
        if new_lastmod:
            old_lastmod = item.get("lastmod")
            if (not old_lastmod) or (new_lastmod > old_lastmod):
                item["lastmod"] = new_lastmod

        pages_by_loc[abs_loc] = item

    add_page(url_for("main.index"), changefreq="daily", priority="1.0")
    add_page(url_for("main.guide"), changefreq="monthly", priority="0.7")
    add_page(url_for("main.organized_crimes"), changefreq="daily", priority="0.9")
    add_page(url_for("main.trend"), changefreq="daily", priority="0.8")
    add_page(url_for("main.tiktok_promo"), changefreq="weekly", priority="0.6")
    add_page(url_for("graveyard.index"), changefreq="daily", priority="0.8")
    add_page(url_for("news.index"), changefreq="daily", priority="0.8")
    add_page(url_for("forum.index"), changefreq="always", priority="0.9")
    add_page(url_for("gang.index"), changefreq="daily", priority="0.8")
    add_page(url_for("main.leaderboard"), changefreq="daily", priority="0.8")
    add_page(url_for("main.chat_lobby"), changefreq="daily", priority="0.8")

    try:
        from models.social import Gang

        top_gangs = Gang.query.order_by(Gang.level.desc(), Gang.exp.desc()).limit(50).all()
        for gang in top_gangs:
            add_page(
                url_for("gang.view", gang_id=gang.id),
                changefreq="weekly",
                priority="0.7",
                lastmod=getattr(gang, "created_at", None),
            )
    except Exception:
        pass

    try:
        from models import Announcement

        announcements = (
            Announcement.query.filter_by(is_active=True)
            .order_by(Announcement.created_at.desc())
            .limit(50)
            .all()
        )
        for a in announcements:
            add_page(
                url_for("news.detail", id=a.id),
                changefreq="weekly",
                priority="0.7",
                lastmod=getattr(a, "created_at", None),
            )
    except Exception:
        pass

    try:
        from models import ForumCategory, ForumTopic

        categories = (
            ForumCategory.query.filter_by(min_rank=0)
            .order_by(ForumCategory.order.asc())
            .limit(30)
            .all()
        )
        for c in categories:
            add_page(
                url_for("forum.category", id=c.id),
                changefreq="weekly",
                priority="0.7",
                lastmod=getattr(c, "created_at", None),
            )

        topics = (
            ForumTopic.query.join(
                ForumCategory,
                ForumTopic.category_id == ForumCategory.id,
            )
            .filter(ForumCategory.min_rank == 0)
            .order_by(ForumTopic.last_post_at.desc())
            .limit(50)
            .all()
        )
        for t in topics:
            add_page(
                url_for("forum.topic", id=t.id),
                changefreq="weekly",
                priority="0.6",
                lastmod=getattr(t, "last_post_at", None) or getattr(t, "created_at", None),
            )
    except Exception:
        pass

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<?xml-stylesheet type="text/xsl" href="{url_for("seo.sitemap_xsl")}"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]

    for _, page in sorted(pages_by_loc.items(), key=lambda kv: kv[0]):
        loc = page["loc"]
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{xml_escape(loc)}</loc>")

        if page.get("include_lang_variants") and langs:
            try:
                xml_lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="x-default" '
                    f'href="{xml_escape(loc)}" />'
                )
                for lang in langs:
                    escaped_lang = xml_escape(lang)
                    escaped_href = xml_escape(_with_lang(loc, lang))
                    xml_lines.append(
                        f'    <xhtml:link rel="alternate" hreflang="{escaped_lang}" '
                        f'href="{escaped_href}" />'
                    )
            except Exception:
                pass

        lastmod = page.get("lastmod")
        if lastmod:
            xml_lines.append(f"    <lastmod>{xml_escape(lastmod)}</lastmod>")

        xml_lines.append(f"    <changefreq>{xml_escape(page['changefreq'])}</changefreq>")
        xml_lines.append(f"    <priority>{xml_escape(page['priority'])}</priority>")
        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")

    xml_sitemap = "\n".join(xml_lines) + "\n"
    return xml_sitemap, 200, {"Content-Type": "application/xml; charset=utf-8"}
