from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models import User, SystemConfig, MoneySinkLog
from models.hostess import Hostess
from services.resource_service import ResourceService
from .utils import update_daily_task_progress
from datetime import datetime, timezone, timedelta
import json
import random

bp = Blueprint('gym', __name__, url_prefix='/gym')


def _aware_utc(dt):
    if dt and getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _round_money(x, step=100):
    try:
        x = float(x)
    except Exception:
        x = 0.0
    step = max(1, int(step))
    return int(round(x / step) * step)


def _cfg_bool(key, default=False):
    v = SystemConfig.get_value(key, 'true' if default else 'false')
    return str(v).strip().lower() in ('1', 'true', 'yes', 'on')


def _cfg_int(key, default):
    try:
        return int(SystemConfig.get_value(key, str(int(default))))
    except Exception:
        return int(default)


def _cfg_float(key, default):
    try:
        return float(SystemConfig.get_value(key, str(float(default))))
    except Exception:
        return float(default)


def _cooldown_seconds_left(last_at, cooldown_seconds, now):
    if not last_at:
        return 0
    a = _aware_utc(last_at)
    if not a:
        return 0
    until = a + timedelta(seconds=int(max(0, cooldown_seconds)))
    return max(0, int((until - now).total_seconds()))


def _get_training_defs():
    return [
        {
            "key": "basic",
            "label": _("تدريب عادي"),
            "gain": max(1, _cfg_int("gym_gain_basic", 1)),
            "exp": max(0, _cfg_int("gym_exp_basic", 2)),
            "duration": max(60, _cfg_int("gym_duration_basic_seconds", 1800)),
            "money_factor": max(0.1, _cfg_float("gym_money_factor_basic", 1.0)),
            "diamond_cost": max(0, _cfg_int("gym_diamonds_basic", 0)),
        },
        {
            "key": "advanced",
            "label": _("تدريب متقدم"),
            "gain": max(1, _cfg_int("gym_gain_advanced", 2)),
            "exp": max(0, _cfg_int("gym_exp_advanced", 6)),
            "duration": max(60, _cfg_int("gym_duration_advanced_seconds", 2700)),
            "money_factor": max(0.1, _cfg_float("gym_money_factor_advanced", 2.5)),
            "diamond_cost": max(0, _cfg_int("gym_diamonds_advanced", 0)),
        },
        {
            "key": "elite",
            "label": _("تدريب نخبة"),
            "gain": max(1, _cfg_int("gym_gain_elite", 3)),
            "exp": max(0, _cfg_int("gym_exp_elite", 14)),
            "duration": max(60, _cfg_int("gym_duration_elite_seconds", 3600)),
            "money_factor": max(0.1, _cfg_float("gym_money_factor_elite", 4.5)),
            "diamond_cost": max(0, _cfg_int("gym_diamonds_elite", 2)),
        },
    ]


def _stat_label(stat):
    return {
        "strength": _("القوة"),
        "defense": _("الدفاع"),
        "agility": _("الرشاقة"),
        "intelligence": _("الذكاء"),
    }.get(stat, stat)


def _stat_icon(stat):
    return {
        "strength": "fas fa-fist-raised",
        "defense": "fas fa-shield-alt",
        "agility": "fas fa-running",
        "intelligence": "fas fa-brain",
    }.get(stat, "fas fa-dumbbell")


def _stat_energy_cost(stat):
    if stat == "intelligence":
        return max(0, _cfg_int("gym_energy_cost_intelligence", 10))
    return max(0, _cfg_int("gym_energy_cost_default", 5))


def _money_base_cost(user, stat):
    base = max(0, _cfg_int("gym_money_base_cost", 100))
    per_level = max(0, _cfg_int("gym_money_per_level", 10))
    per_stat = max(0, _cfg_int("gym_money_per_stat", 2))
    step = max(1, _cfg_int("gym_money_round_step", 50))
    stat_val = int(getattr(user, stat) or 0)
    lvl = int(getattr(user, "level", 1) or 1)
    raw = base + (lvl * per_level) + (stat_val * per_stat)
    return max(0, _round_money(raw, step=step))


