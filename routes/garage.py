from flask import render_template, redirect, url_for, flash, abort
from flask_babel import _
from flask_login import login_required, current_user
from extensions import db, limiter
import random
from models import Vehicle, UserVehicle, User, RaceParticipant, Race
from models.system import SystemConfig
from sqlalchemy import select
from . import bp
from datetime import datetime, timedelta, timezone
from services.resource_service import ResourceService
from routes.utils import update_daily_task_progress

@bp.route('/garage')
@login_required
def garage():
    user_vehicles = UserVehicle.query.filter_by(user_id=current_user.id).limit(50).all()
    now = datetime.now(timezone.utc)
    
    # Check for finished repairs
    for car in user_vehicles:
        if car.repair_until:
            repair_until = car.repair_until
            if repair_until.tzinfo is None:
                repair_until = repair_until.replace(tzinfo=timezone.utc)
                
            if repair_until <= now:
                car.condition = 100
                car.repair_until = None
                db.session.commit()
                flash(_('تم الانتهاء من إصلاح %(name)s!', name=car.vehicle.name), 'success')

    return render_template('garage.html', vehicles=user_vehicles, user=current_user, now=now)

@bp.route('/dealership')
@login_required
def dealership():
    # Show all available vehicle types to buy
    vehicles = Vehicle.query.filter_by(is_active=True).all()
    return render_template('dealership.html', vehicles=vehicles, user=current_user)

