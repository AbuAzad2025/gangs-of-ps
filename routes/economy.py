from flask import render_template, redirect, url_for, flash, Blueprint, abort
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models import Asset, Gang, MoneySinkLog, GangLog
from datetime import datetime, timezone

bp = Blueprint('economy', __name__, url_prefix='/economy')

from services.resource_service import ResourceService

@bp.route('/properties')
@login_required
def properties():
    # Show only unowned properties (templates) that are active
    assets = Asset.query.filter_by(type='house', owner_id=None, gang_id=None, is_active=True).limit(50).all()
    return render_template('properties.html', assets=assets, user=current_user)

@bp.route('/collect_income/<int:asset_id>', methods=['POST'])
@login_required
def collect_income(asset_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك جمع الإيجارات!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك جمع الإيجارات!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك جمع الإيجارات!'), 'danger')
            return redirect(url_for('gym.index'))

    if not asset:
        abort(404)
    
    # Lock User first to prevent race conditions (Consistent Order: User -> Asset)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()
    
    # Lock asset
    asset = db.session.query(Asset).filter_by(id=asset_id).with_for_update().first()
    
    if not asset: # Re-check existence
        abort(404)

    if asset.owner_id != current_user.id:
        flash(_('هذا العقار ليس ملكك!'), 'danger')
        return redirect(url_for('economy.my_properties'))
        
    if not asset.can_collect:
        flash(_('لم يحن موعد جمع الدخل بعد!'), 'warning')
        return redirect(url_for('economy.my_properties'))
        
    # Calculate Net Income
    maintenance = asset.maintenance_cost or 0
    net_income = asset.income - maintenance
    
    # Atomic update via ResourceService
    if not ResourceService.modify_resources(
        current_user.id, 
        {'money': net_income}, 
        'property_income_collection', 
        auto_commit=False, 
        expected_version=current_user.version
    ):
        flash(_('حدث خطأ أثناء جمع الدخل. يرجى المحاولة مرة أخرى.'), 'danger')
        return redirect(url_for('economy.my_properties'))
    
    # Log sink
    if maintenance > 0:
        sink_log = MoneySinkLog(
            user_id=current_user.id,
            sink_type='property_maintenance',
            amount=maintenance,
            details=f"Maintenance for {asset.name}"
        )
        db.session.add(sink_log)
        
    asset.last_collected = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    if maintenance > 0:
         flash(_('تم جمع الدخل %(income)s $ ودفع صيانة %(maint)s $. الصافي: %(net)s $', 
                 income="{:,}".format(asset.income), 
                 maint="{:,}".format(maintenance), 
                 net="{:,}".format(net_income)), 'success')
    else:
         flash(_('تم جمع الدخل %(amount)s $ من %(name)s بنجاح!', amount="{:,}".format(asset.income), name=asset.name), 'success')
    return redirect(url_for('economy.my_properties'))

@bp.route('/collect_gang_income/<int:asset_id>', methods=['POST'])
@login_required
def collect_gang_income(asset_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك جمع إيجارات العصابة!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك جمع إيجارات العصابة!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك جمع إيجارات العصابة!'), 'danger')
            return redirect(url_for('gym.index'))

    if not current_user.gang_id:
        flash(_('أنت لست في عصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    # Lock the gang row to prevent race conditions on money update
    gang = Gang.query.filter_by(id=current_user.gang_id).with_for_update().first()
    if not gang:
        flash(_('العصابة غير موجودة!'), 'danger')
        return redirect(url_for('gang.dashboard'))

    # Allow Leader and Underboss to collect
    if current_user.id != gang.leader_id and current_user.id != gang.underboss_id:
        flash(_('فقط الزعيم أو نائبه يمكنهم جمع إيجارات العصابة!'), 'danger')
        return redirect(url_for('gang.dashboard'))

    # Lock asset
    asset = db.session.query(Asset).filter_by(id=asset_id).with_for_update().first()
    if not asset:
        abort(404)
    
    if asset.gang_id != gang.id:
        flash(_('هذا العقار ليس ملك لعصابتك!'), 'danger')
        return redirect(url_for('gang.dashboard'))
        
    if not asset.can_collect:
        flash(_('لم يحن موعد جمع الدخل بعد!'), 'warning')
        return redirect(url_for('gang.dashboard'))
        
    # Calculate Net Income
    maintenance = asset.maintenance_cost or 0
    net_income = asset.income - maintenance
    
    # Gang Buff (Street Kings) - Money Multiplier
    try:
        from services.gang_service import GangService
        gang_buff = GangService.get_gang_buff(gang.id, 'street_kings')
        if gang_buff > 0:
            bonus = int(net_income * (gang_buff / 100))
            net_income += bonus
            if bonus > 0:
                flash(_('مكافأة ملوك الشوارع: +%(bonus)s$', bonus="{:,}".format(bonus)), 'success')
    except Exception:
        pass

    # Update Gang Money Atomic
    Gang.query.filter(Gang.id == gang.id).update({
        Gang.money: Gang.money + net_income
    }, synchronize_session=False)
    
    # Log sink
    if maintenance > 0:
        sink_log = MoneySinkLog(
            user_id=current_user.id, # Logged under user who collected, or maybe null? User is fine.
            sink_type='gang_property_maintenance',
            amount=maintenance,
            details=f"Gang Maintenance for {asset.name} (Gang {gang.name})"
        )
        db.session.add(sink_log)
    
    # Gang Log
    log = GangLog(
        gang_id=gang.id, 
        user_id=current_user.id, 
        action=_('جمع دخل عقار %(asset)s: +%(net)s$ (صيانة: -%(maint)s$)', 
                 asset=asset.name, net=net_income, maint=maintenance)
    )
    db.session.add(log)
    
    asset.last_collected = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    flash(_('تم جمع الدخل لصالح العصابة بنجاح!'), 'success')
    return redirect(url_for('gang.dashboard'))

@bp.route('/buy_property/<int:asset_id>', methods=['POST'])
@login_required
def buy_property(asset_id):
    asset_template = db.session.get(Asset, asset_id)
    if not asset_template:
        abort(404)
    
    # Verify it's a template
    if asset_template.owner_id is not None or asset_template.gang_id is not None:
        flash(_('هذا العقار مملوك بالفعل!'), 'danger')
        return redirect(url_for('economy.properties'))
        
    if current_user.money < asset_template.value:
        flash(_('معكش مصاري كفاية يا معلم!'), 'danger')
        return redirect(url_for('economy.properties'))
        
    # Lock user to prevent race conditions
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Atomic deduction via ResourceService
    if not ResourceService.modify_resources(
        current_user.id, 
        {'money': -asset_template.value}, 
        'buy_property', 
        auto_commit=False, 
        expected_version=None
    ):
        db.session.rollback()
        flash(_('معكش مصاري كفاية يا معلم! أو حدث خطأ.'), 'danger')
        return redirect(url_for('economy.properties'))
    
    # Create new owned asset based on template
    new_asset = Asset(
        name=asset_template.name,
        type=asset_template.type,
        owner_id=current_user.id,
        value=asset_template.value,
        income=asset_template.income,
        image=asset_template.image,
        is_active=True
    )
    
    db.session.add(new_asset)
    db.session.commit()
    
    flash(_('مبروك! اشتريت %(name)s بنجاح.', name=asset_template.name), 'success')
    return redirect(url_for('economy.properties'))

@bp.route('/buy_gang_property/<int:asset_id>', methods=['POST'])
@login_required
def buy_gang_property(asset_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك شراء عقارات للعصابة!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك شراء عقارات للعصابة!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك شراء عقارات للعصابة!'), 'danger')
            return redirect(url_for('gym.index'))

    if not current_user.gang_id:
        flash(_('أنت لست في عصابة!'), 'danger')
        return redirect(url_for('economy.properties'))
        
    # Lock gang to prevent race conditions
    gang = Gang.query.filter_by(id=current_user.gang_id).with_for_update().first()
    if not gang:
        flash(_('العصابة غير موجودة!'), 'danger')
        return redirect(url_for('economy.properties'))

    if current_user.id != gang.leader_id: # Only leader for now
        flash(_('فقط الزعيم يمكنه شراء ممتلكات للعصابة!'), 'danger')
        return redirect(url_for('economy.properties'))

    asset_template = db.session.get(Asset, asset_id)
    if not asset_template:
        abort(404)
    
    if asset_template.owner_id is not None or asset_template.gang_id is not None:
         flash(_('هذا العقار مملوك بالفعل!'), 'danger')
         return redirect(url_for('economy.properties'))
         
    if gang.money < asset_template.value:
        flash(_('خزينة العصابة لا تكفي!'), 'danger')
        return redirect(url_for('economy.properties'))
        
    # Deduct money (we have the lock, so normal update is fine, but atomic is safer/cleaner)
    gang.money -= asset_template.value
    
    new_asset = Asset(
        name=asset_template.name,
        type=asset_template.type,
        gang_id=gang.id,
        value=asset_template.value,
        income=asset_template.income,
        image=asset_template.image,
        is_active=True
    )
    
    db.session.add(new_asset)
    db.session.commit()
    
    flash(_('مبروك! تم شراء %(name)s للعصابة.', name=asset_template.name), 'success')
    return redirect(url_for('gang.view', gang_id=gang.id))

@bp.route('/my_properties')
@login_required
def my_properties():
    assets = Asset.query.filter_by(owner_id=current_user.id).all()
    return render_template('my_properties.html', assets=assets)
