from flask import Blueprint, make_response, url_for, current_app, render_template
from datetime import datetime, timedelta

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

@bp.route('/sitemap.xml')
def sitemap():
    """
    Generate sitemap.xml dynamically.
    """
    pages = []
    
    # Static pages (1.0 priority)
    # Add rules that don't take arguments
    for rule in current_app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0:
            # Skip admin, developer, and auth routes
            url = str(rule.rule)
            if any(x in url for x in ['/admin/', '/developer/', '/auth/', '/static/']):
                continue
            
            pages.append({
                "loc": url_for(rule.endpoint, _external=True),
                "lastmod": datetime.now().strftime("%Y-%m-%d"),
                "changefreq": "daily",
                "priority": "1.0" if url == "/" else "0.8"
            })

    # You can add dynamic pages here (e.g., news articles) if needed
    # Example:
    # from models.system import Announcement
    # posts = Announcement.query.filter_by(is_active=True).all()
    # for post in posts:
    #     pages.append({
    #         "loc": url_for('news.detail', id=post.id, _external=True),
    #         "lastmod": post.updated_at.strftime("%Y-%m-%d"),
    #         "changefreq": "weekly",
    #         "priority": "0.6"
    #     })

    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response
