from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models import User
from models.hostess import Hostess
from datetime import datetime, timezone, timedelta
from .utils import update_daily_task_progress

bp = Blueprint('hospital', __name__, url_prefix='/hospital')

@bp.route('/')
@login_required
def index():
    return render_template('hospital.html', user=current_user)

@bp.route('/heal', methods=['POST'])
@login_required
def heal():
    cost_per_hp = 10
    now = datetime.now(timezone.utc)
    
    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > now:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'hospital_recovery':
                discount = hostess.buff_value if hostess.buff_value else 0.2
                cost_per_hp = max(1, int(cost_per_hp * (1 - discount)))

    needed_health = current_user.max_health - current_user.health
    
    if needed_health <= 0:
        flash(_('صحتك ممتازة، شو جاي تعمل هون؟'), 'info')
        return redirect(url_for('hospital.index'))
        
    cost = needed_health * cost_per_hp
    
    if current_user.money < cost:
        # Heal partially
        affordable_health = current_user.money // cost_per_hp
        if affordable_health == 0:
            flash(_('طفرنا! ارجع لما يكون معك مصاري.'), 'danger')
            return redirect(url_for('hospital.index'))
            
        current_user.health += affordable_health
        current_user.money -= (affordable_health * cost_per_hp)
        flash(_('تم علاجك جزئياً على قد فلوسك.'), 'warning')
    else:
        current_user.health = current_user.max_health
        current_user.money -= cost
        flash(_('تم علاجك بالكامل! رجعت حصان.'), 'success')
        # Only clear hospital timer if fully healed? Or reduce it?
        # For simplicity, if fully healed, clear it.
        current_user.hospital_until = None
        
    db.session.commit()
    return redirect(url_for('hospital.index'))

@bp.route('/buy_energy', methods=['POST'])
@login_required
def buy_energy():
    cost = 500
    energy_gain = 50
    now = datetime.now(timezone.utc)
    bonus_double_chance = 0.0

    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > now:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'hospital_recovery':
                boost = hostess.buff_value if hostess.buff_value else 0.1
                energy_gain = max(1, int(energy_gain * (1 + boost)))
                bonus_double_chance = min(0.2, boost)
    
    if current_user.money < cost:
        flash(_('طفرنا! بدك 500$ حق مشروب الطاقة.'), 'danger')
        return redirect(url_for('hospital.index'))
    
    if current_user.energy >= current_user.max_energy:
        flash(_('طاقتك مفولة يا وحش!'), 'info')
        return redirect(url_for('hospital.index'))
        
    current_user.money -= cost
    
    # Random Bonus (Red Bull Effect)
    import random
    if random.random() < (0.1 + bonus_double_chance):
        energy_gain *= 2
        flash(_('🚀 المشروب كان أصلي! دبل طاقة! (+%(energy)s طاقة)', energy=energy_gain), 'success')
    else:
        flash(_('شربت مشروب طاقة ورجعتلك الحيوية! (+%(energy)s طاقة)', energy=energy_gain), 'success')

    current_user.energy = min(current_user.energy + energy_gain, current_user.max_energy)
    
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    return redirect(url_for('hospital.index'))

@bp.route('/experimental_surgery', methods=['POST'])
@login_required
def experimental_surgery():
    # Check if already hospitalized
    now = datetime.now(timezone.utc)
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت مريض أصلاً! استنى لما تتعالج.'), 'warning')
            return redirect(url_for('hospital.index'))

    stat_type = request.form.get('type')
    if stat_type not in ['strength', 'defense']:
        flash(_('نوع العملية غير صالح!'), 'danger')
        return redirect(url_for('hospital.index'))

    cost = 50000
    if current_user.money < cost:
        flash(_('العملية مكلفة جداً! تحتاج %(cost)s$.', cost=cost), 'danger')
        return redirect(url_for('hospital.index'))
    
    current_user.money -= cost
    
    import random
    roll = random.randint(1, 100)

    success_threshold = 40
    fail_threshold = 80
    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > now:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'hospital_recovery':
                boost = hostess.buff_value if hostess.buff_value else 0.1
                bonus = min(10, int(boost * 25))
                success_threshold = min(60, success_threshold + bonus)
                fail_threshold = min(90, fail_threshold + bonus)
    
    if roll <= success_threshold:
        gain = random.randint(2, 5)
        if stat_type == 'strength':
            current_user.strength += gain
            msg = _('نجحت العملية! زادت قوتك بمقدار %(gain)s.', gain=gain)
        else:
            current_user.defense += gain
            msg = _('نجحت العملية! زاد دفاعك بمقدار %(gain)s.', gain=gain)
        flash(msg, 'success')
        
    elif roll <= fail_threshold:
        current_user.health = 1
        current_user.hospital_until = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None)
        flash(_('فشلت العملية! الطبيب كان سكران... خسرت فلوسك وصحتك تدهورت.'), 'danger')
        
    else:
        loss = 1
        if stat_type == 'strength':
            current_user.strength = max(1, current_user.strength - loss)
            msg = _('كارثة طبية! العضلات ضمرت... (-%(loss)s قوة)', loss=loss)
        else:
            current_user.defense = max(1, current_user.defense - loss)
            msg = _('كارثة طبية! جسمك صار أضعف... (-%(loss)s دفاع)', loss=loss)
            
        current_user.health = 1
        current_user.hospital_until = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(tzinfo=None)
        flash(msg, 'danger')
        
    db.session.commit()
    return redirect(url_for('hospital.index'))
