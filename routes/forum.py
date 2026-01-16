from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from flask_login import login_required, current_user
from extensions import db, limiter, seo_manager
from models import ForumCategory, ForumTopic, ForumPost
from forms.forum import CreateTopicForm, ReplyForm
from flask_babel import _
from datetime import datetime, timezone
from typing import Optional

bp = Blueprint('forum', __name__, url_prefix='/forum')


def _seo_excerpt(text: str, limit: int = 160) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    s = " ".join(s.split())
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "…"


def _iso(dt) -> Optional[str]:
    if not dt:
        return None
    if getattr(dt, "tzinfo", None) is None:
        try:
            dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    try:
        return dt.isoformat()
    except Exception:
        return None


@bp.route('/')
@limiter.limit("30 per minute")
def index():
    categories = (
        ForumCategory.query.order_by(ForumCategory.order).limit(20).all()
    )
    seo_manager.set(
        title=f"{_('المنتدى')} - {_('عصابات فلسطين')}",
        description=_(
            'منتدى عصابات فلسطين: نقاشات واستراتيجيات وتبادل خبرات بين '
            'اللاعبين.'
        ),
        keywords=_('منتدى, نقاش, عصابات فلسطين, استراتيجيات, لاعبون'),
    )
    seo_manager.add_breadcrumb(_("الرئيسية"), url_for('main.index'))
    seo_manager.add_breadcrumb(_("المنتدى"), url_for('forum.index'))
    return render_template(
        'forum/index.html',
        categories=categories,
        ForumTopic=ForumTopic,
    )


