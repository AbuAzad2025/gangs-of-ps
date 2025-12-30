from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_babel import lazy_gettext as _l

class ManualPaymentForm(FlaskForm):
    amount_usd = SelectField(_l('قيمة الشحن (دولار)'), choices=[
        ('5', _l('5$ - 100 ماسة')),
        ('10', _l('10$ - 250 ماسة')),
        ('50', _l('50$ - 1500 ماسة')),
        ('100', _l('100$ - 4000 ماسة'))
    ], validators=[DataRequired()])
    
    payment_method = SelectField(_l('طريقة الدفع'), choices=[
        ('bank', _l('تحويل بنكي (البنك الوطني/فلسطين)')),
        ('wallet_jawwal', _l('محفظة جوال باي')),
        ('wallet_palpay', _l('محفظة بنك فلسطين')),
        ('contact', _l('تواصل مباشر (واتساب)'))
    ], validators=[DataRequired()])
    
    payment_proof = TextAreaField(_l('تفاصيل التحويل (رقم الحوالة/المرسل)'), 
                                  validators=[DataRequired(), Length(min=10, max=500)])
    
    submit = SubmitField(_l('إرسال إشعار الدفع'))
