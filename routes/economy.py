from flask import render_template, redirect, url_for, flash, Blueprint, abort
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db
from models import Asset, Gang
from datetime import datetime, timezone

bp = Blueprint('economy', __name__, url_prefix='/economy')

@bp.route('/properties')
@login_required
def properties():
    # Show only unowned properties (templates) that are active
    assets = Asset.query.filter_by(type='house', owner_id=None, gang_id=None, is_active=True).all()
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

    asset = db.session.get(Asset, asset_id)
    if not asset:
        abort(404)
    
    if asset.owner_id != current_user.id:
        flash(_('هذا العقار ليس ملكك!'), 'danger')
        return redirect(url_for('economy.my_properties'))
        
    if not asset.can_collect:
        flash(_('لم يحن موعد جمع الدخل بعد!'), 'warning')
        return redirect(url_for('economy.my_properties'))
        
    # Give money
    current_user.money += asset.income
    asset.last_collected = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    
    flash(_('تم جمع الدخل %(amount)s $ من %(name)s بنجاح!', amount=asset.income, name=asset.name), 'success')
    return redirect(url_for('economy.my_properties'))

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
        
    # Deduct money
    current_user.money -= asset_template.value
    
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
    if not current_user.gang_id:
        flash(_('أنت لست في عصابة!'), 'danger')
        return redirect(url_for('economy.properties'))
        
    gang = db.session.get(Gang, current_user.gang_id)
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
