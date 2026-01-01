from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models import User
from models.hostess import Hostess
from services.resource_service import ResourceService
from datetime import datetime, timezone, timedelta
from .utils import update_daily_task_progress

bp = Blueprint('hospital', __name__, url_prefix='/hospital')

@bp.route('/')
@login_required
def index():
    # Calculate costs with discounts
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

    return render_template('hospital.html', user=current_user, cost_per_hp=cost_per_hp)

@bp.route('/heal', methods=['POST'])
@login_required
def heal():
    # Lock user row
    user = db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    cost_per_hp = 10
    now = datetime.now(timezone.utc)
    
    if user.active_hostess_id and user.casino_luck_until:
        luck_until = user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > now:
            hostess = db.session.get(Hostess, user.active_hostess_id)
            if hostess and hostess.buff_type == 'hospital_recovery':
                discount = hostess.buff_value if hostess.buff_value else 0.2
                cost_per_hp = max(1, int(cost_per_hp * (1 - discount)))

    needed_health = user.max_health - user.health
    
    if needed_health <= 0:
        flash(_('صحتك ممتازة، شو جاي تعمل هون؟'), 'info')
        return redirect(url_for('hospital.index'))
        
    cost = needed_health * cost_per_hp
    
    if user.money < cost:
        # Heal partially
        affordable_health = user.money // cost_per_hp
        if affordable_health == 0:
            flash(_('طفرنا! ارجع لما يكون معك مصاري.'), 'danger')
            return redirect(url_for('hospital.index'))
        
        cost_real = affordable_health * cost_per_hp
        # Atomic Update
        success = ResourceService.modify_resources(
            user_id=user.id,
            changes={'money': -cost_real, 'health': affordable_health},
            reason='hospital_heal_partial',
            auto_commit=False,
            expected_version=user.version
        )

        if not success:
            flash(_('حدث خطأ أثناء المعالجة، يرجى المحاولة مرة أخرى.'), 'danger')
            return redirect(url_for('hospital.index'))
            
        flash(_('تم علاجك جزئياً على قد فلوسك.'), 'warning')
    else:
        # Atomic Update
        success = ResourceService.modify_resources(
            user_id=user.id,
            changes={'money': -cost, 'health': needed_health},
            reason='hospital_heal_full',
            auto_commit=False,
            expected_version=user.version
        )

        if not success:
            flash(_('حدث خطأ أثناء المعالجة، يرجى المحاولة مرة أخرى.'), 'danger')
            return redirect(url_for('hospital.index'))

        flash(_('تم علاجك بالكامل! رجعت حصان.'), 'success')
        # Only clear hospital timer if fully healed? Or reduce it?
        # For simplicity, if fully healed, clear it.
        user.hospital_until = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash(_('حدث خطأ أثناء حفظ البيانات، يرجى المحاولة مرة أخرى.'), 'danger')
            return redirect(url_for('hospital.index'))
        
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
        
    if current_user.energy >= current_user.max_energy:
        flash(_('طاقتك مفولة يا وحش!'), 'info')
        return redirect(url_for('hospital.index'))
        
    # Lock user to calculate actual energy gain respecting max_energy
    user = db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    if user.money < cost:
        flash(_('طفرنا! بدك 500$ حق مشروب الطاقة.'), 'danger')
        return redirect(url_for('hospital.index'))
    
    # Random Bonus (Red Bull Effect)
    import random
    if random.random() < (0.1 + bonus_double_chance):
        energy_gain *= 2
        flash(_('🚀 المشروب كان أصلي! دبل طاقة! (+%(energy)s طاقة)', energy=energy_gain), 'success')
    else:
        flash(_('شربت مشروب طاقة ورجعتلك الحيوية! (+%(energy)s طاقة)', energy=energy_gain), 'success')

    actual_gain = min(energy_gain, user.max_energy - user.energy)
    
    # Atomic Update via ResourceService
    success = ResourceService.modify_resources(
        user_id=user.id,
        changes={'money': -cost, 'energy': actual_gain},
        reason='hospital_buy_energy',
        auto_commit=True,
        expected_version=user.version
    )

    if not success:
        flash(_('حدث خطأ أثناء الشراء، يرجى المحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('hospital.index'))
    
    update_daily_task_progress(current_user, 'buy')
    return redirect(url_for('hospital.index'))

@bp.route('/experimental_surgery', methods=['POST'])
@login_required
def experimental_surgery():
    # Lock user row
    user = db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    # Check if already hospitalized
    now = datetime.now(timezone.utc)
    if user.hospital_until:
        hospital_until = user.hospital_until
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
    if user.money < cost:
        flash(_('العملية مكلفة جداً! تحتاج %(cost)s$.', cost=cost), 'danger')
        return redirect(url_for('hospital.index'))

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
    
    changes = {'money': -cost}
    hospital_duration = None
    
    if roll <= success_threshold:
        gain = random.randint(2, 5)
        changes[stat_type] = gain
        if stat_type == 'strength':
            msg = _('نجحت العملية! زادت قوتك بمقدار %(gain)s.', gain=gain)
        else:
            msg = _('نجحت العملية! زاد دفاعك بمقدار %(gain)s.', gain=gain)
        flash(msg, 'success')
        
    elif roll <= fail_threshold:
        changes['health'] = 1 - user.health
        hospital_duration = timedelta(hours=1)
        flash(_('فشلت العملية! الطبيب كان سكران... خسرت فلوسك وصحتك تدهورت.'), 'danger')
        
    else:
        loss = 1
        current_val = getattr(user, stat_type)
        if current_val > 1:
            changes[stat_type] = -loss
            loss_applied = loss
        else:
            loss_applied = 0
            
        changes['health'] = 1 - user.health
        hospital_duration = timedelta(hours=2)
        
        if stat_type == 'strength':
            msg = _('كارثة طبية! العضلات ضمرت... (-%(loss)s قوة)', loss=loss_applied)
        else:
            msg = _('كارثة طبية! جسمك صار أضعف... (-%(loss)s دفاع)', loss=loss_applied)
        flash(msg, 'danger')

    # Atomic Update via ResourceService
    success = ResourceService.modify_resources(
        user_id=user.id,
        changes=changes,
        reason='hospital_experimental_surgery',
        auto_commit=False,
        expected_version=user.version
    )
    
    if not success:
         flash(_('حدث خطأ أثناء العملية، يرجى المحاولة مرة أخرى.'), 'danger')
         return redirect(url_for('hospital.index'))

    if hospital_duration:
        user.hospital_until = (datetime.now(timezone.utc) + hospital_duration).replace(tzinfo=None)
        
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_('حدث خطأ أثناء حفظ البيانات، يرجى المحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('hospital.index'))

    return redirect(url_for('hospital.index'))
