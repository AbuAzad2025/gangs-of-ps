from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
import random
from models import User, SystemConfig, GameLog, UserLog, MoneySinkLog
from models.hostess import Hostess
from datetime import datetime, timezone, timedelta
from services.resource_service import ResourceService

bp = Blueprint('jail', __name__, url_prefix='/jail')


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


def _now_utc():
    return datetime.now(timezone.utc)


def _now_naive_utc():
    return _now_utc().replace(tzinfo=None)


def _today_utc_date(now):
    if getattr(now, "tzinfo", None) is None:
        return now.date()
    return now.astimezone(timezone.utc).date()


def _to_aware(dt):
    if dt and getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _safe_deduct(user, field, amount):
    try:
        cur = int(getattr(user, field) or 0)
    except Exception:
        cur = 0
    return -min(cur, int(abs(amount)))


def _cooldown_seconds_left(last_at, cooldown_seconds, now):
    if not last_at:
        return 0
    a = _to_aware(last_at)
    if not a:
        return 0
    until = a + timedelta(seconds=int(max(0, cooldown_seconds)))
    return max(0, int((until - now).total_seconds()))


def _build_daily_event(user, now):
    if not _cfg_bool('jail_enable_daily_event', True):
        return None

    jail_until = _to_aware(getattr(user, "jail_until", None))
    if not jail_until or jail_until <= now:
        return None

    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    already = (
        UserLog.query.filter(
            UserLog.user_id == user.id,
            UserLog.action == "JAIL_DAILY_EVENT",
            UserLog.timestamp >= day_start,
        )
        .order_by(UserLog.timestamp.desc())
        .first()
    )

    seed = f"{user.id}:{day_start.date().isoformat()}"
    rng = random.Random(seed)
    events = [{"key": "inspection",
               "severity": "warning",
               "title": _("تفتيش مفاجئ ومصادرة"),
               "description": _("تفتيش داخل الأقسام ومصادرة بعض الأغراض الشخصية، مع ضغط نفسي على الأسرى."),
               "delta_minutes": 0,
               "changes": {"energy": -5},
               },
              {"key": "solitary",
               "severity": "danger",
               "title": _("عزل انفرادي"),
               "description": _("نقلك إلى زنزانة انفرادية لفترة قصيرة بعد توتر داخل القسم."),
               "delta_minutes": 15,
               "changes": {"brave": -1},
               },
              {"key": "court_delay",
               "severity": "danger",
               "title": _("تأجيل محكمة عسكرية"),
               "description": _("تم تأجيل الجلسة دون توضيح، وتأخر النظر في ملفك."),
               "delta_minutes": 20,
               "changes": {},
               },
              {"key": "lawyer_volunteer",
               "severity": "success",
               "title": _("محامي متطوع"),
               "description": _("زيارة قانونية سريعة وتقديم طلب مراجعة عاجل."),
               "delta_minutes": -12,
               "changes": {"exp": 25},
               },
              {"key": "collective_support",
               "severity": "info",
               "title": _("تضامن جماعي داخل القسم"),
               "description": _("تنظيم داخل القسم ودعم نفسي متبادل، يساعد على الصمود."),
               "delta_minutes": -4,
               "changes": {"exp": 15},
               },
              {"key": "medical_negligence",
               "severity": "warning",
               "title": _("إهمال طبي وتأخير علاج"),
               "description": _("تأخر في تقديم العلاج داخل العيادة، وإجراءات بطيئة."),
               "delta_minutes": 0,
               "changes": {"health": -int(max(1,
                                              (user.max_health or 0) * 0.02))},
               },
              ]

    event = rng.choice(events)

    applied_effects = []
    delta_minutes = int(event.get("delta_minutes") or 0)
    if delta_minutes != 0:
        applied_effects.append(_("تغيير الحكم: %(sign)s%(min)s دقيقة", sign=(
            "+" if delta_minutes > 0 else ""), min=abs(delta_minutes)))
    for k, v in (event.get("changes") or {}).items():
        try:
            v = int(v)
        except Exception:
            continue
        if v == 0:
            continue
        label = {
            "energy": _("الطاقة"),
            "health": _("الصحة"),
            "brave": _("الشجاعة"),
            "exp": _("الخبرة"),
        }.get(k, k)
        applied_effects.append(f"{label}: {v:+d}")

    if not already:
        set_fields = {}
        if delta_minutes != 0:
            current_jail_until = _to_aware(getattr(user, "jail_until", None))
            if current_jail_until:
                new_jail_until = current_jail_until + \
                    timedelta(minutes=delta_minutes)
                set_fields["jail_until"] = new_jail_until

        changes = {}
        for k, v in (event.get("changes") or {}).items():
            try:
                v = int(v)
            except Exception:
                continue
            if v < 0:
                changes[k] = _safe_deduct(user, k, v)
            elif v > 0:
                changes[k] = v

        ResourceService.modify_resources(
            user.id,
            changes,
            "jail_daily_event",
            auto_commit=True,
            expected_version=user.version,
            set_fields=set_fields or None,
            log_extra={"event_key": event.get("key")},
        )

    return {
        "title": event.get("title"),
        "description": event.get("description"),
        "severity": event.get("severity", "info"),
        "effects": applied_effects,
        "applied": (already is None),
    }


