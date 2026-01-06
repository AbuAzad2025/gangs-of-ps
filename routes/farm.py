from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from datetime import datetime, timezone, timedelta
import random
import json

from extensions import db, limiter
from sqlalchemy import select
from models import Item, UserItem, FarmJob, SystemConfig, UserFacility, User
from models.location import Location
from models.contract import FarmSupplyContract
from services.requirements import check_requirements
from services.resource_service import ResourceService


bp = Blueprint('farm', __name__, url_prefix='/farm')


def _now_utc():
    return datetime.now(timezone.utc)


def _effective_level(user):
    try:
        return int(user.level + (user.rank_points_value // 50))
    except Exception:
        return int(user.level)


def _tier_for_level(level):
    if level < 5:
        return "t1"
    if level < 15:
        return "t2"
    if level < 30:
        return "t3"
    if level < 60:
        return "t4"
    return "t5"


def _weighted_int(low, high, w_low=0.7, w_mid=0.25):
    if low >= high:
        return int(low)
    mid = (low + high) // 2
    r = random.random()
    if r < w_low:
        return random.randint(int(low), int(mid))
    if r < (w_low + w_mid):
        return random.randint(int(mid), int(high))
    return int(high)


def _get_farm_config():
    raw = SystemConfig.get_value("farm_config_json", "")
    if raw:
        try:
            cfg = json.loads(raw)
            if isinstance(cfg, dict) and cfg.get("tiers"):
                return cfg
        except Exception:
            pass

    return {
        "max_parallel_jobs": 1,
        "products": {
            "olive": {"item_name": "زيت زيتون بلدي"},
            "zaatar": {"item_name": "زعتر بلدي"},
            "soap": {"item_name": "صابون نابلسي"},
            "dates": {"item_name": "تمر أريحا"},
            "keffiyeh": {"item_name": "كوفية فلسطينية"},
            "pottery": {"item_name": "فخار الخليل"},
        },
        "requirements": {
            "olive": {"min_intelligence": 0},
            "zaatar": {"min_intelligence": 0},
            "dates": {"min_intelligence": 12},
            "soap": {"min_intelligence": 15},
            "pottery": {"min_intelligence": 18},
            "keffiyeh": {"min_intelligence": 25}
        },
        "tiers": {
            "t1": {
                "olive": {"diamonds": 1, "minutes": (6, 12), "out": (1, 2)},
                "zaatar": {"diamonds": 1, "minutes": (5, 10), "out": (1, 3)},
            },
            "t2": {
                "olive": {"diamonds": 2, "minutes": (8, 14), "out": (1, 3)},
                "zaatar": {"diamonds": 2, "minutes": (7, 12), "out": (2, 5)},
                "soap": {"diamonds": 3, "minutes": (12, 18), "out": (1, 2)},
            },
            "t3": {
                "olive": {"diamonds": 3, "minutes": (10, 18), "out": (2, 5)},
                "zaatar": {"diamonds": 3, "minutes": (9, 16), "out": (3, 7)},
                "soap": {"diamonds": 4, "minutes": (14, 22), "out": (2, 4)},
                "dates": {"diamonds": 5, "minutes": (16, 24), "out": (1, 3)},
            },
            "t4": {
                "olive": {"diamonds": 4, "minutes": (12, 20), "out": (3, 7)},
                "soap": {"diamonds": 6, "minutes": (18, 28), "out": (3, 6)},
                "dates": {"diamonds": 7, "minutes": (18, 28), "out": (2, 5)},
                "keffiyeh": {"diamonds": 8, "minutes": (22, 34), "out": (1, 2)},
            },
            "t5": {
                "olive": {"diamonds": 6, "minutes": (14, 26), "out": (5, 10)},
                "soap": {"diamonds": 10, "minutes": (22, 36), "out": (4, 8)},
                "dates": {"diamonds": 10, "minutes": (22, 36), "out": (4, 8)},
                "keffiyeh": {"diamonds": 12, "minutes": (28, 45), "out": (2, 4)},
                "pottery": {"diamonds": 12, "minutes": (28, 45), "out": (2, 4)},
            },
        },
        "boost": {
            "t1": {"cost_per_minute": 1, "min_cost": 1},
            "t2": {"cost_per_minute": 1, "min_cost": 2},
            "t3": {"cost_per_minute": 2, "min_cost": 3},
            "t4": {"cost_per_minute": 2, "min_cost": 4},
            "t5": {"cost_per_minute": 3, "min_cost": 5},
        }
    }


def _tier_rank(tier):
    return {"t1": 1, "t2": 2, "t3": 3, "t4": 4, "t5": 5}.get(tier, 1)


def _get_facilities_config():
    raw = SystemConfig.get_value("farm_facilities_config_json", "")
    if raw:
        try:
            cfg = json.loads(raw)
            if isinstance(cfg, dict) and cfg.get("facilities"):
                return cfg
        except Exception:
            pass

    return {
        "facilities": {
            "olive_press": {
                "name": "معصرة زيتون",
                "farm_type": "olive",
                "rare_item_name": "زيت زيتون ممتاز",
                "base_rare_chance": 0.03,
                "daily_perk": {"unlock_level": 3, "cooldown_hours": 24, "qty": 1},
                "contract": {"unlock_level": 2},
                "stages": [
                    {"min_tier": "t1", "diamonds": 15, "time_multiplier": 0.92, "rare_bonus": 0.03},
                    {"min_tier": "t2", "diamonds": 35, "time_multiplier": 0.88, "rare_bonus": 0.05},
                    {"min_tier": "t3", "diamonds": 75, "time_multiplier": 0.84, "rare_bonus": 0.07},
                    {"min_tier": "t4", "diamonds": 140, "time_multiplier": 0.80, "rare_bonus": 0.10},
                ],
            },
            "zaatar_nursery": {
                "name": "مشتل زعتر",
                "farm_type": "zaatar",
                "rare_item_name": "زعتر جبلي فاخر",
                "base_rare_chance": 0.03,
                "daily_perk": {"unlock_level": 3, "cooldown_hours": 24, "qty": 1},
                "contract": {"unlock_level": 2},
                "stages": [
                    {"min_tier": "t1", "diamonds": 12, "time_multiplier": 0.92, "rare_bonus": 0.03},
                    {"min_tier": "t2", "diamonds": 30, "time_multiplier": 0.88, "rare_bonus": 0.05},
                    {"min_tier": "t3", "diamonds": 65, "time_multiplier": 0.84, "rare_bonus": 0.07},
                    {"min_tier": "t4", "diamonds": 120, "time_multiplier": 0.80, "rare_bonus": 0.10},
                ],
            },
            "soap_workshop": {
                "name": "ورشة صابون",
                "farm_type": "soap",
                "rare_item_name": "صابون نابلسي فاخر",
                "base_rare_chance": 0.02,
                "daily_perk": {"unlock_level": 3, "cooldown_hours": 24, "qty": 1},
                "contract": {"unlock_level": 2},
                "stages": [
                    {"min_tier": "t2", "diamonds": 20, "time_multiplier": 0.93, "rare_bonus": 0.03},
                    {"min_tier": "t3", "diamonds": 50, "time_multiplier": 0.88, "rare_bonus": 0.05},
                    {"min_tier": "t4", "diamonds": 110, "time_multiplier": 0.84, "rare_bonus": 0.07},
                    {"min_tier": "t5", "diamonds": 200, "time_multiplier": 0.80, "rare_bonus": 0.10},
                ],
            },
            "keffiyeh_workshop": {
                "name": "ورشة كوفية",
                "farm_type": "keffiyeh",
                "rare_item_name": "كوفية مطرزة",
                "base_rare_chance": 0.02,
                "daily_perk": {"unlock_level": 2, "cooldown_hours": 24, "qty": 1},
                "contract": {"unlock_level": 2},
                "stages": [
                    {"min_tier": "t4", "diamonds": 35, "time_multiplier": 0.92, "rare_bonus": 0.03},
                    {"min_tier": "t5", "diamonds": 90, "time_multiplier": 0.88, "rare_bonus": 0.06},
                    {"min_tier": "t5", "diamonds": 180, "time_multiplier": 0.84, "rare_bonus": 0.09},
                ],
            },
        }
    }


def _get_user_facility_level(user_id, facility_key):
    uf = UserFacility.query.filter_by(user_id=user_id, facility_key=facility_key).first()
    return int(uf.level) if uf and uf.level is not None else 0


def _facility_for_farm_type(cfg, farm_type):
    facilities = (cfg.get("facilities") or {})
    for key, meta in facilities.items():
        if meta.get("farm_type") == farm_type:
            return key, meta
    return None, None


def _facility_effects(meta, level):
    stages = list(meta.get("stages") or [])
    lvl = max(0, min(int(level), len(stages)))
    time_mul = 1.0
    rare_bonus = 0.0
    for i in range(lvl):
        st = stages[i] or {}
        try:
            time_mul *= float(st.get("time_multiplier") or 1.0)
        except Exception:
            pass
        try:
            rare_bonus += float(st.get("rare_bonus") or 0.0)
        except Exception:
            pass
    base_rare = float(meta.get("base_rare_chance") or 0.0)
    return time_mul, min(0.95, base_rare + rare_bonus)


def _add_user_item(user_id, item, qty):
    ui = UserItem.query.filter_by(user_id=user_id, item_id=item.id).first()
    if ui:
        ui.quantity += qty
    else:
        ui = UserItem(user_id=user_id, item_id=item.id, quantity=qty)
        db.session.add(ui)
    return ui


@bp.route('/')
@login_required
def index():
    cfg = _get_farm_config()
    fcfg = _get_facilities_config()
    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)

    running = FarmJob.query.filter_by(user_id=current_user.id, status='running').order_by(FarmJob.ends_at.desc()).first()

    catalog = []
    tiers_cfg = cfg.get("tiers") or {}
    requirements_cfg = cfg.get("requirements") or {}

    for farm_type, meta in (cfg.get("products") or {}).items():
        item = Item.query.filter_by(name=meta.get("item_name")).first()
        if not item:
            continue

        min_tier = None
        for t in ["t1", "t2", "t3", "t4", "t5"]:
            if farm_type in (tiers_cfg.get(t) or {}):
                min_tier = t
                break

        req = dict(requirements_cfg.get(farm_type) or {})
        if min_tier:
            req.setdefault("min_tier", min_tier)

        chk = check_requirements(current_user, req)
        is_ok = chk["ok"]
        reasons = chk["reasons"]
        pricing = (tiers_cfg.get(tier) or {}).get(farm_type)

        unlocked = bool(is_ok and pricing)
        locked_reason = reasons[0] if reasons else None
        if not pricing and min_tier and _tier_rank(tier) < _tier_rank(min_tier):
            locked_reason = _('طور نفسك لفتحها.')
        elif not pricing and min_tier:
            locked_reason = locked_reason or _('طور نفسك لفتحها.')

        hint_url = None
        if chk.get("hint_key") == "gym":
            hint_url = url_for('gym.index')
        elif chk.get("hint_key") == "daily_tasks":
            hint_url = url_for('main.daily_tasks')

        catalog.append({
            "farm_type": farm_type,
            "item": item,
            "pricing": pricing,
            "unlocked": unlocked,
            "min_tier": min_tier,
            "locked_reason": locked_reason,
            "reasons": reasons,
            "hint_text": chk.get("hint_text"),
            "hint_url": hint_url,
        })

    if not catalog and not running and cfg.get("products"):
        # If catalog is empty but products exist in config, it means Item query failed for all.
        # This suggests a database sync issue.
        flash(_("تحذير: لم يتم العثور على المنتجات في قاعدة البيانات. يرجى مراجعة الإدارة."), "warning")

    facilities = []
    contract_source = None
    contract_source_level = 0
    for key, meta in sorted((fcfg.get("facilities") or {}).items(), key=lambda x: x[0]):
        name = meta.get("name") or key
        current_level = _get_user_facility_level(current_user.id, key)
        stages = list(meta.get("stages") or [])
        max_level = len(stages)

        next_stage = stages[current_level] if 0 <= current_level < len(stages) else None
        can_upgrade = False
        next_cost = None
        req_tier = None
        if next_stage:
            next_cost = int(next_stage.get("diamonds") or 0)
            req_tier = next_stage.get("min_tier") or "t1"
            can_upgrade = _tier_rank(tier) >= _tier_rank(req_tier)

        time_mul, rare_chance = _facility_effects(meta, current_level)
        facilities.append({
            "key": key,
            "name": name,
            "level": current_level,
            "max_level": max_level,
            "next_cost": next_cost,
            "req_tier": req_tier,
            "can_upgrade": can_upgrade,
            "time_mul": time_mul,
            "rare_chance": rare_chance,
            "daily_perk": meta.get("daily_perk"),
            "contract": meta.get("contract"),
        })

        c = meta.get("contract") or {}
        unlock_lvl = int(c.get("unlock_level") or 0)
        if current_level >= unlock_lvl and current_level > contract_source_level:
            contract_source = key
            contract_source_level = current_level

    locations = Location.query.order_by(Location.id.asc()).all()
    active_contract = FarmSupplyContract.query.filter_by(user_id=current_user.id, status='active').order_by(FarmSupplyContract.ends_at.desc()).first()
    if active_contract and not active_contract.is_active:
        active_contract.status = 'expired'
        db.session.add(active_contract)
        db.session.commit()
        active_contract = None

    active_contract_location = None
    if active_contract:
        try:
            active_contract_location = db.session.get(Location, active_contract.location_id)
        except Exception:
            active_contract_location = None

    tier_n = _tier_rank(tier)
    contract_duration_minutes = int(SystemConfig.get_value("farm_contract_duration_minutes", "60") or 60)
    contract_base_cost = int(SystemConfig.get_value("farm_contract_base_cost", "25") or 25)
    contract_cost_per_tier = int(SystemConfig.get_value("farm_contract_cost_per_tier", "10") or 10)
    contract_base_bonus = float(SystemConfig.get_value("farm_contract_base_bonus", "0.10") or 0.10)
    contract_bonus_per_facility_level = float(SystemConfig.get_value("farm_contract_bonus_per_facility_level", "0.03") or 0.03)
    contract_max_bonus = float(SystemConfig.get_value("farm_contract_max_bonus", "0.25") or 0.25)

    contract_offer = None
    if contract_source:
        bonus = min(contract_max_bonus, contract_base_bonus + contract_bonus_per_facility_level * max(0, contract_source_level - 1) + 0.01 * max(0, tier_n - 1))
        cost = max(1, contract_base_cost + contract_cost_per_tier * max(0, tier_n - 1))
        contract_offer = {
            "facility_key": contract_source,
            "facility_level": contract_source_level,
            "duration_minutes": contract_duration_minutes,
            "bonus_percent": bonus,
            "cost_diamonds": cost,
        }

    return render_template(
        "farm.html",
        user=current_user,
        tier=tier,
        running=running,
        catalog=catalog,
        facilities=facilities,
        locations=locations,
        active_contract=active_contract,
        active_contract_location=active_contract_location,
        contract_offer=contract_offer,
        now=_now_utc()
    )


@bp.route('/facility/upgrade/<facility_key>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def upgrade_facility(facility_key):
    # Lock user to prevent race conditions on facility upgrades
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    fcfg = _get_facilities_config()
    meta = (fcfg.get("facilities") or {}).get(facility_key)
    if not meta:
        flash(_('مرفق غير موجود.'), 'danger')
        return redirect(url_for('farm.index'))

    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)
    current_level = _get_user_facility_level(current_user.id, facility_key)
    stages = list(meta.get("stages") or [])
    if current_level >= len(stages):
        flash(_('تم تطوير هذا المرفق بالكامل.'), 'info')
        return redirect(url_for('farm.index'))

    stage = stages[current_level] or {}
    req_tier = stage.get("min_tier") or "t1"
    if _tier_rank(tier) < _tier_rank(req_tier):
        flash(_('رتبتك لا تسمح بهذا التطوير بعد.'), 'warning')
        return redirect(url_for('farm.index'))

    cost = int(stage.get("diamonds") or 0)
    if cost <= 0:
        flash(_('تكلفة غير صالحة.'), 'danger')
        return redirect(url_for('farm.index'))

    if current_user.diamonds < cost:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=cost), 'danger')
        return redirect(url_for('farm.index'))

    # Atomic deduction via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'diamonds': -cost}, 'farm_facility_upgrade', auto_commit=False, expected_version=None):
        flash(_('ليس لديك ما يكفي من الماس!'), 'danger')
        return redirect(url_for('farm.index'))

    uf = UserFacility.query.filter_by(user_id=current_user.id, facility_key=facility_key).first()
    if not uf:
        uf = UserFacility(user_id=current_user.id, facility_key=facility_key, level=current_level + 1)
        db.session.add(uf)
    else:
        uf.level = current_level + 1
        uf.updated_at = datetime.now(timezone.utc)
        db.session.add(uf)

    db.session.commit()
    flash(_('تم تطوير %(name)s للمستوى %(lvl)s.', name=meta.get("name") or facility_key, lvl=current_level + 1), 'success')
    return redirect(url_for('farm.index'))


