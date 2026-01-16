from flask_wtf import FlaskForm
from wtforms import SubmitField
from flask_babel import lazy_gettext as _l


class AttackForm(FlaskForm):
    submit = SubmitField(_l('هجوم!'))


class HealForm(FlaskForm):
    submit = SubmitField(_l('علاج'))
