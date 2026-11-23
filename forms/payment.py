from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from flask_babel import lazy_gettext as _l


class ManualPaymentForm(FlaskForm):
    amount_usd = SelectField(_l('قيمة الشحن (دولار)'), choices=[
        ('10', _l('10$ - 300 ماسة')),
        ('20', _l('20$ - 650 ماسة')),
        ('50', _l('50$ - 1700 ماسة')),
        ('other', _l('أخرى (حدد المبلغ أدناه)'))
    ], validators=[DataRequired()])
    custom_amount = IntegerField(
        _l('المبلغ بالدولار (لخيار أخرى)'),
        validators=[Optional(), NumberRange(min=10, max=1000)],
    )

    payment_method = SelectField(_l('طريقة الدفع'), choices=[
        ('bank', _l('تحويل بنكي (البنك الوطني/فلسطين)')),
        ('wallet_jawwal', _l('محفظة جوال باي')),
        ('wallet_palpay', _l('محفظة بنك فلسطين')),
        ('contact', _l('تواصل مباشر (واتساب)'))
    ], validators=[DataRequired()])

    payment_proof = TextAreaField(
        _l('تفاصيل التحويل (رقم الحوالة/المرسل)'),
        validators=[
            DataRequired(),
            Length(
                min=10,
                max=500)])

    submit = SubmitField(_l('إرسال إشعار الدفع'))
