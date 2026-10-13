import calendar
from datetime import date
from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional

MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]

def current_year_choices():
    current_year = date.today().year
    return [(y, str(y)) for y in range(current_year - 1, current_year + 3)]

class BudgetForm(FlaskForm):
    category_id = SelectField('Budget Scope / Category', coerce=int, validators=[Optional()])
    monthly_limit = DecimalField('Monthly Limit', places=2, validators=[
        DataRequired(message='Please specify a budget limit amount.'),
        NumberRange(min=1.00, message='Budget limit must be at least 1.00.')
    ])
    month = SelectField('Month', coerce=int, choices=MONTH_CHOICES, default=date.today().month, validators=[DataRequired()])
    year = SelectField('Year', coerce=int, choices=current_year_choices(), default=date.today().year, validators=[DataRequired()])
    submit = SubmitField('Save Budget')