@bp.route('/')
@login_required
def index():
    now = datetime.now(timezone.utc)
    prisoners = User.query.filter(User.jail_until > now).all()

    # Settings
    enable_breakout = SystemConfig.get_value(
        'jail_enable_breakout', 'false') == 'true'
    enable_bribe = SystemConfig.get_value(
        'jail_enable_bribe', 'false') == 'true'
    enable_document_report = _cfg_bool('jail_enable_document_report', True)
    enable_family_visit = _cfg_bool('jail_enable_family_visit', True)
    document_report_energy_cost = max(
        0, _cfg_int('jail_document_report_energy_cost', 5))
    document_report_cooldown_hours = max(
        1, _cfg_int('jail_document_report_cooldown_hours', 3))
    family_visit_cooldown_hours = max(
        1, _cfg_int('jail_family_visit_cooldown_hours', 12))
    enable_self_escape = _cfg_bool('jail_enable_self_escape', True)
    enable_gilboa_escape = _cfg_bool('jail_enable_gilboa_escape', True)
    enable_self_bail_diamonds = _cfg_bool(
        'jail_enable_self_bail_diamonds', True)

    # Calculate Bribe Cost (Dynamic: Level & Time)
    # Base formula: (Level * 100) + (Minutes Left * 50)
    # Minimum: 500

    daily_event = _build_daily_event(current_user, now)

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
                hostess_discount = int(
                    (hostess.buff_value if hostess.buff_value else 0.1) * 100)
                bribe_discount_percent = min(
                    70, bribe_discount_percent + hostess_discount)

    bribe_cost = max(
        1, int(raw_bribe_cost * (1 - bribe_discount_percent / 100)))

    # Calculate Bail Cost (Diamonds) with Discounts
    base_bail_cost = int(
        SystemConfig.get_value(
            'jail_bail_cost_diamonds', '5'))
    # Re-use same discount logic for bail? Code uses same logic in routes.
    bail_cost_diamonds = max(
        1, int(base_bail_cost * (1 - bribe_discount_percent / 100)))

    # Ensure timezone awareness for template comparison
    if current_user.jail_until and current_user.jail_until.tzinfo is None:
        current_user.jail_until = current_user.jail_until.replace(
            tzinfo=timezone.utc)

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
            flash(_('⚖️ تم تجديد الاعتقال الإداري لمدة %(min)s دقيقة إضافية. "ملف سري"!',
                  min=extension), 'danger')

    today = _today_utc_date(now)
    escape_limit = max(1, _cfg_int('jail_self_escape_daily_limit', 3))
    gilboa_limit = max(1, _cfg_int('jail_gilboa_daily_limit', 2))
    try:
        escape_used = int(
            current_user.jail_escape_attempts or 0) if current_user.jail_escape_attempts_date == today else 0
    except Exception:
        escape_used = 0
    try:
        gilboa_used = int(
            current_user.jail_gilboa_attempts or 0) if current_user.jail_gilboa_attempts_date == today else 0
    except Exception:
        gilboa_used = 0

    self_escape_energy_cost = max(
        0, _cfg_int('jail_self_escape_energy_cost', 30))
    self_escape_money_cost = max(0, _cfg_int(
        'jail_self_escape_money_cost', 5000))
    gilboa_energy_cost = max(0, _cfg_int('jail_gilboa_energy_cost', 45))
    gilboa_diamond_cost = max(0, _cfg_int('jail_gilboa_diamond_cost', 8))
    gilboa_cooldown_hours = max(0, _cfg_int('jail_gilboa_cooldown_hours', 6))
    self_bail_diamonds_cost = max(
        0, _cfg_int('jail_self_bail_cost_diamonds', 15))
    self_bail_cooldown_hours = max(
        0, _cfg_int('jail_self_bail_cooldown_hours', 12))

    gilboa_cd_left = _cooldown_seconds_left(
        getattr(
            current_user,
            'jail_gilboa_last_at',
            None),
        gilboa_cooldown_hours *
        3600,
        now)
    self_bail_cd_left = 0
    try:
        last_self_bail = (
            UserLog.query.filter(
                UserLog.user_id == current_user.id,
                UserLog.action == "JAIL_SELF_BAIL") .order_by(
                UserLog.timestamp.desc()) .first())
        if last_self_bail and last_self_bail.timestamp:
            self_bail_cd_left = _cooldown_seconds_left(
                last_self_bail.timestamp, self_bail_cooldown_hours * 3600, now)
    except Exception:
        self_bail_cd_left = 0

    return render_template(
        'jail.html',
        title=_('السجن'),
        jailed_users=prisoners,
        now=now,
        user=current_user,
        enable_breakout=enable_breakout,
        enable_bribe=enable_bribe,
        bribe_cost=bribe_cost,
        bail_cost_diamonds=bail_cost_diamonds,
        daily_event=daily_event,
        enable_document_report=enable_document_report,
        enable_family_visit=enable_family_visit,
        document_report_energy_cost=document_report_energy_cost,
        document_report_cooldown_hours=document_report_cooldown_hours,
        family_visit_cooldown_hours=family_visit_cooldown_hours,
        enable_self_escape=enable_self_escape,
        enable_gilboa_escape=enable_gilboa_escape,
        enable_self_bail_diamonds=enable_self_bail_diamonds,
        escape_limit=escape_limit,
        escape_used=escape_used,
        gilboa_limit=gilboa_limit,
        gilboa_used=gilboa_used,
        self_escape_energy_cost=self_escape_energy_cost,
        self_escape_money_cost=self_escape_money_cost,
        gilboa_energy_cost=gilboa_energy_cost,
        gilboa_diamond_cost=gilboa_diamond_cost,
        gilboa_cooldown_left_seconds=gilboa_cd_left,
        self_bail_diamonds_cost=self_bail_diamonds_cost,
        self_bail_cooldown_left_seconds=self_bail_cd_left)


