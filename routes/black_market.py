from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models import Item, UserItem, User, Message, SystemConfig
from models.contract import FarmSupplyContract
from models.facility import UserFacility
from models.location import Location
from models.combat import ActiveIntel
from .utils import update_daily_task_progress
from datetime import datetime, timedelta, timezone
import math
import random
import json
from services.requirements import tier_for_user, tier_rank, check_requirements

bp = Blueprint('black_market', __name__, url_prefix='/black_market')

FARM_PRODUCT_NAMES = {
    "زيت زيتون بلدي",
    "زيت زيتون ممتاز",
    "زعتر بلدي",
    "زعتر جبلي فاخر",
    "صابون نابلسي",
    "صابون نابلسي فاخر",
    "تمر أريحا",
    "كوفية فلسطينية",
    "كوفية مطرزة",
    "فخار الخليل",
}


def _best_contract_facility_level(user_id):
    keys = ["olive_press", "zaatar_nursery", "soap_workshop", "keffiyeh_workshop"]
    best_level = 0
    for k in keys:
        uf = UserFacility.query.filter_by(user_id=user_id, facility_key=k).first()
        lvl = int(uf.level) if uf and uf.level is not None else 0
        if lvl >= 2 and lvl > best_level:
            best_level = lvl
    return best_level


def _contract_offer(user):
    tier = tier_for_user(user)
    t = tier_rank(tier)
    best_level = _best_contract_facility_level(user.id)
    if best_level <= 0:
        return None

    duration_minutes = int(SystemConfig.get_value("farm_contract_duration_minutes", "60") or 60)
    base_cost = int(SystemConfig.get_value("farm_contract_base_cost", "25") or 25)
    cost_per_tier = int(SystemConfig.get_value("farm_contract_cost_per_tier", "10") or 10)
    base_bonus = float(SystemConfig.get_value("farm_contract_base_bonus", "0.10") or 0.10)
    bonus_per_level = float(SystemConfig.get_value("farm_contract_bonus_per_facility_level", "0.03") or 0.03)
    max_bonus = float(SystemConfig.get_value("farm_contract_max_bonus", "0.25") or 0.25)

    bonus = min(max_bonus, base_bonus + bonus_per_level * max(0, best_level - 1) + 0.01 * max(0, t - 1))
    cost = max(1, base_cost + cost_per_tier * max(0, t - 1))

    return {"duration_minutes": duration_minutes, "bonus_percent": bonus, "cost_diamonds": cost}

# --- Smuggling Helpers ---
def get_smuggling_price(item, location_id=None):
    """Calculates dynamic price based on location and time (hourly)"""
    if not location_id:
        return item.cost
        
    # Seed based on hour, location, and item to ensure consistent prices for everyone in that hour/loc
    now = datetime.now(timezone.utc)
    hour_seed = int(now.timestamp() / 3600) 
    seed = hour_seed + location_id + item.id
    
    # Use a local random instance to not affect global state
    rng = random.Random(seed)
    
    # Multiplier between 0.7 and 1.6
    multiplier = rng.uniform(0.7, 1.6)
    
    # Specific location biases (optional, can be added later)
    
    return int(item.cost * multiplier)
 
def _get_black_market_event():
    raw_key = SystemConfig.get_value('black_market_event', 'none') or 'none'
    key = (raw_key or 'none').strip()
    raw_loc = SystemConfig.get_value('black_market_event_location_id', None)
    try:
        loc_id = int(raw_loc) if raw_loc not in (None, '', 'none') else None
    except Exception:
        loc_id = None
    event = {
        "key": key,
        "location_id": loc_id,
        "title": None,
        "description": None,
        "type": "neutral",
    }
    if key == 'smuggling_boost':
        event["title"] = _('فوضى على الحدود')
        event["description"] = _('أسعار شراء وبيع بضائع التهريب أعلى من المعتاد في المناطق المتأثرة.')
        event["type"] = "buff"
    elif key == 'smuggling_crackdown':
        event["title"] = _('حملة تفتيش على المعابر')
        event["description"] = _('الأسعار أقل من المعتاد وخطر الخسارة أعلى في المناطق المتأثرة.')
        event["type"] = "nerf"
    else:
        event["key"] = "none"
    return event

