from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models import User, SystemConfig, GameLog
from models.hostess import Hostess
from datetime import datetime, timezone, timedelta
from services.resource_service import ResourceService

bp = Blueprint('jail', __name__, url_prefix='/jail')

@bp.route('/')
@login_required
def index():
    now = datetime.now(timezone.utc)
    prisoners = User.query.filter(User.jail_until > now).all()
    
    # Settings
    enable_breakout = SystemConfig.get_value('jail_enable_breakout', 'false') == 'true'
    enable_bribe = SystemConfig.get_value('jail_enable_bribe', 'false') == 'true'
    
    # Calculate Bribe Cost with Discounts
    base_bribe_cost = int(SystemConfig.get_value('jail_bribe_cost', '1000'))
    bribe_discount_percent = 0
    if current_user.gang:
        bribe_discount_percent = min(50, current_user.gang.level * 2)

    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > now:
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'jail_bail_discount':
                hostess_discount = int((hostess.buff_value if hostess.buff_value else 0.1) * 100)
                bribe_discount_percent = min(70, bribe_discount_percent + hostess_discount)
    
    bribe_cost = max(1, int(base_bribe_cost * (1 - bribe_discount_percent / 100)))

    # Calculate Bail Cost (Diamonds) with Discounts
    base_bail_cost = int(SystemConfig.get_value('jail_bail_cost_diamonds', '5'))
    # Re-use same discount logic for bail? Code uses same logic in routes.
    bail_cost_diamonds = max(1, int(base_bail_cost * (1 - bribe_discount_percent / 100)))

    # Ensure timezone awareness for template comparison
    if current_user.jail_until and current_user.jail_until.tzinfo is None:
        current_user.jail_until = current_user.jail_until.replace(tzinfo=timezone.utc)
        
    return render_template('jail.html', title=_('السجن'), jailed_users=prisoners, now=now, user=current_user, 
                           enable_breakout=enable_breakout, enable_bribe=enable_bribe, bribe_cost=bribe_cost, bail_cost_diamonds=bail_cost_diamonds)

@bp.route('/bribe', methods=['POST'])
@login_required
def bribe():
    enable_bribe = SystemConfig.get_value('jail_enable_bribe', 'false') == 'true'
    if not enable_bribe:
        flash(_('نظام الرشوة غير مفعل حالياً!'), 'danger')
        return redirect(url_for('jail.index'))
        
    base_bribe_cost = int(SystemConfig.get_value('jail_bribe_cost', '1000'))
    
    discount_percent = 0
    discount_msg = ""
    if current_user.gang:
        discount_percent = min(50, current_user.gang.level * 2)
        if discount_percent > 0:
            discount_msg = _(' (خصم %(percent)s%% من العصابة)', percent=discount_percent)

    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > datetime.now(timezone.utc):
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'jail_bail_discount':
                hostess_discount = int((hostess.buff_value if hostess.buff_value else 0.1) * 100)
                discount_percent = min(70, discount_percent + hostess_discount)
                discount_msg = (discount_msg or "") + _(' (خصم %(percent)s%% من المضيفة)', percent=hostess_discount)

    bribe_cost = max(1, int(base_bribe_cost * (1 - discount_percent / 100)))
    
    if ResourceService.modify_resources(current_user.id, {'money': -bribe_cost}, 'jail_bribe', auto_commit=False, expected_version=current_user.version):
        current_user.jail_until = None
        
        # Log
        log = GameLog(admin_id=current_user.id, action='JAIL_BRIBE', details=f'Paid {bribe_cost} to get out of jail')
        db.session.add(log)
        db.session.commit()
        
        flash(_('تم دفع الرشوة بنجاح! أنت حر الآن.%(msg)s', msg=discount_msg), 'success')
        return redirect(url_for('main.index'))
    else:
        flash(_('ليس لديك مال كافٍ لدفع الرشوة! تحتاج %(cost)s$.%(msg)s', cost=bribe_cost, msg=discount_msg), 'danger')
        return redirect(url_for('jail.index'))

