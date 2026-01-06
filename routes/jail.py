from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
import random
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
    
    # Calculate Bribe Cost (Dynamic: Level & Time)
    # Base formula: (Level * 100) + (Minutes Left * 50)
    # Minimum: 500
    
    remaining_minutes = 0
    jail_until = current_user.jail_until
    if jail_until and jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)

    if jail_until and jail_until > now:
        remaining_minutes = int((jail_until - now).total_seconds() / 60)
    
    raw_bribe_cost = (current_user.level * 100) + (remaining_minutes * 50)
    raw_bribe_cost = max(500, raw_bribe_cost)

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
    
    bribe_cost = max(1, int(raw_bribe_cost * (1 - bribe_discount_percent / 100)))

    # Calculate Bail Cost (Diamonds) with Discounts
    base_bail_cost = int(SystemConfig.get_value('jail_bail_cost_diamonds', '5'))
    # Re-use same discount logic for bail? Code uses same logic in routes.
    bail_cost_diamonds = max(1, int(base_bail_cost * (1 - bribe_discount_percent / 100)))

    # Ensure timezone awareness for template comparison
    if current_user.jail_until and current_user.jail_until.tzinfo is None:
        current_user.jail_until = current_user.jail_until.replace(tzinfo=timezone.utc)
        
    if prisoners and current_user in prisoners:
        flash(_('أنت الآن في سجن "عوفر" العسكري. الصبر مفتاح الفرج يا بطل.'), 'info')

    # --- Administrative Detention Renewal (Tajdeed Idari) ---
    # 2% chance every time you check your status if you are in jail
    if current_user.jail_until and current_user.jail_until > now:
        if random.random() < 0.02:
            # Extend by 10-30 minutes
            extension = random.randint(10, 30)
            current_user.jail_until += timedelta(minutes=extension)
            db.session.commit()
            flash(_('⚖️ تم تجديد الاعتقال الإداري لمدة %(min)s دقيقة إضافية. "ملف سري"!', min=extension), 'danger')

    return render_template('jail.html', title=_('السجن'), jailed_users=prisoners, now=now, user=current_user, 
                           enable_breakout=enable_breakout, enable_bribe=enable_bribe, bribe_cost=bribe_cost, bail_cost_diamonds=bail_cost_diamonds)

