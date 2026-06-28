from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
from extensions import db, limiter
from models.user import User
from datetime import datetime, timezone
from utils.decorators import check_maintenance, player_only
from services.resource_service import ResourceService
from services.economy_integrity import parse_bank_amount
from routes.utils import track_academy_visit, update_daily_task_progress

bp = Blueprint('bank', __name__, url_prefix='/bank')


def _parse_amount(raw) -> int | None:
    return parse_bank_amount(raw, min_value=1)


def _bank_blocked_redirect():
    """Disaster recovery: status checks return user to the correct blocking screen."""
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
    return None


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
    blocked = _bank_blocked_redirect()
    if blocked:
        return blocked

    amount = _parse_amount(request.form.get('amount', 0))
    if amount is None:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('bank.index'))

    if current_user.money < amount:
        flash(_('لا تملك مالاً كافياً للإيداع!'), 'danger')
        return redirect(url_for('bank.index'))

    if not ResourceService.modify_resources(
        current_user.id,
        {'money': -amount, 'bank_balance': amount},
        'bank_deposit',
        auto_commit=False,
    ):
        db.session.rollback()
        flash(_('لا تملك مالاً كافياً للإيداع!'), 'danger')
        return redirect(url_for('bank.index'))

    try:
        user_ref = db.session.get(User, current_user.id)
        update_daily_task_progress(user_ref, 'bank_deposit')
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_('حدث خطأ أثناء الإيداع. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('bank.index'))
    flash(_('تم إيداع %(amount)s في البنك.', amount=amount), 'success')
    return redirect(url_for('bank.index', fx='deposit', amt=amount))


@bp.route('/withdraw', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def withdraw():
    blocked = _bank_blocked_redirect()
    if blocked:
        return blocked

    amount = _parse_amount(request.form.get('amount', 0))
    if amount is None:
        flash(_('مبلغ غير صالح!'), 'danger')
        return redirect(url_for('bank.index'))

    if current_user.bank_balance < amount:
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        return redirect(url_for('bank.index'))

    if not ResourceService.modify_resources(
        current_user.id,
        {'bank_balance': -amount, 'money': amount},
        'bank_withdraw',
        auto_commit=False,
    ):
        db.session.rollback()
        flash(_('رصيدك في البنك غير كافٍ!'), 'danger')
        return redirect(url_for('bank.index'))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_('حدث خطأ أثناء السحب. حاول مرة أخرى.'), 'danger')
        return redirect(url_for('bank.index'))

    flash(_('تم سحب %(amount)s من البنك.', amount=amount), 'success')
    return redirect(url_for('bank.index', fx='withdraw', amt=amount))


@bp.route('/transfer', methods=['POST'])
@login_required
@check_maintenance('transfers')
@player_only
@limiter.limit("5 per hour")
def transfer():
    blocked = _bank_blocked_redirect()
    if blocked:
        return blocked

    recipient_name = (request.form.get('recipient') or '').strip()
    amount = _parse_amount(request.form.get('amount', 0))

    if not recipient_name:
        flash(_('يجب تحديد اسم المستلم!'), 'danger')
        return redirect(url_for('bank.index'))

    if amount is None:
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

    if not ResourceService.transfer_bank_balance(current_user.id, recipient.id, amount):
        flash(_('حدث خطأ أثناء التحويل!'), 'danger')
        return redirect(url_for('bank.index'))

    flash(_('تم تحويل %(amount)s إلى %(name)s بنجاح.',
          amount=amount, name=recipient.username), 'success')
    return redirect(url_for('bank.index', fx='transfer', amt=amount))