@bp.route('/facility/perk/<facility_key>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def use_facility_perk(facility_key):
    # Lock UserFacility row
    uf = db.session.query(UserFacility).filter_by(user_id=current_user.id, facility_key=facility_key).with_for_update().first()

    fcfg = _get_facilities_config()
    meta = (fcfg.get("facilities") or {}).get(facility_key)
    if not meta:
        flash(_('مرفق غير موجود.'), 'danger')
        return redirect(url_for('farm.index'))

    perk = meta.get("daily_perk") or {}
    unlock_level = int(perk.get("unlock_level") or 0)
    cooldown_hours = int(perk.get("cooldown_hours") or 24)
    qty = int(perk.get("qty") or 1)

    level = int(uf.level) if uf else 0
    if level < unlock_level:
        flash(_('هذه الميزة غير متاحة بعد.'), 'warning')
        return redirect(url_for('farm.index'))

    if not uf:
        # Should be covered by level check (0 < unlock_level usually), but safe to create if logic allows
        uf = UserFacility(user_id=current_user.id, facility_key=facility_key, level=level)
        db.session.add(uf)
        db.session.flush()

    now = datetime.now(timezone.utc)
    last = uf.last_perk_at
    if last and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last and now - last < timedelta(hours=cooldown_hours):
        remaining = timedelta(hours=cooldown_hours) - (now - last)
        minutes = int(remaining.total_seconds() // 60)
        flash(_('لسه بدري! ارجع بعد %(min)s دقيقة.', min=minutes), 'warning')
        return redirect(url_for('farm.index'))

    rare_item_name = meta.get("rare_item_name")
    item = Item.query.filter_by(name=rare_item_name).first() if rare_item_name else None
    if not item:
        flash(_('عنصر المكافأة غير موجود.'), 'danger')
        return redirect(url_for('farm.index'))

    _add_user_item(current_user.id, item, qty)
    uf.last_perk_at = now.replace(tzinfo=None)
    uf.updated_at = now
    db.session.add(uf)
    db.session.commit()

    flash(_('تم تفعيل ميزة %(name)s واستلام %(qty)s × %(item)s.', name=meta.get("name") or facility_key, qty=qty, item=item.name), 'success')
    return redirect(url_for('farm.index'))


@bp.route('/contract/buy', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def buy_contract():
    # Lock user to prevent race conditions on contract purchase
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    location_id = request.form.get("location_id", type=int)
    if not location_id:
        flash(_('اختر المدينة.'), 'warning')
        return redirect(url_for('farm.index'))

    location = db.session.get(Location, location_id)
    if not location:
        flash(_('المدينة غير موجودة.'), 'danger')
        return redirect(url_for('farm.index'))

    cfg = _get_facilities_config()
    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)
    tier_n = _tier_rank(tier)

    best_key = None
    best_level = 0
    for key, meta in (cfg.get("facilities") or {}).items():
        c = meta.get("contract") or {}
        unlock_lvl = int(c.get("unlock_level") or 0)
        l = _get_user_facility_level(current_user.id, key)
        if l >= unlock_lvl and l > best_level:
            best_key = key
            best_level = l

    if not best_key:
        flash(_('طور مرافقك لفتح عقد التوريد.'), 'warning')
        return redirect(url_for('farm.index'))

    duration_minutes = int(SystemConfig.get_value("farm_contract_duration_minutes", "60") or 60)
    base_cost = int(SystemConfig.get_value("farm_contract_base_cost", "25") or 25)
    cost_per_tier = int(SystemConfig.get_value("farm_contract_cost_per_tier", "10") or 10)
    base_bonus = float(SystemConfig.get_value("farm_contract_base_bonus", "0.10") or 0.10)
    bonus_per_level = float(SystemConfig.get_value("farm_contract_bonus_per_facility_level", "0.03") or 0.03)
    max_bonus = float(SystemConfig.get_value("farm_contract_max_bonus", "0.25") or 0.25)

    bonus = min(max_bonus, base_bonus + bonus_per_level * max(0, best_level - 1) + 0.01 * max(0, tier_n - 1))
    cost = max(1, base_cost + cost_per_tier * max(0, tier_n - 1))

    if current_user.diamonds < cost:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=cost), 'danger')
        return redirect(url_for('farm.index'))

    now = datetime.now(timezone.utc)
    active = FarmSupplyContract.query.filter_by(user_id=current_user.id, status='active', location_id=location_id).order_by(FarmSupplyContract.ends_at.desc()).first()
    if active and not active.is_active:
        active.status = 'expired'
        db.session.add(active)
        db.session.commit()
        active = None

    # Atomic Deduction using ResourceService
    success = ResourceService.modify_resources(
        user_id=current_user.id,
        changes={'diamonds': -cost},
        reason='farm_buy_contract',
        auto_commit=False,
        expected_version=current_user.version
    )

    if not success:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=cost), 'danger')
        return redirect(url_for('farm.index'))

    if active:
        ends = active.ends_at
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if ends and ends > now:
            active.ends_at = (ends + timedelta(minutes=duration_minutes)).replace(tzinfo=None)
        else:
            active.ends_at = (now + timedelta(minutes=duration_minutes)).replace(tzinfo=None)
        active.bonus_percent = bonus
        db.session.add(active)
    else:
        contract = FarmSupplyContract(
            user_id=current_user.id,
            location_id=location_id,
            bonus_percent=bonus,
            status='active',
            created_at=now,
            ends_at=(now + timedelta(minutes=duration_minutes)).replace(tzinfo=None),
        )
        db.session.add(contract)

    db.session.commit()

    flash(_('تم تفعيل عقد توريد في %(city)s لمدة %(min)s دقيقة. زيادة بيع: %(pct)s%%', city=location.name, min=duration_minutes, pct=int(bonus * 100)), 'success')
    return redirect(url_for('farm.index'))