@bp.route('/riot', methods=['POST'])
@login_required
def riot():
    # Ensure user is actually in jail
    now = datetime.now(timezone.utc)
    if not current_user.jail_until:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))
    
    jail_until = current_user.jail_until
    if jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)
    
    if jail_until <= now:
        flash(_('لقد انتهت فترة عقوبتك!'), 'success')
        return redirect(url_for('jail.index'))

    # Cost and Risk
    energy_cost = 30
    success_chance = 0.15 # 15% chance to succeed
    
    # Pre-calculate outcome
    is_success = random.random() < success_chance
    
    changes = {'energy': -energy_cost}
    set_fields = {}
    
    if not is_success:
        # Fail: Increase time for LEADER only (Solitary)
        penalty_minutes = random.randint(10, 30)
        # Ensure jail_until is timezone aware
        current_jail_until = current_user.jail_until
        if current_jail_until.tzinfo is None:
            current_jail_until = current_jail_until.replace(tzinfo=timezone.utc)
            
        new_jail_until = current_jail_until + timedelta(minutes=penalty_minutes)
        set_fields['jail_until'] = new_jail_until

    if not ResourceService.modify_resources(current_user.id, changes, 'jail_riot_attempt', auto_commit=True, expected_version=current_user.version, set_fields=set_fields):
        flash(_('تحتاج إلى %(cost)s طاقة للتحريض على التمرد! أو حدث خطأ في التزامن.', cost=energy_cost), 'danger')
        return redirect(url_for('jail.index'))

    if is_success:
        # Success: Reduce time for EVERYONE
        # This part is tricky to do atomically for everyone via ResourceService one by one, 
        # but since it's a "reward" and not critical economy, direct DB update is acceptable for now.
        # Ideally, we should iterate and use optimistic locking, but that might be too slow.
        # We will do a bulk update which is atomic at DB level.
        
        reduction_minutes = random.randint(5, 15)
        
        # Bulk update
        stmt = User.__table__.update().where(
            User.jail_until > now
        ).values(
            jail_until = User.jail_until - timedelta(minutes=reduction_minutes)
        )
        db.session.execute(stmt)
        
        # Bonus for leader
        xp_reward = 500
        # Re-fetch user to get latest version if needed, but we can just force update since we are the actor
        ResourceService.modify_resources(current_user.id, {'exp': xp_reward}, 'jail_riot_success_leader', auto_commit=False)
        
        # Count prisoners for message (approximate)
        count = User.query.filter(User.jail_until > now).count()
        
        flash(_('نجح التمرد! عمت الفوضى وتم تخفيض عقوبة الجميع بمقدار %(min)s دقيقة! وحصلت على %(xp)s خبرة.', min=reduction_minutes, xp=xp_reward), 'success')
        
        # Log
        log = GameLog(admin_id=current_user.id, action='JAIL_RIOT_SUCCESS', details=f'Riot reduced time by {reduction_minutes}m')
        db.session.add(log)
        db.session.commit()
        
    else:
        flash(_('فشل التمرد! تم كشف خطتك ووضعك في الانفرادي. زادت عقوبتك %(min)s دقيقة.', min=penalty_minutes), 'danger')
        
        # Log
        log = GameLog(admin_id=current_user.id, action='JAIL_RIOT_FAIL', details=f'Riot failed, penalty {penalty_minutes}m')
        db.session.add(log)
        db.session.commit()

    return redirect(url_for('jail.index'))

@bp.route('/hunger_strike', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def hunger_strike():
    # Ensure user is actually in jail
    now = datetime.now(timezone.utc)
    if not current_user.jail_until:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))
    
    jail_until = current_user.jail_until
    if jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)
    
    if jail_until <= now:
        flash(_('لقد انتهت فترة عقوبتك!'), 'success')
        return redirect(url_for('jail.index'))

    # Health Check & Cost
    health_cost = int(current_user.max_health * 0.20)
    min_health_required = int(current_user.max_health * 0.30)

    if current_user.health < min_health_required:
        flash(_('صحتك متدهورة جداً! لا يمكنك بدء إضراب الكرامة وأنت في هذه الحالة.'), 'danger')
        return redirect(url_for('jail.index'))

    # Deduct Health
    health_cost = int(current_user.max_health * 0.20)
    
    import random
    chance = random.random()

    changes = {'health': -health_cost}
    set_fields = {}
    
    outcome_type = 'fail' # success, fail, punish
    
    if chance < 0.40:
        # Success: Administration yields
        outcome_type = 'success'
        reduction_minutes = random.randint(15, 45)
        # Ensure jail_until is timezone aware
        current_jail_until = current_user.jail_until
        if current_jail_until.tzinfo is None:
            current_jail_until = current_jail_until.replace(tzinfo=timezone.utc)
            
        new_jail_until = current_jail_until - timedelta(minutes=reduction_minutes)
        set_fields['jail_until'] = new_jail_until

    elif chance < 0.70:
        # Fail: Force feeding / No result
        outcome_type = 'fail'
        # Just health loss (already in changes)

    else:
        # Punishment: Administrative Detention Renewal
        outcome_type = 'punish'
        extension_minutes = random.randint(10, 20)
        
        current_jail_until = current_user.jail_until
        if current_jail_until.tzinfo is None:
            current_jail_until = current_jail_until.replace(tzinfo=timezone.utc)
            
        new_jail_until = current_jail_until + timedelta(minutes=extension_minutes)
        set_fields['jail_until'] = new_jail_until

    if not ResourceService.modify_resources(current_user.id, changes, 'jail_hunger_strike', auto_commit=True, expected_version=current_user.version, set_fields=set_fields):
         flash(_('حدث خطأ أثناء معالجة الإضراب. قد تكون حالتك تغيرت.'), 'danger')
         return redirect(url_for('jail.index'))

    if outcome_type == 'success':
        flash(_('✌️ انتصار الأمعاء الخاوية! رضخت إدارة السجون لمطالبك وتم تخفيض حكمك %(min)s دقيقة.', min=reduction_minutes), 'success')
        log = GameLog(admin_id=current_user.id, action='JAIL_HUNGER_STRIKE_SUCCESS', details=f'Hunger strike reduced time by {reduction_minutes}m')
        db.session.add(log)
        
    elif outcome_type == 'fail':
        flash(_('استمر الإضراب ولكن إدارة السجون ترفض التفاوض. فقدت صحتك بلا نتيجة.', ), 'warning')
        log = GameLog(admin_id=current_user.id, action='JAIL_HUNGER_STRIKE_FAIL', details='Hunger strike failed (neutral)')
        db.session.add(log)
        
    else: # punish
        flash(_('عاقبتك الإدارة بالعزل الانفرادي وتجديد الاعتقال الإداري لمدة %(min)s دقيقة إضافية.', min=extension_minutes), 'danger')
        log = GameLog(admin_id=current_user.id, action='JAIL_HUNGER_STRIKE_PUNISH', details=f'Hunger strike punished by {extension_minutes}m')
        db.session.add(log)

    db.session.commit()
    return redirect(url_for('jail.index'))

