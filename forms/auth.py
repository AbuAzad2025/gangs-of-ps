from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional
from flask_babel import lazy_gettext as _l
from models import User


class LoginForm(FlaskForm):
    username = StringField(_l('اسم المستخدم'), validators=[DataRequired()])
    password = PasswordField(_l('كلمة المرور'), validators=[DataRequired()])
    captcha = StringField(_l('رمز التحقق'), validators=[Optional()])
    remember_me = BooleanField(_l('تذكرني'))
    submit = SubmitField(_l('تسجيل الدخول'))


class RegistrationForm(FlaskForm):
    username = StringField(_l('اسم المستخدم'), validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField(_l('كلمة المرور'), validators=[
        DataRequired(),
        Length(min=8, message=_l('كلمة المرور يجب أن تكون 8 خانات على الأقل')),
    ])
    confirm_password = PasswordField(_l('تأكيد كلمة المرور'), validators=[DataRequired(), EqualTo('password')])
    captcha = StringField(_l('رمز التحقق'), validators=[DataRequired()])
    submit = SubmitField(_l('إنشاء حساب جديد'))

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError(_l('هذا الاسم مستخدم بالفعل. الرجاء اختيار اسم آخر.'))
