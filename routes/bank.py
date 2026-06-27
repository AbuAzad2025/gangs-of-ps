from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models.user import User
from datetime import datetime, timezone
from utils.decorators import check_maintenance, player_only
from services.resource_service import ResourceService
from routes.utils import track_academy_visit, update_daily_task_progress

bp = Blueprint('bank', __name__, url_prefix='/bank')


@bp.route('/')
@login_required
def index():
    from services.economy_academy import (
        compute_economy_health,
        get_lesson_for_day,
        preview_bank_fee,
    )
    from routes.utils import get_onboarding_day

    track_academy_visit(current_user, 'bank_visit')
    onboarding_day = get_onboarding_day(current_user)
    lesson = get_lesson_for_day(1) if onboarding_day == 1 else None
    return render_template(
        'bank.html',
        user=current_user,
        economy_health=compute_economy_health(current_user),
        bank_fee_preview=preview_bank_fee(current_user.bank_balance or 0),
        academy_lesson=lesson,
    )


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

    try:
        amount = int(request.form.get('amount', 0))
    except ValueError:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('bank.index'))

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
    update_daily_task_progress(current_user, 'bank_deposit')
    return redirect(url_for('bank.index', fx='deposit', amt=amount))


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
    # Here we decrement bank_balance, so it will check if bank_balance >=
    # amount.
    if not ResourceService.modify_resources(
        current_user.id,
        {'bank_balance': -amount, 'money': amount},
        'bank_withdraw',
        auto_commit=True
    ):
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        return redirect(url_for('bank.index'))

    flash(_('تم سحب %(amount)s من البنك.', amount=amount), 'success')
    return redirect(url_for('bank.index', fx='withdraw', amt=amount))


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
    try:
        amount = int(request.form.get('amount', 0))
    except ValueError:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('bank.index'))

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

    # Prevent Deadlock: Lock users in ID order (consistent locking order)
    # This ensures that if A sends to B and B sends to A simultaneously,
    # both threads will try to lock the lower ID first, preventing deadlock.
    first_id = min(current_user.id, recipient.id)
    second_id = max(current_user.id, recipient.id)

    # We must lock both before modifying any to avoid deadlock waiting
    # Note: We don't use the result here, just acquiring the row lock for the
    # transaction.
    db.session.query(User).filter_by(id=first_id).with_for_update().first()
    db.session.query(User).filter_by(id=second_id).with_for_update().first()

    # Atomic Update using ResourceService
    # 1. Deduct from sender
    if not ResourceService.modify_resources(
        current_user.id,
        {'bank_balance': -amount},
        f'bank_transfer_sent_to_{recipient.id}',
        auto_commit=False,
        expected_version=None
    ):
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        db.session.rollback()
        return redirect(url_for('bank.index'))

    # 2. Add to recipient
    if not ResourceService.modify_resources(
        recipient.id,
        {'bank_balance': amount},
        f'bank_transfer_received_from_{current_user.id}',
        auto_commit=False,
        expected_version=None
    ):
        # Should not happen unless recipient deleted or locked?
        db.session.rollback()
        flash(_('حدث خطأ أثناء التحويل!'), 'danger')
        return redirect(url_for('bank.index'))

    db.session.commit()

    flash(_('تم تحويل %(amount)s إلى %(name)s بنجاح.',
          amount=amount, name=recipient.username), 'success')
    return redirect(url_for('bank.index', fx='transfer', amt=amount))
