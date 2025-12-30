from flask import render_template, redirect, url_for, flash, abort, request, current_app
from flask_login import login_required, current_user
from extensions import db
from sqlalchemy import or_
from models import Gang, Message, User, Notification, CombatLog
from . import bp
from flask_babel import _
from datetime import datetime, timezone
import os
from werkzeug.utils import secure_filename
import uuid

@bp.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    notifs = current_user.notifications.order_by(Notification.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
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
    
    if notif.link:
        return redirect(notif.link)
    return redirect(url_for('main.notifications'))

@bp.route('/notifications/read_all', methods=['POST'])
@login_required
def read_all_notifications():
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
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
        messages_query = Message.query.filter_by(sender_id=current_user.id, deleted_by_sender=False).order_by(Message.timestamp.desc())
        title = _('البريد الصادر')
    else:
        now = datetime.now(timezone.utc)
        messages_query = Message.query.filter_by(receiver_id=current_user.id, deleted_by_receiver=False).filter(
            (Message.delivery_time <= now) | (Message.delivery_time == None)
        ).order_by(Message.timestamp.desc())
        title = _('البريد الوارد')
        
    messages = messages_query.paginate(page=page, per_page=20, error_out=False)
    
    return render_template('messages.html', messages=messages, box=box, title=title)

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
        
    return render_template('send_message.html', receiver=receiver_arg, subject=subject_arg)

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
    return redirect(url_for('main.messages', box=request.args.get('box', 'inbox')))

@bp.route('/messages/bulk_delete', methods=['POST'])
@login_required
def bulk_delete_messages():
    msg_ids = request.form.getlist('msg_ids')
    box = request.form.get('box', 'inbox')
    
    if not msg_ids:
        flash(_('لم يتم تحديد أي رسالة!'), 'warning')
        return redirect(url_for('main.messages', box=box))
        
    count = 0
    for msg_id in msg_ids:
        msg = db.session.get(Message, int(msg_id))
        if msg:
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
    return redirect(url_for('main.messages', box=box))

@bp.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
        
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
    
    return render_template('profile.html', user=user, combat_logs=combat_logs, total_fights=total_fights, win_rate=win_rate)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    if not os.path.exists(avatars_dir):
        os.makedirs(avatars_dir)
        
    # Get all image files
    avatars = [f for f in os.listdir(avatars_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg'))]
    
    if request.method == 'POST':
        # Handle File Upload
        if 'avatar_upload' in request.files:
            file = request.files['avatar_upload']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext in ['png', 'jpg', 'jpeg', 'gif', 'svg']:
                    filename = secure_filename(f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}")
                    file.save(os.path.join(avatars_dir, filename))
                    current_user.avatar = filename
                    db.session.commit()
                    flash(_('تم رفع الصورة الشخصية بنجاح'), 'success')
                    return redirect(url_for('main.profile', user_id=current_user.id))
                else:
                    flash(_('نوع الملف غير مدعوم (فقط صور)'), 'danger')

        selected_avatar = request.form.get('avatar')
        if selected_avatar and selected_avatar in avatars:
            current_user.avatar = selected_avatar
            db.session.commit()
            flash(_('تم تحديث الصورة الشخصية بنجاح'), 'success')
            return redirect(url_for('main.profile', user_id=current_user.id))
        elif not request.files.get('avatar_upload'): # Only show error if no file upload was attempted
             flash(_('حدث خطأ في اختيار الصورة'), 'danger')
            
    return render_template('edit_profile.html', avatars=avatars)

@bp.route('/leaderboard')
@login_required
def leaderboard():
    top_users = User.query.order_by(User.level.desc(), User.exp.desc()).limit(20).all()
    top_gangs = Gang.query.order_by(Gang.level.desc(), Gang.exp.desc()).limit(20).all()
    top_rich = User.query.order_by(User.money.desc()).limit(20).all()
    
    return render_template('leaderboard.html', top_users=top_users, top_gangs=top_gangs, top_rich=top_rich)

