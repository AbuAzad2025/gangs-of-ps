from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db, limiter
from models import ForumCategory, ForumTopic, ForumPost, UserRank
from forms.forum import CreateTopicForm, ReplyForm
from flask_babel import _
from datetime import datetime, timezone

bp = Blueprint('forum', __name__, url_prefix='/forum')

@bp.route('/')
@limiter.limit("30 per minute")
def index():
    categories = ForumCategory.query.order_by(ForumCategory.order).limit(20).all()
    return render_template('forum/index.html', categories=categories, ForumTopic=ForumTopic)

@bp.route('/category/<int:id>')
def category(id):
    category = ForumCategory.query.get_or_404(id)
    
    # Check permission
    if category.min_rank > 0:
        if not current_user.is_authenticated or current_user.role.value < category.min_rank:
            flash(_('عذراً، لا تملك الصلاحية لدخول هذا القسم.'), 'danger')
            return redirect(url_for('forum.index'))

    page = request.args.get('page', 1, type=int)
    topics = ForumTopic.query.filter_by(category_id=id)\
        .order_by(ForumTopic.is_pinned.desc(), ForumTopic.last_post_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
        
    return render_template('forum/category.html', category=category, topics=topics)

@bp.route('/topic/<int:id>', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def topic(id):
    topic = db.session.get(ForumTopic, id)
    if not topic:
        abort(404)
    topic.views += 1
    db.session.commit()
    
    # SEO
    seo_manager.set(
        title=topic.title,
        description=topic.posts[0].content[:160] if topic.posts else topic.title,
        keywords=f"forum, topic, {topic.title}"
    )
    seo_manager.add_breadcrumb(_("المنتدى"), url_for('forum.index'))
    seo_manager.add_breadcrumb(topic.category.name, url_for('forum.category', id=topic.category_id))
    seo_manager.add_breadcrumb(topic.title, url_for('forum.topic', id=id))
    
    form = ReplyForm()
    
    if form.validate_on_submit():
        if not current_user.is_authenticated:
             return redirect(url_for('main.login', next=request.url))
             
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
            return redirect(url_for('forum.topic', id=topic.id, page=request.args.get('page', 1)))

    page = request.args.get('page', 1, type=int)
    posts = ForumPost.query.filter_by(topic_id=id)\
        .order_by(ForumPost.created_at.asc())\
        .paginate(page=page, per_page=15, error_out=False)
        
    return render_template('forum/topic.html', topic=topic, posts=posts, form=form)

@bp.route('/create/<int:category_id>', methods=['GET', 'POST'])
@login_required
def create_topic(category_id):
    category = db.session.get(ForumCategory, category_id)
    if not category:
        abort(404)
    
    form = CreateTopicForm()
    if form.validate_on_submit():
        topic = ForumTopic(
            category_id=category.id,
            user_id=current_user.id,
            title=form.title.data
        )
        db.session.add(topic)
        db.session.flush() # Get ID
        
        post = ForumPost(
            topic_id=topic.id,
            user_id=current_user.id,
            content=form.content.data
        )
        db.session.add(post)
        db.session.commit()
        
        flash(_('تم إنشاء الموضوع بنجاح!'), 'success')
        return redirect(url_for('forum.topic', id=topic.id))
        
    return render_template('forum/create_topic.html', category=category, form=form)

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
    flash(_('تم تغيير حالة تثبيت الموضوع إلى %(status)s', status=status), 'success')
    return redirect(url_for('forum.topic', id=id))

@bp.route('/post/<int:id>/delete', methods=['POST'])
@login_required
def delete_post(id):
    post = db.session.get(ForumPost, id)
    if not post:
        abort(404)
        
    # Allow deletion if user is owner OR admin/mod
    if post.user_id != current_user.id and not (current_user.is_admin or current_user.is_moderator):
        abort(403)
        
    topic_id = post.topic_id
    db.session.delete(post)
    db.session.commit()
    flash(_('تم حذف الرد بنجاح'), 'success')
    return redirect(url_for('forum.topic', id=topic_id))
