from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models import User, SystemConfig
from models.log import UserLog
from models.hostess import Hostess
from services.resource_service import ResourceService
from datetime import datetime, timezone, timedelta
from .utils import update_daily_task_progress
import json
import math
import random

bp = Blueprint('hospital', __name__, url_prefix='/hospital')


def _aware_utc(dt):
    if not dt:
        return None
    if getattr(dt, 'tzinfo', None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _hospital_cost_per_hp(user, now):
    cost_per_hp = 10
    if user.active_hostess_id and user.casino_luck_until:
        luck_until = _aware_utc(user.casino_luck_until)
        if luck_until and luck_until > now:
            hostess = db.session.get(Hostess, user.active_hostess_id)
            if hostess and hostess.buff_type == 'hospital_recovery':
                discount = hostess.buff_value if hostess.buff_value else 0.2
                cost_per_hp = max(1, int(cost_per_hp * (1 - discount)))
    return cost_per_hp


def _hospital_discount_multiplier(user, now):
    mult = 1.0
    if user.active_hostess_id and user.casino_luck_until:
        luck_until = _aware_utc(user.casino_luck_until)
        if luck_until and luck_until > now:
            hostess = db.session.get(Hostess, user.active_hostess_id)
            if hostess and hostess.buff_type == 'hospital_recovery':
                discount = hostess.buff_value if hostess.buff_value else 0.2
                mult = max(0.4, 1 - float(discount))
    return float(mult)


def _is_hospitalized(user, now):
    until = _aware_utc(user.hospital_until)
    return bool(until and until > now)


def _hospital_remaining_seconds(user, now):
    until = _aware_utc(user.hospital_until)
    if not until:
        return 0
    return max(0, int((until - now).total_seconds()))


def _hospital_activity_cooldown_seconds():
    try:
        return max(
            10, int(
                SystemConfig.get_value(
                    'hospital_activity_cooldown_seconds', '120')))
    except Exception:
        return 120


def _recent_activity_seconds_left(user_id, now):
    cd = _hospital_activity_cooldown_seconds()
    last = (
        UserLog.query.filter_by(user_id=user_id, action='HOSPITAL_ACTIVITY')
        .order_by(UserLog.timestamp.desc())
        .first()
    )
    if not last:
        return 0
    last_ts = _aware_utc(last.timestamp)
    if not last_ts:
        return 0
    diff = (now - last_ts).total_seconds()
    return max(0, int(cd - diff))


@bp.route('/')
@login_required
def index():
    now = datetime.now(timezone.utc)
    cost_per_hp = _hospital_cost_per_hp(current_user, now)
    hospitalized = _is_hospitalized(current_user, now)
    remaining_seconds = _hospital_remaining_seconds(current_user, now)
    until_ts = None
    until = _aware_utc(current_user.hospital_until)
    if until:
        until_ts = int(until.timestamp())

    discount_mult = _hospital_discount_multiplier(current_user, now)

    remaining_minutes = int(
        math.ceil(
            remaining_seconds /
            60.0)) if remaining_seconds else 0
    discharge_base = int(
        SystemConfig.get_value(
            'hospital_fast_discharge_base',
            '5000') or 5000)
    discharge_per_min = int(
        SystemConfig.get_value(
            'hospital_fast_discharge_per_min',
            '150') or 150)
    discharge_level = int(
        SystemConfig.get_value(
            'hospital_fast_discharge_level_factor',
            '200') or 200)
    discharge_cost = 0
    if hospitalized:
        discharge_cost = int(max(0, (discharge_base +
                                     (remaining_minutes *
                                      discharge_per_min) +
                                     ((current_user.level or 1) *
                                      discharge_level)) *
                                 discount_mult))

    speedup_per_min = int(
        SystemConfig.get_value(
            'hospital_speedup_per_min',
            '120') or 120)
    speedup_options = [
        {'minutes': 15, 'cost': int(max(0, (15 * speedup_per_min) * discount_mult))},
        {'minutes': 60, 'cost': int(max(0, (60 * speedup_per_min) * discount_mult))},
    ]

    activity_wait = _recent_activity_seconds_left(
        current_user.id, now) if hospitalized else 0

    return render_template(
        'hospital.html',
        user=current_user,
        now=now,
        cost_per_hp=cost_per_hp,
        hospitalized=hospitalized,
        hospital_until_ts=until_ts,
        hospital_remaining_seconds=remaining_seconds,
        discharge_cost=discharge_cost,
        speedup_options=speedup_options,
        activity_wait_seconds=activity_wait,
    )


@bp.route('/heal', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def heal():
    # Lock user row
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

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
            expected_version=None
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
            flash(
                _('حدث خطأ أثناء حفظ البيانات، يرجى المحاولة مرة أخرى.'),
                'danger')
            return redirect(url_for('hospital.index'))

    return redirect(url_for('hospital.index'))


@bp.route('/buy_energy', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
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

    # Lock user to calculate actual energy gain respecting max_energy
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    if user.money < cost:
        flash(_('طفرنا! بدك 500$ حق مشروب الطاقة.'), 'danger')
        return redirect(url_for('hospital.index'))

    # Random Bonus (Red Bull Effect)
    import random
    if random.random() < (0.1 + bonus_double_chance):
        energy_gain *= 2
        flash(_('🚀 المشروب كان أصلي! دبل طاقة! (+%(energy)s طاقة)',
              energy=energy_gain), 'success')
    else:
        flash(_('شربت مشروب طاقة ورجعتلك الحيوية! (+%(energy)s طاقة)',
              energy=energy_gain), 'success')

    actual_gain = min(energy_gain, user.max_energy - user.energy)

    # Atomic Update via ResourceService
    success = ResourceService.modify_resources(
        user_id=user.id,
        changes={'money': -cost, 'energy': actual_gain},
        reason='hospital_buy_energy',
        auto_commit=False,
        expected_version=None
    )

    if not success:
        db.session.rollback()
        flash(_('حدث خطأ أثناء الشراء، يرجى المحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('hospital.index'))

    update_daily_task_progress(current_user, 'buy')
    db.session.commit()
    return redirect(url_for('hospital.index'))


@bp.route('/discharge', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def discharge():
    now = datetime.now(timezone.utc)
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    until = _aware_utc(user.hospital_until)
    if not until or until <= now:
        user.hospital_until = None
        db.session.commit()
        flash(_('تم خروجك من المستشفى.'), 'success')
        return redirect(url_for('hospital.index'))
    flash(_('لسه وقتك ما خلص. استخدم تسريع/تخريج فوري.'), 'warning')
    return redirect(url_for('hospital.index'))


@bp.route('/fast_discharge', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def fast_discharge():
    now = datetime.now(timezone.utc)
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

    until = _aware_utc(user.hospital_until)
    if not until or until <= now:
        user.hospital_until = None
        db.session.commit()
        flash(_('أنت جاهز للخروج.'), 'success')
        return redirect(url_for('hospital.index'))

    remaining_seconds = max(0, int((until - now).total_seconds()))
    remaining_minutes = int(
        math.ceil(
            remaining_seconds /
            60.0)) if remaining_seconds else 0

    discount_mult = _hospital_discount_multiplier(user, now)
    discharge_base = int(
        SystemConfig.get_value(
            'hospital_fast_discharge_base',
            '5000') or 5000)
    discharge_per_min = int(
        SystemConfig.get_value(
            'hospital_fast_discharge_per_min',
            '150') or 150)
    discharge_level = int(
        SystemConfig.get_value(
            'hospital_fast_discharge_level_factor',
            '200') or 200)
    cost = int(max(0, (discharge_base +
                       (remaining_minutes *
                        discharge_per_min) +
                       ((user.level or 1) *
                        discharge_level)) *
                   discount_mult))

    if user.money < cost:
        flash(_('بدك %(cost)s$ للتخريج الفوري.', cost=cost), 'danger')
        return redirect(url_for('hospital.index'))

    if not ResourceService.modify_resources(
        user_id=user.id,
        changes={'money': -cost},
        reason='hospital_fast_discharge',
        auto_commit=False,
        expected_version=None,
        set_fields={'hospital_until': None},
    ):
        db.session.rollback()
        flash(_('حدث خطأ أثناء التخريج. حاول مرة ثانية.'), 'danger')
        return redirect(url_for('hospital.index'))

    db.session.commit()
    flash(_('تم التخريج الفوري. يلا عالشارع!'), 'success')
    return redirect(url_for('hospital.index'))


@bp.route('/speed_up', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def speed_up():
    now = datetime.now(timezone.utc)
    minutes = int(request.form.get('minutes', 0) or 0)
    if minutes <= 0:
        return redirect(url_for('hospital.index'))

    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    until = _aware_utc(user.hospital_until)
    if not until or until <= now:
        flash(_('أنت مش بالمستشفى.'), 'info')
        user.hospital_until = None
        db.session.commit()
        return redirect(url_for('hospital.index'))

    speedup_per_min = int(
        SystemConfig.get_value(
            'hospital_speedup_per_min',
            '120') or 120)
    discount_mult = _hospital_discount_multiplier(user, now)
    cost = int(max(0, (minutes * speedup_per_min) * discount_mult))

    if user.money < cost:
        flash(_('بدك %(cost)s$ للتسريع.', cost=cost), 'danger')
        return redirect(url_for('hospital.index'))

    new_until = until - timedelta(minutes=minutes)
    set_fields = {'hospital_until': None}
    if new_until > now:
        set_fields['hospital_until'] = new_until.replace(tzinfo=None)

    if not ResourceService.modify_resources(
        user_id=user.id,
        changes={'money': -cost},
        reason='hospital_speed_up',
        auto_commit=False,
        expected_version=None,
        set_fields=set_fields,
    ):
        db.session.rollback()
        flash(_('حدث خطأ أثناء التسريع. حاول مرة ثانية.'), 'danger')
        return redirect(url_for('hospital.index'))

    db.session.commit()
    flash(_('تم تسريع العلاج %(m)s دقيقة.', m=minutes), 'success')
    return redirect(url_for('hospital.index'))


@bp.route('/activity', methods=['POST'])
@login_required
@limiter.limit("15 per minute")
def activity():
    now = datetime.now(timezone.utc)
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    until = _aware_utc(user.hospital_until)
    if not until or until <= now:
        user.hospital_until = None
        db.session.commit()
        flash(_('أنت مش بالمستشفى.'), 'info')
        return redirect(url_for('hospital.index'))

    wait = _recent_activity_seconds_left(user.id, now)
    if wait > 0:
        flash(_('استنى شوي… %(s)s ثانية حتى تقدر تعمل نشاط جديد.', s=wait), 'warning')
        return redirect(url_for('hospital.index'))

    key = (request.form.get('key') or '').strip().lower()
    if key not in ['tv', 'physio', 'coffee']:
        flash(_('النشاط غير معروف.'), 'warning')
        return redirect(url_for('hospital.index'))

    changes = {}
    set_fields = {}

    if key == 'tv':
        xp = random.randint(10, 25)
        changes['exp'] = xp
        msg = _(
            'تابعت مسلسل بالمستشفى… راحت عليك نص ساعة بالضحك. (+%(xp)s خبرة)',
            xp=xp)
        flash(msg, 'success')
    elif key == 'coffee':
        cost = 250
        if user.money < cost:
            flash(_('بدك %(cost)s$ للقهوة.', cost=cost), 'danger')
            return redirect(url_for('hospital.index'))
        gain = random.randint(8, 20)
        actual_gain = min(gain, (user.max_energy or 0) - (user.energy or 0))
        changes['money'] = -cost
        if actual_gain > 0:
            changes['energy'] = actual_gain
        flash(_('قهوة المستشفى… مرّة بس بتصحصح. (+%(e)s طاقة)',
              e=actual_gain), 'success')
    else:
        xp = random.randint(5, 15)
        changes['exp'] = xp
        reduction = 0
        if random.random() < 0.35:
            reduction = random.randint(5, 15)
            new_until = until - timedelta(minutes=reduction)
            if new_until <= now:
                set_fields['hospital_until'] = None
            else:
                set_fields['hospital_until'] = new_until.replace(tzinfo=None)
        if reduction:
            flash(_('جلسة علاج طبيعي! خفّضت الوقت %(m)s دقيقة (+%(xp)s خبرة)',
                  m=reduction, xp=xp), 'success')
        else:
            flash(_('جلسة علاج طبيعي خفيفة… المهم تتحرك. (+%(xp)s خبرة)', xp=xp), 'info')

    if not changes:
        return redirect(url_for('hospital.index'))

    log_details = json.dumps({'key': key}, ensure_ascii=False)
    db.session.add(
        UserLog(
            user_id=user.id,
            action='HOSPITAL_ACTIVITY',
            details=log_details,
            result='ok'))

    if not ResourceService.modify_resources(
        user_id=user.id,
        changes=changes,
        reason=f'hospital_activity_{key}',
        auto_commit=False,
        expected_version=None,
        set_fields=set_fields if set_fields else None,
    ):
        db.session.rollback()
        flash(_('حدث خطأ أثناء النشاط. حاول مرة ثانية.'), 'danger')
        return redirect(url_for('hospital.index'))

    db.session.commit()
    return redirect(url_for('hospital.index'))


@bp.route('/experimental_surgery', methods=['POST'])
@login_required
def experimental_surgery():
    # Lock user row
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

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
        flash(
            _('فشلت العملية! الطبيب كان سكران... خسرت فلوسك وصحتك تدهورت.'),
            'danger')

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
            msg = _(
                'كارثة طبية! العضلات ضمرت... (-%(loss)s قوة)',
                loss=loss_applied)
        else:
            msg = _(
                'كارثة طبية! جسمك صار أضعف... (-%(loss)s دفاع)',
                loss=loss_applied)
        flash(msg, 'danger')

    # Atomic Update via ResourceService
    success = ResourceService.modify_resources(
        user_id=user.id,
        changes=changes,
        reason='hospital_experimental_surgery',
        auto_commit=False,
        expected_version=None
    )

    if not success:
        flash(_('حدث خطأ أثناء العملية، يرجى المحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('hospital.index'))

    if hospital_duration:
        user.hospital_until = (
            datetime.now(
                timezone.utc) +
            hospital_duration).replace(
            tzinfo=None)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_('حدث خطأ أثناء حفظ البيانات، يرجى المحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('hospital.index'))

    return redirect(url_for('hospital.index'))