@bp.route('/lawyer_visit', methods=['POST'])
@login_required
def lawyer_visit():
    # Ensure user is actually in jail
    now = datetime.now(timezone.utc)
    if not current_user.jail_until:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))
    
    jail_until = current_user.jail_until
    if jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)
    
    if jail_until <= now:
        flash(_('لقد انتهت فترة عقوبتك!'), 'success')
        return redirect(url_for('jail.index'))

    # Cost Calculation
    cost = (current_user.level * 200) + 1000
    reduction_minutes = 20

    if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'jail_lawyer_visit', auto_commit=False, expected_version=current_user.version):
        flash(_('لا تملك تكاليف المحامي! تحتاج إلى %(cost)d$.', cost=cost), 'danger')
        return redirect(url_for('jail.index'))

    # Apply Reduction
    current_user.jail_until -= timedelta(minutes=reduction_minutes)
    
    db.session.commit()
    
    flash(_('قام المحامي بتقديم استئناف عاجل! تم تخفيض الحكم %(min)s دقيقة.', min=reduction_minutes), 'success')
    return redirect(url_for('jail.index'))

@bp.route('/hard_labor', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def hard_labor():
    # Ensure user is actually in jail
    now = datetime.now(timezone.utc)
    if not current_user.jail_until:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))
    
    jail_until = current_user.jail_until
    if jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)
    
    if jail_until <= now:
        flash(_('لقد انتهت فترة عقوبتك!'), 'success')
        return redirect(url_for('jail.index'))

    # Cost and Reward
    energy_cost = 10
    time_reduction_minutes = 2
    cash_reward_min = 10
    cash_reward_max = 50
    
    cash_reward = random.randint(cash_reward_min, cash_reward_max)
    
    # Calculate new jail time
    # Ensure jail_until is timezone aware
    current_jail_until = current_user.jail_until
    if current_jail_until.tzinfo is None:
        current_jail_until = current_jail_until.replace(tzinfo=timezone.utc)
        
    new_jail_until = current_jail_until - timedelta(minutes=time_reduction_minutes)
    
    changes = {'energy': -energy_cost, 'money': cash_reward}
    set_fields = {'jail_until': new_jail_until}

    if not ResourceService.modify_resources(current_user.id, changes, 'jail_hard_labor', auto_commit=True, expected_version=current_user.version, set_fields=set_fields):
        flash(_('تحتاج إلى %(cost)s طاقة للقيام بالأعمال الشاقة! أو حدث خطأ في التزامن.', cost=energy_cost), 'danger')
        return redirect(url_for('jail.index'))

    # Log handled by ResourceService
    
    flash(_('قمت بعمل شاق في المغسلة! تم تخفيض عقوبتك %(min)s دقيقة وحصلت على %(money)s$.', min=time_reduction_minutes, money=cash_reward), 'success')
    return redirect(url_for('jail.index'))