def _build_training_options(user):
    defs = _get_training_defs()
    out = {}
    for stat in ("strength", "defense", "agility", "intelligence"):
        base_money = _money_base_cost(user, stat)
        energy_cost = _stat_energy_cost(stat)
        options = []
        for d in defs:
            gain = int(d["gain"])
            money = _round_money(
                base_money *
                float(
                    d["money_factor"]),
                step=_cfg_int(
                    "gym_money_round_step",
                    50))
            diamonds = int(d.get("diamond_cost") or 0)
            options.append(
                {
                    "key": d["key"],
                    "label": d["label"],
                    "gain": gain,
                    "exp": int(d["exp"]),
                    "duration": int(d["duration"]),
                    "energy_cost": energy_cost,
                    "money_cost": int(money),
                    "diamond_cost": diamonds,
                }
            )
        out[stat] = options
    return out


def _claim_rewards(user):
    # Ensure we have the latest user state and lock the row to prevent race conditions
    # We use the ID to query, ensuring we get the session object attached to
    # this transaction
    user = db.session.query(User).filter_by(
        id=user.id).with_for_update().first()

    if not user.gym_activity:
        user.gym_until = None
        db.session.commit()
        return False

    try:
        data = json.loads(user.gym_activity)
        stat = data.get('stat')
        exp_gain = int(data.get('exp_gain', 0) or 0)
        stat_gain = int(data.get('stat_gain', 0) or 0)
        plan_key = str(data.get('plan') or '')
        money_cost = int(data.get('money_cost', 0) or 0)
        diamond_cost = int(data.get('diamond_cost', 0) or 0)

        changes = {'exp': exp_gain}
        if stat in ('strength', 'defense', 'agility', 'intelligence'):
            changes[stat] = stat_gain

        ok = ResourceService.modify_resources(
            user.id,
            changes,
            f'gym_reward_{stat}',
            auto_commit=False,
            expected_version=user.version,
            set_fields={
                'gym_activity': None,
                'gym_until': None},
            log_extra={
                'plan': plan_key,
                'money_cost': money_cost,
                'diamond_cost': diamond_cost},
        )
        if not ok:
            db.session.rollback()
            flash(_('حدث خطأ أثناء استلام المكافأة.'), 'danger')
            return False

        user.add_rank_points(1)
        leveled_up = user.check_level_up()
        if leveled_up:
            ref_url = url_for(
                'main.register',
                ref=user.referral_code,
                _external=True)
            share_text = _(
                "أصبحت زعيم مستوى %(level)s في عصابات فلسطين! هل تجرؤ على تحديي؟ %(url)s",
                level=user.level,
                url=ref_url)
            wa_link = f"https://wa.me/?text={share_text}"

            flash(
                _(
                    'مبروك! وصلت للمستوى %(level)s! '
                    '<a href="%(url)s" target="_blank" class="btn btn-sm btn-success ml-2">'
                    '<i class="fab fa-whatsapp"></i> شارك</a>',
                    level=user.level,
                    url=wa_link),
                'success')

        update_daily_task_progress(user, 'gym')

        msg = _(
            'انتهى التمرين! حصلت على %(exp)s خبرة و %(stat)s %(stat_name)s',
            exp=exp_gain,
            stat=stat_gain,
            stat_name=_stat_label(stat))
        flash(msg, 'success')

    except Exception:
        flash(_('حدث خطأ أثناء استلام المكافأة.'), 'danger')
        try:
            user.gym_activity = None
            user.gym_until = None
            db.session.commit()
        except Exception:
            db.session.rollback()
        return False

    db.session.commit()
    return True


