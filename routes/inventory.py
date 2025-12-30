from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from extensions import db
from models import UserItem, Item
from flask_babel import _
from datetime import datetime, timezone

bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@bp.route('/')
@login_required
def index():
    items = UserItem.query.filter_by(user_id=current_user.id).join(Item).filter(UserItem.quantity > 0).all()
    return render_template('inventory.html', items=items)

@bp.route('/equip/<int:item_id>', methods=['POST'])
@login_required
def equip(item_id):
    user_item = UserItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    
    if user_item.item.type not in ['weapon', 'armor']:
        flash(_('لا يمكن تجهيز هذا العنصر.'), 'warning')
        return redirect(url_for('inventory.index'))
    
    # Unequip current item of same type
    current_equipped = UserItem.query.join(Item).filter(
        UserItem.user_id == current_user.id,
        UserItem.is_equipped == True,
        Item.type == user_item.item.type
    ).first()
    
    if current_equipped:
        current_equipped.is_equipped = False
        
    user_item.is_equipped = True
    db.session.commit()
    
    flash(_('تم تجهيز %(name)s بنجاح.', name=user_item.item.name), 'success')
    return redirect(url_for('inventory.index'))

@bp.route('/unequip/<int:item_id>', methods=['POST'])
@login_required
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

    user_item = UserItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    
    if not user_item.is_equipped:
        flash(_('هذا العنصر غير مجهز أصلاً.'), 'warning')
        return redirect(url_for('inventory.index'))
        
    user_item.is_equipped = False
    db.session.commit()
    
    flash(_('تم إلغاء تجهيز %(name)s.', name=user_item.item.name), 'success')
    return redirect(url_for('inventory.index'))

@bp.route('/repair/<int:item_id>', methods=['POST'])
@login_required
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

    user_item = db.session.get(UserItem, item_id)
    if not user_item:
        abort(404)
    if user_item.user_id != current_user.id:
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

    current_user.money -= cost
    user_item.condition = 100
    db.session.commit()

    flash(_('تم إصلاح %(name)s وأصبح كالجديد.', name=user_item.item.name), 'success')
    return redirect(url_for('inventory.index'))