@bp.route('/bribe', methods=['POST'])
@login_required
def bribe():
    enable_bribe = SystemConfig.get_value('jail_enable_bribe', 'false') == 'true'
    if not enable_bribe:
        flash(_('نظام الرشوة غير مفعل حالياً!'), 'danger')
        return redirect(url_for('jail.index'))
        
    remaining_minutes = 0
    jail_until = current_user.jail_until
    if jail_until and jail_until.tzinfo is None:
        jail_until = jail_until.replace(tzinfo=timezone.utc)
        
    now = datetime.now(timezone.utc)
    if jail_until and jail_until > now:
        remaining_minutes = int((jail_until - now).total_seconds() / 60)
    
    # Dynamic Bribe Cost (Same as index)
    raw_bribe_cost = (current_user.level * 100) + (remaining_minutes * 50)
    raw_bribe_cost = max(500, raw_bribe_cost)
    base_bribe_cost = raw_bribe_cost
    
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
    
    if ResourceService.modify_resources(current_user.id, {'money': -bribe_cost}, 'jail_bribe', auto_commit=False, expected_version=current_user.version, set_fields={'jail_until': None}):
        
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

    # Deadlock Prevention: Lock both users in ID order
    users_to_lock = sorted([current_user.id, prisoner.id])
    db.session.query(User).filter(User.id.in_(users_to_lock)).with_for_update().all()

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
@limiter.limit("5 per minute")
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
    # Pre-calculate outcome
    import random
    success_chance = 0.3
    is_success = random.random() < success_chance
    
    changes = {'energy': -energy_cost}
    set_fields = {}
    
    if is_success:
        prisoner.jail_until = None
        # We can't update prisoner via ResourceService of current_user easily here without 2 calls.
        # But prisoner release is just setting jail_until=None.
        # We'll do it via direct assignment after cost deduction success.
        
        # Reward
        xp_reward = random.randint(100, 300)
        
        # Critical Success (20% chance): Gain Intelligence
        intelligence_gain = 0
        if random.random() < 0.2:
             intelligence_gain = 1
             flash(_('تطورت مهاراتك في التخطيط! (+1 ذكاء)'), 'info')

        changes['exp'] = xp_reward
        if intelligence_gain > 0:
            changes['intelligence'] = intelligence_gain
            
    else:
        # Fail - go to jail?
        fail_jail_minutes = 5
        set_fields['jail_until'] = datetime.now(timezone.utc) + timedelta(minutes=fail_jail_minutes)

    if not ResourceService.modify_resources(current_user.id, changes, 'jail_breakout', auto_commit=False, expected_version=current_user.version, set_fields=set_fields):
        flash(_('تحتاج إلى 50 طاقة لمحاولة التهريب! أو حدث خطأ في التزامن.'), 'danger')
        return redirect(url_for('jail.index'))
    
    if is_success:
        # Commit prisoner release
        prisoner.jail_until = None
        
        log = GameLog(admin_id=current_user.id, action='JAIL_BREAKOUT', details=f'Broke out {prisoner.username}')
        db.session.add(log)
        
        flash(_('نجحت العملية! تم تهريب %(name)s وحصلت على %(xp)s خبرة.', name=prisoner.username, xp=xp_reward), 'success')
    else:
        flash(_('فشلت العملية! تم القبض عليك وإيداعك السجن لمدة 5 دقائق.'), 'danger')

    db.session.commit()
    return redirect(url_for('jail.index'))