@bp.route('/self_escape', methods=['POST'])
@login_required
@limiter.limit("6 per minute")
def self_escape():
    if not _cfg_bool('jail_enable_self_escape', True):
        flash(_('محاولة الهروب غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('jail.index'))

    now = _now_utc()
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    jail_until = _to_aware(getattr(user, "jail_until", None))
    if not jail_until or jail_until <= now:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))

    today = _today_utc_date(now)
    limit = max(1, _cfg_int('jail_self_escape_daily_limit', 3))
    used = int(
        user.jail_escape_attempts or 0) if user.jail_escape_attempts_date == today else 0
    if used >= limit:
        flash(_('لقد استنفدت محاولات الهروب لليوم.'), 'warning')
        return redirect(url_for('jail.index'))

    energy_cost = max(0, _cfg_int('jail_self_escape_energy_cost', 30))
    money_cost = max(0, _cfg_int('jail_self_escape_money_cost', 5000))
    if user.energy < energy_cost:
        flash(_('تحتاج إلى %(cost)s طاقة لمحاولة الهروب.', cost=energy_cost), 'danger')
        return redirect(url_for('jail.index'))
    if user.money < money_cost:
        flash(_('تحتاج إلى %(cost)s$ لتجهيز الأدوات.', cost=money_cost), 'danger')
        return redirect(url_for('jail.index'))

    success_chance = max(
        0.0, min(
            1.0, _cfg_float(
                'jail_self_escape_success_chance', 0.12)))
    exp_reward = max(0, _cfg_int('jail_self_escape_exp_reward', 60))
    penalty_min = max(0, _cfg_int('jail_self_escape_penalty_min', 15))
    penalty_max = max(penalty_min, _cfg_int(
        'jail_self_escape_penalty_max', 35))
    injury_pct = max(
        0.0, min(
            0.50, _cfg_float(
                'jail_self_escape_injury_pct', 0.05)))

    is_success = random.random() < success_chance
    now_naive = _now_naive_utc()

    set_fields = {
        "jail_escape_attempts_date": today,
        "jail_escape_attempts": used + 1,
        "jail_escape_last_at": now_naive,
    }
    changes = {"energy": -energy_cost, "money": -money_cost, "exp": exp_reward}

    if is_success:
        set_fields["jail_until"] = None
        ok = ResourceService.modify_resources(
            user.id,
            changes,
            "jail_self_escape",
            auto_commit=False,
            expected_version=user.version,
            set_fields=set_fields,
            log_extra={"success": True},
        )
        if not ok:
            db.session.rollback()
            flash(_('حدث خطأ أثناء محاولة الهروب.'), 'danger')
            return redirect(url_for('jail.index'))

        db.session.add(
            MoneySinkLog(
                user_id=user.id,
                sink_type="jail_escape_tools",
                amount=money_cost,
                details="Self escape tools"))
        db.session.add(
            GameLog(
                admin_id=user.id,
                action='JAIL_SELF_ESCAPE_SUCCESS',
                details=f'Energy {energy_cost}, Money {money_cost}'))
        db.session.commit()
        flash(_('نجحت بخطف لحظة فوضى والهروب من السجن!'), 'success')
        return redirect(url_for('main.index', fx='escape_success'))

    penalty_minutes = random.randint(
        penalty_min, penalty_max) if penalty_max > 0 else 0
    health_loss = int(max(0, (user.max_health or 0) * injury_pct))
    if health_loss > 0:
        changes["health"] = -health_loss
    set_fields["jail_until"] = (
        _to_aware(user.jail_until) or now) + timedelta(minutes=penalty_minutes)

    ok = ResourceService.modify_resources(
        user.id,
        changes,
        "jail_self_escape",
        auto_commit=False,
        expected_version=user.version,
        set_fields=set_fields,
        log_extra={"success": False, "penalty_minutes": penalty_minutes},
    )
    if not ok:
        db.session.rollback()
        flash(_('حدث خطأ أثناء محاولة الهروب.'), 'danger')
        return redirect(url_for('jail.index'))

    db.session.add(
        MoneySinkLog(
            user_id=user.id,
            sink_type="jail_escape_tools",
            amount=money_cost,
            details="Self escape tools"))
    db.session.add(
        GameLog(
            admin_id=user.id,
            action='JAIL_SELF_ESCAPE_FAIL',
            details=f'Penalty {penalty_minutes}m'))
    db.session.commit()
    flash(
        random.choice([
            _('فشلت المحاولة وتم كشفك. زادت عقوبتك %(min)s دقيقة.', min=penalty_minutes),
            _('انكشف أمرك… فشل الهروب وزادت العقوبة %(min)s دقيقة.', min=penalty_minutes),
            _('ما زبطت! كشفوك وزادوا عليك %(min)s دقيقة.', min=penalty_minutes),
        ]),
        'danger',
    )
    return redirect(url_for('jail.index', fx='escape_fail'))