@bp.route('/pay_bail/<int:prisoner_id>', methods=['POST'])
@login_required
def pay_bail(prisoner_id):
    # Enable/Disable setting
    enable_bribe = SystemConfig.get_value('jail_enable_bribe', 'false') == 'true'
    if not enable_bribe:
        flash(_('نظام الرشوة/الكفالة غير مفعل حالياً!'), 'danger')
        return redirect(url_for('jail.index'))

    prisoner = User.query.get_or_404(prisoner_id)
    
    # Ensure timezone awareness for comparison
    jail_until = prisoner.jail_until
    if jail_until and jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)

    if not jail_until or jail_until <= datetime.now(timezone.utc):
        flash(_('هذا اللاعب ليس في السجن!'), 'warning')
        return redirect(url_for('jail.index'))

    if current_user.id == prisoner.id:
        flash(_('لا يمكنك دفع كفالة لنفسك بالماس، استخدم خيار الرشوة بالمال!'), 'warning')
        return redirect(url_for('jail.index'))

    # Cost in Diamonds
    base_bail_cost = int(SystemConfig.get_value('jail_bail_cost_diamonds', '5'))
    
    discount_percent = 0
    discount_msg = ""
    if current_user.gang:
        discount_percent = min(50, current_user.gang.level * 2)
        if discount_percent > 0:
            discount_msg = _(' (خصم %(percent)s%% من العصابة)', percent=discount_percent)

    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > datetime.now(timezone.utc):
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'jail_bail_discount':
                hostess_discount = int((hostess.buff_value if hostess.buff_value else 0.1) * 100)
                discount_percent = min(70, discount_percent + hostess_discount)
                discount_msg = (discount_msg or "") + _(' (خصم %(percent)s%% من المضيفة)', percent=hostess_discount)

    bail_cost_diamonds = max(1, int(base_bail_cost * (1 - discount_percent / 100)))

    if ResourceService.modify_resources(current_user.id, {'diamonds': -bail_cost_diamonds}, 'jail_bail', auto_commit=False, expected_version=current_user.version):
        prisoner.jail_until = None
        
        # Log
        log = GameLog(admin_id=current_user.id, action='JAIL_BAIL', details=f'Paid {bail_cost_diamonds} diamonds to free {prisoner.username}')
        db.session.add(log)
        db.session.commit()
        
        flash(_('تم دفع الكفالة بنجاح! تم إخراج %(name)s من السجن.%(msg)s', name=prisoner.username, msg=discount_msg), 'success')
    else:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.%(msg)s', cost=bail_cost_diamonds, msg=discount_msg), 'danger')

    return redirect(url_for('jail.index'))

@bp.route('/breakout/<int:prisoner_id>', methods=['POST'])
@login_required
def breakout(prisoner_id):
    # Status Check (Actor)
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك تهريب الآخرين!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك تهريب الآخرين!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك تهريب الآخرين!'), 'danger')
            return redirect(url_for('gym.index'))

    enable_breakout = SystemConfig.get_value('jail_enable_breakout', 'false') == 'true'
    if not enable_breakout:
        flash(_('نظام الهروب غير مفعل حالياً!'), 'danger')
        return redirect(url_for('jail.index'))

    prisoner = User.query.get_or_404(prisoner_id)
    
    # Ensure timezone awareness for comparison
    jail_until = prisoner.jail_until
    if jail_until and jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)

    if not jail_until or jail_until <= datetime.now(timezone.utc):
        flash(_('هذا اللاعب ليس في السجن!'), 'warning')
        return redirect(url_for('jail.index'))

    if current_user.id == prisoner.id:
        flash(_('لا يمكنك تهريب نفسك بهذه الطريقة!'), 'warning')
        return redirect(url_for('jail.index'))

    # Cost / Risk logic
    energy_cost = 50
    
    # Atomic Energy Deduction
    if not ResourceService.modify_resources(current_user.id, {'energy': -energy_cost}, 'jail_breakout_attempt', auto_commit=False, expected_version=current_user.version):
        flash(_('تحتاج إلى 50 طاقة لمحاولة التهريب!'), 'danger')
        return redirect(url_for('jail.index'))
    
    # Success chance (e.g., 30% + level diff?)
    import random
    success_chance = 0.3
    
    if random.random() < success_chance:
        prisoner.jail_until = None
        
        # Reward
        xp_reward = random.randint(100, 300)
        
        # Critical Success (20% chance): Gain Intelligence
        intelligence_gain = 0
        if random.random() < 0.2:
             intelligence_gain = 1
             flash(_('تطورت مهاراتك في التخطيط! (+1 ذكاء)'), 'info')

        changes = {'exp': xp_reward}
        if intelligence_gain > 0:
            changes['intelligence'] = intelligence_gain
            
        # Don't use expected_version here because we just modified the user (energy deduction)
        # and the version in memory might be stale compared to DB if not refreshed.
        # Since we are in the same transaction and hold the lock, it is safe.
        ResourceService.modify_resources(current_user.id, changes, 'jail_breakout_success', auto_commit=False)
        
        log = GameLog(admin_id=current_user.id, action='JAIL_BREAKOUT', details=f'Broke out {prisoner.username}')
        db.session.add(log)
        
        flash(_('نجحت العملية! تم تهريب %(name)s وحصلت على %(xp)s خبرة.', name=prisoner.username, xp=xp_reward), 'success')
    else:
        # Fail - go to jail?
        fail_jail_minutes = 5
        current_user.jail_until = datetime.now(timezone.utc) + timedelta(minutes=fail_jail_minutes)
        
        flash(_('فشلت العملية! تم القبض عليك وإيداعك السجن لمدة 5 دقائق.'), 'danger')

    db.session.commit()
    return redirect(url_for('jail.index'))
