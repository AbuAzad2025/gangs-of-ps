from functools import wraps
from flask import flash, redirect, url_for, session, request
from flask_babel import gettext as _
from flask_login import current_user
from models.user import UserRole
from datetime import datetime, timezone, timedelta


def check_player_status(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return func(*args, **kwargs)
        now = datetime.now(timezone.utc)
        if current_user.jail_until:
            jail_until = current_user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)
            if jail_until > now:
                flash(_('أنت في السجن ولا يمكنك القيام بهذا النشاط!'), 'danger')
                return redirect(url_for('jail.index'))
        if current_user.hospital_until:
            hospital_until = current_user.hospital_until
            if hospital_until.tzinfo is None:
                hospital_until = hospital_until.replace(tzinfo=timezone.utc)
            if hospital_until > now:
                flash(_('أنت في المستشفى ولا يمكنك القيام بهذا النشاط!'), 'danger')
                return redirect(url_for('hospital.index'))
        if current_user.gym_until:
            gym_until = current_user.gym_until
            if gym_until.tzinfo is None:
                gym_until = gym_until.replace(tzinfo=timezone.utc)
            if gym_until > now:
                flash(_('أنت تتدرب ولا يمكنك القيام بهذا النشاط!'), 'danger')
                return redirect(url_for('gym.index'))
        return func(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('main.login'))
            if current_user.role.value < role.value:
                flash(_('ليس لديك صلاحية للوصول إلى هذه الصفحة.'), 'danger')
                return redirect(url_for('main.hara'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    return role_required(UserRole.ADMIN)(f)


def super_admin_required(f):
    return role_required(UserRole.SUPER_ADMIN)(f)


def developer_required(f):
    return role_required(UserRole.DEVELOPER)(f)


def moderator_required(f):
    return role_required(UserRole.MODERATOR)(f)


def double_verification_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        verified_at_str = session.get('admin_verified_at')
        if not verified_at_str:
            session['next_url'] = request.url
            return redirect(url_for('main.admin_verify'))
        try:
            if isinstance(verified_at_str, str):
                verified_at = datetime.fromisoformat(verified_at_str)
            else:
                verified_at = verified_at_str
            if verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - verified_at > timedelta(minutes=15):
                session.pop('admin_verified_at', None)
                session['next_url'] = request.url
                flash(_('انتهت جلسة التحقق، يرجى التأكيد مرة أخرى.'), 'warning')
                return redirect(url_for('main.admin_verify'))
        except Exception:
            session.pop('admin_verified_at', None)
            session['next_url'] = request.url
            return redirect(url_for('main.admin_verify'))
        return f(*args, **kwargs)
    return decorated_function


def check_maintenance(feature_key=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from models.system import SystemConfig
            if SystemConfig.get_value('maintenance_mode') == 'true':
                if not current_user.is_authenticated or current_user.role.value < UserRole.ADMIN.value:
                    flash(_('النظام في وضع الصيانة حالياً.'), 'warning')
                    return redirect(url_for('main.index'))
            if feature_key:
                if SystemConfig.get_value(f'maintenance_{feature_key}') == 'true':
                    if not current_user.is_authenticated or current_user.role.value < UserRole.ADMIN.value:
                        flash(_('هذه الميزة معطلة مؤقتاً للصيانة.'), 'warning')
                        return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def player_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        if current_user.role.value >= UserRole.MODERATOR.value:
            if current_user.role != UserRole.DEVELOPER:
                flash(_('لا يُسمح للإداريين بالمشاركة في اللعب لضمان النزاهة.'), 'danger')
                return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function