@bp.route('/gilboa_escape', methods=['POST'])
@login_required
@limiter.limit("4 per minute")
def gilboa_escape():
    if not _cfg_bool('jail_enable_gilboa_escape', True):
        flash(_('مغامرة جلبوع غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('jail.index'))

    now = _now_utc()
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    jail_until = _to_aware(getattr(user, "jail_until", None))
    if not jail_until or jail_until <= now:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))

    today = _today_utc_date(now)
    limit = max(1, _cfg_int('jail_gilboa_daily_limit', 2))
    used = int(
        user.jail_gilboa_attempts or 0) if user.jail_gilboa_attempts_date == today else 0
    if used >= limit:
        flash(_('لا يمكنك تكرار مغامرة جلبوع أكثر اليوم.'), 'warning')
        return redirect(url_for('jail.index'))

    cooldown_hours = max(0, _cfg_int('jail_gilboa_cooldown_hours', 6))
    cd_left = _cooldown_seconds_left(
        getattr(
            user,
            "jail_gilboa_last_at",
            None),
        cooldown_hours *
        3600,
        now)
    if cd_left > 0:
        minutes = int((cd_left + 59) // 60)
        flash(
            _('لا تزال المغامرة تحت التبريد. انتظر %(m)s دقيقة.', m=minutes),
            'warning')
        return redirect(url_for('jail.index'))

    energy_cost = max(0, _cfg_int('jail_gilboa_energy_cost', 45))
    diamond_cost = max(0, _cfg_int('jail_gilboa_diamond_cost', 8))
    if user.energy < energy_cost:
        flash(_('تحتاج إلى %(cost)s طاقة.'), 'danger')
        return redirect(url_for('jail.index'))
    if user.diamonds < diamond_cost:
        flash(_('تحتاج إلى %(cost)s ماسة لهذه المغامرة.'), 'danger')
        return redirect(url_for('jail.index'))

    success_chance = max(
        0.0, min(
            1.0, _cfg_float(
                'jail_gilboa_success_chance', 0.35)))
    exp_reward = max(0, _cfg_int('jail_gilboa_exp_reward', 180))
    penalty_min = max(0, _cfg_int('jail_gilboa_penalty_min', 25))
    penalty_max = max(penalty_min, _cfg_int('jail_gilboa_penalty_max', 55))
    injury_pct = max(
        0.0, min(
            0.75, _cfg_float(
                'jail_gilboa_injury_pct', 0.10)))

    is_success = random.random() < success_chance
    now_naive = _now_naive_utc()

    set_fields = {
        "jail_gilboa_attempts_date": today,
        "jail_gilboa_attempts": used + 1,
        "jail_gilboa_last_at": now_naive,
    }
    changes = {
        "energy": -
        energy_cost,
        "diamonds": -
        diamond_cost,
        "exp": exp_reward}

    if is_success:
        set_fields["jail_until"] = None
        ok = ResourceService.modify_resources(
            user.id,
            changes,
            "jail_gilboa_escape",
            auto_commit=False,
            expected_version=user.version,
            set_fields=set_fields,
            log_extra={"success": True},
        )
        if not ok:
            db.session.rollback()
            flash(_('حدث خطأ أثناء المغامرة.'), 'danger')
            return redirect(url_for('jail.index'))

        try:
            user.unlock_achievement(
                'gilboa_escape',
                _('ملحمة جلبوع'),
                _('نجحت في هروب أسطوري من السجن.'),
                points=25)
        except Exception:
            pass

        db.session.add(
            GameLog(
                admin_id=user.id,
                action='JAIL_GILBOA_SUCCESS',
                details=f'Energy {energy_cost}, Diamonds {diamond_cost}'))
        db.session.commit()
        flash(_('نجحت مغامرة جلبوع! خرجت من السجن رغم التشديد.'), 'success')
        return redirect(url_for('main.index', fx='escape_success'))

    penalty_minutes = random.randint(
        penalty_min, penalty_max) if penalty_max > 0 else 0
    health_loss = int(max(0, (user.max_health or 0) * injury_pct))
    if health_loss > 0:
        changes["health"] = -health_loss
    set_fields["jail_until"] = (
        _to_aware(user.jail_until) or now) + timedelta(minutes=penalty_minutes)

    ok = ResourceService.modify_resources(
        user.id,
        changes,
        "jail_gilboa_escape",
        auto_commit=False,
        expected_version=user.version,
        set_fields=set_fields,
        log_extra={"success": False, "penalty_minutes": penalty_minutes},
    )
    if not ok:
        db.session.rollback()
        flash(_('حدث خطأ أثناء المغامرة.'), 'danger')
        return redirect(url_for('jail.index'))

    db.session.add(
        GameLog(
            admin_id=user.id,
            action='JAIL_GILBOA_FAIL',
            details=f'Penalty {penalty_minutes}m'))
    db.session.commit()
    flash(
        _('فشلت مغامرة جلبوع. تم تشديد الإجراءات وزادت عقوبتك %(min)s دقيقة.'),
        'danger')
    return redirect(url_for('jail.index', fx='escape_fail'))


@bp.route('/self_bail', methods=['POST'])
@login_required
@limiter.limit("6 per minute")
def self_bail():
    if not _cfg_bool('jail_enable_self_bail_diamonds', True):
        flash(_('الكفالة بالماس غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('jail.index'))

    now = _now_utc()
    user = db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()
    jail_until = _to_aware(getattr(user, "jail_until", None))
    if not jail_until or jail_until <= now:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))

    cooldown_hours = max(0, _cfg_int('jail_self_bail_cooldown_hours', 12))
    try:
        last = (
            UserLog.query.filter(
                UserLog.user_id == user.id,
                UserLog.action == "JAIL_SELF_BAIL") .order_by(
                UserLog.timestamp.desc()) .first())
        cd_left = _cooldown_seconds_left(
            getattr(
                last,
                "timestamp",
                None),
            cooldown_hours *
            3600,
            now) if last else 0
    except Exception:
        cd_left = 0
    if cd_left > 0:
        minutes = int((cd_left + 59) // 60)
        flash(
            _('لا يمكنك تكرار الكفالة الآن. انتظر %(m)s دقيقة.', m=minutes),
            'warning')
        return redirect(url_for('jail.index'))

    diamond_cost = max(0, _cfg_int('jail_self_bail_cost_diamonds', 15))
    if user.diamonds < diamond_cost:
        flash(_('لا تملك ألماس كافٍ. تحتاج %(cost)s ماسة.'), 'danger')
        return redirect(url_for('jail.index'))

    ok = ResourceService.modify_resources(
        user.id,
        {'diamonds': -diamond_cost},
        'jail_self_bail',
        auto_commit=False,
        expected_version=user.version,
        set_fields={'jail_until': None},
        log_extra={'diamonds_cost': diamond_cost},
    )
    if not ok:
        db.session.rollback()
        flash(_('فشلت العملية.'), 'danger')
        return redirect(url_for('jail.index'))

    db.session.add(
        GameLog(
            admin_id=user.id,
            action='JAIL_SELF_BAIL',
            details=f'Paid {diamond_cost} diamonds'))
    db.session.commit()
    flash(_('تمت الكفالة بالماس. أنت حر الآن.'), 'success')
    return redirect(url_for('main.index', fx='escape_success'))


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
    success_chance = 0.15  # 15% chance to succeed

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
            current_jail_until = current_jail_until.replace(
                tzinfo=timezone.utc)

        new_jail_until = current_jail_until + \
            timedelta(minutes=penalty_minutes)
        set_fields['jail_until'] = new_jail_until

    if not ResourceService.modify_resources(
        current_user.id,
        changes,
        'jail_riot_attempt',
        auto_commit=False,
        expected_version=current_user.version,
            set_fields=set_fields):
        flash(_('تحتاج إلى %(cost)s طاقة للتحريض على التمرد! أو حدث خطأ في التزامن.',
              cost=energy_cost), 'danger')
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
            jail_until=User.jail_until - timedelta(minutes=reduction_minutes)
        )
        db.session.execute(stmt)

        # Bonus for leader
        xp_reward = 500
        # Re-fetch user to get latest version if needed, but we can just force
        # update since we are the actor
        ResourceService.modify_resources(
            current_user.id, {
                'exp': xp_reward}, 'jail_riot_success_leader', auto_commit=False)

        flash(
            _(
                'نجح التمرد! عمت الفوضى وتم تخفيض عقوبة الجميع بمقدار %(min)s دقيقة! وحصلت على %(xp)s خبرة.',
                min=reduction_minutes,
                xp=xp_reward),
            'success')

        # Log
        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_RIOT_SUCCESS',
            details=f'Riot reduced time by {reduction_minutes}m')
        db.session.add(log)
        db.session.commit()

    else:
        flash(_('فشل التمرد! تم كشف خطتك ووضعك في الانفرادي. زادت عقوبتك %(min)s دقيقة.',
              min=penalty_minutes), 'danger')

        # Log
        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_RIOT_FAIL',
            details=f'Riot failed, penalty {penalty_minutes}m')
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
        flash(
            _('صحتك متدهورة جداً! لا يمكنك بدء إضراب الكرامة وأنت في هذه الحالة.'),
            'danger')
        return redirect(url_for('jail.index'))

    # Deduct Health
    health_cost = int(current_user.max_health * 0.20)

    import random
    chance = random.random()

    changes = {'health': -health_cost}
    set_fields = {}

    outcome_type = 'fail'  # success, fail, punish

    if chance < 0.40:
        # Success: Administration yields
        outcome_type = 'success'
        reduction_minutes = random.randint(15, 45)
        # Ensure jail_until is timezone aware
        current_jail_until = current_user.jail_until
        if current_jail_until.tzinfo is None:
            current_jail_until = current_jail_until.replace(
                tzinfo=timezone.utc)

        new_jail_until = current_jail_until - \
            timedelta(minutes=reduction_minutes)
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
            current_jail_until = current_jail_until.replace(
                tzinfo=timezone.utc)

        new_jail_until = current_jail_until + \
            timedelta(minutes=extension_minutes)
        set_fields['jail_until'] = new_jail_until

    if not ResourceService.modify_resources(
        current_user.id,
        changes,
        'jail_hunger_strike',
        auto_commit=False,
        expected_version=current_user.version,
            set_fields=set_fields):
        flash(_('حدث خطأ أثناء معالجة الإضراب. قد تكون حالتك تغيرت.'), 'danger')
        return redirect(url_for('jail.index'))

    if outcome_type == 'success':
        flash(
            _(
                '✌️ انتصار الأمعاء الخاوية! رضخت إدارة السجون لمطالبك وتم تخفيض حكمك %(min)s دقيقة.',
                min=reduction_minutes),
            'success')
        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_HUNGER_STRIKE_SUCCESS',
            details=f'Hunger strike reduced time by {reduction_minutes}m')
        db.session.add(log)

    elif outcome_type == 'fail':
        flash(_('استمر الإضراب ولكن إدارة السجون ترفض التفاوض. فقدت صحتك بلا نتيجة.', ), 'warning')
        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_HUNGER_STRIKE_FAIL',
            details='Hunger strike failed (neutral)')
        db.session.add(log)

    else:  # punish
        flash(
            _(
                'عاقبتك الإدارة بالعزل الانفرادي وتجديد الاعتقال الإداري لمدة %(min)s دقيقة إضافية.',
                min=extension_minutes),
            'danger')
        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_HUNGER_STRIKE_PUNISH',
            details=f'Hunger strike punished by {extension_minutes}m')
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

    # Calculate new jail time
    current_jail_until = current_user.jail_until
    if current_jail_until.tzinfo is None:
        current_jail_until = current_jail_until.replace(tzinfo=timezone.utc)
    new_jail_until = current_jail_until - timedelta(minutes=reduction_minutes)

    if not ResourceService.modify_resources(
        current_user.id,
        {
            'money': -cost},
        'jail_lawyer_visit',
        auto_commit=False,
        expected_version=current_user.version,
        set_fields={
            'jail_until': new_jail_until}):
        flash(_('لا تملك تكاليف المحامي! تحتاج إلى %(cost)d$.', cost=cost), 'danger')
        return redirect(url_for('jail.index'))

    db.session.add(
        MoneySinkLog(
            user_id=current_user.id,
            sink_type="jail_lawyer_visit",
            amount=cost,
            details="Lawyer visit"))
    db.session.add(
        GameLog(
            admin_id=current_user.id,
            action='JAIL_LAWYER_VISIT',
            details=f'Paid {cost}$ for lawyer, reduced {reduction_minutes}m'))
    db.session.commit()

    flash(_('قام المحامي بتقديم استئناف عاجل! تم تخفيض الحكم %(min)s دقيقة.',
          min=reduction_minutes), 'success')
    return redirect(url_for('jail.index'))


