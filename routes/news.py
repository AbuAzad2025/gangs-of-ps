from flask import Blueprint, render_template, abort
from flask_login import login_required
from models import Announcement

bp = Blueprint('news', __name__, url_prefix='/news')

@bp.route('/')
@login_required
def index():
    # Show active announcements, ordered by newest first
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).all()
    return render_template('news.html', announcements=announcements)

@bp.route('/<int:id>')
@login_required
def detail(id):
    announcement = db.session.get(Announcement, id)
    if not announcement:
        abort(404)
    if not announcement.is_active:
        abort(404)
    return render_template('news_detail.html', announcement=announcement)
