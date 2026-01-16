from flask import render_template, redirect, url_for, flash, abort, request, current_app, jsonify, session
from flask_login import login_required, current_user
from extensions import db, limiter, cache
from sqlalchemy import or_
from sqlalchemy.exc import ProgrammingError, OperationalError
from models import Gang, Message, User, Notification, CombatLog, Hostess
from models.social import PublicChat, PrivateChat, Friendship
from models.user import UserRole
from models.system import SystemConfig, SecurityLog
from . import bp
from flask_babel import _
from datetime import datetime, timezone, timedelta
import os
import re
import json
from werkzeug.utils import secure_filename
import uuid
import secrets
from services.budget_service import BudgetService
from services.revenue_service import RevenueService
from services.resource_service import ResourceService
from services.ai_hostess_service import AIHostessService


def contains_prohibited_content(text):
    # URLs
    if re.search(r'(https?://|www\.)\S+', text):
        return True
    # Emails
    if re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text):
        return True
    # Phone numbers (7+ digits)
    if re.search(r'\d[\d\s-]{6,}\d', text):
        return True
    return False


def _is_privileged_chat_user(u) -> bool:
    try:
        return bool(
            u and getattr(
                u,
                "role",
                None) in {
                UserRole.DEVELOPER,
                UserRole.SUPER_ADMIN,
                UserRole.ADMIN,
                UserRole.MODERATOR})
    except Exception:
        return False


def _strangers_access_reason(u):
    if not (u and getattr(u, "is_authenticated", False)):
        return _('هذه الغرفة تتطلب تسجيل الدخول.')
    if _is_privileged_chat_user(u):
        return None
    if getattr(u, "is_suspicious", False):
        return _('حسابك تحت المراجعة حالياً.')
    if not getattr(u, "birthdate", None):
        return _('أكمل بيانات ملفك (تاريخ الميلاد) للدخول.')
    try:
        age = u.age
    except Exception:
        age = None
    if age is None:
        return _('أكمل بيانات ملفك (تاريخ الميلاد) للدخول.')
    if age < 18:
        return _('هذه الغرفة متاحة لمن عمره 18+ فقط.')
    return None


def _get_or_create_guest_chat_user() -> User:
    guest_user_id = session.get('guest_chat_user_id')
    if guest_user_id:
        u = db.session.get(User, int(guest_user_id))
        if u and u.role == UserRole.GUEST:
            return u

    for attempt in range(8):
        suffix = secrets.token_urlsafe(6).replace('-', '').replace('_', '')
        username = f"Guest{suffix}"
        if not User.query.filter_by(username=username).first():
            u = User(
                username=username,
                role=UserRole.GUEST,
                email=None,
                is_verified=False,
                avatar='default.png')
            u.set_password(secrets.token_urlsafe(32))
            db.session.add(u)
            db.session.commit()
            session['guest_chat_user_id'] = u.id
            return u

    u = User(
        username=f"Guest{secrets.token_hex(6)}",
        role=UserRole.GUEST,
        email=None,
        is_verified=False,
        avatar='default.png')
    u.set_password(secrets.token_urlsafe(32))
    db.session.add(u)
    db.session.commit()
    session['guest_chat_user_id'] = u.id
    return u


def _friendship_key(a_id: int, b_id: int):
    a_id = int(a_id)
    b_id = int(b_id)
    if a_id <= b_id:
        return a_id, b_id
    return b_id, a_id


