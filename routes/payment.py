from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import PaymentTransaction
from forms.payment import ManualPaymentForm
from flask_babel import _
from . import bp
import uuid


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
            _('تم استلام طلبك! سيتم مراجعة الدفع وإضافة الماسات لحسابك قريباً.'),
            'info')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('main.hara'))

    return render_template(
        'buy_diamonds.html',
        title=_('شراء الماس'),
        form=form,
        next_url=next_url)

# Secure or remove the debug route
# @bp.route('/process_payment/<int:amount>')
# @login_required
# def process_payment(amount):
#     ...
