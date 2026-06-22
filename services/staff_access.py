"""Staff permissions, role labels, and hub links (UserRole vs UserRank)."""
from __future__ import annotations

from typing import Any, Dict, List

from flask_babel import lazy_gettext as _

from models.user import UserRole


# UserRole = صلاحية إدارية/حساب (مشرف، مدير، مطور، VIP...)
# UserRank  = رتبة لعب تلقائية من المستوى (متشرد، لص، زعيم...)

ADMIN_ROLE_LABELS = {
    UserRole.GUEST: _('زائر (دردشة فقط)'),
    UserRole.USER: _('لاعب عادي'),
    UserRole.SUBSCRIBER: _('مشترك VIP'),
    UserRole.MODERATOR: _('مشرف'),
    UserRole.ADMIN: _('مدير'),
    UserRole.SUPER_ADMIN: _('مدير أعلى'),
    UserRole.DEVELOPER: _('مطور'),
}


def role_label(role: UserRole) -> str:
    if role is None:
        return str(_('لاعب'))
    return str(ADMIN_ROLE_LABELS.get(role, role.name))


def selectable_admin_roles() -> List[UserRole]:
    return [
        UserRole.GUEST,
        UserRole.USER,
        UserRole.SUBSCRIBER,
        UserRole.MODERATOR,
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
        UserRole.DEVELOPER,
    ]


def is_staff(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if not user.is_authenticated:
        return False
    try:
        return user.role.value >= UserRole.MODERATOR.value
    except Exception:
        return False


def staff_hub_links(user) -> List[Dict[str, Any]]:
    """Navigation entries for profile/sidebar based on administrative role."""
    if not is_staff(user):
        return []

    links: List[Dict[str, Any]] = [
        {
            'endpoint': 'main.staff_chat',
            'icon': 'fas fa-comments',
            'label': _('إدارة الدردشة'),
            'css': 'text-warning',
        },
        {
            'endpoint': 'main.chat_lobby',
            'icon': 'fas fa-door-open',
            'label': _('غرف الدردشة'),
            'css': 'text-info',
        },
    ]

    if getattr(user, 'is_admin', False) or getattr(user, 'is_developer', False):
        links.append({
            'url': '/admin/',
            'icon': 'fas fa-user-shield',
            'label': _('لوحة التحكم (Admin)'),
            'css': 'text-danger',
        })

    if getattr(user, 'is_developer', False):
        links.extend([
            {
                'endpoint': 'main.dev_dashboard',
                'icon': 'fas fa-code',
                'label': _('لوحة المطور'),
                'css': 'text-info',
            },
            {
                'endpoint': 'main.dev_users',
                'icon': 'fas fa-users-cog',
                'label': _('إدارة اللاعبين'),
                'css': 'text-light',
            },
            {
                'endpoint': 'main.dev_settings',
                'icon': 'fas fa-cogs',
                'label': _('إعدادات النظام'),
                'css': 'text-gold',
            },
        ])

    return links


def staff_capabilities(user) -> List[str]:
    """Human-readable list of what this role can do (own profile)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    caps: List[str] = []
    try:
        role = user.role
    except Exception:
        return caps

    if role.value >= UserRole.MODERATOR.value:
        caps.extend([
            _('حذف رسائل الدردشة العامة وكتم/حظر المخالفين'),
            _('مراجعة بلاغات الدردشة من لوحة الإشراف'),
            _('عرض موازنة اللاعبين عند زيارة ملفاتهم'),
        ])
    if role.value >= UserRole.ADMIN.value:
        caps.extend([
            _('الوصول إلى Flask-Admin لإدارة المحتوى والمستخدمين'),
            _('تعديل إعدادات الدردشة (بطء الإرسال)'),
        ])
    if role == UserRole.DEVELOPER:
        caps.extend([
            _('لوحة المطور الكاملة: اقتصاد، نسخ احتياطي، موسم، صيانة'),
            _('تعديل موارد اللاعبين وتعيين الصلاحيات الإدارية'),
            _('تقرير المال الحقيقي في الملف الشخصي'),
        ])
    return caps