@bp.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    notifs = current_user.notifications.order_by(
        Notification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('notifications.html', notifications=notifs)


@bp.route('/notifications/read/<int:id>', methods=['GET', 'POST'])
@login_required
def read_notification(id):
    notif = db.session.get(Notification, id)
    if not notif:
        abort(404)
    if notif.user_id != current_user.id:
        abort(403)

    if not notif.is_read:
        notif.is_read = True
        db.session.commit()

    if notif.link and (notif.link.startswith(
            '/') or notif.link.startswith(request.host_url)):
        return redirect(notif.link)
    return redirect(url_for('main.notifications'))


@bp.route('/notifications/read_all', methods=['POST'])
@login_required
def read_all_notifications():
    current_user.notifications.filter_by(
        is_read=False).update({'is_read': True})
    db.session.commit()
    flash(_('تم تحديد الكل كمقروء.'), 'success')
    return redirect(url_for('main.notifications'))


@bp.route('/notifications/delete/<int:id>', methods=['POST'])
@login_required
def delete_notification(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id != current_user.id:
        abort(403)

    db.session.delete(notif)
    db.session.commit()
    flash(_('تم حذف الإشعار.'), 'success')
    return redirect(url_for('main.notifications'))


@bp.route('/gangs')
@login_required
def gangs():
    # Redirect to the main gang blueprint index
    return redirect(url_for('gang.index'))


@bp.route('/messages')
@login_required
def messages():
    box = request.args.get('box', 'inbox')
    page = request.args.get('page', 1, type=int)

    if box == 'sent':
        messages_query = Message.query.filter_by(
            sender_id=current_user.id,
            deleted_by_sender=False).order_by(
            Message.timestamp.desc())
        title = _('البريد الصادر')
    else:
        now = datetime.now(timezone.utc)
        messages_query = Message.query.filter_by(
            receiver_id=current_user.id,
            deleted_by_receiver=False).filter(
            (Message.delivery_time <= now) | (
                Message.delivery_time is None)).order_by(
                Message.timestamp.desc())
        title = _('البريد الوارد')

    messages = messages_query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        'messages.html',
        messages=messages,
        box=box,
        title=title)


@bp.route('/messages/view/<int:msg_id>')
@login_required
def view_message(msg_id):
    msg = db.session.get(Message, msg_id)
    if not msg:
        abort(404)

    # Check permissions
    if msg.sender_id != current_user.id and msg.receiver_id != current_user.id:
        abort(403)

    # Mark as read if receiver
    if msg.receiver_id == current_user.id and not msg.is_read:
        msg.is_read = True
        db.session.commit()

    return render_template('view_message.html', message=msg)


@bp.route('/invite')
@login_required
def invite_friends():
    # Ensure user has a code (migration for old users)
    if not current_user.referral_code:
        import secrets
        current_user.referral_code = secrets.token_hex(4)
        db.session.commit()

    referral_link = url_for(
        'main.register',
        ref=current_user.referral_code,
        _external=True)

    # Stats: Count pending and completed referrals
    # 'referrals_sent' is the backref from Referral model
    pending_count = 0
    completed_count = 0
    referrals_list = []

    if hasattr(current_user, 'referrals_sent'):
        for ref in current_user.referrals_sent:
            if ref.status == 'completed':
                completed_count += 1
            else:
                pending_count += 1
            referrals_list.append(ref)

    # Set Open Graph tags for sharing
    from extensions import seo_manager
    seo_manager.set(
        title=_(
            "انضم لعصابة %(user)s في عصابات فلسطين",
            user=current_user.username),
        description=_("ساعدني في السيطرة على المدينة! سجل الآن واحصل على مكافآت حصرية."),
        image=url_for(
            'static',
            filename='images/hostesses/jasmine.png',
            _external=True))

    return render_template('invite_friends.html',
                           link=referral_link,
                           pending=pending_count,
                           completed=completed_count,
                           referrals=referrals_list)


@bp.route('/messages/send', methods=['GET', 'POST'])
@login_required
def send_message():
    if request.method == 'POST':
        receiver_username = request.form.get('receiver')
        subject = request.form.get('subject')
        body = request.form.get('body')

        receiver = User.query.filter_by(username=receiver_username).first()

        if not receiver:
            flash(_('المستخدم غير موجود!'), 'danger')
            return redirect(url_for('main.send_message'))

        if receiver.id == current_user.id:
            flash(_('لا يمكنك مراسلة نفسك!'), 'danger')
            return redirect(url_for('main.send_message'))

        msg = Message(
            sender_id=current_user.id,
            receiver_id=receiver.id,
            subject=subject,
            body=body
        )
        db.session.add(msg)
        db.session.commit()

        flash(_('تم إرسال الرسالة بنجاح!'), 'success')
        return redirect(url_for('main.messages', box='sent'))

    receiver_arg = request.args.get('to')
    subject_arg = request.args.get('subject', '')
    if subject_arg and not subject_arg.startswith('Re:'):
        subject_arg = 'Re: ' + subject_arg

    return render_template(
        'send_message.html',
        receiver=receiver_arg,
        subject=subject_arg)


@bp.route('/messages/delete/<int:msg_id>', methods=['POST'])
@login_required
def delete_message(msg_id):
    msg = db.session.get(Message, msg_id)
    if not msg:
        abort(404)

    if msg.receiver_id == current_user.id:
        msg.deleted_by_receiver = True
    elif msg.sender_id == current_user.id:
        msg.deleted_by_sender = True
    else:
        abort(403)

    if msg.deleted_by_sender and msg.deleted_by_receiver:
        db.session.delete(msg)

    db.session.commit()
    flash(_('تم حذف الرسالة.'), 'success')
    return redirect(
        url_for(
            'main.messages',
            box=request.args.get(
                'box',
                'inbox')))


@bp.route('/messages/bulk_delete', methods=['POST'])
@login_required
def bulk_delete_messages():
    msg_ids = request.form.getlist('msg_ids')
    box = request.form.get('box', 'inbox')

    if not msg_ids:
        flash(_('لم يتم تحديد أي رسالة!'), 'warning')
        return redirect(url_for('main.messages', box=box))

    try:
        # Convert IDs to integers
        msg_ids = [int(mid) for mid in msg_ids]

        # Limit to 50 messages to prevent abuse/memory issues
        msg_ids = msg_ids[:50]

        # Optimization: Fetch all messages in one query
        messages = Message.query.filter(Message.id.in_(msg_ids)).all()

        count = 0
        for msg in messages:
            if msg.receiver_id == current_user.id and box == 'inbox':
                msg.deleted_by_receiver = True
                count += 1
            elif msg.sender_id == current_user.id and box == 'sent':
                msg.deleted_by_sender = True
                count += 1

            if msg.deleted_by_sender and msg.deleted_by_receiver:
                db.session.delete(msg)

        db.session.commit()
        if count > 0:
            flash(_('تم حذف %(count)d رسالة.', count=count), 'success')
    except ValueError:
        flash(_('بيانات غير صالحة'), 'danger')

    return redirect(url_for('main.messages', box=box))


@bp.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    now = datetime.now(timezone.utc)

    # Get recent combat activity
    combat_logs = CombatLog.query.filter(
        or_(CombatLog.attacker_id == user.id, CombatLog.defender_id == user.id)
    ).order_by(CombatLog.timestamp.desc()).limit(10).all()

    # Calculate stats
    total_fights = CombatLog.query.filter(
        or_(CombatLog.attacker_id == user.id, CombatLog.defender_id == user.id)
    ).count()

    wins = CombatLog.query.filter_by(winner_id=user.id).count()
    win_rate = int((wins / total_fights) * 100) if total_fights > 0 else 0

    budget = None
    budget_range = (request.args.get('budget_range') or '30d').strip()
    can_view_budget = (current_user.id == user.id) or (
        current_user.role.value >= UserRole.MODERATOR.value)
    if can_view_budget:
        budget = BudgetService.compute_user_budget(user.id, budget_range)

    revenue_report = None
    revenue_month = (request.args.get('rev_month') or '').strip()
    revenue_search = (request.args.get('rev_q') or '').strip()
    can_view_revenue = (user.id == current_user.id) and (
        current_user.role.value >= UserRole.DEVELOPER.value)
    if can_view_revenue:
        revenue_report = RevenueService.real_money_report(
            month=revenue_month or None, search=revenue_search or None)

    friendship_state = None
    friends_list = []
    friend_requests_in = []
    friend_requests_out = []
    pending_friends_in_count = 0

    try:
        if current_user.id != user.id:
            u1, u2 = _friendship_key(current_user.id, user.id)
            rel = Friendship.query.filter_by(user1_id=u1, user2_id=u2).first()
            if rel:
                if rel.status == 'accepted':
                    friendship_state = 'friends'
                elif rel.status == 'pending':
                    friendship_state = 'outgoing' if int(
                        rel.requester_id) == int(
                        current_user.id) else 'incoming'
                elif rel.status == 'blocked':
                    friendship_state = 'blocked'
            if not friendship_state:
                friendship_state = 'none'
        else:
            rels = Friendship.query.filter(
                or_(Friendship.user1_id == current_user.id, Friendship.user2_id == current_user.id)
            ).all()
            accepted = [r for r in rels if r.status == 'accepted']
            pending_in = [
                r for r in rels if r.status == 'pending' and int(
                    r.requester_id) != int(
                    current_user.id)]
            pending_out = [
                r for r in rels if r.status == 'pending' and int(
                    r.requester_id) == int(
                    current_user.id)]

            ids = []
            for r in accepted:
                ids.append(r.other_user_id(current_user.id))
            for r in pending_in:
                ids.append(r.other_user_id(current_user.id))
            for r in pending_out:
                ids.append(r.other_user_id(current_user.id))
            ids = sorted({int(x) for x in ids if x})
            users_by_id = {}
            if ids:
                users_by_id = {
                    u.id: u for u in User.query.filter(
                        User.id.in_(ids)).all()}

            friends_list = [
                {
                    'user': users_by_id.get(
                        r.other_user_id(
                            current_user.id)), 'rel': r} for r in accepted if users_by_id.get(
                    r.other_user_id(
                        current_user.id))]
            friend_requests_in = [
                {
                    'user': users_by_id.get(
                        r.other_user_id(
                            current_user.id)), 'rel': r} for r in pending_in if users_by_id.get(
                    r.other_user_id(
                        current_user.id))]
            friend_requests_out = [
                {
                    'user': users_by_id.get(
                        r.other_user_id(
                            current_user.id)), 'rel': r} for r in pending_out if users_by_id.get(
                    r.other_user_id(
                        current_user.id))]
            pending_friends_in_count = len(friend_requests_in)
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        if current_user.id != user.id:
            friendship_state = 'none'

    return render_template(
        'profile.html',
        user=user,
        combat_logs=combat_logs,
        total_fights=total_fights,
        win_rate=win_rate,
        now=now,
        budget=budget,
        budget_range=budget_range,
        can_view_budget=can_view_budget,
        can_view_revenue=can_view_revenue,
        revenue_report=revenue_report,
        revenue_month=revenue_month,
        revenue_search=revenue_search,
        friendship_state=friendship_state,
        friends_list=friends_list,
        friend_requests_in=friend_requests_in,
        friend_requests_out=friend_requests_out,
        pending_friends_in_count=pending_friends_in_count,
    )


@bp.route('/friends/request/<int:user_id>', methods=['POST'])
@login_required
def friend_request(user_id):
    target = db.session.get(User, user_id)
    if not target:
        abort(404)
    if int(target.id) == int(current_user.id):
        flash(_('لا يمكنك إضافة نفسك.'), 'warning')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=target.id))
    if getattr(current_user, 'role', None) == UserRole.GUEST:
        abort(403)

    u1, u2 = _friendship_key(current_user.id, target.id)
    rel = Friendship.query.filter_by(user1_id=u1, user2_id=u2).first()
    now = datetime.now(timezone.utc)

    if not rel:
        rel = Friendship(
            user1_id=u1,
            user2_id=u2,
            requester_id=current_user.id,
            status='pending',
            created_at=now)
        db.session.add(rel)
        db.session.add(Notification(
            user_id=target.id,
            title=_('طلب صداقة'),
            message=_('%(u)s أرسل لك طلب صداقة.', u=current_user.username),
            link=url_for('main.profile', user_id=current_user.id),
        ))
        db.session.commit()
        flash(_('تم إرسال طلب الصداقة.'), 'success')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=target.id))

    if rel.status == 'accepted':
        flash(_('أنتما أصدقاء بالفعل.'), 'info')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=target.id))

    if rel.status == 'blocked':
        flash(_('لا يمكن إرسال طلب صداقة.'), 'danger')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=target.id))

    if rel.status == 'pending':
        if int(rel.requester_id) == int(current_user.id):
            flash(_('طلب الصداقة قيد الانتظار.'), 'info')
            return redirect(
                request.referrer or url_for(
                    'main.profile',
                    user_id=target.id))
        rel.status = 'accepted'
        rel.updated_at = now
        db.session.add(Notification(
            user_id=target.id,
            title=_('تمت الصداقة'),
            message=_('%(u)s قبل طلب صداقتك.', u=current_user.username),
            link=url_for('main.profile', user_id=current_user.id),
        ))
        db.session.commit()
        flash(_('تم قبول الطلب وأصبحتما أصدقاء.'), 'success')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=target.id))

    flash(_('حالة غير معروفة.'), 'danger')
    return redirect(
        request.referrer or url_for(
            'main.profile',
            user_id=target.id))


