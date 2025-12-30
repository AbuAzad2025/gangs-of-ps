from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_babel import lazy_gettext as _l

class CreateTopicForm(FlaskForm):
    title = StringField(_l('عنوان الموضوع'), validators=[DataRequired(), Length(min=5, max=100)])
    content = TextAreaField(_l('محتوى الموضوع'), validators=[DataRequired(), Length(min=10)])
    submit = SubmitField(_l('نشر الموضوع'))

class ReplyForm(FlaskForm):
    content = TextAreaField(_l('الرد'), validators=[DataRequired(), Length(min=2)])
    submit = SubmitField(_l('إرسال الرد'))
