from flask import Blueprint, render_template, abort, url_for
from flask_babel import gettext as _
from models import Announcement
from extensions import db, seo_manager, limiter, cache

bp = Blueprint('news', __name__, url_prefix='/news')


@bp.route('/')
@limiter.limit("20 per minute")
@cache.cached(timeout=300)
def index():
    # SEO
    seo_manager.set(
        title=_("أخبار وتحديثات عصابات فلسطين"),
        description=_("تابع آخر أخبار وتحديثات لعبة عصابات فلسطين. كن أول من يعلم عن الفعاليات والميزات الجديدة."),
        keywords="news, updates, announcements, اخبار اللعبة, تحديثات, فعاليات")
    seo_manager.add_breadcrumb(_("الأخبار"), url_for('news.index'))

    # Show active announcements, ordered by newest first
    announcements = Announcement.query.filter_by(
        is_active=True).order_by(
        Announcement.created_at.desc()).limit(20).all()
    return render_template('news.html', announcements=announcements)


@bp.route('/<int:id>')
@limiter.limit("20 per minute")
@cache.cached(timeout=300)
def detail(id):
    announcement = db.session.get(Announcement, id)
    if not announcement:
        abort(404)
    if not announcement.is_active:
        abort(404)

    # SEO
    seo_manager.set(
        title=announcement.title,
        description=announcement.content[:160] if announcement.content else _("تفاصيل الخبر"),
        keywords="news, announcement, خبر"
    )
    seo_manager.add_breadcrumb(_("الأخبار"), url_for('news.index'))
    seo_manager.add_breadcrumb(
        announcement.title, url_for(
            'news.detail', id=id))

    return render_template('news_detail.html', announcement=announcement)
