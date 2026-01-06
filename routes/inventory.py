from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from extensions import db, limiter
from sqlalchemy import select
from models import UserItem, Item, User
from flask_babel import _
from datetime import datetime, timezone

from services.resource_service import ResourceService

bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@bp.route('/')
@login_required
def index():
    items = UserItem.query.filter_by(user_id=current_user.id).join(Item).filter(UserItem.quantity > 0).all()
    return render_template('inventory.html', items=items)

@bp.route('/equip/<int:item_id>', methods=['POST'])
@login_required
def equip(item_id):
    # Lock User first to prevent deadlocks (User -> UserItem)
    db.session.execute(select(User).where(User.id == current_user.id).with_for_update()).scalar_one()

    # Lock the item row
    user_item = db.session.query(UserItem).filter_by(id=item_id, user_id=current_user.id).with_for_update().first()
    if not user_item:
        abort(404)
    
    if user_item.item.type not in ['weapon', 'armor']:
        flash(_('لا يمكن تجهيز هذا العنصر.'), 'warning')
        return redirect(url_for('inventory.index'))
    
    # Unequip current item of same type (find and lock)
    current_equipped = UserItem.query.join(Item).filter(
        UserItem.user_id == current_user.id,
        UserItem.is_equipped == True,
        Item.type == user_item.item.type
    ).with_for_update().first()
    
    if current_equipped:
        current_equipped.is_equipped = False
        
    user_item.is_equipped = True
    db.session.commit()
    
    flash(_('تم تجهيز %(name)s بنجاح.', name=user_item.item.name), 'success')
    return redirect(url_for('inventory.index'))

@bp.route('/unequip/<int:item_id>', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def unequip(item_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك تغيير عتادك!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك تغيير عتادك!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك تغيير عتادك!'), 'danger')
            return redirect(url_for('gym.index'))

    # Lock User first to prevent deadlocks (User -> UserItem)
    db.session.execute(select(User).where(User.id == current_user.id).with_for_update()).scalar_one()

    # Lock the item row
    user_item = db.session.query(UserItem).filter_by(id=item_id, user_id=current_user.id).with_for_update().first()
    if not user_item:
        abort(404)
    
    if not user_item.is_equipped:
        flash(_('هذا العنصر غير مجهز أصلاً.'), 'warning')
        return redirect(url_for('inventory.index'))
        
    user_item.is_equipped = False
    db.session.commit()
    
    flash(_('تم إلغاء تجهيز %(name)s.', name=user_item.item.name), 'success')
    return redirect(url_for('inventory.index'))

@bp.route('/repair/<int:item_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def repair(item_id):
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إصلاح العتاد!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إصلاح العتاد!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إصلاح العتاد!'), 'danger')
            return redirect(url_for('gym.index'))

    # 1. Read Item (No Lock) to estimate cost
    user_item = db.session.get(UserItem, item_id)
    if not user_item or user_item.user_id != current_user.id:
        abort(404)

    if user_item.item.type not in ['weapon', 'armor']:
        flash(_('يمكن إصلاح الأسلحة والدروع فقط من هنا.'), 'warning')
        return redirect(url_for('inventory.index'))

    if user_item.condition is None or user_item.condition >= 100:
        flash(_('العتاد سليم ولا يحتاج إصلاح.'), 'info')
        return redirect(url_for('inventory.index'))

    damage = 100 - user_item.condition
    base_cost = max(1, user_item.item.cost)
    cost = int(damage * (base_cost * 0.003))
    cost = max(1, cost)
    
    if current_user.money < cost:
        flash(_('تحتاج %(cost)s شيكل لإصلاح العتاد!', cost=cost), 'danger')
        return redirect(url_for('inventory.index'))

    # 1. Lock User first to prevent deadlock (User -> Item)
    db.session.execute(select(User).where(User.id == current_user.id).with_for_update()).scalar_one()

    # 2. Lock Item
    # and ensure consistent lock order (User -> Item) if other routes follow this.
    user_item = db.session.query(UserItem).filter_by(id=item_id, user_id=current_user.id).with_for_update().first()
    
    if not user_item:
        abort(404)
        
    # Verify Condition/Cost again after lock
    current_damage = 100 - (user_item.condition or 100)
    if current_damage <= 0:
        db.session.rollback()
        flash(_('العتاد سليم بالفعل.'), 'info')
        return redirect(url_for('inventory.index'))
        
    # Recalculate cost
    real_cost = int(current_damage * (base_cost * 0.003))
    real_cost = max(1, real_cost)
    
    # 3. Call ResourceService (it will re-lock User, which is fine as we hold the lock)
    if not ResourceService.modify_resources(current_user.id, {'money': -real_cost}, 'repair_item', auto_commit=False, expected_version=None):
         db.session.rollback()
         flash(_('لا تملك كاش كافي!'), 'danger')
         return redirect(url_for('inventory.index'))

    # 3. Update Item
    user_item.condition = 100
    db.session.commit()
    
    flash(_('تم إصلاح %(name)s مقابل %(cost)s$.', name=user_item.item.name, cost=real_cost), 'success')
    return redirect(url_for('inventory.index'))
