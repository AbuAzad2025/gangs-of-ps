"""Staff / moderator routes (chat oversight, shared admin tools)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user

from utils.decorators import moderator_required, role_required
from extensions import db
from models.social import PublicChat
from models.system import SecurityLog, SystemConfig
from models.user import User, UserRole
from services.staff_access import (
    role_label,
    staff_capabilities,
    staff_hub_links,
)
from . import bp


def _parse_log_details(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {'raw': raw}


def _now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@bp.route('/staff/chat')
@moderator_required
def staff_chat():
    now = _now_naive()

    reports_raw = (
        SecurityLog.query.filter_by(event_type='chat_report')
        .order_by(SecurityLog.timestamp.desc())
        .limit(100)
        .all()
    )
    reports = []
    for row in reports_raw:
        details = _parse_log_details(row.details)
        reports.append({
            'id': row.id,
            'timestamp': row.timestamp,
            'ip': row.ip_address,
            'details': details,
        })

    ban_logs = (
        SecurityLog.query.filter_by(event_type='chat_ban')
        .order_by(SecurityLog.timestamp.desc())
        .limit(30)
        .all()
    )

    chat_banned = (
        User.query.filter_by(is_chat_banned=True)
        .order_by(User.username.asc())
        .limit(200)
        .all()
    )
    muted = (
        User.query.filter(User.chat_muted_until.isnot(None))
        .filter(User.chat_muted_until > now)
        .order_by(User.chat_muted_until.desc())
        .limit(200)
        .all()
    )

    slow_global = SystemConfig.get_value('chat_slow_mode_seconds', '2')
    slow_vip = SystemConfig.get_value('chat_slow_mode_seconds_vip', slow_global)
    slow_general = SystemConfig.get_value(
        'chat_slow_mode_seconds_general', slow_global)

    can_edit_settings = current_user.role.value >= UserRole.ADMIN.value

    return render_template(
        'staff/chat_dashboard.html',
        title=_('إدارة الدردشة'),
        reports=reports,
        ban_logs=ban_logs,
        chat_banned=chat_banned,
        muted_users=muted,
        slow_global=slow_global,
        slow_vip=slow_vip,
        slow_general=slow_general,
        can_edit_settings=can_edit_settings,
        staff_capabilities=staff_capabilities(current_user),
        hub_links=staff_hub_links(current_user),
        role_label=role_label(current_user.role),
        now=now,
    )


@bp.route('/staff/chat/unban/<int:user_id>', methods=['POST'])
@moderator_required
def staff_chat_unban(user_id):
    from services.chat_security import moderator_can_act

    user = db.session.get(User, user_id)
    if not user:
        flash(_('المستخدم غير موجود.'), 'danger')
        return redirect(url_for('main.staff_chat'))
    if not moderator_can_act(current_user, user):
        flash(_('لا يمكنك إلغاء حظر هذا المستخدم.'), 'danger')
        return redirect(url_for('main.staff_chat'))

    user.is_chat_banned = False
    db.session.commit()
    flash(_('تم إلغاء حظر %(name)s من الدردشة.', name=user.username), 'success')
    return redirect(url_for('main.staff_chat'))


@bp.route('/staff/chat/unmute/<int:user_id>', methods=['POST'])
@moderator_required
def staff_chat_unmute(user_id):
    from services.chat_security import moderator_can_act

    user = db.session.get(User, user_id)
    if not user:
        flash(_('المستخدم غير موجود.'), 'danger')
        return redirect(url_for('main.staff_chat'))
    if not moderator_can_act(current_user, user):
        flash(_('لا يمكنك إلغاء كتم هذا المستخدم.'), 'danger')
        return redirect(url_for('main.staff_chat'))

    user.chat_muted_until = None
    db.session.commit()
    flash(_('تم إلغاء كتم %(name)s.', name=user.username), 'success')
    return redirect(url_for('main.staff_chat'))


@bp.route('/staff/chat/settings', methods=['POST'])
@role_required(UserRole.ADMIN)
def staff_chat_settings():
    try:
        slow = max(0, min(60, int(request.form.get('chat_slow_mode_seconds', 2))))
        slow_general = max(
            0, min(60, int(request.form.get('chat_slow_mode_seconds_general', slow))))
        slow_vip = max(
            0, min(60, int(request.form.get('chat_slow_mode_seconds_vip', slow))))
        SystemConfig.set_value(
            'chat_slow_mode_seconds',
            slow,
            _('بطء الإرسال الافتراضي (ثوانٍ)'))
        SystemConfig.set_value(
            'chat_slow_mode_seconds_general',
            slow_general,
            _('بطء غرفة العام'))
        SystemConfig.set_value(
            'chat_slow_mode_seconds_vip',
            slow_vip,
            _('بطء غرفة VIP'))
        flash(_('تم حفظ إعدادات الدردشة.'), 'success')
    except Exception:
        flash(_('قيم غير صالحة.'), 'danger')
    return redirect(url_for('main.staff_chat'))


@bp.route('/staff/chat/delete/<int:msg_id>', methods=['POST'])
@moderator_required
def staff_chat_delete_message(msg_id):
    msg = db.session.get(PublicChat, msg_id)
    if not msg:
        flash(_('الرسالة غير موجودة.'), 'danger')
        return redirect(url_for('main.staff_chat'))

    room = msg.room or 'general'
    db.session.delete(msg)
    db.session.commit()

    try:
        from services.chat_realtime import emit_public_chat_delete
        emit_public_chat_delete(room, msg_id)
    except Exception:
        pass

    flash(_('تم حذف الرسالة.'), 'success')
    return redirect(url_for('main.staff_chat'))
