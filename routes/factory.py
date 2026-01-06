from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from datetime import datetime, timezone, timedelta
import random
import json

from extensions import db, limiter
from sqlalchemy import select
from models import Item, UserItem, FactoryJob, SystemConfig, User, MoneySinkLog
from services.requirements import check_requirements
from services.resource_service import ResourceService


bp = Blueprint('factory', __name__, url_prefix='/factory')


def _now_utc():
    return datetime.now(timezone.utc)


def _get_material_item(name):
    return Item.query.filter_by(name=name).first()


def _get_user_item_qty(user_id, item_id):
    ui = UserItem.query.filter_by(user_id=user_id, item_id=item_id).first()
    return ui.quantity if ui else 0


def _add_user_item(user_id, item, qty):
    # Atomic update for existing items
    result = UserItem.query.filter_by(user_id=user_id, item_id=item.id).update({
        UserItem.quantity: UserItem.quantity + qty
    }, synchronize_session=False)
    
    if result == 0:
        # Item doesn't exist, create it
        # Handle race condition using nested transaction (savepoint)
        try:
            with db.session.begin_nested():
                ui = UserItem(user_id=user_id, item_id=item.id, quantity=qty)
                db.session.add(ui)
            return ui
        except Exception:
            # Race condition: someone inserted it just now.
            # Fallback to update
            UserItem.query.filter_by(user_id=user_id, item_id=item.id).update({
                UserItem.quantity: UserItem.quantity + qty
            }, synchronize_session=False)
            return None
    
    return None


def _consume_user_item(user_id, item_id, qty):
    # Atomic consumption using update with criteria
    result = UserItem.query.filter(
        UserItem.user_id == user_id,
        UserItem.item_id == item_id,
        UserItem.quantity >= qty
    ).update({
        UserItem.quantity: UserItem.quantity - qty
    }, synchronize_session=False)
    
    if result > 0:
        # Cleanup empty items if needed, though 0 quantity is often fine to keep
        # But to match previous logic (delete if <= 0):
        # We can't easily delete in the same query. 
        # We can do a second query to clean up, or just leave it at 0.
        # Previous logic:
        # if ui.quantity <= 0: db.session.delete(ui)
        
        # Let's clean up zero quantity items
        UserItem.query.filter(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id,
            UserItem.quantity <= 0
        ).delete(synchronize_session=False)
        return True
        
    return False


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


def _get_factory_config():
    raw = SystemConfig.get_value("factory_config_json", "")
    if raw:
        try:
            cfg = json.loads(raw)
            if isinstance(cfg, dict) and cfg.get("tiers"):
                return cfg
        except Exception:
            pass

    return {
        "metal_item_name": "سبائك معدن",
        "explosive_item_name": "متفجرات محلية",
        "max_parallel_jobs": 1,
        "smelt_sources": [
            ("هاتف مسروق", 1.0),
            ("دراجة هوائية مسروقة", 1.2),
            ("مجوهرات مسروقة", 1.4),
            ("ساعة يد فاخرة مسروقة", 1.6),
            ("آثار مسروقة", 1.8),
            ("سلاح مهرب (M16)", 2.0),
        ],
        "tiers": {
            "t1": {"bullet_diamonds": 0, "bullet_metal": 2, "bullet_out": (10, 15), "bullet_minutes": (5, 10),
                   "expl_diamonds": 3, "expl_metal": 3, "expl_out": (1, 1), "expl_minutes": (10, 16)},
            "t2": {"bullet_diamonds": 0, "bullet_metal": 4, "bullet_out": (20, 30), "bullet_minutes": (8, 14),
                   "expl_diamonds": 5, "expl_metal": 4, "expl_out": (1, 2), "expl_minutes": (12, 18)},
            "t3": {"bullet_diamonds": 0, "bullet_metal": 6, "bullet_out": (35, 50), "bullet_minutes": (12, 18),
                   "expl_diamonds": 7, "expl_metal": 5, "expl_out": (2, 3), "expl_minutes": (15, 22)},
            "t4": {"bullet_diamonds": 0, "bullet_metal": 8, "bullet_out": (55, 80), "bullet_minutes": (15, 24),
                   "expl_diamonds": 10, "expl_metal": 7, "expl_out": (3, 5), "expl_minutes": (18, 28)},
            "t5": {"bullet_diamonds": 0, "bullet_metal": 10, "bullet_out": (85, 120), "bullet_minutes": (20, 30),
                   "expl_diamonds": 14, "expl_metal": 9, "expl_out": (5, 8), "expl_minutes": (22, 35)},
        },
        "requirements": {
            "bullets": {"min_tier": "t1", "min_intelligence": 0},
            "explosives": {"min_tier": "t2", "min_intelligence": 18}
        },
        "boost": {
            "t1": {"cost_per_minute": 1, "min_cost": 1},
            "t2": {"cost_per_minute": 1, "min_cost": 2},
            "t3": {"cost_per_minute": 2, "min_cost": 3},
            "t4": {"cost_per_minute": 2, "min_cost": 4},
            "t5": {"cost_per_minute": 3, "min_cost": 5}
        }
    }


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