def _apply_black_market_event(price, location_id, event):
    if not event:
        return price
    key = event.get("key") or "none"
    if key == "none":
        return price
    target_loc = event.get("location_id")
    if target_loc and location_id and location_id != target_loc:
        return price
    if key == "smuggling_boost":
        return int(price * 1.25)
    if key == "smuggling_crackdown":
        return int(price * 0.75)
    return price

from sqlalchemy import text

@bp.route('/')
@login_required
def index():
    # Smuggling items are initialized in utils/essentials.py
    
    now = datetime.now(timezone.utc)
    current_loc_id = current_user.location_id
    black_market_event = _get_black_market_event()

    changed_status = False
    if current_user.safe_house_until:
        safe_until = current_user.safe_house_until
        if safe_until.tzinfo is None:
            safe_until = safe_until.replace(tzinfo=timezone.utc)
        if safe_until <= now:
            current_user.is_safe_house_active = False
            current_user.safe_house_until = None
            changed_status = True

    if current_user.disguise_until:
        disguise_until = current_user.disguise_until
        if disguise_until.tzinfo is None:
            disguise_until = disguise_until.replace(tzinfo=timezone.utc)
        if disguise_until <= now:
            current_user.is_disguised = False
            current_user.disguise_until = None
            changed_status = True

    if changed_status:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    try:
        weapons = Item.query.filter_by(type='weapon', is_black_market=True).all()
        armors = Item.query.filter_by(type='armor', is_black_market=True).all()
        consumables = Item.query.filter_by(type='consumable', is_black_market=True).all()
        loot_items = UserItem.query.filter_by(user_id=current_user.id).join(Item).filter(Item.type == 'loot').all()
    except Exception:
        db.session.rollback()
        weapons = []
        armors = []
        consumables = []
        loot_items = []
    
    # Smuggling Items with dynamic prices
    try:
        smuggling_items_query = Item.query.filter_by(type='smuggling').all()
        smuggling_items = []
        
        for item in smuggling_items_query:
            price = get_smuggling_price(item, current_loc_id)
            price = _apply_black_market_event(price, current_loc_id, black_market_event)
            
            # Check user inventory
            user_qty = 0
            u_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
            if u_item:
                user_qty = u_item.quantity
                
            smuggling_items.append({
                'item': item,
                'current_price': price,
                'user_quantity': user_qty,
                'trend': 'up' if price > item.cost else 'down' # Simple trend indicator
            })
    except Exception:
        db.session.rollback()
        smuggling_items = []
        
    bullets_factory_only = SystemConfig.get_value('economy_bullets_only_from_factory', 'false') == 'true'

    try:
        active_contract = FarmSupplyContract.query.filter_by(
            user_id=current_user.id,
            location_id=current_loc_id,
            status='active'
        ).order_by(FarmSupplyContract.ends_at.desc()).first()
        if active_contract and not active_contract.is_active:
            active_contract.status = 'expired'
            db.session.add(active_contract)
            db.session.commit()
            active_contract = None
    except Exception:
        db.session.rollback()
        active_contract = None

    contract_offer = _contract_offer(current_user)
    
    current_location = db.session.get(Location, current_loc_id) if current_loc_id else None


    services_requirements = {
        "safe_house": {"min_tier": "t2", "min_intelligence": 8},
        "disguise": {"min_tier": "t1", "min_intelligence": 6},
        "spy": {"min_tier": "t2", "min_intelligence": 12},
        "cool_off": {"min_tier": "t1", "min_intelligence": 5},
    }
    services_access = {}
    for k, req in services_requirements.items():
        chk = check_requirements(current_user, req)
        hint_url = None
        if chk.get("hint_key") == "gym":
            hint_url = url_for('gym.index')
        elif chk.get("hint_key") == "daily_tasks":
            hint_url = url_for('main.daily_tasks')
        services_access[k] = {"unlocked": bool(chk["ok"]), "reason": chk["reason"], "hint_text": chk.get("hint_text"), "hint_url": hint_url}

    return render_template('black_market.html', 
                           weapons=weapons, 
                           armors=armors, 
                           consumables=consumables, 
                           loot_items=loot_items, 
                           smuggling_items=smuggling_items,
                           user=current_user,
                           bullets_factory_only=bullets_factory_only,
                           active_contract=active_contract,
                           contract_offer=contract_offer,
                           current_location=current_location,
                           services_access=services_access,
                           black_market_event=black_market_event)

