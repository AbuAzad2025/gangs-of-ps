from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, session
from flask_login import login_required, current_user
from extensions import db, limiter
from flask_babel import _
from models import Race, RaceParticipant, UserVehicle, User, Hostess
from models.log import UserLog
from models.system import SystemConfig
from datetime import datetime, timezone
import json
import math
import random
from services.resource_service import ResourceService

bp = Blueprint('racing', __name__, url_prefix='/casino/racing')


def _round_money(value, step=100):
    try:
        v = int(value)
    except Exception:
        v = 0
    if step <= 1:
        return max(0, v)
    return max(0, int(round(v / step) * step))


def _clamp(value, lo, hi):
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _vehicle_multiplier(vehicle):
    price = getattr(vehicle, 'price', None) or 0
    if price <= 0:
        return 1.0
    vtype = (getattr(vehicle, 'type', '') or '').lower()
    risk = getattr(vehicle, 'risk', None) or 0

    m = 0.80 + (price / 220000.0)
    m *= (1.0 + (_clamp(risk, 0, 100) / 1000.0))
    if vtype == 'mushtuba':
        m *= 0.95
    if m < 0.75:
        m = 0.75
    if m > 3.0:
        m = 3.0
    return m


def _calc_upgrade_cost(my_car, part_type):
    if part_type == 'engine':
        base = 5000
        level = my_car.engine_level
    elif part_type == 'tires':
        base = 3000
        level = my_car.tires_level
    elif part_type == 'armor':
        base = 4000
        level = my_car.armor_level
    else:
        return None

    mult = _vehicle_multiplier(my_car.vehicle)
    return _round_money(base * (level + 1) * mult, 100)


def _calc_upgrade_caps(vehicle):
    price = getattr(vehicle, 'price', None) or 0
    speed = getattr(vehicle, 'speed', None) or 0
    defense = getattr(vehicle, 'defense', None) or 0
    risk = getattr(vehicle, 'risk', None) or 0
    vtype = (getattr(vehicle, 'type', '') or '').lower()

    price_score = _clamp((price - 20000) / 280000.0, 0.0, 1.0)
    speed_score = _clamp((speed - 20) / 120.0, 0.0, 1.0)
    defense_score = _clamp((defense - 20) / 120.0, 0.0, 1.0)
    risk_score = _clamp(risk / 100.0, 0.0, 1.0)

    engine_max = 4 + int(round((10 * price_score) +
                         (4 * speed_score) - (2 * risk_score)))
    tires_max = 4 + int(round((9 * price_score) +
                        (5 * speed_score) - (2 * risk_score)))
    armor_max = 3 + int(round((9 * price_score) +
                        (5 * defense_score) - (3 * risk_score)))

    if speed < 30:
        engine_max -= 1
        tires_max -= 1
    if defense < 30:
        armor_max -= 1

    if vtype == 'mushtuba':
        engine_max -= 1
        tires_max -= 1
        armor_max -= 1

    engine_max = int(_clamp(engine_max, 3, 16))
    tires_max = int(_clamp(tires_max, 3, 16))
    armor_max = int(_clamp(armor_max, 2, 14))

    return {
        'engine': int(engine_max),
        'tires': int(tires_max),
        'armor': int(armor_max)}


def _max_driving_skill(user):
    lvl = int(getattr(user, 'level', 1) or 1)
    cap = 10 + int(round((lvl * 1.6) + (math.sqrt(max(1, lvl)) * 2.2)))
    return int(_clamp(cap, 10, 100))


def _ai_race_daily_limit():
    limits = {
        'easy': 20,
        'normal': 12,
        'hard': 6,
    }
    try:
        legacy = SystemConfig.get_value('ai_race_daily_limit', None)
        legacy_int = int(legacy) if legacy is not None else None
    except Exception:
        legacy_int = None

    for diff in list(limits.keys()):
        key = f'ai_race_daily_limit_{diff}'
        try:
            raw = SystemConfig.get_value(key, None)
            if raw is None:
                if legacy_int is not None:
                    limits[diff] = max(0, int(legacy_int))
            else:
                limits[diff] = max(0, int(raw))
        except Exception:
            if legacy_int is not None:
                limits[diff] = max(0, int(legacy_int))

    return limits


