from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import PaymentTransaction
from forms.payment import ManualPaymentForm
from flask_babel import _
from . import bp
import uuid

@bp.route('/buy_diamonds', methods=['GET', 'POST'])
@login_required
def buy_diamonds():
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
        
        flash(_('تم استلام طلبك! سيتم مراجعة الدفع وإضافة الماسات لحسابك قريباً.'), 'info')
        return redirect(url_for('main.hara')) # Redirect to dashboard
        
    return render_template('buy_diamonds.html', title=_('شراء الماس'), form=form)

# Secure or remove the debug route
# @bp.route('/process_payment/<int:amount>')
# @login_required
# def process_payment(amount):
#     ...