@bp.route('/category/<int:id>')
def category(id):
    category = ForumCategory.query.get_or_404(id)

    # Check permission
    if category.min_rank > 0:
        if not current_user.is_authenticated or (
            current_user.role.value < category.min_rank
        ):
            flash(_('عذراً، لا تملك الصلاحية لدخول هذا القسم.'), 'danger')
            return redirect(url_for('forum.index'))

    page = request.args.get('page', 1, type=int)
    topics = (
        ForumTopic.query.filter_by(category_id=id)
        .order_by(ForumTopic.is_pinned.desc(), ForumTopic.last_post_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    seo_manager.set(
        title=f"{category.title} - {_('المنتدى')} - {_('عصابات فلسطين')}",
        description=(category.description or category.title),
        keywords=_("منتدى, %(cat)s, عصابات فلسطين, نقاش, مواضيع")
        % {"cat": category.title},
    )
    if page and int(page) > 1:
        seo_manager.set(robots="noindex,follow")
    seo_manager.add_breadcrumb(_("الرئيسية"), url_for('main.index'))
    seo_manager.add_breadcrumb(_("المنتدى"), url_for('forum.index'))
    seo_manager.add_breadcrumb(
        category.title,
        url_for('forum.category', id=category.id),
    )

    return render_template(
        'forum/category.html',
        category=category,
        topics=topics,
    )


@bp.route('/topic/<int:id>', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def topic(id):
    topic = db.session.get(ForumTopic, id)
    if not topic:
        abort(404)

    page = request.args.get('page', 1, type=int)

    if topic.category and int(topic.category.min_rank or 0) > 0:
        if (not current_user.is_authenticated) or (
            current_user.role.value < int(topic.category.min_rank or 0)
        ):
            flash(_('عذراً، لا تملك الصلاحية لدخول هذا الموضوع.'), 'danger')
            return redirect(url_for('forum.index'))

    topic.views += 1
    db.session.commit()

    # SEO
    category_title = topic.category.title if topic.category else _("المنتدى")
    first_post = topic.posts.order_by(ForumPost.created_at.asc()).first()
    excerpt = _seo_excerpt(first_post.content if first_post else "", 160)
    page_url = url_for('forum.topic', id=topic.id, _external=True)
    created_iso = _iso(topic.created_at)
    modified_iso = _iso(topic.last_post_at)
    author_name = (
        getattr(getattr(first_post, "user", None), "username", None)
        or getattr(getattr(topic, "user", None), "username", None)
    )
    posts_count = topic.posts.count()
    keywords = _(
        "منتدى, موضوع, %(title)s, %(cat)s, عصابات فلسطين"
    ) % {"title": topic.title, "cat": category_title}
    seo_manager.set(
        title=f"{topic.title} - {category_title} - {_('عصابات فلسطين')}",
        description=(excerpt or topic.title),
        keywords=keywords,
        type="article",
        schema={
            "@context": "https://schema.org",
            "@type": "DiscussionForumPosting",
            "headline": topic.title,
            "text": (excerpt or topic.title),
            "url": page_url,
            "mainEntityOfPage": {"@type": "WebPage", "@id": page_url},
            **({"datePublished": created_iso} if created_iso else {}),
            **({"dateModified": modified_iso} if modified_iso else {}),
            **(
                {"author": {"@type": "Person", "name": author_name}}
                if author_name
                else {}
            ),
            **({"articleSection": category_title} if category_title else {}),
            "commentCount": posts_count,
            "interactionStatistic": [
                {
                    "@type": "InteractionCounter",
                    "interactionType": {"@type": "ViewAction"},
                    "userInteractionCount": int(topic.views or 0),
                },
                {
                    "@type": "InteractionCounter",
                    "interactionType": {"@type": "CommentAction"},
                    "userInteractionCount": int(posts_count or 0),
                },
            ],
        },
    )
    if page and int(page) > 1:
        seo_manager.set(robots="noindex,follow")
    seo_manager.add_breadcrumb(_("الرئيسية"), url_for('main.index'))
    seo_manager.add_breadcrumb(_("المنتدى"), url_for('forum.index'))
    seo_manager.add_breadcrumb(
        topic.category.title,
        url_for('forum.category', id=topic.category_id),
    )
    seo_manager.add_breadcrumb(topic.title, url_for('forum.topic', id=id))

    form = ReplyForm()

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            next_url = request.full_path.rstrip('?')
            return redirect(url_for('main.login', next=next_url))

        if topic.is_locked:
            flash(_('هذا الموضوع مغلق ولا يمكن الرد عليه.'), 'danger')
        else:
            post = ForumPost(
                topic_id=topic.id,
                user_id=current_user.id,
                content=form.content.data
            )
            topic.last_post_at = datetime.now(timezone.utc)
            db.session.add(post)
            db.session.commit()
            flash(_('تم إضافة ردك بنجاح!'), 'success')
            return redirect(
                url_for(
                    'forum.topic',
                    id=topic.id,
                    page=request.args.get('page', 1),
                )
            )

    posts = (
        ForumPost.query.filter_by(topic_id=id)
        .order_by(ForumPost.created_at.asc())
        .paginate(page=page, per_page=15, error_out=False)
    )

    return render_template(
        'forum/topic.html',
        topic=topic,
        posts=posts,
        form=form,
    )


@bp.route('/create/<int:category_id>', methods=['GET', 'POST'])
@login_required
def create_topic(category_id):
    category = db.session.get(ForumCategory, category_id)
    if not category:
        abort(404)

    seo_manager.set(
        title=f"{_('إنشاء موضوع')} - {category.title} - {_('المنتدى')}",
        description=_('إنشاء موضوع جديد في المنتدى.'),
        robots="noindex,nofollow",
    )

    form = CreateTopicForm()
    if form.validate_on_submit():
        topic = ForumTopic(
            category_id=category.id,
            user_id=current_user.id,
            title=form.title.data
        )
        db.session.add(topic)
        db.session.flush()

        post = ForumPost(
            topic_id=topic.id,
            user_id=current_user.id,
            content=form.content.data
        )
        db.session.add(post)
        db.session.commit()

        flash(_('تم إنشاء الموضوع بنجاح!'), 'success')
        return redirect(url_for('forum.topic', id=topic.id))

    return render_template(
        'forum/create_topic.html',
        category=category,
        form=form,
    )


@bp.route('/topic/<int:id>/delete', methods=['POST'])
@login_required
def delete_topic(id):
    topic = db.session.get(ForumTopic, id)
    if not topic:
        abort(404)

    if not (current_user.is_admin or current_user.is_moderator):
        abort(403)

    category_id = topic.category_id
    db.session.delete(topic)
    db.session.commit()
    flash(_('تم حذف الموضوع بنجاح'), 'success')
    return redirect(url_for('forum.category', id=category_id))


@bp.route('/topic/<int:id>/lock', methods=['POST'])
@login_required
def lock_topic(id):
    topic = db.session.get(ForumTopic, id)
    if not topic:
        abort(404)

    if not (current_user.is_admin or current_user.is_moderator):
        abort(403)

    topic.is_locked = not topic.is_locked
    db.session.commit()
    status = _('مغلق') if topic.is_locked else _('مفتوح')
    flash(_('تم تغيير حالة الموضوع إلى %(status)s', status=status), 'success')
    return redirect(url_for('forum.topic', id=id))


@bp.route('/topic/<int:id>/pin', methods=['POST'])
@login_required
def pin_topic(id):
    topic = db.session.get(ForumTopic, id)
    if not topic:
        abort(404)

    if not (current_user.is_admin or current_user.is_moderator):
        abort(403)

    topic.is_pinned = not topic.is_pinned
    db.session.commit()
    status = _('مُثبت') if topic.is_pinned else _('غير مُثبت')
    flash(
        _('تم تغيير حالة تثبيت الموضوع إلى %(status)s', status=status),
        'success',
    )
    return redirect(url_for('forum.topic', id=id))


@bp.route('/post/<int:id>/delete', methods=['POST'])
@login_required
def delete_post(id):
    post = db.session.get(ForumPost, id)
    if not post:
        abort(404)

    # Allow deletion if user is owner OR admin/mod
    if post.user_id != current_user.id and not (
        current_user.is_admin or current_user.is_moderator
    ):
        abort(403)

    topic_id = post.topic_id
    db.session.delete(post)
    db.session.commit()
    flash(_('تم حذف الرد بنجاح'), 'success')
    return redirect(url_for('forum.topic', id=topic_id))
