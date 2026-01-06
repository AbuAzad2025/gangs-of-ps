from flask import Blueprint, request, redirect, url_for, flash
from flask_login import current_user
from extensions import db
from datetime import datetime, timezone
from flask_babel import _

bp = Blueprint('main', __name__)

@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        # 1. Jail Check (Integration)
        if current_user.jail_until:
            now = datetime.now(timezone.utc)
            jail_until = current_user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)
            
            if jail_until > now:
                # User is in jail. Restrict access.
                endpoint = request.endpoint
                if not endpoint:
                    return

                # Allowed Prefixes
                if endpoint.startswith('jail.') or endpoint.startswith('static'):
                    return
                
                # Allowed Specific Endpoints (Auth & Communication)
                allowed_endpoints = {
                    'main.logout', 
                    'main.messages', 
                    'main.view_message', 
                    'main.notifications', 
                    'main.read_notification',
                    'main.read_all_notifications',
                    'main.delete_notification'
                }
                
                if endpoint in allowed_endpoints:
                    return

                # Prevent redirect loop
                if endpoint == 'jail.index':
                    return

                flash(_('🚫 لا يمكنك التجول وأنت في سجن عوفر!'), 'danger')
                return redirect(url_for('jail.index'))

        # 2. Resource Regeneration
        try:
            # Check if method exists (handling potential migration lag during dev)
            if hasattr(current_user, 'regenerate_resources'):
                current_user.regenerate_resources()
                db.session.commit()
        except Exception:
            db.session.rollback()

from . import auth, core, gameplay, payment, social, economy, garage, developer, search, graveyard, racing, errors, trend, black_market