@bp.route('/buy_car/<int:vehicle_id>', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def buy_car(vehicle_id):
    # Lock user to prevent race conditions (e.g. buying multiple active cars)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك شراء سيارات!'), 'danger')
            return redirect(url_for('jail.index'))
            
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك شراء سيارات!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك شراء سيارات!'), 'danger')
            return redirect(url_for('gym.index'))

    vehicle = Vehicle.query.get_or_404(vehicle_id)
    
    if current_user.money < vehicle.price:
        flash(_('معكش مصاري كفاية يا زعيم!'), 'danger')
        return redirect(url_for('main.dealership'))
    
    # Atomic Update via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'money': -vehicle.price}, 'buy_vehicle', auto_commit=False, expected_version=None):
        flash(_('معكش مصاري كفاية يا زعيم!'), 'danger')
        return redirect(url_for('main.dealership'))
    
    new_car = UserVehicle(user_id=current_user.id, vehicle_id=vehicle.id, is_active=True)
    
    # Deactivate other cars
    existing_cars = UserVehicle.query.filter_by(user_id=current_user.id).limit(50).all()
    for car in existing_cars:
        car.is_active = False
    
    db.session.add(new_car)
    db.session.commit()
    update_daily_task_progress(current_user, 'buy')
    
    flash(_('مبروك! اشتريت %(vehicle_name)s بنجاح.', vehicle_name=vehicle.name), 'success')
    return redirect(url_for('main.garage'))

@bp.route('/repair_car/<int:user_vehicle_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def repair_car(user_vehicle_id):
    # Lock user to prevent concurrent repairs/double spending
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إصلاح السيارات!'), 'danger')
            return redirect(url_for('jail.index'))
            
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إصلاح السيارات!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إصلاح السيارات!'), 'danger')
            return redirect(url_for('gym.index'))

    car = db.session.get(UserVehicle, user_vehicle_id)
    if not car:
        abort(404)
    if car.user_id != current_user.id:
        return redirect(url_for('main.garage'))
        
    if car.condition >= 100:
        flash(_('السيارة سليمة ولا تحتاج لإصلاح!'), 'warning')
        return redirect(url_for('main.garage'))
        
    if car.repair_until:
        repair_until = car.repair_until
        if repair_until.tzinfo is None:
            repair_until = repair_until.replace(tzinfo=timezone.utc)
        if repair_until > now:
            flash(_('السيارة قيد الإصلاح بالفعل!'), 'warning')
            return redirect(url_for('main.garage'))
        
    # Cost calculation: 0.3% of car price per 1% damage
    damage = 100 - car.condition
    cost = int(damage * car.vehicle.price * 0.003)
    
    if current_user.money < cost:
        flash(_('تحتاج %(cost)s شيكل لإصلاح السيارة بالكامل!', cost=cost), 'danger')
        return redirect(url_for('main.garage'))
        
    # Atomic Update via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'repair_car', auto_commit=False, expected_version=None):
        flash(_('تحتاج %(cost)s شيكل لإصلاح السيارة بالكامل!', cost=cost), 'danger')
        return redirect(url_for('main.garage'))
    
    # Time: 1 minute per 10% damage (min 1 minute)
    minutes = max(1, int(damage / 10))
    car.repair_until = (now + timedelta(minutes=minutes)).replace(tzinfo=None)
    
    db.session.commit()
    
    flash(_('بدأت عملية الإصلاح. ستستغرق %(min)s دقيقة.', min=minutes), 'info')
    return redirect(url_for('main.garage'))

@bp.route('/sell_car/<int:user_vehicle_id>', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def sell_car(user_vehicle_id):
    # Lock user to prevent double selling
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك بيع السيارات!'), 'danger')
            return redirect(url_for('jail.index'))
            
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك بيع السيارات!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك بيع السيارات!'), 'danger')
            return redirect(url_for('gym.index'))

    car = db.session.get(UserVehicle, user_vehicle_id)
    if not car:
        abort(404)
    if car.user_id != current_user.id:
        return redirect(url_for('main.garage'))

    active_race_ref = db.session.query(RaceParticipant.id).join(Race, Race.id == RaceParticipant.race_id).filter(
        RaceParticipant.user_vehicle_id == car.id,
        Race.status.in_(['waiting', 'in_progress'])
    ).first()
    if active_race_ref:
        flash(_('لا يمكنك بيع هذه السيارة لأنها مشاركة في سباق.'), 'danger')
        return redirect(url_for('main.garage'))
        
    if car.condition < 100:
        flash(_('لا يمكنك بيع سيارة متضررة! قم بإصلاحها أولاً.'), 'danger')
        return redirect(url_for('main.garage'))
        
    # Sell price is 50% of original price
    sell_price = int(car.vehicle.price * 0.5)
    
    # Atomic Update via ResourceService
    if not ResourceService.modify_resources(current_user.id, {'money': sell_price}, 'sell_car', auto_commit=False, expected_version=None):
        db.session.rollback()
        flash(_('حدث خطأ أثناء بيع السيارة. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('main.garage'))
    
    # If active, deactivate
    if car.is_active:
        car.is_active = False

    RaceParticipant.query.filter_by(user_vehicle_id=car.id).delete(synchronize_session=False)
    db.session.delete(car)
    db.session.commit()
    
    flash(_('تم بيع السيارة %(name)s وحصلت على %(price)s شيكل.', name=car.vehicle.name, price=sell_price), 'success')
    return redirect(url_for('main.garage'))

@bp.route('/activate_car/<int:user_vehicle_id>', methods=['POST'])
@login_required
def activate_car(user_vehicle_id):
    # Lock user to prevent concurrent sell/modification
    db.session.execute(select(User).where(User.id == current_user.id).with_for_update()).scalar()
    
    car = db.session.get(UserVehicle, user_vehicle_id)
    if not car:
        abort(404)
    if car.user_id != current_user.id:
        return redirect(url_for('main.garage'))
    
    # --- Mashtoub Campaign Check ---
    # If car price is low (< 30,000), it's considered "Mashtoub" or "Illegal" risk.
    if car.vehicle.price < 30000:
        is_campaign_active = SystemConfig.get_value('mashtoub_campaign_active', 'false') == 'true'
        base_risk = 0.50 if is_campaign_active else 0.10
        
        if random.random() < base_risk: # 10% normally, 50% during campaign
            # Seize car
            vehicle_name = car.vehicle.name
            
            # Deactivate if it was active (it wasn't yet, but just in case)
            # Delete user vehicle
            RaceParticipant.query.filter_by(user_vehicle_id=car.id).delete(synchronize_session=False)
            db.session.delete(car)
            db.session.commit()
            
            flash(_('🚓 حملة على المشطوب! الشرطة صادرت سيارة %(name)s لأنها مش قانونية. "القانون فوق الجميع" قال.', name=vehicle_name), 'danger')
            return redirect(url_for('main.garage'))

    # Deactivate others
    existing_cars = UserVehicle.query.filter_by(user_id=current_user.id).all()
    for c in existing_cars:
        c.is_active = False
    
    car.is_active = True
    db.session.commit()
    
    flash(_('تم تفعيل السيارة %(vehicle_name)s!', vehicle_name=car.vehicle.name), 'success')
    return redirect(url_for('main.garage'))

@bp.route('/tune_car/<int:user_vehicle_id>', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def tune_car(user_vehicle_id):
    # Lock user first to prevent deadlock (User -> UserVehicle order)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    # Lock user vehicle row
    car = db.session.query(UserVehicle).filter_by(id=user_vehicle_id).with_for_update().first()
    
    if not car:
        abort(404)
    if car.user_id != current_user.id:
        return redirect(url_for('main.garage'))
        
    cost = 2000
    
    if current_user.money < cost:
        flash(_('معكش مصاري للتعديل يا كبير!'), 'danger')
        return redirect(url_for('main.garage'))
        
    if car.condition >= 200:
        flash(_('السيارة معدلة عالآخر!'), 'warning')
        return redirect(url_for('main.garage'))
    
    if car.condition < 100:
        flash(_('لا يمكنك تعديل سيارة متضررة! قم بإصلاحها أولاً.'), 'danger')
        return redirect(url_for('main.garage'))
        
    # Atomic Update via ResourceService
    # We already locked User, so this is safe/re-entrant in same transaction
    if not ResourceService.modify_resources(current_user.id, {'money': -cost}, 'tune_vehicle', auto_commit=False, expected_version=None):
        flash(_('معكش مصاري للتعديل يا كبير!'), 'danger')
        return redirect(url_for('main.garage'))
        
    # We use condition > 100 to represent "Tuned" status
    # Normal max is 100. Tuned max is 200.
    car.condition = min(car.condition + 20, 200)
    
    db.session.commit()
    
    flash(_('تم تعديل محرك %(vehicle_name)s! السرعة والأداء زادوا.', vehicle_name=car.vehicle.name), 'success')
    return redirect(url_for('main.garage'))