def _tier_rank(tier):
    return {"t1": 1, "t2": 2, "t3": 3, "t4": 4, "t5": 5}.get(tier, 1)


def _check_requirements(user, req, tier):
    reasons = []
    min_tier = req.get("min_tier")
    if min_tier and _tier_rank(tier) < _tier_rank(min_tier):
        reasons.append(_('تحتاج رتبة أعلى (%(tier)s).', tier=min_tier))

    min_intel = req.get("min_intelligence")
    if min_intel is not None:
        try:
            min_intel = int(min_intel)
        except Exception:
            min_intel = None
    if min_intel is not None and int(user.intelligence) < min_intel:
        reasons.append(_('تحتاج ذكاء %(n)s.', n=min_intel))

    return (len(reasons) == 0), reasons


@bp.route('/')
@login_required
def index():
    cfg = _get_factory_config()
    metal_item = _get_material_item(cfg["metal_item_name"])
    explosive_item = _get_material_item(cfg["explosive_item_name"])

    metal_qty = _get_user_item_qty(current_user.id, metal_item.id) if metal_item else 0
    explosive_qty = _get_user_item_qty(current_user.id, explosive_item.id) if explosive_item else 0

    active_job = FactoryJob.query.filter_by(user_id=current_user.id, status='running').order_by(FactoryJob.ends_at.desc()).first()

    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)
    pricing = cfg["tiers"][tier]

    reqs = cfg.get("requirements") or {}
    job_cards = []
    for jt in ["bullets", "explosives"]:
        chk = check_requirements(current_user, reqs.get(jt) or {})
        ok = chk["ok"]
        reasons = chk["reasons"]
        hint_url = None
        if chk.get("hint_key") == "gym":
            hint_url = url_for('gym.index')
        elif chk.get("hint_key") == "daily_tasks":
            hint_url = url_for('main.daily_tasks')
        job_cards.append({
            "job_type": jt,
            "unlocked": bool(ok),
            "locked_reason": reasons[0] if reasons else None,
            "hint_text": chk.get("hint_text"),
            "hint_url": hint_url,
        })

    smeltable = []
    for name, weight in cfg["smelt_sources"]:
        item = Item.query.filter_by(name=name).first()
        if not item:
            continue
        qty = _get_user_item_qty(current_user.id, item.id)
        if qty > 0:
            smeltable.append({"item": item, "qty": qty, "weight": weight})

    return render_template(
        'factory.html',
        user=current_user,
        metal_item=metal_item,
        explosive_item=explosive_item,
        metal_qty=metal_qty,
        explosive_qty=explosive_qty,
        active_job=active_job,
        tier=tier,
        pricing=pricing,
        job_cards=job_cards,
        smeltable=smeltable,
        now=_now_utc(),
    )