@bp.route('/')
@login_required
def index():
    now = datetime.now(timezone.utc)
    remaining_seconds = 0
    training_options = _build_training_options(current_user)
    active = False
    active_data = None

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)

        if now >= gym_until:
            _claim_rewards(current_user)
            return redirect(url_for('gym.index'))

        remaining_seconds = int((gym_until - now).total_seconds())
        active = remaining_seconds > 0
        if current_user.gym_activity:
            try:
                active_data = json.loads(current_user.gym_activity)
            except Exception:
                active_data = None

    speedup_enabled = _cfg_bool('gym_enable_speedup', True)
    speedup_per_min_money = max(0, _cfg_int('gym_speedup_per_min_money', 120))
    speedup_fast_finish_diamonds = max(
        0, _cfg_int('gym_speedup_finish_diamonds', 5))
    speedup_options_minutes_raw = (
        SystemConfig.get_value(
            'gym_speedup_options_minutes',
            '15,60') or '15,60')
    try:
        speedup_minutes = [int(x.strip()) for x in str(
            speedup_options_minutes_raw).split(',') if x.strip()]
    except Exception:
        speedup_minutes = [15, 60]
    speedup_minutes = [m for m in speedup_minutes if m > 0]
    speedup_options = []
    if active and speedup_enabled and speedup_per_min_money > 0:
        for m in speedup_minutes:
            cost = int(
                _round_money(
                    m * speedup_per_min_money,
                    step=_cfg_int(
                        'gym_money_round_step',
                        50)))
            speedup_options.append({'minutes': m, 'cost': cost})

    return render_template(
        'gym.html',
        user=current_user,
        now=now,
        remaining_seconds=remaining_seconds,
        active=active,
        active_data=active_data,
        training_options=training_options,
        speedup_enabled=speedup_enabled,
        speedup_options=speedup_options,
        speedup_finish_diamonds=speedup_fast_finish_diamonds,
    )


