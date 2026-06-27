import uuid

from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db, csrf
from models import PaymentTransaction
from forms.payment import ManualPaymentForm
from flask_babel import _
from services.resource_service import ResourceService
from services.stripe_service import (
    DIAMOND_PACKAGES,
    create_checkout_session,
    get_publishable_key,
    handle_webhook_payload,
    stripe_enabled,
)
from sqlalchemy.exc import IntegrityError
from services.economy_policy import (
    SUPPORT_WHATSAPP_DISPLAY,
    get_whatsapp_diamond_purchase_url,
)
from . import bp


def _sanitize_next_url(raw: str) -> str:
    next_url = (raw or '').strip()
    if not next_url:
        return ''
    if not next_url.startswith('/'):
        return ''
    if next_url.startswith('//') or next_url.startswith('/\\'):
        return ''
    return next_url


@bp.route('/buy_diamonds', methods=['GET', 'POST'])
@login_required
def buy_diamonds():
    next_url = _sanitize_next_url(request.args.get(
        'next') or request.form.get('next') or '')
    form = ManualPaymentForm()
    if form.validate_on_submit():
        amount = int(form.amount_usd.data)
        diamonds_map = {
            5: 100,
            10: 250,
            50: 1500,
            100: 4000
        }
        diamonds = diamonds_map.get(amount, 0)

        trans_id = str(uuid.uuid4())
        transaction = PaymentTransaction(
            user_id=current_user.id,
            amount_usd=float(amount),
            diamonds_amount=diamonds,
            transaction_id=trans_id,
            status='pending',
            payment_method=form.payment_method.data,
            payment_proof=form.payment_proof.data,
            is_verified=False
        )

        db.session.add(transaction)
        db.session.commit()

        flash(
            _('تم استلام طلبك! راسل المطور على واتساب لتسريع التأكيد وإضافة الماس.'),
            'info')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('main.hara'))

    stripe_msg = None
    if request.args.get('stripe') == 'success':
        stripe_msg = _('تم الدفع! ستُضاف الماسات خلال ثوانٍ بعد تأكيد Stripe.')
    elif request.args.get('stripe') == 'cancel':
        stripe_msg = _('تم إلغاء الدفع.')

    wa_url = get_whatsapp_diamond_purchase_url(
        current_user.username,
        int(form.amount_usd.data) if form.amount_usd.data else None,
    ) if current_user.is_authenticated else get_whatsapp_diamond_purchase_url('')

    return render_template(
        'buy_diamonds.html',
        title=_('شراء الماس'),
        form=form,
        next_url=next_url,
        stripe_enabled=stripe_enabled(),
        stripe_publishable_key=get_publishable_key(),
        diamond_packages=DIAMOND_PACKAGES,
        stripe_message=stripe_msg,
        whatsapp_url=wa_url,
        whatsapp_display=SUPPORT_WHATSAPP_DISPLAY,
    )


@bp.route('/stripe/checkout', methods=['POST'])
@login_required
def stripe_checkout():
    if not stripe_enabled():
        flash(_('الدفع الإلكتروني غير مفعّل حالياً.'), 'warning')
        return redirect(url_for('main.buy_diamonds'))

    package_key = (request.form.get('package') or '').strip()
    next_url = _sanitize_next_url(request.form.get('next') or '')
    success_url = url_for('main.buy_diamonds', _external=True)
    cancel_url = url_for('main.buy_diamonds', _external=True)

    checkout_url, err = create_checkout_session(
        current_user.id,
        package_key,
        success_url,
        cancel_url,
    )
    if err or not checkout_url:
        flash(_('تعذّر بدء الدفع: %(err)s', err=err or _('خطأ غير معروف')), 'danger')
        return redirect(url_for('main.buy_diamonds', next=next_url))

    return redirect(checkout_url)


@bp.route('/stripe/webhook', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    if not stripe_enabled():
        return {'ok': False}, 400

    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    result = handle_webhook_payload(payload, sig)
    if not result.get('ok'):
        current_app.logger.warning("Stripe webhook error: %s", result.get('error'))
        return {'ok': False}, 400
    if result.get('ignored'):
        return {'ok': True}, 200

    user_id = int(result.get('user_id') or 0)
    diamonds = int(result.get('diamonds') or 0)
    if user_id <= 0 or diamonds <= 0:
        return {'ok': False, 'error': 'invalid metadata'}, 400

    session_id = result.get('session_id') or ''
    if not session_id:
        return {'ok': False, 'error': 'missing session_id'}, 400

    existing = PaymentTransaction.query.filter_by(
        transaction_id=session_id,
    ).first()
    if existing and existing.is_verified:
        return {'ok': True}, 200

    try:
        tx = PaymentTransaction(
            user_id=user_id,
            amount_usd=float(result.get('amount_usd') or 0),
            diamonds_amount=diamonds,
            transaction_id=session_id,
            status='processing',
            payment_method='stripe',
            payment_proof='stripe webhook',
            is_verified=False,
        )
        db.session.add(tx)
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        dup = PaymentTransaction.query.filter_by(transaction_id=session_id).first()
        if dup and dup.is_verified:
            return {'ok': True}, 200
        current_app.logger.warning(
            'Stripe webhook duplicate race for session %s', session_id)
        return {'ok': True}, 200

    if not ResourceService.modify_resources(
        user_id,
        {'diamonds': diamonds},
        'stripe_checkout',
        auto_commit=False,
        expected_version=None,
    ):
        db.session.rollback()
        return {'ok': False}, 500

    tx.status = 'completed'
    tx.is_verified = True
    db.session.commit()
    return {'ok': True}, 200

# Secure or remove the debug route
# @bp.route('/process_payment/<int:amount>')
# @login_required
# def process_payment(amount):
#     ...