@bp.route('/smelt', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def smelt():
    # Status Check
    now = _now_utc()
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
             flash(_('أنت في السجن ولا يمكنك استخدام المصنع!'), 'danger')
             return redirect(url_for('jail.index'))
             
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
             flash(_('أنت في المستشفى ولا يمكنك استخدام المصنع!'), 'danger')
             return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
             flash(_('أنت تتدرب ولا يمكنك استخدام المصنع!'), 'danger')
             return redirect(url_for('gym.index'))

    cfg = _get_factory_config()
    metal_item = _get_material_item(cfg["metal_item_name"])
    if not metal_item:
        flash(_('عنصر المعدن غير موجود في قاعدة البيانات.'), 'danger')
        return redirect(url_for('factory.index'))

    item_id = request.form.get('item_id', type=int)
    if not item_id:
        flash(_('عنصر غير صالح.'), 'danger')
        return redirect(url_for('factory.index'))

    src_item = db.session.get(Item, item_id)
    if not src_item:
        flash(_('العنصر غير موجود.'), 'danger')
        return redirect(url_for('factory.index'))

    allowed_names = {name for name, _ in cfg["smelt_sources"]}
    if src_item.name not in allowed_names:
        flash(_('لا يمكنك صهر هذا العنصر.'), 'warning')
        return redirect(url_for('factory.index'))

    smelt_cost = 5000
    if current_user.money < smelt_cost:
        flash(_('لا تملك كاش كافي للصهر! التكلفة: %(cost)s$', cost=smelt_cost), 'danger')
        return redirect(url_for('factory.index'))

    # Atomic deduction via ResourceService (Locks User)
    if not ResourceService.modify_resources(current_user.id, {'money': -smelt_cost}, 'factory_smelt_cost', auto_commit=False, expected_version=None):
        flash(_('لا تملك كاش كافي للصهر!'), 'danger')
        return redirect(url_for('factory.index'))

    # Consume Item (Locks UserItem) - Consistent Order: User -> UserItem
    if not _consume_user_item(current_user.id, src_item.id, 1):
        db.session.rollback() # Refund money
        flash(_('لا تملك هذا العنصر.'), 'danger')
        return redirect(url_for('factory.index'))

    sink_log = MoneySinkLog(
        user_id=current_user.id,
        sink_type='factory_smelt_cost',
        amount=smelt_cost,
        details=f"Smelted {src_item.name}"
    )
    db.session.add(sink_log)


    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)
    weights = {n: float(w) for n, w in cfg.get("smelt_sources", [])}
    base = max(1, int(round(weights.get(src_item.name, 1.0))))
    if tier in {"t4", "t5"}:
        base += 1
    elif tier in {"t2", "t3"}:
        base += 0

    bonus_roll = random.random()
    ingots = base
    if bonus_roll < 0.05:
        ingots += 3
    elif bonus_roll < 0.25:
        ingots += 2
    elif bonus_roll < 0.6:
        ingots += 1

    _add_user_item(current_user.id, metal_item, ingots)
    db.session.commit()

    flash(_('تم صهر %(name)s وتحويله إلى %(qty)s سبائك معدن.', name=src_item.name, qty=ingots), 'success')
    return redirect(url_for('factory.index'))


@bp.route('/start', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def start_job():
    cfg = _get_factory_config()
    metal_item = _get_material_item(cfg["metal_item_name"])
    explosive_item = _get_material_item(cfg["explosive_item_name"])
    if not metal_item or not explosive_item:
        flash(_('عناصر المصنع غير مكتملة في قاعدة البيانات.'), 'danger')
        return redirect(url_for('factory.index'))

    max_parallel = 1
    try:
        max_parallel = int(cfg.get("max_parallel_jobs") or 1)
    except Exception:
        max_parallel = 1
    running_count = FactoryJob.query.filter_by(user_id=current_user.id, status='running').count()
    if running_count >= max_parallel:
        flash(_('لديك عملية تصنيع جارية بالفعل.'), 'warning')
        return redirect(url_for('factory.index'))

    job_type = (request.form.get('job_type') or '').strip()
    if job_type not in {'bullets', 'explosives'}:
        flash(_('نوع عملية غير صالح.'), 'danger')
        return redirect(url_for('factory.index'))

    lvl = _effective_level(current_user)
    tier = _tier_for_level(lvl)
    pricing = cfg["tiers"][tier]

    reqs = cfg.get("requirements") or {}
    chk = check_requirements(current_user, reqs.get(job_type) or {})
    if not chk["ok"]:
        msg = chk["reason"] or _('طور نفسك لفتحها.')
        if chk.get("hint_text"):
            msg = f"{msg} — {chk.get('hint_text')}"
        flash(_('طور نفسك لفتحها: %(reason)s', reason=msg), 'warning')
        return redirect(url_for('factory.index'))

    if job_type == 'bullets':
        diamonds_cost = int(pricing["bullet_diamonds"])
        metal_cost = int(pricing["bullet_metal"])
        out_min, out_max = pricing["bullet_out"]
        min_m, max_m = pricing["bullet_minutes"]
    else:
        diamonds_cost = int(pricing["expl_diamonds"])
        metal_cost = int(pricing["expl_metal"])
        out_min, out_max = pricing["expl_out"]
        min_m, max_m = pricing["expl_minutes"]

    if current_user.diamonds < diamonds_cost:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=diamonds_cost), 'danger')
        return redirect(url_for('factory.index'))

    if _get_user_item_qty(current_user.id, metal_item.id) < metal_cost:
        flash(_('لا تملك سبائك معدن كافية للتصنيع.'), 'danger')
        return redirect(url_for('factory.index'))

    # Atomic deduction for diamonds via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'diamonds': -diamonds_cost}, 'factory_start_job', auto_commit=False, expected_version=None):
        flash(_('ليس لديك ما يكفي من الماس!'), 'danger')
        return redirect(url_for('factory.index'))

    # Consume items after ensuring diamonds are deducted
    if not _consume_user_item(current_user.id, metal_item.id, metal_cost):
        # Rollback transaction
        db.session.rollback()
        flash(_('لا تملك سبائك معدن كافية للتصنيع.'), 'danger')
        return redirect(url_for('factory.index'))

    minutes = _weighted_int(int(min_m), int(max_m), w_low=0.6, w_mid=0.3)
    output_amount = _weighted_int(int(out_min), int(out_max), w_low=0.7, w_mid=0.25)
    ends_at = (_now_utc() + timedelta(minutes=minutes)).replace(tzinfo=None)

    job = FactoryJob(
        user_id=current_user.id,
        job_type=job_type,
        metal_used=metal_cost,
        diamonds_used=diamonds_cost,
        output_amount=output_amount,
        status='running',
        started_at=_now_utc().replace(tzinfo=None),
        ends_at=ends_at,
    )
    db.session.add(job)
    db.session.commit()

    flash(_('بدأ التصنيع! راجع المصنع بعد %(min)s دقيقة.', min=minutes), 'success')
    return redirect(url_for('factory.index'))


