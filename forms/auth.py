from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, DateField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional, Email
from flask_babel import lazy_gettext as _l
from models import User


class LoginForm(FlaskForm):
    username = StringField(_l('اسم المستخدم'), validators=[DataRequired()])
    password = PasswordField(_l('كلمة المرور'), validators=[DataRequired()])
    captcha = StringField(_l('رمز التحقق'), validators=[Optional()])
    remember_me = BooleanField(_l('تذكرني'))
    submit = SubmitField(_l('تسجيل الدخول'))


class RegistrationForm(FlaskForm):
    username = StringField(
        _l('اسم المستخدم'), validators=[
            DataRequired(), Length(
                min=2, max=20)])
    email = StringField(
        _l('البريد الإلكتروني (اختياري - لاستعادة كلمة المرور)'),
        validators=[Optional(), Email(message=_l('بريد إلكتروني غير صالح'))])
    birthdate = DateField(
        _l('تاريخ الميلاد'),
        validators=[
            DataRequired()],
        format='%Y-%m-%d')
    playstyle = SelectField(
        _l('أسلوبك'),
        choices=[
            ('fighter', _l('مقاتل')),
            ('trader', _l('تاجر')),
            ('planner', _l('مخطط')),
        ],
        default='fighter',
        validators=[DataRequired()],
    )
    password = PasswordField(_l('كلمة المرور'), validators=[
        DataRequired(),
        Length(min=8, message=_l('كلمة المرور يجب أن تكون 8 خانات على الأقل')),
    ])
    confirm_password = PasswordField(
        _l('تأكيد كلمة المرور'), validators=[
            DataRequired(), EqualTo('password')])
    captcha = StringField(_l('رمز التحقق'), validators=[DataRequired()])
    submit = SubmitField(_l('إنشاء حساب جديد'))

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError(
                _l('هذا الاسم مستخدم بالفعل. الرجاء اختيار اسم آخر.'))

    def validate_email(self, email):
        if email.data:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError(
                    _l('هذا البريد مستخدم بالفعل.'))


class ForgotPasswordForm(FlaskForm):
    email = StringField(
        _l('البريد الإلكتروني'),
        validators=[DataRequired(), Email(message=_l('بريد إلكتروني غير صالح'))])
    submit = SubmitField(_l('إرسال رابط الاستعادة'))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('كلمة المرور الجديدة'), validators=[
        DataRequired(),
        Length(min=8, message=_l('كلمة المرور يجب أن تكون 8 خانات على الأقل')),
    ])
    confirm_password = PasswordField(
        _l('تأكيد كلمة المرور'), validators=[
            DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('تحديث كلمة المرور'))