def _ai_race_used_today(user_id, difficulty):
    diff = (difficulty or 'normal').strip().lower()
    if diff not in ['easy', 'normal', 'hard']:
        diff = 'normal'
    start = datetime.now(
        timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0)
    action = f'AI_RACE_BET_{diff.upper()}'
    return (
        db.session.query(UserLog.id)
        .filter(
            UserLog.user_id == user_id,
            UserLog.action == action,
            UserLog.timestamp >= start,
        )
        .count()
    )


def _is_unlimited_user(user):
    try:
        if getattr(user, 'is_developer', False):
            return True
    except Exception:
        pass

    try:
        uname = (getattr(user, 'username', '') or '').casefold()
        if uname == 'azad':
            return True
    except Exception:
        pass

    return False


def _get_pvp_result_for_user(user_id, race_id):
    logs = (
        UserLog.query.filter_by(user_id=user_id, action='RACE_PVP_RESULT')
        .order_by(UserLog.timestamp.desc())
        .limit(25)
        .all()
    )
    for log in logs:
        try:
            data = json.loads(log.details or '{}')
        except Exception:
            continue
        if data.get('race_id') == race_id:
            return data
    return None


@bp.route('/')
@login_required
def index():
    # Show active lobbies
    active_races = Race.query.filter(
        Race.status == 'waiting').order_by(
        Race.created_at.desc()).limit(50).all()

    # User's active car
    my_car = UserVehicle.query.filter_by(
        user_id=current_user.id, is_active=True).first()

    upgrade_costs = None
    upgrade_caps = None
    training_options = None
    max_skill = _max_driving_skill(current_user)
    ai_result = session.pop('ai_race_result', None)
    ai_limits = _ai_race_daily_limit()
    ai_unlimited = _is_unlimited_user(current_user)
    if ai_unlimited:
        ai_used = {'easy': 0, 'normal': 0, 'hard': 0}
    else:
        ai_used = {
            'easy': _ai_race_used_today(
                current_user.id,
                'easy') if ai_limits.get(
                'easy',
                0) > 0 else 0,
            'normal': _ai_race_used_today(
                current_user.id,
                'normal') if ai_limits.get(
                    'normal',
                    0) > 0 else 0,
            'hard': _ai_race_used_today(
                current_user.id,
                'hard') if ai_limits.get(
                'hard',
                0) > 0 else 0,
        }
    if my_car:
        upgrade_caps = _calc_upgrade_caps(my_car.vehicle)
        upgrade_costs = {
            'engine': _calc_upgrade_cost(my_car, 'engine'),
            'tires': _calc_upgrade_cost(my_car, 'tires'),
            'armor': _calc_upgrade_cost(my_car, 'armor'),
        }

        skill = max(1, int(getattr(current_user, 'driving_skill', 1) or 1))
        base_per_skill = 1000
        if skill < max_skill:
            defs = [
                {'key': 'basic', 'label': _('تدريب عادي'), 'gain': 1, 'factor': 1.0},
                {'key': 'advanced', 'label': _('تدريب متقدم'), 'gain': 2, 'factor': 2.5},
                {'key': 'elite', 'label': _('تدريب نخبة'), 'gain': 3, 'factor': 4.5},
            ]
            training_options = []
            for d in defs:
                gain = min(int(d['gain']), max_skill - skill)
                if gain <= 0:
                    continue
                cost = _round_money(
                    base_per_skill * skill * float(d['factor']) * (gain / float(d['gain'])), 100)
                training_options.append(
                    {'key': d['key'], 'label': d['label'], 'gain': gain, 'cost': cost})

    return render_template(
        'casino/racing/index.html',
        races=active_races,
        my_car=my_car,
        upgrade_costs=upgrade_costs,
        upgrade_caps=upgrade_caps,
        training_options=training_options,
        max_driving_skill=max_skill,
        ai_race_result=ai_result,
        ai_race_limits=ai_limits,
        ai_race_used=ai_used,
        ai_race_unlimited=ai_unlimited,
    )