@bp.route('/buy_smuggling/<int:item_id>', methods=['POST'])
@login_required
def buy_smuggling(item_id):
    # Status Check (Copy-paste standard checks or use decorator if available)
    now = datetime.now(timezone.utc)
    if current_user.jail_until and current_user.jail_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في السجن!'), 'danger')
        return redirect(url_for('black_market.index'))
    if current_user.hospital_until and current_user.hospital_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في المستشفى!'), 'danger')
        return redirect(url_for('hospital.index'))
        
    item = db.session.get(Item, item_id)
    if not item or item.type != 'smuggling':
        abort(404)
        
    quantity = int(request.form.get('quantity', 0))
    if quantity <= 0:
        flash(_('كمية غير صحيحة!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    black_market_event = _get_black_market_event()
    price = get_smuggling_price(item, current_user.location_id)
    price = _apply_black_market_event(price, current_user.location_id, black_market_event)
    total_cost = price * quantity
    
    if current_user.money < total_cost:
        flash(_('ليس لديك مال كافي!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    current_user.money -= total_cost
    
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
    if user_item:
        user_item.quantity += quantity
    else:
        user_item = UserItem(user_id=current_user.id, item_id=item.id, quantity=quantity)
        db.session.add(user_item)
        
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    flash(_('تم شراء %(qty)s من %(name)s بسعر %(price)s للقطعة.', qty=quantity, name=item.name, price=price), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/sell_smuggling/<int:item_id>', methods=['POST'])
@login_required
def sell_smuggling(item_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until and current_user.jail_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في السجن!'), 'danger')
        return redirect(url_for('black_market.index'))
    if current_user.hospital_until and current_user.hospital_until.replace(tzinfo=timezone.utc) > now:
        flash(_('أنت في المستشفى!'), 'danger')
        return redirect(url_for('hospital.index'))

    item = db.session.get(Item, item_id)
    if not item or item.type != 'smuggling':
        abort(404)
        
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
    if not user_item or user_item.quantity <= 0:
        flash(_('لا تملك هذا الغرض!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    quantity = int(request.form.get('quantity', 0))
    if quantity <= 0 or quantity > user_item.quantity:
        flash(_('كمية غير صحيحة!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    black_market_event = _get_black_market_event()
    price = get_smuggling_price(item, current_user.location_id)
    price = _apply_black_market_event(price, current_user.location_id, black_market_event)
    total_value = price * quantity

    bonus_pct = 0.0
    if item.name in FARM_PRODUCT_NAMES:
        contract = FarmSupplyContract.query.filter_by(
            user_id=current_user.id,
            location_id=current_user.location_id,
            status='active'
        ).order_by(FarmSupplyContract.ends_at.desc()).first()
        if contract and contract.is_active:
            try:
                bonus_pct = float(contract.bonus_percent or 0.0)
            except Exception:
                bonus_pct = 0.0
            total_value = int(total_value * (1 + bonus_pct))
    
    current_user.money += total_value
    user_item.quantity -= quantity
    
    if user_item.quantity == 0:
        db.session.delete(user_item)
        
    db.session.commit()
    if bonus_pct > 0:
        flash(_('تم بيع %(qty)s من %(name)s بسعر %(price)s للقطعة. عقد توريد +%(pct)s%%. الربح: %(val)s', qty=quantity, name=item.name, price=price, pct=int(bonus_pct * 100), val=total_value), 'success')
    else:
        flash(_('تم بيع %(qty)s من %(name)s بسعر %(price)s للقطعة. الربح: %(val)s', qty=quantity, name=item.name, price=price, val=total_value), 'success')
    return redirect(url_for('black_market.index'))


@bp.route('/buy_service/<service_type>', methods=['POST'])
@login_required
def buy_service(service_type):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك التعامل مع السوق السوداء!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك التعامل مع السوق السوداء!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك التعامل مع السوق السوداء!'), 'danger')
            return redirect(url_for('gym.index'))

    service_requirements = {
        "safe_house": {"min_tier": "t2", "min_intelligence": 8},
        "disguise": {"min_tier": "t1", "min_intelligence": 6},
        "cool_off": {"min_tier": "t1", "min_intelligence": 5},
    }
    if service_type in service_requirements:
        chk = check_requirements(current_user, service_requirements[service_type])
        if not chk["ok"]:
            flash(_('طور نفسك لفتحها: %(reason)s', reason=chk["reason"]), 'warning')
            return redirect(url_for('black_market.index'))

    if service_type == 'safe_house':
        cost = 50000
        duration = 24 # hours
        
        if current_user.money < cost:
            flash(_('تحتاج إلى 50,000$ لاستئجار منزل آمن!'), 'danger')
            return redirect(url_for('black_market.index'))
            
        current_user.money -= cost
        current_user.is_safe_house_active = True
        
        # Extend if already active, else set new
        safe_house_until = current_user.safe_house_until
        if safe_house_until and safe_house_until.tzinfo is None:
            safe_house_until = safe_house_until.replace(tzinfo=timezone.utc)
            
        if safe_house_until and safe_house_until > now:
            current_user.safe_house_until = safe_house_until + timedelta(hours=duration)
        else:
            current_user.safe_house_until = now + timedelta(hours=duration)
            
        flash(_('تم استئجار المنزل الآمن لمدة 24 ساعة! لا يمكن لأحد مهاجمتك الآن.'), 'success')
        
    elif service_type == 'disguise':
        cost = 10000
        duration = 1 # hours
        
        if current_user.money < cost:
            flash(_('تحتاج إلى 10,000$ لشراء تنكر!'), 'danger')
            return redirect(url_for('black_market.index'))
            
        current_user.money -= cost
        current_user.is_disguised = True
        
        if current_user.disguise_until and current_user.disguise_until > now:
            current_user.disguise_until += timedelta(hours=duration)
        else:
            current_user.disguise_until = now + timedelta(hours=duration)
            
        flash(_('تم تفعيل التخفي لمدة ساعة! سيظهر اسمك كمجهول عند الهجوم.'), 'success')
    elif service_type == 'cool_off':
        heat = 0
        try:
            heat = current_user.heat_value(now=now)
        except Exception:
            heat = 0
        if heat <= 0:
            flash(_('حرارتك صفر… خليك هادي.'), 'info')
            return redirect(url_for('black_market.index'))

        cost = 5000 + (heat * 700)
        if current_user.money < cost:
            flash(_('تحتاج إلى %(cost)s$ لتخفيف الحرارة الحالية.', cost=cost), 'danger')
            return redirect(url_for('black_market.index'))

        current_user.money -= cost
        try:
            current_user.add_heat(-40, now=now)
        except Exception:
            pass
        flash(_('دفعت رشوة ونظفت آثارك. الحرارة انخفضت.'), 'success')
        
    else:
        flash(_('خدمة غير معروفة!'), 'danger')
        
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    return redirect(url_for('black_market.index'))

@bp.route('/buy_bullets', methods=['POST'])
@login_required
def buy_bullets():
    if SystemConfig.get_value('economy_bullets_only_from_factory', 'false') == 'true':
        flash(_('الذخيرة يتم إنتاجها من المصانع.'), 'info')
        return redirect(url_for('factory.index'))

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك شراء الرصاص!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك شراء الرصاص!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك شراء الرصاص!'), 'danger')
            return redirect(url_for('gym.index'))

    quantity = request.form.get('quantity', type=int)
    if not quantity or quantity <= 0:
        flash(_('الكمية غير صحيحة!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    cost_per_bullet = 10
    total_cost = quantity * cost_per_bullet
    
    if current_user.money < total_cost:
        flash(_('معكش مصاري كفاية!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    current_user.money -= total_cost
    current_user.bullets += quantity
    
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    
    flash(_('تم شراء %(qty)s رصاصة بنجاح!', qty=quantity), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/spy', methods=['POST'])
@login_required
def spy():
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إرسال مخبرين!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إرسال مخبرين!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إرسال مخبرين!'), 'danger')
            return redirect(url_for('gym.index'))

    chk = check_requirements(current_user, {"min_tier": "t2", "min_intelligence": 12})
    if not chk["ok"]:
        flash(_('طور نفسك لفتحها: %(reason)s', reason=chk["reason"]), 'warning')
        return redirect(url_for('black_market.index'))

    target_username = request.form.get('username')
    if not target_username:
        flash(_('يرجى إدخال اسم اللاعب!'), 'danger')
        return redirect(url_for('black_market.index'))

    target = User.query.filter_by(username=target_username).first()
    if not target:
        flash(_('اللاعب غير موجود!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    if target.id == current_user.id:
        flash(_('لا يمكنك التجسس على نفسك!'), 'warning')
        return redirect(url_for('black_market.index'))

    # Logic: Cost and Time depend on level difference
    # If target is higher level -> More expensive, takes longer
    # If I have high intelligence -> Cheaper, faster
    
    level_diff = target.level - current_user.level
    intel_factor = current_user.intelligence / 10.0  # Higher intel reduces cost/time
    
    base_cost = 5000
    base_time = 10 # minutes
    
    # Cost Multiplier: +10% per level diff (if target is higher), reduced by Intel
    cost_multiplier = 1.0 + (max(0, level_diff) * 0.1) - (intel_factor * 0.05)
    cost_multiplier = max(0.5, cost_multiplier) # Min 50% cost
    
    final_cost = int(base_cost * cost_multiplier)
    
    # Check Money
    if current_user.money < final_cost:
        flash(_('تحتاج إلى %(cost)s$ لعملية التجسس هذه!', cost=final_cost), 'danger')
        return redirect(url_for('black_market.index'))
        
    # Time Multiplier: Similar logic
    time_multiplier = 1.0 + (max(0, level_diff) * 0.05) - (intel_factor * 0.1)
    time_multiplier = max(0.2, time_multiplier) # Min 20% time (2 mins)
    
    final_time_minutes = int(base_time * time_multiplier)
    delivery_time = datetime.now(timezone.utc) + timedelta(minutes=final_time_minutes)
    
    # Deduct Money
    current_user.money -= final_cost
    
    # Prepare Report Data
    # Estimated bullets to kill (Assuming avg player dmg = 20 for calculation)
    # Formula: (HP + Defense) / Dmg
    estimated_hp = target.health
    estimated_def = target.defense
    avg_dmg = 20
    bullets_needed = math.ceil((estimated_hp + (estimated_def * 0.5)) / avg_dmg) # Simple formula
    
    location_name = target.location.name if target.location else _("غير معروف")
    safe_house_until = target.safe_house_until
    if safe_house_until and safe_house_until.tzinfo is None:
        safe_house_until = safe_house_until.replace(tzinfo=timezone.utc)
    safe_house_status = _("نشط") if (target.is_safe_house_active and safe_house_until and safe_house_until > now) else _("غير نشط")
    
    report_body = f"""
    <strong>{_('تقرير استخباراتي عن الهدف:')} {target.username}</strong><br><br>
    <ul>
        <li><strong>{_('الموقع الحالي:')}</strong> {location_name}</li>
        <li><strong>{_('المنزل الآمن:')}</strong> {safe_house_status}</li>
        <li><strong>{_('المستوى:')}</strong> {target.level}</li>
        <li><strong>{_('الصحة المقدرة:')}</strong> {estimated_hp} / {target.max_health}</li>
        <li><strong>{_('الدفاع:')}</strong> {estimated_def}</li>
        <li><strong>{_('رصاصات للقتل (تقريبي):')}</strong> {bullets_needed} {_('رصاصة')}</li>
        <li><strong>{_('الكاش:')}</strong> ${target.money:,}</li>
    </ul>
    <br>
    <small>{_('ملاحظة: هذه المعلومات دقيقة وقت طلب التقرير وقد تتغير.')}</small>
    """
    
    # Create Message
    msg = Message(
        sender_id=current_user.id, # From "Self" or "System"
        receiver_id=current_user.id,
        subject=_('تقرير سري: %(name)s', name=target.username),
        body=report_body,
        delivery_time=delivery_time
    )
    
    db.session.add(msg)
    
    # Create Active Intel (Valid from delivery time for 24 hours)
    intel = ActiveIntel(
        user_id=current_user.id,
        target_id=target.id,
        start_time=delivery_time,
        expires_at=delivery_time + timedelta(hours=24)
    )
    db.session.add(intel)
    
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    
    flash(_('بدأ المخبر العمل. التكلفة: %(cost)s$. سيصل التقرير خلال %(time)s دقيقة.', cost=final_cost, time=final_time_minutes), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/buy/<int:item_id>', methods=['POST'])
@login_required
def buy(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        abort(404)
    
    if not item.is_black_market:
        flash(_('هذا الغرض غير متوفر في السوق السوداء!'), 'danger')
        return redirect(url_for('black_market.index'))

    if current_user.money < item.cost:
        flash(_('معكش مصاري كفاية يا معلم!'), 'danger')
        return redirect(url_for('black_market.index'))
    
    current_user.money -= item.cost
    
    # Check if user already has this item
    user_item = UserItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()
    
    if user_item:
        user_item.quantity += 1
    else:
        user_item = UserItem(user_id=current_user.id, item_id=item.id, quantity=1)
        db.session.add(user_item)
    
    db.session.commit()
    
    update_daily_task_progress(current_user, 'buy')
    
    flash(_('تم شراء %(name)s من السوق السوداء بنجاح!', name=item.name), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/sell_loot/<int:user_item_id>', methods=['POST'])
@login_required
def sell_loot(user_item_id):
    user_item = db.session.get(UserItem, user_item_id)
    if not user_item:
        abort(404)
        
    if user_item.user_id != current_user.id:
        flash(_('هذا الغرض ليس ملكك!'), 'danger')
        return redirect(url_for('black_market.index'))
        
    if user_item.item.type != 'loot':
        flash(_('لا يمكنك بيع هذا الغرض هنا! فقط المسروقات.'), 'warning')
        return redirect(url_for('black_market.index'))
        
    if user_item.condition is not None and user_item.condition < 100:
        flash(_('لا يمكن بيع مسروقات متضررة! قم بإصلاحها أولاً.'), 'danger')
        return redirect(url_for('black_market.index'))
        
    # Sell Price: 60% of original cost
    sell_price = int(user_item.item.cost * 0.6)
    
    current_user.money += sell_price
    
    if user_item.quantity > 1:
        user_item.quantity -= 1
    else:
        db.session.delete(user_item)
        
    db.session.commit()
    
    flash(_('تم بيع %(name)s مقابل %(price)s شيكل.', name=user_item.item.name, price=sell_price), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/repair_loot/<int:user_item_id>', methods=['POST'])
@login_required
def repair_loot(user_item_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إصلاح المسروقات!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إصلاح المسروقات!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إصلاح المسروقات!'), 'danger')
            return redirect(url_for('gym.index'))

    user_item = db.session.get(UserItem, user_item_id)
    if not user_item:
        abort(404)
    if user_item.user_id != current_user.id:
        flash(_('هذا الغرض ليس ملكك!'), 'danger')
        return redirect(url_for('black_market.index'))
    if user_item.item.type != 'loot':
        flash(_('فقط المسروقات يمكن إصلاحها هنا.'), 'warning')
        return redirect(url_for('black_market.index'))
    
    if user_item.condition is None or user_item.condition >= 100:
        flash(_('الغرض سليم ولا يحتاج لإصلاح.'), 'info')
        return redirect(url_for('black_market.index'))
    
    damage = 100 - user_item.condition
    base_cost = user_item.item.cost
    # Repair cost: 0.5% of value per 1% damage
    # Total repair from 0% to 100% costs 50% of item value
    # Sell price is 60% of value, ensuring profit margin
    cost = int(damage * (base_cost * 0.005) * user_item.quantity)
    
    if current_user.money < cost:
        flash(_('تحتاج %(cost)s شيكل لإصلاح المسروقات!', cost=cost), 'danger')
        return redirect(url_for('black_market.index'))
    
    current_user.money -= cost
    user_item.condition = 100
    db.session.commit()
    
    flash(_('تم إصلاح المسروقات وأصبحت جاهزة للبيع.'), 'success')
    return redirect(url_for('black_market.index'))

@bp.route('/repair_all_loot', methods=['POST'])
@login_required
def repair_all_loot():
    # Find all damaged loot items for the user
    damaged_items = []
    user_items = UserItem.query.filter_by(user_id=current_user.id).all()
    
    for ui in user_items:
        if ui.item.type == 'loot' and ui.condition is not None and ui.condition < 100:
            damaged_items.append(ui)
            
    if not damaged_items:
        flash(_('لا يوجد مسروقات متضررة لإصلاحها.'), 'info')
        return redirect(url_for('black_market.index'))
        
    total_cost = 0
    for ui in damaged_items:
        damage = 100 - ui.condition
        item_cost = int(damage * (ui.item.cost * 0.005) * ui.quantity)
        total_cost += item_cost
        
    if current_user.money < total_cost:
        flash(_('تحتاج %(cost)s شيكل لإصلاح كل المسروقات! لديك %(money)s فقط.', cost=total_cost, money=current_user.money), 'danger')
        return redirect(url_for('black_market.index'))
        
    # Process repair
    current_user.money -= total_cost
    for ui in damaged_items:
        ui.condition = 100
        
    db.session.commit()
    
    flash(_('تم إصلاح كل المسروقات (%(count)d قطعة) بتكلفة %(cost)s شيكل.', count=len(damaged_items), cost=total_cost), 'success')
    return redirect(url_for('black_market.index'))


@bp.route('/extend_contract', methods=['POST'])
@login_required
def extend_contract():
    offer = _contract_offer(current_user)
    if not offer:
        flash(_('طور مرافقك لفتح عقد التوريد.'), 'warning')
        return redirect(url_for('farm.index'))

    cost = int(offer["cost_diamonds"])
    duration_minutes = int(offer["duration_minutes"])
    bonus = float(offer["bonus_percent"])

    if current_user.diamonds < cost:
        flash(_('ليس لديك ما يكفي من الماس! تحتاج إلى %(cost)s ماسة.', cost=cost), 'danger')
        return redirect(url_for('black_market.index'))

    now = datetime.now(timezone.utc)
    location_id = current_user.location_id
    contract = FarmSupplyContract.query.filter_by(
        user_id=current_user.id,
        location_id=location_id,
        status='active'
    ).order_by(FarmSupplyContract.ends_at.desc()).first()
    if contract and not contract.is_active:
        contract.status = 'expired'
        db.session.add(contract)
        db.session.commit()
        contract = None

    current_user.diamonds = max(0, int(current_user.diamonds) - cost)

    if contract:
        ends = contract.ends_at
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if ends and ends > now:
            contract.ends_at = (ends + timedelta(minutes=duration_minutes)).replace(tzinfo=None)
        else:
            contract.ends_at = (now + timedelta(minutes=duration_minutes)).replace(tzinfo=None)
        contract.bonus_percent = bonus
        db.session.add(contract)
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
    flash(_('تم تمديد عقد التوريد. +%(pct)s%% لمدة %(min)s دقيقة.', pct=int(bonus * 100), min=duration_minutes), 'success')
    return redirect(url_for('black_market.index'))