@bp.route('/cancel', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def cancel_training():
    # Lock user row to prevent double cancellation/rewards
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

    if not user.gym_activity:
        user.gym_until = None
        db.session.commit()
        flash(_('تم إلغاء فترة الراحة.'), 'info')
        return redirect(url_for('gym.index'))

    try:
        data = json.loads(user.gym_activity)
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
            # Use user.id which is locked
            ok = ResourceService.modify_resources(
                user.id,
                changes,
                f'gym_partial_{stat}',
                auto_commit=False,
                expected_version=user.version,
                set_fields={'gym_activity': None, 'gym_until': None},
                log_extra={'ratio': ratio},
            )
            if not ok:
                db.session.rollback()
                flash(_('حدث خطأ أثناء الإلغاء.'), 'danger')
                return redirect(url_for('gym.index'))
            flash(
                _(
                    'تم إنهاء التمرين مبكراً. حصلت على %(exp)s خبرة و %(stat)s %(stat_name)s '
                    'بناءً على المدة التي قضيتها.',
                    exp=partial_exp,
                    stat=earned_stat,
                    stat_name=_stat_label(stat)),
                'warning')
        else:
            ResourceService.modify_resources(
                user.id,
                {},
                'gym_cancel',
                auto_commit=False,
                expected_version=user.version,
                set_fields={
                    'gym_activity': None,
                    'gym_until': None})
            flash(
                _('تم إنهاء التمرين مبكراً جداً! لم تحصل على أي فائدة.'),
                'warning')

    except Exception:
        # flash(str(e), 'danger') # Debug
        flash(_('حدث خطأ أثناء الإلغاء.'), 'danger')

    db.session.commit()
    return redirect(url_for('gym.index'))


@bp.route('/speed_up', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def speed_up():
    if not _cfg_bool('gym_enable_speedup', True):
        flash(_('ميزة تسريع التدريب غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('gym.index'))

    minutes = request.form.get('minutes', type=int) or 0
    if minutes <= 0:
        flash(_('طلب غير صالح.'), 'danger')
        return redirect(url_for('gym.index'))

    now = datetime.now(timezone.utc)
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

    until = _aware_utc(user.gym_until)
    if not until or until <= now:
        flash(_('لا يوجد تدريب فعّال للتسريع.'), 'info')
        return redirect(url_for('gym.index'))

    today = now.date()
    speedup_limit = max(0, _cfg_int('gym_speedup_daily_limit', 50))
    used = int(user.gym_speedups_count or 0) if getattr(
        user, "gym_speedups_date", None) == today else 0
    if speedup_limit and used >= speedup_limit:
        flash(_('وصلت لحد التسريع اليومي.'), 'warning')
        return redirect(url_for('gym.index'))

    per_min = max(0, _cfg_int('gym_speedup_per_min_money', 120))
    step = max(1, _cfg_int('gym_money_round_step', 50))
    cost = int(_round_money(minutes * per_min, step=step))
    if user.money < cost:
        flash(_('لا تملك مال كافٍ للتسريع. تحتاج %(cost)s$.'), 'danger')
        return redirect(url_for('gym.index'))

    new_until = until - timedelta(minutes=minutes)
    set_fields = {
        'gym_until': new_until.replace(tzinfo=None),
        'gym_speedups_date': today,
        'gym_speedups_count': used + 1,
    }
    ok = ResourceService.modify_resources(
        user.id,
        {'money': -cost},
        'gym_speedup',
        auto_commit=False,
        expected_version=user.version,
        set_fields=set_fields,
        log_extra={'minutes': minutes},
    )
    if not ok:
        db.session.rollback()
        flash(_('فشل التسريع.'), 'danger')
        return redirect(url_for('gym.index'))

    db.session.add(
        MoneySinkLog(
            user_id=user.id,
            sink_type="gym_speedup",
            amount=cost,
            details=f"Speedup {minutes}m"))
    db.session.commit()
    flash(_('تم تسريع التدريب %(m)s دقيقة.'), 'success')
    return redirect(url_for('gym.index'))


@bp.route('/finish_now', methods=['POST'])
@login_required
@limiter.limit("6 per minute")
def finish_now():
    if not _cfg_bool('gym_enable_speedup', True):
        flash(_('ميزة التسريع غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('gym.index'))

    now = datetime.now(timezone.utc)
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    until = _aware_utc(user.gym_until)
    if not until or until <= now:
        flash(_('لا يوجد تدريب فعّال.'), 'info')
        return redirect(url_for('gym.index'))

    today = now.date()
    speedup_limit = max(0, _cfg_int('gym_speedup_daily_limit', 50))
    used = int(user.gym_speedups_count or 0) if getattr(
        user, "gym_speedups_date", None) == today else 0
    if speedup_limit and used >= speedup_limit:
        flash(_('وصلت لحد التسريع اليومي.'), 'warning')
        return redirect(url_for('gym.index'))

    cost = max(0, _cfg_int('gym_speedup_finish_diamonds', 5))
    if user.diamonds < cost:
        flash(_('لا تملك ألماس كافٍ. تحتاج %(cost)s ماسة.'), 'danger')
        return redirect(url_for('gym.index'))

    set_fields = {
        'gym_until': now.replace(
            tzinfo=None),
        'gym_speedups_date': today,
        'gym_speedups_count': used + 1}
    ok = ResourceService.modify_resources(
        user.id,
        {'diamonds': -cost},
        'gym_finish_now',
        auto_commit=False,
        expected_version=user.version,
        set_fields=set_fields,
        log_extra={'cost_diamonds': cost},
    )
    if not ok:
        db.session.rollback()
        flash(_('فشل إنهاء التدريب.'), 'danger')
        return redirect(url_for('gym.index'))

    db.session.commit()
    return redirect(url_for('gym.index'))


@bp.route('/train/<stat>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def train(stat):
    # Lock user row to prevent concurrent training
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

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
            flash(_('أنت تتمرن حالياً! انتظر %(min)s دقيقة و %(sec)s ثانية.',
                  min=minutes, sec=seconds), 'warning')
            return redirect(url_for('gym.index'))

    plan = (request.form.get('plan') or 'basic').strip()
    defs = {d['key']: d for d in _get_training_defs()}
    d = defs.get(plan)
    if stat not in ('strength', 'defense', 'agility', 'intelligence'):
        flash(_('تمرين غير معروف!'), 'danger')
        return redirect(url_for('gym.index'))
    if not d:
        flash(_('خطة تدريب غير صالحة.'), 'danger')
        return redirect(url_for('gym.index'))

    today = now.date()
    session_limit = max(0, _cfg_int('gym_daily_sessions_limit', 100))
    used_sessions = int(
        user.gym_sessions_count or 0) if getattr(
        user,
        "gym_sessions_date",
        None) == today else 0
    if session_limit and used_sessions >= session_limit:
        flash(_('وصلت لحد تمارين اليوم.'), 'warning')
        return redirect(url_for('gym.index'))

    cost_energy = _stat_energy_cost(stat)
    base_money = _money_base_cost(user, stat)
    cost_money = int(
        _round_money(
            base_money *
            float(
                d['money_factor']),
            step=_cfg_int(
                'gym_money_round_step',
                50)))
    cost_diamonds = int(d.get('diamond_cost') or 0)

    stat_gain = int(d['gain'])
    msg = _(
        '%(plan)s: بدأت تدريب %(stat)s',
        plan=d['label'],
        stat=_stat_label(stat))

    # Hostess Buff
    exp_gain = int(d['exp'])

    # Track extra stats for hostess buff
    extra_stat_gain = 0

    if current_user.active_hostess_id:
        hostess = db.session.get(Hostess, current_user.active_hostess_id)
        if hostess and hostess.buff_type == 'gym_boost':
            extra_exp = int(
                2 * (hostess.buff_value if hostess.buff_value else 0.5))
            exp_gain += extra_exp

            # Chance for double stat gain
            chance = hostess.buff_value if hostess.buff_value else 0.2
            if random.random() < chance:
                extra_stat_gain = 1
                msg += _(" (مكافأة المضيفة: تدريب مضاعف!)")

    # Gang Buff (Gym Rat)
    try:
        from services.gang_service import GangService
        gang_buff = GangService.get_gang_buff(current_user.gang_id, 'gym_rat')
        if gang_buff > 0:
            # Increase EXP
            exp_gain = int(exp_gain * (1 + gang_buff / 100))

            # Increase Stat Chance
            if random.random() < (gang_buff / 100):
                extra_stat_gain += 1
                if "مكافأة" not in msg:
                    msg += _(" (مكافأة العصابة!)")
    except Exception as e:
        current_app.logger.error(f"Error applying gang buff: {e}")

    duration = int(d['duration'])
    activity_data = {
        'stat': stat,
        'plan': d['key'],
        'exp_gain': exp_gain,
        'stat_gain': stat_gain + extra_stat_gain,
        'start_time': now.timestamp(),
        'duration': duration,
        'money_cost': cost_money,
        'energy_cost': cost_energy,
        'diamond_cost': cost_diamonds,
    }

    injury_chance_pct = max(0, _cfg_int('gym_injury_chance_percent', 2))
    injured = (
        not current_app.config.get(
            'TESTING', False)) and (
        random.randint(
            1, 100) <= injury_chance_pct)

    changes = {'money': -cost_money, 'energy': -cost_energy}
    if cost_diamonds > 0:
        changes['diamonds'] = -cost_diamonds

    set_fields = {
        'gym_sessions_date': today,
        'gym_sessions_count': used_sessions + 1,
        'last_gym_training': now.replace(tzinfo=None),
    }

    if injured:
        hospital_time = max(10, _cfg_int('gym_injury_hospital_seconds', 120))
        set_fields['hospital_until'] = (
            now +
            timedelta(
                seconds=hospital_time)).replace(
            tzinfo=None)
        set_fields['gym_activity'] = None
        set_fields['gym_until'] = None
    else:
        set_fields['gym_activity'] = json.dumps(activity_data)
        set_fields['gym_until'] = (
            now +
            timedelta(
                seconds=duration)).replace(
            tzinfo=None)

    success = ResourceService.modify_resources(
        user_id=user.id,
        changes=changes,
        reason=f'gym_train_{stat}',
        auto_commit=False,
        expected_version=user.version,
        set_fields=set_fields,
        log_extra={'plan': d['key'], 'injured': injured},
    )

    if not success:
        db.session.rollback()
        if current_user.money < cost_money:
            flash(_('طفرنا! بدك مصاري عشان تتمرن.'), 'danger')
        elif cost_diamonds > 0 and current_user.diamonds < cost_diamonds:
            flash(_('بدك ألماس عشان التدريب هذا.'), 'danger')
        elif current_user.energy < cost_energy:
            flash(_('طاقتك ما بتكفي للتمرين!'), 'danger')
        else:
            flash(_('حدث خطأ أثناء الخصم، حاول مرة أخرى.'), 'danger')
        return redirect(url_for('gym.index'))

    db.session.add(
        MoneySinkLog(
            user_id=user.id,
            sink_type="gym_train",
            amount=cost_money,
            details=f"{stat}:{
                d['key']}"))
    db.session.commit()

    if injured:
        flash(_('آخ! شديت على حالك زيادة ومزقت عضلة. ريح شوي بالمستشفى.'), 'danger')
        return redirect(url_for('hospital.index'))

    flash(msg + _(' (بدأ التدريب...)'), 'success')
    return redirect(url_for('gym.index'))
