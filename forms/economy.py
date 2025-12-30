from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from flask_babel import lazy_gettext as _l

class SendMoneyForm(FlaskForm):
    username = StringField(_l('اسم المستلم'), validators=[DataRequired()])
    amount = IntegerField(_l('المبلغ'), validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField(_l('تحويل الأموال'))

class DepositForm(FlaskForm):
    amount = IntegerField(_l('المبلغ'), validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField(_l('إيداع في البنك'))