@bp.route('/create', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def create():
    db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

    existing_race = Race.query.filter_by(
        creator_id=current_user.id,
        status='waiting').first()
    if existing_race:
        flash(
            _('عندك سباق بانتظار المتحدين بالفعل. احذفه أو استنى حد ينضم.'),
            'warning')
        return redirect(url_for('racing.room', race_id=existing_race.id))

    bet = int(request.form.get('bet', 0))
    if bet < 100:
        flash(_('أقل رهان هو 100 شيكل!'), 'danger')
        return redirect(url_for('racing.index'))

    if current_user.money < bet:
        flash(_('معكش مصاري كفاية!'), 'danger')
        return redirect(url_for('racing.index'))

    my_car = UserVehicle.query.filter_by(
        user_id=current_user.id, is_active=True).first()
    if not my_car:
        flash(_('لازم يكون عندك سيارة مفعلة عشان تسابق!'), 'danger')
        return redirect(url_for('racing.index'))

    if my_car.condition < 50:
        flash(_('سيارتك خربانة! صلحها قبل السباق.'), 'danger')
        return redirect(url_for('racing.index'))

    # Atomic deduction via ResourceService
    if not ResourceService.modify_resources(
            current_user.id, {
            'money': -bet}, 'create_race', auto_commit=False, expected_version=None):
        flash(_('معكش مصاري كفاية!'), 'danger')
        return redirect(url_for('racing.index'))

    race = Race(creator_id=current_user.id, bet_amount=bet)
    db.session.add(race)
    db.session.commit()  # Commit to get ID

    # Add creator as participant
    participant = RaceParticipant(
        race_id=race.id,
        user_id=current_user.id,
        user_vehicle_id=my_car.id)
    db.session.add(participant)
    db.session.commit()

    flash(_('تم إنشاء السباق! بانتظار المتحدين...'), 'success')
    return redirect(url_for('racing.room', race_id=race.id))


@bp.route('/cancel/<int:race_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def cancel(race_id):
    race = Race.query.with_for_update().get(race_id)
    if not race or race.status != 'waiting':
        flash(_('السباق غير متاح للإلغاء.'), 'warning')
        return redirect(url_for('racing.index'))

    if race.creator_id != current_user.id:
        flash(_('فقط المنشئ يمكنه إلغاء السباق.'), 'danger')
        return redirect(url_for('racing.index'))

    participants = RaceParticipant.query.filter_by(race_id=race.id).all()
    if len(participants) > 1:
        flash(_('لا يمكنك إلغاء السباق بعد انضمام لاعبين آخرين.'), 'warning')
        return redirect(url_for('racing.room', race_id=race.id))

    if not ResourceService.modify_resources(
            current_user.id, {
            'money': race.bet_amount}, 'cancel_race_refund', auto_commit=False, expected_version=None):
        flash(_('حدث خطأ أثناء إرجاع الرهان. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('racing.room', race_id=race.id))

    db.session.delete(race)
    db.session.commit()
    flash(_('تم إلغاء السباق وإرجاع الرهان.'), 'success')
    return redirect(url_for('racing.index'))


@bp.route('/join/<int:race_id>', methods=['POST'])
@login_required
def join(race_id):
    # Lock race to prevent double start
    race = Race.query.with_for_update().get(race_id)
    if not race or race.status != 'waiting':
        flash(_('السباق غير متاح!'), 'danger')
        return redirect(url_for('racing.index'))

    if current_user.money < race.bet_amount:
        flash(_('معكش مصاري كفاية للانضمام!'), 'danger')
        return redirect(url_for('racing.index'))

    my_car = UserVehicle.query.filter_by(
        user_id=current_user.id, is_active=True).first()
    if not my_car:
        flash(_('لازم يكون عندك سيارة مفعلة!'), 'danger')
        return redirect(url_for('racing.index'))

    if my_car.condition < 50:
        flash(_('سيارتك خربانة! صلحها أول.'), 'danger')
        return redirect(url_for('racing.index'))

    # Check if already joined
    existing = RaceParticipant.query.filter_by(
        race_id=race.id, user_id=current_user.id).first()
    if existing:
        return redirect(url_for('racing.room', race_id=race.id))

    # Atomic deduction via ResourceService
    if not ResourceService.modify_resources(
            current_user.id, {
            'money': -race.bet_amount}, 'join_race', auto_commit=False, expected_version=None):
        flash(_('معكش مصاري كفاية للانضمام!'), 'danger')
        return redirect(url_for('racing.index'))

    participant = RaceParticipant(
        race_id=race.id,
        user_id=current_user.id,
        user_vehicle_id=my_car.id)
    db.session.add(participant)
    db.session.commit()

    flash(_('انضممت للسباق!'), 'success')
    return redirect(url_for('racing.room', race_id=race.id))


@bp.route('/room/<int:race_id>')
@login_required
def room(race_id):
    race = db.session.get(Race, race_id)
    if not race:
        abort(404)

    participants = RaceParticipant.query.filter_by(race_id=race.id).all()
    is_participant = any(p.user_id == current_user.id for p in participants)

    pvp_result = None
    show_pvp_modal = False
    if race.status == 'finished' and is_participant:
        pvp_result = _get_pvp_result_for_user(current_user.id, race.id)
        if pvp_result:
            key = f'pvp_result_shown_{race.id}'
            if not session.get(key):
                session[key] = True
                show_pvp_modal = True

    # Spy Logic
    spy_data = {}
    if current_user.active_hostess_id:
        h = db.session.get(Hostess, current_user.active_hostess_id)
        if h and h.role == 'spy':
            # Check expiry
            now = datetime.now(timezone.utc)
            if current_user.casino_luck_until and current_user.casino_luck_until.replace(
                    tzinfo=timezone.utc) > now:
                # Active Spy
                for p in participants:
                    if p.user_id != current_user.id:
                        spy_data[p.user_id] = {
                            'engine': p.user_vehicle.engine_level,
                            'tires': p.user_vehicle.tires_level,
                            'armor': p.user_vehicle.armor_level,
                            'condition': p.user_vehicle.condition,
                            'skill': p.user.driving_skill
                        }

    return render_template(
        'casino/racing/room.html',
        race=race,
        participants=participants,
        is_participant=is_participant,
        user=current_user,
        spy_data=spy_data,
        pvp_result=pvp_result,
        show_pvp_modal=show_pvp_modal,
    )


@bp.route('/start/<int:race_id>', methods=['POST'])
@login_required
def start(race_id):
    # Lock race to prevent double start
    race = Race.query.with_for_update().get(race_id)
    if not race or race.status != 'waiting':
        flash(_('لا يمكن بدء السباق!'), 'danger')
        return redirect(url_for('racing.index'))

    if race.creator_id != current_user.id:
        flash(_('فقط المنشئ يمكنه بدء السباق!'), 'danger')
        return redirect(url_for('racing.room', race_id=race.id))

    participants = RaceParticipant.query.filter_by(race_id=race.id).all()
    if len(participants) < 2:
        flash(_('تحتاج لمتسابق واحد على الأقل لتبدأ!'), 'warning')
        return redirect(url_for('racing.room', race_id=race.id))

    # Lock all participants (Users) to prevent race conditions on skills/vehicles
    # Sort IDs to prevent deadlocks
    participant_user_ids = sorted([p.user_id for p in participants])
    if participant_user_ids:
        # We lock the users, which implicitly ensures their associated data (like driving_skill)
        # is safe from concurrent modification if accessed through these locked
        # instances
        db.session.query(User).filter(
            User.id.in_(participant_user_ids)).with_for_update().all()

    # --- RACE LOGIC ---
    race.status = 'finished'  # Simplify for now (instant result)

    results = []

    for p in participants:
        # Score Formula:
        # Base Speed + (Engine * 5) + (Tires * 3) + (Driver Skill * 2) +
        # Random(0-20)

        base_speed = p.user_vehicle.vehicle.speed
        engine_bonus = p.user_vehicle.engine_level * 5
        tires_bonus = p.user_vehicle.tires_level * 3
        driver_bonus = p.user.driving_skill * 2
        luck_base = random.randint(0, 20)
        luck_bonus = 0

        # Hostess Luck Bonus
        if p.user.casino_luck_until and p.user.casino_luck_until.replace(
                tzinfo=timezone.utc) > datetime.now(timezone.utc):
            luck_bonus = 15  # Significant boost
        luck = luck_base + luck_bonus

        pre_condition_score = base_speed + engine_bonus + \
            tires_bonus + driver_bonus + luck

        # Apply Condition Malus (if damaged)
        condition_before = int(p.user_vehicle.condition or 0)
        condition_factor = p.user_vehicle.condition / 100.0
        total_score = pre_condition_score * condition_factor

        p.score = total_score
        results.append(p)

        # Damage the car slightly
        damage = random.randint(1, 5)
        condition_after = max(0, condition_before - damage)
        p.user_vehicle.condition = max(0, p.user_vehicle.condition - damage)

        details = {
            'race_id': race.id,
            'bet_amount': int(race.bet_amount),
            'participants': int(len(participants)),
            'vehicle': {
                'name': getattr(p.user_vehicle.vehicle, 'name', ''),
                'speed': int(base_speed),
                'engine_level': int(p.user_vehicle.engine_level),
                'tires_level': int(p.user_vehicle.tires_level),
            },
            'driver_skill': int(p.user.driving_skill),
            'calc': {
                'engine_bonus': int(engine_bonus),
                'tires_bonus': int(tires_bonus),
                'driver_bonus': int(driver_bonus),
                'luck_base': int(luck_base),
                'luck_bonus': int(luck_bonus),
                'pre_condition_score': float(pre_condition_score),
                'condition_before': int(condition_before),
                'condition_factor': float(condition_factor),
                'final_score': float(total_score),
                'damage': int(damage),
                'condition_after': int(condition_after),
            },
        }
        db.session.add(
            UserLog(
                user_id=p.user_id,
                action='RACE_PVP_RESULT',
                details=json.dumps(details, ensure_ascii=False),
                result='success',
            )
        )

        # Improve driver skill (small chance)
        if random.random() < 0.3:
            cap = _max_driving_skill(p.user)
            if p.user.driving_skill < cap:
                p.user.driving_skill = min(cap, p.user.driving_skill + 1)

    # Sort by score desc
    results.sort(key=lambda x: x.score, reverse=True)

    # Assign Ranks and Rewards
    total_pot = race.bet_amount * len(participants)

    # Winner takes all (or split 70/30 etc. - lets do Winner Takes All for
    # excitement)
    winner = results[0]
    winner.reward = total_pot
    # Atomic Update via ResourceService
    ResourceService.modify_resources(
        winner.user.id, {
            'money': total_pot}, 'race_win', auto_commit=False, expected_version=None)

    for i, p in enumerate(results):
        p.rank = i + 1
        try:
            detail_log = (
                UserLog.query.filter_by(
                    user_id=p.user_id,
                    action='RACE_PVP_RESULT') .order_by(
                    UserLog.timestamp.desc()) .first())
            if detail_log:
                data = json.loads(detail_log.details or '{}')
                if data.get('race_id') == race.id:
                    data['rank'] = int(p.rank)
                    data['score'] = float(p.score or 0.0)
                    data['winner_user_id'] = int(winner.user_id)
                    data['reward'] = int(p.reward or 0)
                    detail_log.details = json.dumps(data, ensure_ascii=False)
        except Exception:
            pass

    db.session.commit()

    flash(_('انتهى السباق! الفائز هو %(name)s',
          name=winner.user.username), 'success')
    return redirect(url_for('racing.room', race_id=race.id))


@bp.route('/train_driver', methods=['POST'])
@login_required
def train_driver():
    level = (request.form.get('level') or 'basic').strip()
    skill = max(1, int(getattr(current_user, 'driving_skill', 1) or 1))
    max_skill = _max_driving_skill(current_user)

    if skill >= max_skill:
        flash(_('وصلت للحد الأقصى لمهارة السائق حسب مستواك!'), 'warning')
        return redirect(url_for('racing.index'))

    levels = {
        'basic': {'gain': 1, 'factor': 1.0},
        'advanced': {'gain': 2, 'factor': 2.5},
        'elite': {'gain': 3, 'factor': 4.5},
    }
    cfg = levels.get(level, levels['basic'])
    desired_gain = int(cfg['gain'])
    gain = min(desired_gain, max_skill - skill)
    if gain <= 0:
        flash(_('وصلت للحد الأقصى لمهارة السائق حسب مستواك!'), 'warning')
        return redirect(url_for('racing.index'))

    factor = float(cfg['factor'])
    cost = _round_money(1000 * skill * factor *
                        (gain / float(desired_gain)), 100)

    if current_user.money < cost:
        flash(_('بدك %(cost)s للتدريب!', cost=cost), 'danger')
        return redirect(url_for('racing.index'))

    if not ResourceService.modify_resources(
            current_user.id, {
            'money': -cost}, 'train_driver', auto_commit=False, expected_version=None):
        flash(_('بدك %(cost)s للتدريب!', cost=cost), 'danger')
        return redirect(url_for('racing.index'))

    current_user.driving_skill = min(
        max_skill, current_user.driving_skill + gain)
    db.session.commit()

    flash(_('تدربت وتحسنت مهاراتك في القيادة!'), 'success')
    return redirect(url_for('racing.index'))


@bp.route('/upgrade_car/<part_type>', methods=['POST'])
@login_required
def upgrade_car(part_type):
    my_car = UserVehicle.query.filter_by(
        user_id=current_user.id, is_active=True).first()
    if not my_car:
        return redirect(url_for('racing.index'))

    caps = _calc_upgrade_caps(my_car.vehicle)

    if part_type == 'engine':
        current_level = my_car.engine_level
    elif part_type == 'tires':
        current_level = my_car.tires_level
    elif part_type == 'armor':
        current_level = my_car.armor_level
    else:
        return redirect(url_for('racing.index'))

    max_level = int(caps.get(part_type, 0) or 0)
    if current_level >= max_level:
        flash(_('وصلت للحد الأقصى لهذا التطوير حسب نوع السيارة!'), 'warning')
        return redirect(url_for('racing.index'))

    cost = _calc_upgrade_cost(my_car, part_type)
    if cost is None:
        return redirect(url_for('racing.index'))

    if current_user.money < cost:
        flash(_('معكش مصاري للتطوير!'), 'danger')
        return redirect(url_for('racing.index'))

    if not ResourceService.modify_resources(
            current_user.id, {
            'money': -cost}, 'upgrade_car', auto_commit=False, expected_version=None):
        flash(_('معكش مصاري للتطوير!'), 'danger')
        return redirect(url_for('racing.index'))

    if part_type == 'engine':
        my_car.engine_level += 1
    elif part_type == 'tires':
        my_car.tires_level += 1
    elif part_type == 'armor':
        my_car.armor_level += 1

    db.session.commit()
    flash(_('تم تطوير السيارة بنجاح!'), 'success')
    return redirect(url_for('racing.index'))


@bp.route('/ai_race', methods=['POST'])
@login_required
def ai_race():
    db.session.query(User).filter_by(
        id=current_user.id).with_for_update().first()

    bet = int(request.form.get('bet', 0))
    difficulty = (request.form.get('difficulty') or 'normal').strip().lower()
    if difficulty not in ['easy', 'normal', 'hard']:
        difficulty = 'normal'

    if not _is_unlimited_user(current_user):
        daily_limits = _ai_race_daily_limit()
        daily_limit = int(daily_limits.get(difficulty, 0) or 0)
        if daily_limit > 0:
            used_today = _ai_race_used_today(current_user.id, difficulty)
            if used_today >= daily_limit:
                flash(
                    _(
                        'وصلت للحد اليومي لسباقات الكمبيوتر (%(limit)s) لهذه الصعوبة. ارجع بكرة!',
                        limit=daily_limit),
                    'warning')
                return redirect(url_for('racing.index'))

    if bet < 100:
        flash(_('أقل رهان هو 100 شيكل!'), 'danger')
        return redirect(url_for('racing.index'))

    my_car = UserVehicle.query.filter_by(
        user_id=current_user.id, is_active=True).first()
    if not my_car:
        flash(_('لازم يكون عندك سيارة مفعلة عشان تسابق!'), 'danger')
        return redirect(url_for('racing.index'))

    if my_car.condition < 50:
        flash(_('سيارتك خربانة! صلحها قبل السباق.'), 'danger')
        return redirect(url_for('racing.index'))

    if current_user.money < bet:
        flash(_('معكش مصاري كفاية!'), 'danger')
        return redirect(url_for('racing.index'))

    payout_mult = {
        'easy': 1.5,
        'normal': 2.0,
        'hard': 2.6}.get(
        difficulty,
        2.0)

    if not ResourceService.modify_resources(
            current_user.id, {
            'money': -bet}, f'ai_race_bet_{difficulty}', auto_commit=False, expected_version=None):
        flash(_('معكش مصاري كفاية!'), 'danger')
        return redirect(url_for('racing.index'))

    def calc_score(
            base_speed,
            engine_level,
            tires_level,
            driver_skill,
            condition,
            luck_bonus=0):
        luck = random.randint(0, 20) + int(luck_bonus)
        total = base_speed + (engine_level * 5) + \
            (tires_level * 3) + (driver_skill * 2) + luck
        total *= (max(0, int(condition)) / 100.0)
        return total

    base_speed = my_car.vehicle.speed
    my_engine = my_car.engine_level
    my_tires = my_car.tires_level
    my_skill = current_user.driving_skill

    luck_bonus = 0
    if current_user.casino_luck_until and current_user.casino_luck_until.replace(
            tzinfo=timezone.utc) > datetime.now(timezone.utc):
        luck_bonus = 15

    player_score = calc_score(
        base_speed,
        my_engine,
        my_tires,
        my_skill,
        my_car.condition,
        luck_bonus=luck_bonus)

    opponents = []
    opp_count = 3
    diff_factor = {
        'easy': 0.92,
        'normal': 1.02,
        'hard': 1.12}.get(
        difficulty,
        1.02)
    caps = _calc_upgrade_caps(my_car.vehicle)
    for i in range(opp_count):
        o_engine = min(caps['engine'], max(
            0, int(round(my_engine * diff_factor + random.randint(-2, 2)))))
        o_tires = min(caps['tires'], max(
            0, int(round(my_tires * diff_factor + random.randint(-2, 2)))))
        o_skill = max(
            1, int(round(my_skill * diff_factor + random.randint(-3, 4))))
        o_cond = max(75, min(100, int(97 + random.randint(-12, 4))))
        o_speed = max(
            5, int(round(base_speed * diff_factor + random.randint(-7, 10))))
        score = calc_score(
            o_speed,
            o_engine,
            o_tires,
            o_skill,
            o_cond,
            luck_bonus=0)
        opponents.append(
            {
                'name': f'AI-{i + 1}',
                'score': score,
                'engine': o_engine,
                'tires': o_tires,
                'skill': o_skill,
                'speed': o_speed,
                'condition': o_cond,
            }
        )

    best_opp = max(opponents, key=lambda x: x['score'])
    win = player_score >= best_opp['score']

    damage = random.randint(1, 5)
    my_car.condition = max(0, my_car.condition - damage)

    if win:
        winnings = int(bet * payout_mult)
        ResourceService.modify_resources(current_user.id,
                                         {'money': winnings},
                                         f'ai_race_win_{difficulty}',
                                         auto_commit=False,
                                         expected_version=None)
        flash(_('فزت على الكمبيوتر! ربحت %(amt)s شيكل.', amt=winnings), 'success')
    else:
        flash(_('خسرت قدام الكمبيوتر! الفائز: %(name)s',
              name=best_opp['name']), 'danger')

    session['ai_race_result'] = {
        'difficulty': difficulty,
        'bet': bet,
        'player': {
            'score': player_score,
            'engine': my_engine,
            'tires': my_tires,
            'skill': my_skill,
            'speed': base_speed,
            'condition': my_car.condition,
        },
        'best_ai': best_opp,
        'opponents': opponents,
        'win': bool(win),
        'winnings': int(winnings) if win else 0,
        'damage': int(damage),
    }

    db.session.commit()
    return redirect(url_for('racing.index'))