@bp.route('/start', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def start():
    cfg = _get_farm_config()
    fcfg = _get_facilities_config()

    max_parallel = 1
    try:
        max_parallel = int(cfg.get("max_parallel_jobs") or 1)
    except Exception:
        max_parallel = 1
    if FarmJob.query.filter_by(user_id=current_user.id, status='running').count() >= max_parallel:
        flash(_('لديك عملية مزرعة جارية بالفعل.'), 'warning')
        return redirect(url_for('farm.index'))

    farm_type = (request.form.get("farm_type") or "").strip()

    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)

    tier_cfg = (cfg.get("tiers") or {}).get(tier, {})
    if farm_type not in tier_cfg:
        flash(_('هذا الخيار غير متاح لرتبتك حالياً.'), 'warning')
        return redirect(url_for('farm.index'))

    req = dict((cfg.get("requirements") or {}).get(farm_type) or {})
    min_tier = None
    for t in ["t1", "t2", "t3", "t4", "t5"]:
        if farm_type in ((cfg.get("tiers") or {}).get(t) or {}):
            min_tier = t
            break
    if min_tier:
        req.setdefault("min_tier", min_tier)

    chk = check_requirements(current_user, req)
    if not chk["ok"]:
        msg = chk["reason"] or _('طور نفسك لفتحها.')
        if chk.get("hint_text"):
            msg = f"{msg} — {chk.get('hint_text')}"
        flash(_('طور نفسك لفتحها: %(reason)s', reason=msg), 'warning')
        return redirect(url_for('farm.index'))

    product_meta = (cfg.get("products") or {}).get(farm_type) or {}
    item_name = product_meta.get("item_name")
    item = Item.query.filter_by(name=item_name).first()
    if not item:
        flash(_('عنصر الإنتاج غير موجود.'), 'danger')
        return redirect(url_for('farm.index'))

    facility_key, facility_meta = _facility_for_farm_type(fcfg, farm_type)
    facility_level = _get_user_facility_level(current_user.id, facility_key) if facility_key else 0
    time_mul, rare_chance = _facility_effects(facility_meta, facility_level) if facility_meta else (1.0, 0.0)

    pricing = tier_cfg[farm_type]
    diamonds_cost = int(pricing.get("diamonds") or 1)
    min_m, max_m = pricing.get("minutes") or (10, 20)
    out_min, out_max = pricing.get("out") or (1, 1)

    if current_user.diamonds < diamonds_cost:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=diamonds_cost), 'danger')
        return redirect(url_for('farm.index'))

    # Atomic deduction via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'diamonds': -diamonds_cost}, 'farm_start_job', auto_commit=False, expected_version=None):
        flash(_('ليس لديك ما يكفي من الماس!'), 'danger')
        return redirect(url_for('farm.index'))

    minutes = _weighted_int(int(min_m), int(max_m), w_low=0.65, w_mid=0.3)
    output_amount = _weighted_int(int(out_min), int(out_max), w_low=0.7, w_mid=0.25)

    if time_mul and time_mul != 1.0:
        minutes = max(1, int(round(minutes * float(time_mul))))

    is_rare = False
    if rare_chance and random.random() < float(rare_chance):
        is_rare = True
        rare_item_name = (facility_meta or {}).get("rare_item_name")
        if rare_item_name:
            rare_item = Item.query.filter_by(name=rare_item_name).first()
            if rare_item:
                item = rare_item
                output_amount = max(1, int(round(output_amount * 1.15)))

    ends_at = (_now_utc() + timedelta(minutes=minutes)).replace(tzinfo=None)
    job = FarmJob(
        user_id=current_user.id,
        farm_type=farm_type,
        output_item_id=item.id,
        output_amount=output_amount,
        diamonds_used=diamonds_cost,
        status='running',
        started_at=_now_utc().replace(tzinfo=None),
        ends_at=ends_at,
    )
    db.session.add(job)
    db.session.commit()

    if is_rare:
        flash(_('إنتاج نادر! راجع المزرعة بعد %(min)s دقيقة.', min=minutes), 'success')
    else:
        flash(_('بدأت العملية! راجع المزرعة بعد %(min)s دقيقة.', min=minutes), 'success')
    return redirect(url_for('farm.index'))


