from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models import User
from models.hostess import Hostess
from services.resource_service import ResourceService
from .utils import update_daily_task_progress
from datetime import datetime, timezone, timedelta
import json
import random

bp = Blueprint('gym', __name__, url_prefix='/gym')

def _claim_rewards(user):
    if not user.gym_activity:
        user.gym_until = None
        db.session.commit()
        return False
        
    try:
        data = json.loads(user.gym_activity)
        stat = data.get('stat')
        exp_gain = data.get('exp_gain', 0)
        stat_gain = data.get('stat_gain', 0)
        
        changes = {
            'exp': exp_gain,
            stat: stat_gain
        }
        
        ResourceService.modify_resources(
            user.id,
            changes,
            f'gym_reward_{stat}',
            auto_commit=False,
            expected_version=user.version
        )
        
        user.add_rank_points(1)
        if user.check_level_up():
            flash(_('مبروك! وصلت للمستوى %(level)s!', level=user.level), 'success')
            
        update_daily_task_progress(user, 'gym')
        
        msg = _('انتهى التمرين! حصلت على %(exp)s خبرة و %(stat)s %(stat_name)s', 
               exp=exp_gain, stat=stat_gain, stat_name=stat)
        flash(msg, 'success')
        
    except Exception as e:
        flash(_('حدث خطأ أثناء استلام المكافأة.'), 'danger')
        
    user.gym_activity = None
    user.gym_until = None
    db.session.commit()
    return True

@bp.route('/')
@login_required
def index():
    now = datetime.now(timezone.utc)
    remaining_seconds = 0
    
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
            
        if now >= gym_until:
            _claim_rewards(current_user)
            return redirect(url_for('gym.index'))
            
        remaining_seconds = int((gym_until - now).total_seconds())
            
    return render_template('gym.html', user=current_user, now=now, remaining_seconds=remaining_seconds)

@bp.route('/cancel', methods=['POST'])
@login_required
def cancel_training():
    if not current_user.gym_activity:
        current_user.gym_until = None
        db.session.commit()
        flash(_('تم إلغاء فترة الراحة.'), 'info')
        return redirect(url_for('gym.index'))
        
    try:
        data = json.loads(current_user.gym_activity)
        stat = data.get('stat')
        total_exp = data.get('exp_gain', 0)
        total_stat = data.get('stat_gain', 0)
        start_ts = data.get('start_time', 0)
        duration = data.get('duration', 120)
        
        start_time = datetime.fromtimestamp(start_ts, timezone.utc)
        now = datetime.now(timezone.utc)
        elapsed = (now - start_time).total_seconds()
        
        # Calculate ratio (cap at 1.0)
        ratio = min(1.0, max(0.0, elapsed / duration))
        
        partial_exp = int(total_exp * ratio)
        partial_stat = total_stat * ratio 
        
        # Probabilistic rounding for stats
        earned_stat = int(partial_stat)
        remainder = partial_stat - earned_stat
        if random.random() < remainder:
            earned_stat += 1
            
        if earned_stat > 0 or partial_exp > 0:
            changes = {
                'exp': partial_exp,
                stat: earned_stat
            }
            ResourceService.modify_resources(current_user.id, changes, f'gym_partial_{stat}', auto_commit=False)
            flash(_('تم إنهاء التمرين مبكراً. حصلت على %(exp)s خبرة و %(stat)s %(stat_name)s بناءً على المدة التي قضيتها.', 
                   exp=partial_exp, stat=earned_stat, stat_name=stat), 'warning')
        else:
             flash(_('تم إنهاء التمرين مبكراً جداً! لم تحصل على أي فائدة.'), 'warning')

    except Exception as e:
        # flash(str(e), 'danger') # Debug
        flash(_('حدث خطأ أثناء الإلغاء.'), 'danger')

    current_user.gym_activity = None
    current_user.gym_until = None
    db.session.commit()
    return redirect(url_for('gym.index'))

