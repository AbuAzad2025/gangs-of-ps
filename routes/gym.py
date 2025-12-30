from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models.hostess import Hostess
from .utils import update_daily_task_progress
from datetime import datetime, timezone, timedelta
import random

bp = Blueprint('gym', __name__, url_prefix='/gym')

@bp.route('/')
@login_required
def index():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    remaining_seconds = 0
    if current_user.gym_until and current_user.gym_until > now:
        remaining_seconds = int((current_user.gym_until - now).total_seconds())
    return render_template('gym.html', user=current_user, now=now, remaining_seconds=remaining_seconds)

@bp.route('/train/<stat>', methods=['POST'])
@login_required
def train(stat):
    # Check if already training
    if current_user.gym_until and current_user.gym_until > datetime.now(timezone.utc).replace(tzinfo=None):
        remaining = current_user.gym_until - datetime.now(timezone.utc).replace(tzinfo=None)
        minutes = int(remaining.total_seconds() / 60)
        seconds = int(remaining.total_seconds() % 60)
        flash(_('أنت تتمرن حالياً! انتظر %(min)s دقيقة و %(sec)s ثانية.', min=minutes, sec=seconds), 'warning')
        return redirect(url_for('gym.index'))

    if stat == 'intelligence':
        cost_energy = 10
    else:
        cost_energy = 5
    cost_money = 100
    
    if current_user.energy < cost_energy:
        flash(_('طاقتك ما بتكفي للتمرين!'), 'danger')
        return redirect(url_for('gym.index'))
        
    if current_user.money < cost_money:
        flash(_('طفرنا! بدك مصاري عشان تتمرن.'), 'danger')
        return redirect(url_for('gym.index'))
    
    current_user.energy -= cost_energy
    current_user.money -= cost_money
    
    if not current_app.config.get('TESTING', False) and random.randint(1, 100) <= 2:
        hospital_time = 120 # 2 minutes
        current_user.hospital_until = (datetime.now(timezone.utc) + timedelta(seconds=hospital_time)).replace(tzinfo=None)
        
        flash(_('آخ! شديت على حالك زيادة ومزقت عضلة. ريح شوي بالمستشفى.'), 'danger')
        db.session.commit()
        return redirect(url_for('hospital.index'))

    if stat == 'strength':
        current_user.strength += 1
        msg = _('تمرنت وزادت قوتك!')
    elif stat == 'defense':
        current_user.defense += 1
        msg = _('تمرنت وزاد دفاعك!')
    elif stat == 'agility':
        current_user.agility += 1
        msg = _('تمرنت وزادت رشاقتك!')
    elif stat == 'intelligence':
        current_user.intelligence += 1
        msg = _('درست وزاد ذكاؤك!')
    else:
        flash(_('تمرين غير معروف!'), 'danger')
        return redirect(url_for('gym.index'))
        
    # Hostess Buff
    exp_gain = 2
    if current_user.active_hostess_id:
        hostess = db.session.get(Hostess, current_user.active_hostess_id)
        if hostess and hostess.buff_type == 'gym_boost':
            extra_exp = int(2 * (hostess.buff_value if hostess.buff_value else 0.5))
            exp_gain += extra_exp
            
            # Chance for double stat gain
            chance = hostess.buff_value if hostess.buff_value else 0.2
            if random.random() < chance:
                if stat == 'strength': current_user.strength += 1
                elif stat == 'defense': current_user.defense += 1
                elif stat == 'agility': current_user.agility += 1
                elif stat == 'intelligence': current_user.intelligence += 1
                msg += _(" (مكافأة المضيفة: تدريب مضاعف!)")

    current_user.exp += exp_gain
    current_user.add_rank_points(1)
    if current_user.check_level_up():
        flash(_('مبروك! وصلت للمستوى %(level)s!', level=current_user.level), 'success')

    now = datetime.now(timezone.utc)
    current_user.last_gym_training = now
    # Set Gym Status for 2 minutes
    current_user.gym_until = (now + timedelta(minutes=2)).replace(tzinfo=None)
    
    db.session.commit()
    
    update_daily_task_progress(current_user, 'gym')
    
    flash(msg, 'success')
    return redirect(url_for('gym.index'))