@bp.route('/friends/accept/<int:user_id>', methods=['POST'])
@login_required
def friend_accept(user_id):
    other = db.session.get(User, user_id)
    if not other:
        abort(404)
    if getattr(current_user, 'role', None) == UserRole.GUEST:
        abort(403)

    u1, u2 = _friendship_key(current_user.id, other.id)
    rel = Friendship.query.filter_by(user1_id=u1, user2_id=u2).first()
    if not rel or rel.status != 'pending':
        flash(_('لا يوجد طلب صداقة صالح.'), 'warning')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=current_user.id))
    if int(rel.requester_id) != int(other.id):
        flash(_('لا يوجد طلب وارد من هذا المستخدم.'), 'warning')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=current_user.id))

    rel.status = 'accepted'
    rel.updated_at = datetime.now(timezone.utc)
    db.session.add(Notification(
        user_id=other.id,
        title=_('تمت الصداقة'),
        message=_('%(u)s قبل طلب صداقتك.', u=current_user.username),
        link=url_for('main.profile', user_id=current_user.id),
    ))
    db.session.commit()
    flash(_('تم قبول طلب الصداقة.'), 'success')
    return redirect(
        request.referrer or url_for(
            'main.profile',
            user_id=current_user.id))


@bp.route('/friends/reject/<int:user_id>', methods=['POST'])
@login_required
def friend_reject(user_id):
    other = db.session.get(User, user_id)
    if not other:
        abort(404)
    if getattr(current_user, 'role', None) == UserRole.GUEST:
        abort(403)

    u1, u2 = _friendship_key(current_user.id, other.id)
    rel = Friendship.query.filter_by(user1_id=u1, user2_id=u2).first()
    if not rel or rel.status != 'pending' or int(
            rel.requester_id) != int(other.id):
        flash(_('لا يوجد طلب وارد من هذا المستخدم.'), 'warning')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=current_user.id))

    db.session.delete(rel)
    db.session.commit()
    flash(_('تم رفض الطلب.'), 'success')
    return redirect(
        request.referrer or url_for(
            'main.profile',
            user_id=current_user.id))


@bp.route('/friends/remove/<int:user_id>', methods=['POST'])
@login_required
def friend_remove(user_id):
    other = db.session.get(User, user_id)
    if not other:
        abort(404)
    if getattr(current_user, 'role', None) == UserRole.GUEST:
        abort(403)

    u1, u2 = _friendship_key(current_user.id, other.id)
    rel = Friendship.query.filter_by(user1_id=u1, user2_id=u2).first()
    if not rel:
        flash(_('لا توجد علاقة لإزالتها.'), 'info')
        return redirect(
            request.referrer or url_for(
                'main.profile',
                user_id=other.id))

    db.session.delete(rel)
    db.session.commit()
    flash(_('تمت الإزالة.'), 'success')
    return redirect(
        request.referrer or url_for(
            'main.profile',
            user_id=other.id))