@bp.route('/train/<stat>', methods=['POST'])
@login_required
def train(stat):
    # Lock user row to prevent concurrent training
    user = db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Check if already training
    now = datetime.now(timezone.utc)
    
    if user.gym_until:
        gym_until = user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
            
        if gym_until > now:
            remaining = gym_until - now
            minutes = int(remaining.total_seconds() / 60)
            seconds = int(remaining.total_seconds() % 60)
            flash(_('أنت تتمرن حالياً! انتظر %(min)s دقيقة و %(sec)s ثانية.', min=minutes, sec=seconds), 'warning')
            return redirect(url_for('gym.index'))

    if stat == 'intelligence':
        cost_energy = 10
    else:
        cost_energy = 5
    cost_money = 100
    
    # Atomic Deduction for Money AND Energy
    success = ResourceService.modify_resources(
        user_id=current_user.id,
        changes={'money': -cost_money, 'energy': -cost_energy},
        reason=f'gym_train_{stat}',
        auto_commit=False,
        expected_version=user.version
    )
    
    if not success:
        if current_user.money < cost_money:
            flash(_('طفرنا! بدك مصاري عشان تتمرن.'), 'danger')
        elif current_user.energy < cost_energy:
            flash(_('طاقتك ما بتكفي للتمرين!'), 'danger')
        else:
            flash(_('حدث خطأ أثناء الخصم، حاول مرة أخرى.'), 'danger')
        return redirect(url_for('gym.index'))
    
    # Check for injury chance
    if not current_app.config.get('TESTING', False) and random.randint(1, 100) <= 2:
        hospital_time = 120 # 2 minutes
        current_user.hospital_until = datetime.now(timezone.utc) + timedelta(seconds=hospital_time)
        
        flash(_('آخ! شديت على حالك زيادة ومزقت عضلة. ريح شوي بالمستشفى.'), 'danger')
        db.session.commit()
        return redirect(url_for('hospital.index'))

    if stat == 'strength':
        stat_gain = 1
        msg = _('تمرنت وزادت قوتك!')
    elif stat == 'defense':
        stat_gain = 1
        msg = _('تمرنت وزاد دفاعك!')
    elif stat == 'agility':
        stat_gain = 1
        msg = _('تمرنت وزادت رشاقتك!')
    elif stat == 'intelligence':
        stat_gain = 1
        msg = _('درست وزاد ذكاؤك!')
    else:
        flash(_('تمرين غير معروف!'), 'danger')
        return redirect(url_for('gym.index'))
        
    # Hostess Buff
    exp_gain = 2
    
    # Track extra stats for hostess buff
    extra_stat_gain = 0
    
    if current_user.active_hostess_id:
        hostess = db.session.get(Hostess, current_user.active_hostess_id)
        if hostess and hostess.buff_type == 'gym_boost':
            extra_exp = int(2 * (hostess.buff_value if hostess.buff_value else 0.5))
            exp_gain += extra_exp
            
            # Chance for double stat gain
            chance = hostess.buff_value if hostess.buff_value else 0.2
            if random.random() < chance:
                extra_stat_gain = 1
                msg += _(" (مكافأة المضيفة: تدريب مضاعف!)")

    # Store Activity Data (Instead of applying immediately)
    activity_data = {
        'stat': stat,
        'exp_gain': exp_gain,
        'stat_gain': stat_gain + extra_stat_gain,
        'start_time': datetime.now(timezone.utc).timestamp(),
        'duration': 120
    }
    
    current_user.gym_activity = json.dumps(activity_data)
    
    now = datetime.now(timezone.utc)
    current_user.last_gym_training = now
    # Set Gym Status for 2 minutes
    current_user.gym_until = now + timedelta(minutes=2)
    
    db.session.commit()
    
    flash(msg + _(' (بدأ التدريب...)'), 'success')
    return redirect(url_for('gym.index'))
