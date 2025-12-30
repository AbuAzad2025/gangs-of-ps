from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user
from models.user import UserRole
from flask_babel import _

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
