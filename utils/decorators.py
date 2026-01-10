from functools import wraps
from flask import flash, redirect, url_for
from flask_babel import gettext as _
from flask_login import current_user
from datetime import datetime, timezone

def check_player_status(func):
    """
    Decorator to check if player is in Jail, Hospital, or Gym.
    Redirects to appropriate page if restricted.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return func(*args, **kwargs)
            
        now = datetime.now(timezone.utc)
        
        # Check Jail
        if current_user.jail_until:
            jail_until = current_user.jail_until
            if jail_until.tzinfo is None:
                jail_until = jail_until.replace(tzinfo=timezone.utc)
            if jail_until > now:
                flash(_('أنت في السجن ولا يمكنك القيام بهذا النشاط!'), 'danger')
                return redirect(url_for('jail.index'))
        
        # Check Hospital
        if current_user.hospital_until:
            hospital_until = current_user.hospital_until
            if hospital_until.tzinfo is None:
                hospital_until = hospital_until.replace(tzinfo=timezone.utc)
            if hospital_until > now:
                flash(_('أنت في المستشفى ولا يمكنك القيام بهذا النشاط!'), 'danger')
                return redirect(url_for('hospital.index'))

        # Check Gym
        if current_user.gym_until:
            gym_until = current_user.gym_until
            if gym_until.tzinfo is None:
                gym_until = gym_until.replace(tzinfo=timezone.utc)
            if gym_until > now:
                flash(_('أنت تتدرب ولا يمكنك القيام بهذا النشاط!'), 'danger')
                return redirect(url_for('gym.index'))
                
        return func(*args, **kwargs)
    return wrapper