@bp.route('/document_report', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def document_report():
    if not _cfg_bool('jail_enable_document_report', True):
        flash(_('ميزة التوثيق غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('jail.index'))

    now = datetime.now(timezone.utc)
    jail_until = _to_aware(current_user.jail_until)
    if not jail_until or jail_until <= now:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))

    cooldown_hours = max(1, _cfg_int('jail_document_report_cooldown_hours', 3))
    cooldown = now - timedelta(hours=cooldown_hours)
    last = (
        UserLog.query.filter(
            UserLog.user_id == current_user.id,
            UserLog.action == "JAIL_DOCUMENT_REPORT",
            UserLog.timestamp >= cooldown,
        )
        .order_by(UserLog.timestamp.desc())
        .first()
    )
    if last:
        flash(_('يمكنك استخدام التوثيق مرة كل %(h)s ساعات.',
              h=cooldown_hours), 'warning')
        return redirect(url_for('jail.index'))

    energy_cost = max(0, _cfg_int('jail_document_report_energy_cost', 5))
    if current_user.energy < energy_cost:
        flash(_('تحتاج إلى %(cost)s طاقة للتوثيق.', cost=energy_cost), 'danger')
        return redirect(url_for('jail.index'))

    success_chance = max(
        0.0, min(
            1.0, _cfg_float(
                'jail_document_report_success_chance', 0.35)))
    min_reduction = max(0, _cfg_int('jail_document_report_reduction_min', 3))
    max_reduction = max(min_reduction, _cfg_int(
        'jail_document_report_reduction_max', 8))
    exp_reward = max(0, _cfg_int('jail_document_report_exp_reward', 40))

    success = random.random() < success_chance
    reduction_minutes = random.randint(
        min_reduction, max_reduction) if success else 0

    set_fields = {}
    if success:
        current_jail_until = _to_aware(current_user.jail_until)
        if current_jail_until:
            set_fields["jail_until"] = current_jail_until - \
                timedelta(minutes=reduction_minutes)

    changes = {"energy": -energy_cost, "exp": exp_reward}
    ok = ResourceService.modify_resources(
        current_user.id,
        changes,
        "jail_document_report",
        auto_commit=True,
        expected_version=current_user.version,
        set_fields=set_fields or None,
        log_extra={"success": success, "reduction_minutes": reduction_minutes},
    )
    if not ok:
        flash(_('حدث خطأ أثناء التوثيق. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('jail.index'))

    if success:
        flash(_('تم توثيق الانتهاكات وإيصالها للخارج. تم تخفيض حكمك %(min)s دقيقة.',
              min=reduction_minutes), 'success')
    else:
        flash(_('تم توثيق الانتهاكات، لكن لم يحدث تأثير فوري على ملفك.'), 'info')
    return redirect(url_for('jail.index'))


@bp.route('/family_visit', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def family_visit():
    if not _cfg_bool('jail_enable_family_visit', True):
        flash(_('ميزة الزيارة غير مفعلة حالياً.'), 'warning')
        return redirect(url_for('jail.index'))

    now = datetime.now(timezone.utc)
    jail_until = _to_aware(current_user.jail_until)
    if not jail_until or jail_until <= now:
        flash(_('أنت لست في السجن!'), 'warning')
        return redirect(url_for('jail.index'))

    cooldown_hours = max(1, _cfg_int('jail_family_visit_cooldown_hours', 12))
    cooldown = now - timedelta(hours=cooldown_hours)
    last = (
        UserLog.query.filter(
            UserLog.user_id == current_user.id,
            UserLog.action == "JAIL_FAMILY_VISIT",
            UserLog.timestamp >= cooldown,
        )
        .order_by(UserLog.timestamp.desc())
        .first()
    )
    if last:
        flash(_('يمكنك طلب الزيارة مرة كل %(h)s ساعات.', h=cooldown_hours), 'warning')
        return redirect(url_for('jail.index'))

    approve_chance = max(
        0.0, min(
            1.0, _cfg_float(
                'jail_family_visit_approve_chance', 0.45)))
    min_reduction = max(0, _cfg_int('jail_family_visit_reduction_min', 6))
    max_reduction = max(min_reduction, _cfg_int(
        'jail_family_visit_reduction_max', 14))
    exp_reward = max(0, _cfg_int('jail_family_visit_exp_reward', 20))

    approved = random.random() < approve_chance
    reduction_minutes = random.randint(
        min_reduction, max_reduction) if approved else 0

    set_fields = {}
    changes = {}
    if approved:
        current_jail_until = _to_aware(current_user.jail_until)
        if current_jail_until:
            set_fields["jail_until"] = current_jail_until - \
                timedelta(minutes=reduction_minutes)
        changes["exp"] = exp_reward

    ok = ResourceService.modify_resources(
        current_user.id,
        changes,
        "jail_family_visit",
        auto_commit=True,
        expected_version=current_user.version,
        set_fields=set_fields or None,
        log_extra={
            "approved": approved,
            "reduction_minutes": reduction_minutes},
    )
    if not ok:
        flash(_('حدث خطأ أثناء معالجة طلب الزيارة.'), 'danger')
        return redirect(url_for('jail.index'))

    if approved:
        flash(_('تمت الزيارة. ثباتك أقوى! تم تخفيض حكمك %(min)s دقيقة.',
              min=reduction_minutes), 'success')
    else:
        flash(_('تم رفض الزيارة اليوم. حاول لاحقاً.'), 'warning')
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

    new_jail_until = current_jail_until - \
        timedelta(minutes=time_reduction_minutes)

    changes = {'energy': -energy_cost, 'money': cash_reward}
    set_fields = {'jail_until': new_jail_until}

    if not ResourceService.modify_resources(
        current_user.id,
        changes,
        'jail_hard_labor',
        auto_commit=True,
        expected_version=current_user.version,
            set_fields=set_fields):
        flash(_('تحتاج إلى %(cost)s طاقة للقيام بالأعمال الشاقة! أو حدث خطأ في التزامن.',
              cost=energy_cost), 'danger')
        return redirect(url_for('jail.index'))

    # Log handled by ResourceService

    flash(_('قمت بعمل شاق في المغسلة! تم تخفيض عقوبتك %(min)s دقيقة وحصلت على %(money)s$.',
          min=time_reduction_minutes, money=cash_reward), 'success')
    return redirect(url_for('jail.index'))


@bp.route('/bribe', methods=['POST'])
@login_required
def bribe():
    enable_bribe = SystemConfig.get_value(
        'jail_enable_bribe', 'false') == 'true'
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
            discount_msg = _(
                ' (خصم %(percent)s%% من العصابة)',
                percent=discount_percent)

    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > datetime.now(timezone.utc):
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'jail_bail_discount':
                hostess_discount = int(
                    (hostess.buff_value if hostess.buff_value else 0.1) * 100)
                discount_percent = min(70, discount_percent + hostess_discount)
                discount_msg = (
                    discount_msg or "") + _(' (خصم %(percent)s%% من المضيفة)', percent=hostess_discount)

    bribe_cost = max(1, int(base_bribe_cost * (1 - discount_percent / 100)))

    if ResourceService.modify_resources(current_user.id,
                                        {'money': -bribe_cost},
                                        'jail_bribe',
                                        auto_commit=False,
                                        expected_version=current_user.version,
                                        set_fields={'jail_until': None}):

        # Log
        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_BRIBE',
            details=f'Paid {bribe_cost} to get out of jail')
        db.session.add(log)
        db.session.add(
            MoneySinkLog(
                user_id=current_user.id,
                sink_type="jail_bribe",
                amount=bribe_cost,
                details="Bribe"))
        db.session.commit()

        flash(_('تم دفع الرشوة بنجاح! أنت حر الآن.%(msg)s',
              msg=discount_msg), 'success')
        return redirect(url_for('main.index', fx='escape_success'))
    else:
        flash(_('ليس لديك مال كافٍ لدفع الرشوة! تحتاج %(cost)s$.%(msg)s',
              cost=bribe_cost, msg=discount_msg), 'danger')
        return redirect(url_for('jail.index'))


@bp.route('/pay_bail/<int:prisoner_id>', methods=['POST'])
@login_required
def pay_bail(prisoner_id):
    # Enable/Disable setting
    enable_bribe = SystemConfig.get_value(
        'jail_enable_bribe', 'false') == 'true'
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
        flash(
            _('لا يمكنك دفع كفالة لنفسك بالماس، استخدم خيار الرشوة بالمال!'),
            'warning')
        return redirect(url_for('jail.index'))

    # Cost in Diamonds
    base_bail_cost = int(
        SystemConfig.get_value(
            'jail_bail_cost_diamonds', '5'))

    discount_percent = 0
    discount_msg = ""
    if current_user.gang:
        discount_percent = min(50, current_user.gang.level * 2)
        if discount_percent > 0:
            discount_msg = _(
                ' (خصم %(percent)s%% من العصابة)',
                percent=discount_percent)

    if current_user.active_hostess_id and current_user.casino_luck_until:
        luck_until = current_user.casino_luck_until
        if luck_until.tzinfo is None:
            luck_until = luck_until.replace(tzinfo=timezone.utc)

        if luck_until > datetime.now(timezone.utc):
            hostess = db.session.get(Hostess, current_user.active_hostess_id)
            if hostess and hostess.buff_type == 'jail_bail_discount':
                hostess_discount = int(
                    (hostess.buff_value if hostess.buff_value else 0.1) * 100)
                discount_percent = min(70, discount_percent + hostess_discount)
                discount_msg = (
                    discount_msg or "") + _(' (خصم %(percent)s%% من المضيفة)', percent=hostess_discount)

    bail_cost_diamonds = max(
        1, int(base_bail_cost * (1 - discount_percent / 100)))

    # Deadlock Prevention: Lock both users in ID order
    users_to_lock = sorted([current_user.id, prisoner.id])
    db.session.query(User).filter(
        User.id.in_(users_to_lock)).with_for_update().all()

    if ResourceService.modify_resources(current_user.id,
                                        {'diamonds': -bail_cost_diamonds},
                                        'jail_bail',
                                        auto_commit=False,
                                        expected_version=current_user.version):
        prisoner.jail_until = None

        # Log
        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_BAIL',
            details=f'Paid {bail_cost_diamonds} diamonds to free {prisoner.username}')
        db.session.add(log)
        db.session.commit()

        flash(_('تم دفع الكفالة بنجاح! تم إخراج %(name)s من السجن.%(msg)s',
              name=prisoner.username, msg=discount_msg), 'success')
    else:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.%(msg)s',
              cost=bail_cost_diamonds, msg=discount_msg), 'danger')

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

    enable_breakout = SystemConfig.get_value(
        'jail_enable_breakout', 'false') == 'true'
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
            flash(
                random.choice([
                    _('تطورت مهاراتك في التخطيط! (+1 ذكاء)'),
                    _('تعلمت حركة جديدة… (+1 ذكاء)'),
                    _('صار عندك خبرة بالتخطيط أكثر! (+1 ذكاء)'),
                ]),
                'info',
            )

        changes['exp'] = xp_reward
        if intelligence_gain > 0:
            changes['intelligence'] = intelligence_gain

    else:
        # Fail - go to jail?
        fail_jail_minutes = 5
        set_fields['jail_until'] = datetime.now(
            timezone.utc) + timedelta(minutes=fail_jail_minutes)

    if not ResourceService.modify_resources(
        current_user.id,
        changes,
        'jail_breakout',
        auto_commit=False,
        expected_version=current_user.version,
            set_fields=set_fields):
        flash(
            random.choice([
                _('تحتاج إلى 50 طاقة لمحاولة التهريب! أو حدث خطأ في التزامن.'),
                _('بدك 50 طاقة عشان التهريب… أو صار خلل بالتزامن.'),
                _('التهريب بدّه 50 طاقة… أو في مشكلة تزامن.'),
            ]),
            'danger')
        return redirect(url_for('jail.index'))

    if is_success:
        # Commit prisoner release
        prisoner.jail_until = None

        log = GameLog(
            admin_id=current_user.id,
            action='JAIL_BREAKOUT',
            details=f'Broke out {prisoner.username}')
        db.session.add(log)

        flash(
            random.choice([
                _('نجحت العملية! تم تهريب %(name)s وحصلت على %(xp)s خبرة.',
                  name=prisoner.username, xp=xp_reward),
                _('عملية التهريب نجحت! طلّعت %(name)s وكسبت %(xp)s خبرة.',
                  name=prisoner.username, xp=xp_reward),
                _('نفّذت التهريب! %(name)s صار حر… وأنت ربحت %(xp)s خبرة.',
                  name=prisoner.username, xp=xp_reward),
            ]),
            'success',
        )
    else:
        flash(
            random.choice([
                _('فشلت العملية! تم القبض عليك وإيداعك السجن لمدة 5 دقائق.'),
                _('انمسكت وأنت بتحاول… 5 دقائق سجن زيادة.'),
                _('ما زبطت التهريب… قبضوا عليك وسجنوك 5 دقائق.'),
            ]),
            'danger',
        )

    db.session.commit()
    return redirect(url_for('jail.index'))