@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    avatars_dir = os.path.join(
        current_app.root_path,
        'static',
        'images',
        'avatars')
    if not os.path.exists(avatars_dir):
        os.makedirs(avatars_dir)

    # Get all image files
    avatars = [
        f for f in os.listdir(avatars_dir) if f.lower().endswith(
            ('.png', '.jpg', '.jpeg', '.gif', '.svg'))]

    if request.method == 'POST':
        # Handle Personal Info Update
        if 'gender' in request.form:
            current_user.gender = request.form.get('gender')
            dob = request.form.get('birthdate')
            if dob:
                try:
                    current_user.birthdate = datetime.strptime(
                        dob, '%Y-%m-%d').date()
                except ValueError:
                    pass
            db.session.commit()
            flash(_('تم تحديث المعلومات الشخصية بنجاح'), 'success')
            return redirect(url_for('main.edit_profile'))

        # Handle File Upload
        if 'avatar_upload' in request.files:
            file = request.files['avatar_upload']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext in ['png', 'jpg', 'jpeg', 'gif', 'svg']:
                    filename = secure_filename(
                        f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}")
                    file.save(os.path.join(avatars_dir, filename))
                    current_user.avatar = filename
                    db.session.commit()
                    flash(_('تم رفع الصورة الشخصية بنجاح'), 'success')
                    return redirect(
                        url_for(
                            'main.profile',
                            user_id=current_user.id))
                else:
                    flash(_('نوع الملف غير مدعوم (فقط صور)'), 'danger')

        selected_avatar = request.form.get('avatar')
        if selected_avatar and selected_avatar in avatars:
            current_user.avatar = selected_avatar
            db.session.commit()
            flash(_('تم تحديث الصورة الشخصية بنجاح'), 'success')
            return redirect(url_for('main.profile', user_id=current_user.id))
        # Only show error if no file upload was attempted
        elif not request.files.get('avatar_upload'):
            flash(_('حدث خطأ في اختيار الصورة'), 'danger')

    return render_template('edit_profile.html', avatars=avatars)


@bp.route('/leaderboard')
@limiter.limit("20 per minute")
@cache.cached(timeout=300)
def leaderboard():
    # SEO
    from extensions import seo_manager
    seo_manager.set(
        title=_("قائمة المتصدرين - أقوى العصابات واللاعبين"),
        description=_("تعرف على أقوى اللاعبين والعصابات في عصابات فلسطين. هل تملك ما يلزم لتكون في القمة؟"),
        keywords="leaderboard, top players, gangs ranking, متصدرين, اقوى اللاعبين, ترتيب العصابات")
    seo_manager.add_breadcrumb(
        _("قائمة المتصدرين"),
        url_for('main.leaderboard'))

    top_users = User.query.order_by(
        User.level.desc(),
        User.exp.desc()).limit(20).all()
    top_gangs = Gang.query.order_by(
        Gang.level.desc(),
        Gang.exp.desc()).limit(20).all()
    top_rich = User.query.order_by(User.money.desc()).limit(20).all()

    return render_template(
        'leaderboard.html',
        top_users=top_users,
        top_gangs=top_gangs,
        top_rich=top_rich)


@bp.route('/api/public-chat/messages')
def get_public_chat_messages():
    since_id = request.args.get('since_id', type=int)
    room = request.args.get('room', default='general')

    valid_rooms = {
        'general',
        'dating',
        'strangers',
        'beginners',
        'trade',
        'vip'}
    if room not in valid_rooms:
        room = 'general'

    if room == 'vip':
        if (not current_user.is_authenticated) or (
                current_user.role.value < UserRole.SUBSCRIBER.value):
            return jsonify({'error': _('هذه غرفة VIP. قم بالترقية للدخول.'), 'messages': [
            ], 'last_id': since_id or 0}), 403

    if room == 'dating':
        if not current_user.is_authenticated:
            return jsonify({'error': _('هذه الغرفة تتطلب تسجيل الدخول.'),
                           'messages': [], 'last_id': since_id or 0}), 403

    if room == 'strangers':
        if current_user.is_authenticated:
            return jsonify({'error': _('هذه الغرفة للزوار فقط.'),
                           'messages': [], 'last_id': since_id or 0}), 403

    q = PublicChat.query.filter_by(room=room)

    if since_id and since_id > 0:
        # Delta fetch: Get messages after since_id (Oldest first of the new
        # batch)
        messages = q.filter(
            PublicChat.id > since_id).order_by(
            PublicChat.created_at.asc()).limit(200).all()
    else:
        # Initial fetch: Get latest 50 messages (Newest first, then reverse)
        messages = q.order_by(PublicChat.created_at.desc()).limit(50).all()
        messages = list(reversed(messages))

    items = [m.to_dict() for m in messages]
    last_id = since_id or 0
    if items:
        last_id = max(last_id, max(m['id'] for m in items))

    resp = jsonify({'messages': items, 'last_id': last_id})

    if messages:
        try:
            # Use the last message's time for Last-Modified header
            resp.headers['Last-Modified'] = messages[-1].created_at.strftime(
                '%a, %d %b %Y %H:%M:%S GMT')
        except Exception:
            pass
    return resp


@bp.route('/api/public-chat/send', methods=['POST'])
@limiter.limit("10 per minute;120 per hour")
def send_public_chat_message():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    data = request.get_json(silent=True) or {}
    msg_content = (data.get('message') or '').strip()
    room = (data.get('room') or 'general').strip()

    valid_rooms = {
        'general',
        'dating',
        'strangers',
        'beginners',
        'trade',
        'vip'}
    if room not in valid_rooms:
        room = 'general'

    if room == 'strangers':
        if current_user.is_authenticated:
            return jsonify({'error': _('هذه الغرفة للزوار فقط.')}), 403
        actor = _get_or_create_guest_chat_user()
    else:
        if not current_user.is_authenticated:
            return jsonify({'error': _('الدردشة للمسجلين فقط.')}), 403
        actor = current_user

    if getattr(actor, 'is_chat_banned', False):
        return jsonify({'error': _('عذراً، أنت محظور من الدردشة.')}), 403
    if getattr(actor, 'chat_muted_until', None):
        until = actor.chat_muted_until
        if until and until > now.replace(tzinfo=None):
            return jsonify({'error': _('أنت تحت كتم مؤقت. حاول لاحقاً.')}), 403

    if room == 'vip':
        if (not current_user.is_authenticated) or (
                actor.role.value < UserRole.SUBSCRIBER.value):
            return jsonify(
                {'error': _('هذه غرفة VIP. قم بالترقية للدخول.')}), 403

    if room == 'dating':
        if not current_user.is_authenticated:
            return jsonify({'error': _('هذه الغرفة تتطلب تسجيل الدخول.')}), 403

    if not msg_content:
        return jsonify({'error': 'Message cannot be empty'}), 400

    if len(msg_content) > 500:
        return jsonify({'error': 'Message too long'}), 400

    if contains_prohibited_content(msg_content):
        return jsonify(
            {'error': _('عذراً، يمنع إرسال الروابط أو الإيميلات أو أرقام الهواتف.')}), 400

    if room == 'strangers':
        if re.search(
            r"\[\[(image|video|file):",
            msg_content,
                flags=re.IGNORECASE):
            return jsonify(
                {'error': _('المرفقات غير متاحة في غرفة الغرباء.')}), 400

    def _get_cfg_int(key: str, default: int) -> int:
        try:
            v = SystemConfig.get_value(key, str(default))
            return int(v) if v is not None else default
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            return default

    slow_mode_seconds = max(
        0, min(
            60, _get_cfg_int(
                'chat_slow_mode_seconds', 2)))
    slow_mode_seconds = max(
        0, min(
            60, _get_cfg_int(
                f'chat_slow_mode_seconds_{room}', slow_mode_seconds)))
    duplicate_window_seconds = max(
        0, min(
            3600, _get_cfg_int(
                'chat_duplicate_window_seconds', 60)))
    duplicate_window_seconds = max(0, min(3600, _get_cfg_int(
        f'chat_duplicate_window_seconds_{room}', duplicate_window_seconds)))

    if current_user.is_authenticated and current_user.is_moderator:
        slow_mode_seconds = 0

    # Rate limit check for same room
    last = PublicChat.query.filter_by(
        user_id=actor.id, room=room).order_by(
        PublicChat.created_at.desc()).first()
    if last:
        try:
            last_dt = last.created_at
            if slow_mode_seconds > 0 and last_dt and (
                    now - last_dt.replace(tzinfo=timezone.utc)).total_seconds() < slow_mode_seconds:
                return jsonify(
                    {'error': _('انتظر قليلاً قبل إرسال رسالة أخرى.')}), 429
            if duplicate_window_seconds > 0 and last_dt and last.message.strip() == msg_content and (
                    now - last_dt.replace(tzinfo=timezone.utc)).total_seconds() < duplicate_window_seconds:
                return jsonify({'error': _('رسالة مكررة خلال دقيقة.')}), 400
        except Exception:
            pass

    chat = PublicChat(user_id=actor.id, message=msg_content, room=room)
    db.session.add(chat)
    db.session.commit()

    return jsonify(chat.to_dict())