@bp.route('/claim/<int:job_id>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def claim(job_id):
    cfg = _get_factory_config()
    explosive_item = _get_material_item(cfg["explosive_item_name"])

    # Lock User first to prevent deadlock (User -> Job)
    db.session.execute(select(User).where(User.id == current_user.id).with_for_update()).scalar_one()

    # Lock the job row to prevent double claiming
    job = FactoryJob.query.filter_by(id=job_id, user_id=current_user.id).with_for_update().first()
    if not job or job.status != 'running':
        flash(_('هذه العملية غير موجودة.'), 'danger')
        return redirect(url_for('factory.index'))

    if not job.is_ready:
        flash(_('لسه بدري! العملية لم تنته بعد.'), 'warning')
        return redirect(url_for('factory.index'))

    if job.job_type == 'bullets':
        if not ResourceService.modify_resources(current_user.id, {'bullets': int(job.output_amount)}, 'factory_claim_bullets', auto_commit=False, expected_version=None):
            flash(_('حدث خطأ أثناء استلام الموارد. حاول مرة أخرى.'), 'danger')
            return redirect(url_for('factory.index'))
    else:
        if not explosive_item:
            flash(_('عنصر المتفجرات غير موجود.'), 'danger')
            return redirect(url_for('factory.index'))
        _add_user_item(current_user.id, explosive_item, int(job.output_amount))

    job.status = 'claimed'
    job.claimed_at = _now_utc().replace(tzinfo=None)
    db.session.add(job)
    db.session.commit()

    flash(_('تم استلام الإنتاج بنجاح.'), 'success')
    return redirect(url_for('factory.index'))


@bp.route('/boost/<int:job_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def boost(job_id):
    # Status Check
    now = _now_utc()
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
             flash(_('أنت في السجن ولا يمكنك استخدام المصنع!'), 'danger')
             return redirect(url_for('jail.index'))
             
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
             flash(_('أنت في المستشفى ولا يمكنك استخدام المصنع!'), 'danger')
             return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
             flash(_('أنت تتدرب ولا يمكنك استخدام المصنع!'), 'danger')
             return redirect(url_for('gym.index'))

    # Lock User first
    db.session.execute(select(User).where(User.id == current_user.id).with_for_update()).scalar_one()

    # Lock job
    job = FactoryJob.query.filter_by(id=job_id, user_id=current_user.id).with_for_update().first()
    if not job or job.status != 'running':
        flash(_('هذه العملية غير موجودة.'), 'danger')
        return redirect(url_for('factory.index'))

    if job.is_ready:
        flash(_('العملية انتهت بالفعل.'), 'info')
        return redirect(url_for('factory.index'))

    mode = (request.form.get('mode') or 'finish').strip()
    if mode not in {"finish"}:
        mode = "finish"

    cfg = _get_factory_config()
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
        return redirect(url_for('factory.index'))

    # Atomic deduction via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'diamonds': -diamonds_cost}, 'factory_boost_job', auto_commit=False, expected_version=None):
        flash(_('ليس لديك ما يكفي من الماس!'), 'danger')
        return redirect(url_for('factory.index'))

    job.ends_at = now.replace(tzinfo=None)
    db.session.add(job)
    db.session.commit()

    flash(_('تم تسريع التصنيع وإنهاؤه فوراً مقابل %(cost)s ماسة.', cost=diamonds_cost), 'success')
    return redirect(url_for('factory.index'))
