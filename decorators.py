from functools import wraps
from flask import abort, redirect, url_for, flash, session, request
from flask_login import current_user
from models.user import UserRole
from flask_babel import _
from datetime import datetime, timedelta, timezone

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('main.login'))
            
            # Hierarchical check: DEVELOPER > ADMIN > MODERATOR > USER
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
            return redirect(url_for('developer.admin_verify'))
        
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
                return redirect(url_for('developer.admin_verify'))
        except Exception:
            session.pop('admin_verified_at', None)
            session['next_url'] = request.url
            return redirect(url_for('developer.admin_verify'))
        
        return f(*args, **kwargs)
    return decorated_function

def check_maintenance(feature_key=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from models.system import SystemConfig
            
            # Global maintenance
            if SystemConfig.get_value('maintenance_mode') == 'true':
                if not current_user.is_authenticated or current_user.role.value < UserRole.ADMIN.value:
                     flash(_('النظام في وضع الصيانة حالياً.'), 'warning')
                     return redirect(url_for('main.index'))

            # Feature specific lock
            if feature_key:
                if SystemConfig.get_value(f'maintenance_{feature_key}') == 'true':
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
            # Allow Developers and Master Key 'azad' to play
            if current_user.role != UserRole.DEVELOPER and current_user.username != 'azad':
                flash(_('لا يُسمح للإداريين بالمشاركة في اللعب لضمان النزاهة.'), 'danger')
                return redirect(url_for('main.index'))
            
        return f(*args, **kwargs)
    return decorated_function
