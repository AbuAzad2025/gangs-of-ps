from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models.user import User
from models import UserLog
from datetime import datetime, timezone
from decorators import check_maintenance, player_only
from services.resource_service import ResourceService

bp = Blueprint('bank', __name__, url_prefix='/bank')

@bp.route('/')
@login_required
def index():
    return render_template('bank.html', user=current_user)

@bp.route('/deposit', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def deposit():
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('jail.index'))
            
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('gym.index'))

    amount = int(request.form.get('amount', 0))
    
    if amount <= 0:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('bank.index'))
        
    if current_user.money < amount:
        flash(_('لا تملك مالاً كافياً للإيداع!'), 'danger')
        return redirect(url_for('bank.index'))
        
    # Atomic Update using ResourceService (logs before/after)
    if not ResourceService.modify_resources(
        current_user.id, 
        {'money': -amount, 'bank_balance': amount}, 
        'bank_deposit', 
        auto_commit=True
    ):
        flash(_('لا تملك مالاً كافياً للإيداع!'), 'danger')
        return redirect(url_for('bank.index'))
    
    flash(_('تم إيداع %(amount)s في البنك.', amount=amount), 'success')
    return redirect(url_for('bank.index'))

@bp.route('/withdraw', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def withdraw():
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('jail.index'))
            
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('gym.index'))

    amount = int(request.form.get('amount', 0))
    
    if amount <= 0:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('bank.index'))
        
    if current_user.bank_balance < amount:
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        return redirect(url_for('bank.index'))
        
    # Atomic Update using ResourceService (logs before/after)
    # Check bank_balance explicitly in ResourceService call via check_balance logic
    # Note: ResourceService checks balance for negative changes.
    # Here we decrement bank_balance, so it will check if bank_balance >= amount.
    if not ResourceService.modify_resources(
        current_user.id, 
        {'bank_balance': -amount, 'money': amount}, 
        'bank_withdraw', 
        auto_commit=True
    ):
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        return redirect(url_for('bank.index'))
    
    flash(_('تم سحب %(amount)s من البنك.', amount=amount), 'success')
    return redirect(url_for('bank.index'))

@bp.route('/transfer', methods=['POST'])
@login_required
@check_maintenance('transfers')
@player_only
@limiter.limit("5 per hour")
def transfer():
    # Status Check
    now = datetime.now(timezone.utc)
    if current_user.jail_until:
        jail_until = current_user.jail_until
        if jail_until.tzinfo is None:
            jail_until = jail_until.replace(tzinfo=timezone.utc)
        if jail_until > now:
            flash(_('أنت في السجن ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('jail.index'))
            
    if current_user.hospital_until:
        hospital_until = current_user.hospital_until
        if hospital_until.tzinfo is None:
            hospital_until = hospital_until.replace(tzinfo=timezone.utc)
        if hospital_until > now:
            flash(_('أنت في المستشفى ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('hospital.index'))
            
    if current_user.gym_until:
        gym_until = current_user.gym_until
        if gym_until.tzinfo is None:
            gym_until = gym_until.replace(tzinfo=timezone.utc)
        if gym_until > now:
            flash(_('أنت تتدرب ولا يمكنك استخدام البنك!'), 'danger')
            return redirect(url_for('gym.index'))

    recipient_name = request.form.get('recipient')
    amount = int(request.form.get('amount', 0))
    
    if not recipient_name:
        flash(_('يجب تحديد اسم المستلم!'), 'danger')
        return redirect(url_for('bank.index'))
        
    if amount <= 0:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('bank.index'))
        
    if current_user.bank_balance < amount:
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        return redirect(url_for('bank.index'))
        
    recipient = User.query.filter_by(username=recipient_name).first()
    
    if not recipient:
        flash(_('المستخدم غير موجود!'), 'danger')
        return redirect(url_for('bank.index'))
        
    if recipient.id == current_user.id:
        flash(_('لا يمكنك التحويل لنفسك!'), 'danger')
        return redirect(url_for('bank.index'))
        
    # Atomic Update using ResourceService
    # 1. Deduct from sender
    if not ResourceService.modify_resources(
        current_user.id, 
        {'bank_balance': -amount}, 
        f'bank_transfer_sent_to_{recipient.id}', 
        auto_commit=False
    ):
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        db.session.rollback()
        return redirect(url_for('bank.index'))

    # 2. Add to recipient
    if not ResourceService.modify_resources(
        recipient.id, 
        {'bank_balance': amount}, 
        f'bank_transfer_received_from_{current_user.id}', 
        auto_commit=False
    ):
        # Should not happen unless recipient deleted or locked?
        db.session.rollback()
        flash(_('حدث خطأ أثناء التحويل!'), 'danger')
        return redirect(url_for('bank.index'))
    
    db.session.commit()
    
    flash(_('تم تحويل %(amount)s إلى %(name)s بنجاح.', amount=amount, name=recipient.username), 'success')
    return redirect(url_for('bank.index'))