@bp.route('/claim/<int:job_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def claim(job_id):
    job = FarmJob.query.filter_by(id=job_id, user_id=current_user.id).first()
    if not job or job.status != 'running':
        flash(_('هذه العملية غير موجودة.'), 'danger')
        return redirect(url_for('farm.index'))

    if not job.is_ready:
        flash(_('لسه بدري! العملية لم تنته بعد.'), 'warning')
        return redirect(url_for('farm.index'))

    item = job.output_item or (db.session.get(Item, job.output_item_id) if job.output_item_id else None)
    if not item:
        flash(_('عنصر الإنتاج غير موجود.'), 'danger')
        return redirect(url_for('farm.index'))

    _add_user_item(current_user.id, item, int(job.output_amount))
    job.status = 'claimed'
    job.claimed_at = _now_utc().replace(tzinfo=None)
    db.session.add(job)
    db.session.commit()

    flash(_('تم استلام الإنتاج: %(qty)s × %(name)s.', qty=job.output_amount, name=item.name), 'success')
    return redirect(url_for('farm.index'))


@bp.route('/boost/<int:job_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def boost(job_id):
    # Lock job row to prevent double boosting
    job = FarmJob.query.filter_by(id=job_id, user_id=current_user.id).with_for_update().first()
    if not job or job.status != 'running':
        flash(_('هذه العملية غير موجودة.'), 'danger')
        return redirect(url_for('farm.index'))

    if job.is_ready:
        flash(_('العملية انتهت بالفعل.'), 'info')
        return redirect(url_for('farm.index'))

    cfg = _get_farm_config()
    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)
    boost_cfg = (cfg.get("boost") or {}).get(tier) or {}
    cost_per_min = int(boost_cfg.get("cost_per_minute") or 1)
    min_cost = int(boost_cfg.get("min_cost") or 1)

    now = _now_utc()
    ends = job.ends_at
    if ends and ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    remaining_seconds = max(1, int((ends - now).total_seconds()))
    remaining_minutes = max(1, (remaining_seconds + 59) // 60)
    diamonds_cost = max(min_cost, int(remaining_minutes * cost_per_min))

    if current_user.diamonds < diamonds_cost:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=diamonds_cost), 'danger')
        return redirect(url_for('farm.index'))

    # Atomic deduction via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'diamonds': -diamonds_cost}, 'farm_boost_job', auto_commit=False, expected_version=None):
        flash(_('ليس لديك ما يكفي من الماس!'), 'danger')
        return redirect(url_for('farm.index'))

    job.ends_at = now.replace(tzinfo=None)
    db.session.add(job)
    db.session.commit()

    flash(_('تم إنهاء العملية فوراً مقابل %(cost)s ماسة.', cost=diamonds_cost), 'success')
    return redirect(url_for('farm.index'))
