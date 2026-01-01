from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from extensions import db
from flask_babel import _
from models import Location, UserItem, Item
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from models import User
import random
from services.resource_service import ResourceService

bp = Blueprint('travel', __name__, url_prefix='/travel')

@bp.route('/')
@login_required
def index():
    if Location.query.filter(Location.name != 'Default City').count() == 0:
        from utils.essentials import initialize_locations
        initialize_locations()
        db.session.commit()

    locations = Location.query.filter(Location.id != current_user.location_id).all()
    current_location = db.session.get(Location, current_user.location_id) if current_user.location_id else None
    
    # Calculate remaining cooldown
    remaining_time = 0
    if current_user.last_travel and current_user.location_id:
        # Assuming cooldown is based on the current location (the one we traveled TO)
        # If user has no location (e.g. initial), cooldown is 0
        if current_location:
            elapsed = datetime.now(timezone.utc) - current_user.last_travel.replace(tzinfo=timezone.utc) if current_user.last_travel.tzinfo is None else datetime.now(timezone.utc) - current_user.last_travel
            cooldown_duration = current_location.cooldown
            if elapsed.total_seconds() < cooldown_duration:
                remaining_time = int(cooldown_duration - elapsed.total_seconds())

    return render_template('travel.html', locations=locations, current_location=current_location, remaining_time=remaining_time)

@bp.route('/fly/<int:location_id>', methods=['POST'])
@login_required
def fly(location_id):
    target_location = db.session.get(Location, location_id)
    if not target_location:
        abort(404)

    user = db.session.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    ).scalar_one()
    
    # Check Status (Jail/Hospital/Gym)
    now = datetime.now(timezone.utc)
    
    if user.jail_until:
        jail_until = user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك السفر!'), 'danger')
            return redirect(url_for('jail.index'))

    if user.hospital_until:
        hospital_until = user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك السفر!'), 'danger')
            return redirect(url_for('hospital.index'))

    if user.gym_until:
        gym_until = user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب في الجيم ولا يمكنك السفر!'), 'danger')
            return redirect(url_for('gym.index'))

    # Check if already there
    if user.location_id == target_location.id:
        flash(_('أنت موجود هنا بالفعل!'), 'warning')
        return redirect(url_for('travel.index'))

    # Check Cooldown
    if user.last_travel and user.location_id:
        current_loc = db.session.get(Location, user.location_id)
        if current_loc:
            elapsed = datetime.now(timezone.utc) - user.last_travel.replace(tzinfo=timezone.utc) if user.last_travel.tzinfo is None else datetime.now(timezone.utc) - user.last_travel
            if elapsed.total_seconds() < current_loc.cooldown:
                flash(_('عليك الانتظار قبل السفر مرة أخرى!'), 'danger')
                return redirect(url_for('travel.index'))

    # Check Money
    if user.money < target_location.cost:
        flash(_('ليس لديك مال كافٍ للسفر!'), 'danger')
        return redirect(url_for('travel.index'))

    # --- SMUGGLING CHECK ---
    # Check if user has smuggling items
    smuggling_items = UserItem.query.filter_by(user_id=user.id).join(Item).filter(Item.type == 'smuggling').all()
    smuggling_risk_base = 0
    total_smuggling_qty = 0
    
    if smuggling_items:
        for ui in smuggling_items:
            total_smuggling_qty += ui.quantity
            
        # Risk: 15% base + 2% per item
        smuggling_risk_base = 15 + (total_smuggling_qty * 2)
        
        # Intelligence reduces risk
        intel_factor = user.intelligence * 0.1
        smuggling_risk = max(5, smuggling_risk_base - intel_factor) # Min 5% risk always
        
        risk_roll = random.randint(1, 100)
        
        if risk_roll <= smuggling_risk:
            # BUSTED!
            jail_time = 30 # minutes
            fine_amount = int(user.money * 0.2) # 20% fine
            
            # Confiscate items
            for ui in smuggling_items:
                db.session.delete(ui)
            
            # Atomic Fine via ResourceService
            ResourceService.modify_resources(user.id, {'money': -fine_amount}, 'smuggling_bust_fine', auto_commit=False, expected_version=user.version)
            
            # current_user.money -= fine_amount # Removed
            user.jail_until = datetime.now(timezone.utc) + timedelta(minutes=jail_time)
            
            db.session.commit()
            
            flash(_('🚔 كبسة! الشرطة فتشت السيارة ولقت المهربات. تمت مصادرة البضاعة وسجنك 30 دقيقة وغرامة %(fine)s$.', fine=fine_amount), 'danger')
            return redirect(url_for('jail.index'))

    # Process Travel
    
    travel_cost = target_location.cost

    # Random Events Logic (Normal)
    event_roll = 50 if current_app.config.get('TESTING') else random.randint(1, 100)
    msg_extra = ""
    
    # 1. Checkpoint (10% chance) - Only if not smuggling (smuggling check already happened)
    if event_roll <= 10:
        bribe = int(travel_cost * 0.5)
        if user.money >= (travel_cost + bribe):
            # Atomic Bribe via ResourceService
            ResourceService.modify_resources(user.id, {'money': -bribe}, 'travel_bribe', auto_commit=False, expected_version=user.version)
            msg_extra = _(" 👮 صادفك حاجز ودققت عليك، دفعت %(bribe)s رشوة لتمشي أمورك.", bribe=bribe)
        else:
            # Jail!
            jail_time = 15 # minutes
            user.jail_until = datetime.now(timezone.utc) + timedelta(minutes=jail_time)
            
            # Atomic deduction for travel cost
            ResourceService.modify_resources(user.id, {'money': -travel_cost}, 'travel_cost_jail', auto_commit=False, expected_version=user.version)

            db.session.commit()
            flash(_('👮 مسكوك عالمانع! معكش تدفع الرشوة. 15 دقيقة سجن.'), 'danger')
            return redirect(url_for('jail.index'))
            
    # 2. Cousin Driver (5% chance)
    elif event_roll >= 95:
        travel_cost = 0
        msg_extra = _(" 🚕 طلع الشوفير ابن عمك! التوصيلة ببلاش.")

    # Atomic deduction
    # Note: travel_cost might be 0.
    if travel_cost > 0:
        if not ResourceService.modify_resources(user.id, {'money': -travel_cost}, 'travel_cost', auto_commit=False, expected_version=user.version):
            # Should not happen if checks passed and no intervening deductions, but possible.
            flash(_('ليس لديك مال كافٍ للسفر!'), 'danger')
            return redirect(url_for('travel.index'))

    # current_user.money -= travel_cost # Removed
    user.location_id = target_location.id
    user.last_travel = datetime.now(timezone.utc)
    
    db.session.commit()
    
    flash(_('وصلت إلى %(name)s بنجاح!', name=target_location.name) + msg_extra, 'success')
    return redirect(url_for('travel.index'))