@bp.route('/api/public-chat/upload', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def public_chat_upload():
    room = (request.form.get('room') or 'general').strip()
    valid_rooms = {
        'general',
        'dating',
        'strangers',
        'beginners',
        'trade',
        'vip'}
    if room not in valid_rooms:
        room = 'general'

    if room == 'strangers':
        return jsonify(
            {'error': _('المرفقات غير متاحة في غرفة الغرباء.')}), 403

    if room == 'vip' and current_user.role.value < UserRole.SUBSCRIBER.value:
        return jsonify({'error': _('هذه غرفة VIP. قم بالترقية للدخول.')}), 403

    if room in {'dating', 'strangers'} and (not current_user.is_authenticated):
        return jsonify({'error': _('هذه الغرفة تتطلب تسجيل الدخول.')}), 403
    if room == 'strangers':
        reason = _strangers_access_reason(current_user)
        if reason:
            return jsonify({'error': reason}), 403

    if 'file' not in request.files:
        return jsonify({'error': _('الملف مطلوب.')}), 400

    f = request.files['file']
    if not f or not f.filename:
        return jsonify({'error': _('الملف غير صالح.')}), 400

    original_name = f.filename
    ext = ''
    if '.' in original_name:
        ext = original_name.rsplit('.', 1)[1].lower()

    allowed = {
        'png': 'image',
        'jpg': 'image',
        'jpeg': 'image',
        'gif': 'image',
        'webp': 'image',
        'mp4': 'video',
        'pdf': 'file',
        'txt': 'file',
    }
    kind = allowed.get(ext)
    if not kind:
        return jsonify({'error': _('نوع الملف غير مدعوم.')}), 400

    try:
        f.stream.seek(0, os.SEEK_END)
        size = int(f.stream.tell() or 0)
        f.stream.seek(0)
    except Exception:
        size = 0

    max_bytes = 8 * 1024 * 1024
    if request.content_length and request.content_length > (
            max_bytes + 1024 * 64):
        return jsonify({'error': _('حجم الملف كبير جداً.')}), 400
    if size and size > max_bytes:
        return jsonify({'error': _('حجم الملف كبير جداً.')}), 400

    uploads_dir = os.path.join(
        current_app.root_path,
        'static',
        'uploads',
        'chat')
    os.makedirs(uploads_dir, exist_ok=True)

    safe_name = secure_filename(original_name) or f"file.{ext}"
    filename = secure_filename(f"chat_{current_user.id}_{uuid.uuid4().hex}.{ext}")
    save_path = os.path.join(uploads_dir, filename)
    try:
        f.save(save_path)
    except Exception:
        return jsonify({'error': _('فشل رفع الملف.')}), 500

    rel_path = f"uploads/chat/{filename}"
    token = f"[[{kind}:{rel_path}|{safe_name}]]" if kind == 'file' else f"[[{kind}:{rel_path}]]"
    return jsonify({'success': True,
                    'kind': kind,
                    'path': rel_path,
                    'token': token,
                    'name': safe_name})


@bp.route('/api/public-chat/ban/<int:user_id>', methods=['POST'])
@login_required
def ban_public_chat_user(user_id):
    if current_user.role.value < UserRole.MODERATOR.value:
        return jsonify({'error': _('غير مصرح لك بذلك.')}), 403

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': _('المستخدم غير موجود.')}), 404

    if user.role.value >= current_user.role.value:
        return jsonify(
            {'error': _('لا يمكنك حظر شخص بنفس رتبتك أو أعلى.')}), 403

    user.is_chat_banned = True
    db.session.commit()
    return jsonify({'success': True, 'message': _(
        'تم حظر المستخدم من الدردشة.')})


@bp.route('/api/public-chat/unban/<int:user_id>', methods=['POST'])
@login_required
def unban_public_chat_user(user_id):
    if current_user.role.value < UserRole.MODERATOR.value:
        return jsonify({'error': _('غير مصرح لك بذلك.')}), 403

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': _('المستخدم غير موجود.')}), 404

    user.is_chat_banned = False
    db.session.commit()
    return jsonify({'success': True, 'message': _(
        'تم إلغاء حظر المستخدم من الدردشة.')})


@bp.route('/api/public-chat/mute/<int:user_id>', methods=['POST'])
@login_required
def mute_public_chat_user(user_id):
    if current_user.role.value < UserRole.MODERATOR.value:
        return jsonify({'error': _('غير مصرح لك بذلك.')}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': _('المستخدم غير موجود.')}), 404
    minutes = request.args.get('minutes', default=30, type=int)
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user.chat_muted_until = now + timedelta(minutes=max(1, minutes))
    db.session.commit()
    return jsonify({'success': True, 'message': _('تم كتم المستخدم مؤقتاً.')})


@bp.route('/api/public-chat/unmute/<int:user_id>', methods=['POST'])
@login_required
def unmute_public_chat_user(user_id):
    if current_user.role.value < UserRole.MODERATOR.value:
        return jsonify({'error': _('غير مصرح لك بذلك.')}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': _('المستخدم غير موجود.')}), 404
    user.chat_muted_until = None
    db.session.commit()
    return jsonify({'success': True, 'message': _('تم إلغاء الكتم.')})


@bp.route('/api/public-chat/delete/<int:msg_id>', methods=['POST'])
@login_required
def delete_public_chat_message(msg_id):
    if current_user.role.value < UserRole.MODERATOR.value:
        return jsonify({'error': _('غير مصرح لك بذلك.')}), 403
    m = db.session.get(PublicChat, msg_id)
    if not m:
        return jsonify({'error': _('الرسالة غير موجودة.')}), 404
    db.session.delete(m)
    db.session.commit()
    return jsonify({'success': True, 'message': _('تم حذف الرسالة.')})


@bp.route('/api/public-chat/report/<int:msg_id>', methods=['POST'])
@limiter.limit("30 per hour")
@login_required
def report_public_chat_message(msg_id):
    actor = current_user
    m = db.session.get(PublicChat, msg_id)
    if not m:
        return jsonify({'error': _('الرسالة غير موجودة.')}), 404

    try:
        details = {
            'msg_id': int(m.id),
            'room': str(m.room or ''),
            'reported_user_id': int(m.user_id),
            'reporter_user_id': int(actor.id),
            'reporter_username': str(getattr(actor, 'username', '') or ''),
            'message_preview': (str(m.message or '')[:140]),
        }
        db.session.add(
            SecurityLog(
                event_type='chat_report',
                ip_address=request.remote_addr,
                details=json.dumps(
                    details,
                    ensure_ascii=False)))
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'error': _('حدث خطأ أثناء الإبلاغ.')}), 500

    return jsonify({'success': True, 'message': _('تم إرسال البلاغ.')})


@bp.route('/api/chat/smart', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def smart_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    hostess_id = data.get('hostess_id')

    if not message:
        return jsonify({'error': _('الرسالة مطلوبة.')}), 400

    hostess = None
    if hostess_id:
        try:
            hostess = db.session.get(Hostess, int(hostess_id))
        except Exception:
            hostess = None
    if not hostess:
        hostess = Hostess.query.filter_by(role='greeter').first()
        if not hostess:
            hostess = Hostess.query.filter(
                (Hostess.name.ilike('%Jasmin%')) | (
                    Hostess.name.ilike('%Jasmine%'))).first()
            if not hostess:
                hostess = Hostess.query.first()

    if not hostess:
        return jsonify({'error': _('المضيفة غير موجودة.')}), 404

    user_context = {
        'id': int(current_user.id),
        'name': str(current_user.username or ''),
        'is_guest': False,
        'money': int(getattr(current_user, 'money', 0) or 0),
        'level': int(getattr(current_user, 'level', 0) or 0),
    }

    ai_service = AIHostessService()
    session_key = f'user_chat_history_{hostess.id}_{current_user.id}'
    chat_history = session.get(session_key, [])

    try:
        response_text = ai_service.get_response(
            user_message=message,
            hostess_context=hostess.to_dict(),
            user_context=user_context,
            chat_history=chat_history
        )
    except Exception:
        response_text = ai_service._rule_based_response(
            message, hostess.to_dict(), user_context)

    chat_history.append({'role': 'user', 'content': message})
    chat_history.append({'role': 'assistant', 'content': response_text})
    if len(chat_history) > 20:
        chat_history = chat_history[-20:]
    session[session_key] = chat_history
    session.modified = True

    return jsonify({'response': response_text,
                    'hostess_name': hostess.name,
                    'hostess_image': hostess.image})

# --- Messenger (Private Chat) Routes ---


@bp.route('/messenger')
@login_required
def messenger():
    chat_with_id = request.args.get('chat_with', type=int)
    target_user = None
    if chat_with_id:
        target_user = db.session.get(User, chat_with_id)
    return render_template('social/messenger.html', target_user=target_user)


@bp.route('/api/messenger/conversations')
@login_required
def messenger_conversations():
    # Fetch recent messages involving user
    messages = (
        PrivateChat.query.filter(
            or_(
                (PrivateChat.sender_id == current_user.id)
                & PrivateChat.deleted_by_sender.is_(False),
                (PrivateChat.receiver_id == current_user.id)
                & PrivateChat.deleted_by_receiver.is_(False),
            )
        )
        .order_by(PrivateChat.created_at.desc())
        .limit(200)
        .all()
    )

    conversations = {}
    for msg in messages:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        if other_id not in conversations:
            other_user = msg.receiver if msg.sender_id == current_user.id else msg.sender
            conversations[other_id] = {
                'user_id': other_id,
                'username': other_user.username if other_user else 'Unknown',
                'avatar': other_user.avatar if other_user else 'default.png',
                'last_message': msg.message,
                'timestamp': msg.created_at.isoformat(),
                'is_read': msg.is_read if msg.receiver_id == current_user.id else True,
                'unread_count': 0}

    # Calculate unread counts
    unread_counts = db.session.query(
        PrivateChat.sender_id, db.func.count(PrivateChat.id)
    ).filter(
        PrivateChat.receiver_id == current_user.id,
        PrivateChat.is_read.is_(False),
        PrivateChat.deleted_by_receiver.is_(False)
    ).group_by(PrivateChat.sender_id).all()

    for sender_id, count in unread_counts:
        if sender_id in conversations:
            conversations[sender_id]['unread_count'] = count

    return jsonify(list(conversations.values()))


@bp.route('/api/messenger/messages/<int:user_id>')
@login_required
def messenger_messages(user_id):
    other_user = db.session.get(User, user_id)
    if not other_user:
        return jsonify({'error': 'User not found'}), 404

    messages = (
        PrivateChat.query.filter(
            or_(
                (PrivateChat.sender_id == current_user.id)
                & (PrivateChat.receiver_id == user_id)
                & PrivateChat.deleted_by_sender.is_(False),
                (PrivateChat.receiver_id == current_user.id)
                & (PrivateChat.sender_id == user_id)
                & PrivateChat.deleted_by_receiver.is_(False),
            )
        )
        .order_by(PrivateChat.created_at.asc())
        .limit(100)
        .all()
    )

    return jsonify([msg.to_dict() for msg in messages])


@bp.route('/api/messenger/send', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def messenger_send():
    if current_user.is_muted:
        return jsonify({'error': _('أنت مكتوم لا يمكنك التحدث!')}), 403

    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()

    if not receiver_id or not content:
        return jsonify({'error': 'Missing data'}), 400

    if len(content) > 1000:
        return jsonify({'error': 'Message too long'}), 400

    if contains_prohibited_content(content):
        return jsonify(
            {'error': _('عذراً، يمنع إرسال الروابط أو الإيميلات أو أرقام الهواتف.')}), 400

    receiver = db.session.get(User, receiver_id)
    if not receiver:
        return jsonify({'error': 'User not found'}), 404

    msg = PrivateChat(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        message=content
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify(msg.to_dict())


@bp.route('/api/messenger/mark_read/<int:user_id>', methods=['POST'])
@login_required
def messenger_mark_read(user_id):
    PrivateChat.query.filter_by(
        sender_id=user_id,
        receiver_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})

# --- Chat Lobby & Random Match ---


@bp.route('/chat/room/<string:room_name>')
def chat_room(room_name):
    valid_rooms = [
        'general',
        'dating',
        'strangers',
        'beginners',
        'trade',
        'vip']
    if room_name not in valid_rooms:
        abort(404)

    room_titles = {
        'general': _('الغرفة العامة'),
        'dating': _('غرفة التعارف'),
        'strangers': _('غرفة الغرباء'),
        'beginners': _('غرفة المبتدئين'),
        'trade': _('غرفة التجارة'),
        'vip': _('غرفة VIP')
    }

    if room_name == 'vip' and (not current_user.is_authenticated):
        flash(_('هذه غرفة VIP وتتطلب تسجيل الدخول.'), 'warning')
        return redirect(url_for('main.login', next=request.path))

    if room_name == 'dating' and (not current_user.is_authenticated):
        flash(_('هذه الغرفة تتطلب تسجيل الدخول.'), 'warning')
        return redirect(url_for('main.login', next=request.path))

    chat_user_id = current_user.id if current_user.is_authenticated else 0
    if room_name == 'strangers':
        if current_user.is_authenticated:
            flash(_('هذه الغرفة للزوار فقط.'), 'warning')
            return redirect(url_for('main.chat_room', room_name='general'))
        try:
            guest_u = _get_or_create_guest_chat_user()
            chat_user_id = guest_u.id
        except Exception:
            chat_user_id = 0

    vip_upgrade_cost_diamonds = 250
    try:
        vip_upgrade_cost_diamonds = int(
            SystemConfig.get_value(
                'vip_upgrade_cost_diamonds',
                str(vip_upgrade_cost_diamonds)) or vip_upgrade_cost_diamonds)
    except Exception:
        vip_upgrade_cost_diamonds = 250

    if room_name == 'vip' and current_user.is_authenticated and current_user.role.value < UserRole.SUBSCRIBER.value:
        try:
            user_diamonds = int(getattr(current_user, 'diamonds', 0) or 0)
        except Exception:
            user_diamonds = 0
        if user_diamonds < int(vip_upgrade_cost_diamonds):
            flash(
                _('لا تملك ماساً كافياً للترقية. يمكنك شراء الماس أولاً.'),
                'warning')
            return redirect(url_for('main.buy_diamonds', next=request.path))

    vip_can_chat = True
    if room_name == 'vip':
        vip_can_chat = current_user.is_authenticated and (
            current_user.role.value >= UserRole.SUBSCRIBER.value)

    donation_target_username = None
    try:
        dev_id = int(
            SystemConfig.get_value(
                'developer_donation_user_id',
                '1') or 1)
        dev_user = db.session.get(User, dev_id)
        donation_target_username = dev_user.username if dev_user else None
    except Exception:
        donation_target_username = None

    # SEO
    from extensions import seo_manager
    seo_manager.set(
        title=f"{_('دردشة')} - {room_titles.get(room_name, room_name)}",
        description=f"{_('انضم للدردشة في')} {room_titles.get(room_name, room_name)}",
        keywords=f"chat, {room_name}, room"
    )

    return render_template(
        'social/chat_room.html',
        current_room=room_name,
        room_title=room_titles.get(room_name, room_name),
        can_chat=vip_can_chat,
        chat_user_id=chat_user_id,
        vip_upgrade_cost_diamonds=vip_upgrade_cost_diamonds,
        donation_target_username=donation_target_username,
        hide_page_title=True,
        hide_footer=True,
        hide_sidebar=True,
        page_container_class='container-fluid p-0',
        body_extra_class='chatna-body',
    )


@bp.route('/chat/lobby')
def chat_lobby():
    # SEO
    from extensions import seo_manager
    seo_manager.set(
        title=_("غرف الدردشة - تعارف ودردشة"),
        description=_("تحدث مع أصدقاء جدد، ابحث عن شريك، أو انضم لغرف الدردشة العامة."),
        keywords=(
            "chat, chat rooms, arab chat, dating chat, random chat, "
            "دردشة, شات, غرف دردشة, دردشة عربية, دردشة تعارف, دردشة غرباء, "
            "غرفة عامة, غرفة مبتدئين, غرفة تجارة, عصابات فلسطين"
        ))
    vip_upgrade_cost_diamonds = 250
    try:
        vip_upgrade_cost_diamonds = int(
            SystemConfig.get_value(
                'vip_upgrade_cost_diamonds',
                str(vip_upgrade_cost_diamonds)) or vip_upgrade_cost_diamonds)
    except Exception:
        vip_upgrade_cost_diamonds = 250

    donation_target_username = None
    try:
        dev_id = int(
            SystemConfig.get_value(
                'developer_donation_user_id',
                '1') or 1)
        dev_user = db.session.get(User, dev_id)
        donation_target_username = dev_user.username if dev_user else None
    except Exception:
        donation_target_username = None

    is_vip = bool(
        current_user.is_authenticated and current_user.role.value >= UserRole.SUBSCRIBER.value)

    return render_template(
        'social/chat_lobby.html',
        vip_upgrade_cost_diamonds=vip_upgrade_cost_diamonds,
        donation_target_username=donation_target_username,
        is_vip=is_vip,
        hide_page_title=True,
        hide_footer=True,
        hide_sidebar=True,
        page_container_class='container-fluid p-0',
        body_extra_class='chatna-body',
    )


@bp.route('/chat/vip/upgrade', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def chat_vip_upgrade():
    if current_user.role.value >= UserRole.SUBSCRIBER.value:
        flash(_('أنت بالفعل VIP.'), 'info')
        return redirect(url_for('main.chat_room', room_name='vip'))

    cost = 250
    try:
        cost = int(
            SystemConfig.get_value(
                'vip_upgrade_cost_diamonds',
                str(cost)) or cost)
    except Exception:
        cost = 250

    ok = ResourceService.modify_resources(
        current_user.id,
        {'diamonds': -max(1, int(cost))},
        'vip_upgrade',
        check_balance=True,
        auto_commit=True,
        expected_version=None,
        set_fields={'role': UserRole.SUBSCRIBER},
        log_extra={'vip_cost_diamonds': int(cost)},
    )
    if not ok:
        flash(_('رصيد الماس غير كافٍ للترقية.'), 'danger')
        return redirect(
            url_for(
                'main.buy_diamonds',
                next=url_for(
                    'main.chat_room',
                    room_name='vip')))

    flash(_('تمت ترقية حسابك إلى VIP بنجاح.'), 'success')
    return redirect(url_for('main.chat_room', room_name='vip'))


@bp.route('/chat/vip/donate', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def chat_vip_donate():
    currency = (request.form.get('currency') or 'diamonds').strip().lower()
    amount_raw = (request.form.get('amount') or '').strip()
    try:
        amount = int(amount_raw)
    except Exception:
        amount = 0

    if currency not in {'diamonds', 'money'}:
        flash(_('عملة غير صالحة.'), 'danger')
        return redirect(url_for('main.chat_room', room_name='vip'))

    if amount <= 0:
        flash(_('أدخل مبلغاً صحيحاً.'), 'danger')
        return redirect(url_for('main.chat_room', room_name='vip'))

    try:
        dev_id = int(
            SystemConfig.get_value(
                'developer_donation_user_id',
                '1') or 1)
    except Exception:
        dev_id = 1

    if dev_id == current_user.id:
        flash(_('لا يمكنك التبرع لنفسك.'), 'danger')
        return redirect(url_for('main.chat_room', room_name='vip'))

    dev_user = db.session.get(User, dev_id)
    if not dev_user:
        flash(_('حساب المطور غير موجود.'), 'danger')
        return redirect(url_for('main.chat_room', room_name='vip'))

    ids = sorted([current_user.id, dev_user.id])
    db.session.query(User).filter(
        User.id.in_(ids)).order_by(
        User.id.asc()).with_for_update().all()

    reason_sent = f"dev_donation_sent_{currency}"
    reason_received = f"dev_donation_received_{currency}"

    ok1 = ResourceService.modify_resources(
        current_user.id,
        {currency: -amount},
        reason_sent,
        check_balance=True,
        auto_commit=False,
        expected_version=None,
        log_extra={'to_user_id': dev_user.id},
    )
    if not ok1:
        db.session.rollback()
        flash(_('رصيدك غير كافٍ.'), 'danger')
        if currency == 'diamonds':
            return redirect(
                url_for(
                    'main.buy_diamonds',
                    next=url_for(
                        'main.chat_room',
                        room_name='vip')))
        return redirect(url_for('main.chat_room', room_name='vip'))

    ok2 = ResourceService.modify_resources(
        dev_user.id,
        {currency: amount},
        reason_received,
        check_balance=False,
        auto_commit=False,
        expected_version=None,
        log_extra={'from_user_id': current_user.id},
    )
    if not ok2:
        db.session.rollback()
        flash(_('حدث خطأ أثناء التبرع.'), 'danger')
        return redirect(url_for('main.chat_room', room_name='vip'))

    db.session.commit()
    flash(_('شكراً لك! تم إرسال التبرع بنجاح.'), 'success')
    return redirect(url_for('main.chat_room', room_name='vip'))


@bp.route('/api/chat/online_users')
def get_online_users():
    gender = request.args.get('gender')
    min_age = request.args.get('min_age', type=int)
    max_age = request.args.get('max_age', type=int)

    now = datetime.now(timezone.utc)
    # Online = seen in last 5 minutes
    query = User.query.filter(User.last_seen >= now - timedelta(minutes=5))

    if gender and gender in ['male', 'female']:
        query = query.filter(User.gender == gender)

    users = query.limit(100).all()

    # Filter by age in python (easier than complex date SQL for now)
    filtered_users = []
    for u in users:
        age = u.age
        if min_age and (age is None or age < min_age):
            continue
        if max_age and (age is None or age > max_age):
            continue
        filtered_users.append({
            'id': u.id,
            'username': u.username,
            'avatar': u.avatar,
            'gender': u.gender,
            'age': age,
            'country': u.country,
            'level': u.level,
            'is_vip': bool(u.role and u.role.value >= UserRole.SUBSCRIBER.value)
        })

    return jsonify(filtered_users)


def _valid_chat_room(room):
    valid_rooms = {
        'general',
        'dating',
        'strangers',
        'beginners',
        'trade',
        'vip'}
    return room if room in valid_rooms else 'general'


def _typing_cache_key(room):
    return f"chat_typing_room:{room}"


def _prune_typing_state(state, now_ts, max_age_seconds):
    pruned = {}
    for user_id_str, info in (state or {}).items():
        try:
            last = float((info or {}).get('ts') or 0)
        except Exception:
            last = 0
        if now_ts - last <= max_age_seconds:
            pruned[user_id_str] = info
    return pruned


@bp.route('/api/chat/typing', methods=['GET'])
@login_required
def chat_typing_get():
    room = _valid_chat_room(request.args.get('room') or 'general')
    if room == 'vip' and current_user.role.value < UserRole.SUBSCRIBER.value:
        return jsonify({'room': room, 'typing': []}), 403
    now_ts = datetime.now(timezone.utc).timestamp()
    state = cache.get(_typing_cache_key(room)) or {}
    state = _prune_typing_state(state, now_ts, 6)
    cache.set(_typing_cache_key(room), state, timeout=30)

    items = []
    for user_id_str, info in state.items():
        try:
            user_id = int(user_id_str)
        except Exception:
            continue
        if user_id == current_user.id:
            continue
        items.append({
            'id': user_id,
            'username': (info or {}).get('username') or 'Unknown',
            'avatar': (info or {}).get('avatar') or 'default.png',
        })

    return jsonify({'room': room, 'typing': items})


@bp.route('/api/chat/typing', methods=['POST'])
@login_required
@limiter.limit("60 per minute")
def chat_typing_set():
    data = request.get_json(silent=True) or {}
    room = _valid_chat_room((data.get('room') or 'general').strip())
    if room == 'vip' and current_user.role.value < UserRole.SUBSCRIBER.value:
        return jsonify({'success': False}), 403
    is_typing = bool(data.get('is_typing'))
    now_ts = datetime.now(timezone.utc).timestamp()

    state = cache.get(_typing_cache_key(room)) or {}
    state = _prune_typing_state(state, now_ts, 6)
    uid = str(current_user.id)

    if is_typing:
        state[uid] = {
            'username': current_user.username,
            'avatar': current_user.avatar or 'default.png',
            'ts': now_ts
        }
    else:
        state.pop(uid, None)

    cache.set(_typing_cache_key(room), state, timeout=30)
    return jsonify({'success': True})


@bp.route('/api/chat/random_match')
@login_required
def random_match():
    # Find a random user online who is not me
    reason = _strangers_access_reason(current_user)
    if reason:
        return jsonify({'error': reason}), 403

    now = datetime.now(timezone.utc)
    query = User.query.filter(
        User.last_seen >= now - timedelta(minutes=5),
        User.id != current_user.id
    )
    query = query.filter(
        User.is_suspicious.is_(False),
        User.is_chat_banned.is_(False),
        User.birthdate.isnot(None))

    # Filter preferences
    pref_gender = request.args.get('gender')
    if pref_gender in ['male', 'female']:
        query = query.filter(User.gender == pref_gender)

    candidates = query.limit(300).all()
    allowed = []
    for u in candidates:
        try:
            age = u.age
        except Exception:
            age = None
        if age is None or age < 18:
            continue
        allowed.append(u)

    if not allowed:
        return ("", 204)

    import random
    user = random.choice(allowed)

    return jsonify({
        'id': user.id,
        'username': user.username,
        'avatar': user.avatar,
        'gender': user.gender,
        'age': user.age
    })


@bp.route('/api/messenger/delete/<int:msg_id>', methods=['POST'])
@login_required
def messenger_delete(msg_id):
    msg = db.session.get(PrivateChat, msg_id)
    if not msg:
        return jsonify({'error': 'Message not found'}), 404

    if msg.sender_id == current_user.id:
        msg.deleted_by_sender = True
    elif msg.receiver_id == current_user.id:
        msg.deleted_by_receiver = True
    else:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.commit()
    return jsonify({'success': True})
