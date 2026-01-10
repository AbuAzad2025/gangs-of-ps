from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db, limiter
from flask_babel import _
from models import Bounty, User
from sqlalchemy import func, select
from services.resource_service import ResourceService
from datetime import datetime, timezone

bp = Blueprint('bounties', __name__, url_prefix='/bounties')

@bp.route('/')
@login_required
def index():
    # Group bounties by target
    # This query might need adjustment depending on exact needs, but getting all bounties is a start
    bounties = Bounty.query.order_by(Bounty.amount.desc()).limit(50).all()
    return render_template('bounties.html', bounties=bounties)

@bp.route('/place', methods=['POST'])
@login_required
def place():
    username = request.form.get('username')
    amount = request.form.get('amount', type=int)
    is_anonymous = request.form.get('anonymous') == 'on'

    if not username or not amount:
        flash(_('يرجى ملء جميع الحقول!'), 'danger')
        return redirect(url_for('bounties.index'))

    if amount <= 0:
        flash(_('يجب أن يكون المبلغ أكبر من صفر!'), 'danger')
        return redirect(url_for('bounties.index'))

    if current_user.money < amount:
        flash(_('ليس لديك مال كافٍ!'), 'danger')
        return redirect(url_for('bounties.index'))

    target = User.query.filter_by(username=username).first()
    if not target:
        flash(_('المستخدم غير موجود!'), 'danger')
        return redirect(url_for('bounties.index'))

    if target.id == current_user.id:
        flash(_('لا يمكنك وضع مكافأة على نفسك!'), 'danger')
        return redirect(url_for('bounties.index'))

    # Atomic Deduction
    if not ResourceService.modify_resources(current_user.id, {'money': -amount}, 'place_bounty', auto_commit=False, expected_version=None):
        flash(_('ليس لديك مال كافٍ!'), 'danger')
        return redirect(url_for('bounties.index'))
    
    # Create bounty
    bounty = Bounty(
        placer_id=current_user.id,
        target_id=target.id,
        amount=amount,
        is_anonymous=is_anonymous
    )
    db.session.add(bounty)
    db.session.commit()

    flash(_('تم وضع المكافأة بنجاح!'), 'success')
    return redirect(url_for('bounties.index'))

@bp.route('/buy_off/<int:bounty_id>', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def buy_off(bounty_id):
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك إزالة المكافآت!'), 'danger')
            return redirect(url_for('jail.index'))
    
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك إزالة المكافآت!'), 'danger')
            return redirect(url_for('hospital.index'))

    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك إزالة المكافآت!'), 'danger')
            return redirect(url_for('gym.index'))

    bounty = db.session.get(Bounty, bounty_id)
    if not bounty:
        abort(404)
    
    # Only the target can buy off the bounty? Or anyone? 
    # Usually the target bribes to remove it.
    if bounty.target_id != current_user.id:
        flash(_('يمكنك فقط إزالة المكافآت الموضوعة عليك!'), 'danger')
        return redirect(url_for('bounties.index'))

    # Lock user to prevent race conditions (Global Lock Order: User -> Bounty)
    db.session.query(User).filter_by(id=current_user.id).with_for_update().first()

    # Lock Bounty
    bounty = db.session.query(Bounty).filter_by(id=bounty_id).with_for_update().first()
    if not bounty:
        flash(_('المكافأة لم تعد موجودة!'), 'warning')
        return redirect(url_for('bounties.index'))

    if current_user.money < bounty.amount:
        flash(_('ليس لديك مال كافٍ لإزالة المكافأة!'), 'danger')
        return redirect(url_for('bounties.index'))

    # Atomic Deduction
    if not ResourceService.modify_resources(current_user.id, {'money': -bounty.amount}, 'buy_off_bounty', auto_commit=False, expected_version=None):
        db.session.rollback()
        flash(_('ليس لديك مال كافٍ لإزالة المكافأة!'), 'danger')
        return redirect(url_for('bounties.index'))

    db.session.delete(bounty)
    db.session.commit()

    flash(_('تمت إزالة المكافأة بنجاح!'), 'success')
    return redirect(url_for('bounties.index'))
