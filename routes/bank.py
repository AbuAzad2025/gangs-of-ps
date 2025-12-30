from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models.user import User
from datetime import datetime, timezone

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
        
    # Atomic Update using explicit update queries to prevent race conditions
    User.query.filter_by(id=current_user.id).update({'money': User.money - amount, 'bank_balance': User.bank_balance + amount})
    db.session.commit()
    
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
        
    # Atomic Update
    User.query.filter_by(id=current_user.id).update({'bank_balance': User.bank_balance - amount, 'money': User.money + amount})
    db.session.commit()
    
    flash(_('تم سحب %(amount)s من البنك.', amount=amount), 'success')
    return redirect(url_for('bank.index'))

@bp.route('/transfer', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
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
        
    # Atomic Update
    User.query.filter_by(id=current_user.id).update({'bank_balance': User.bank_balance - amount})
    User.query.filter_by(id=recipient.id).update({'bank_balance': User.bank_balance + amount})
    db.session.commit()
    
    flash(_('تم تحويل %(amount)s إلى %(name)s بنجاح.', amount=amount, name=recipient.username), 'success')
    return redirect(url_for('bank.index'))
