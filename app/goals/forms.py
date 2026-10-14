from datetime import date, timedelta
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length
from app.transactions.forms import PAYMENT_METHODS

FREQUENCY_CHOICES = [
    ('weekly', 'Weekly (Every 7 days)'),
    ('monthly', 'Monthly (Same day each month)'),
    ('yearly', 'Yearly (Once per year)'),
]

class SavingsGoalForm(FlaskForm):
    title = StringField('Goal Title', validators=[DataRequired(), Length(min=3, max=128)])
    target_amount = DecimalField('Target Savings Amount', places=2, validators=[
        DataRequired(),
        NumberRange(min=1.00, message='Target amount must be at least 1.00.')
    ])
    current_amount = DecimalField('Starting Amount', places=2, default=0.00, validators=[
        NumberRange(min=0.00, message='Starting amount cannot be negative.')
    ])
    target_date = DateField('Target Completion Date', default=lambda: date.today() + timedelta(days=90), validators=[DataRequired()])
    submit = SubmitField('Save Goal')

class DepositGoalForm(FlaskForm):
    deposit_amount = DecimalField('Deposit Amount', places=2, validators=[
        DataRequired(),
        NumberRange(min=0.01, message='Deposit must be at least 0.01.')
    ])
    submit = SubmitField('Add Funds')

class RecurringExpenseForm(FlaskForm):
    description = StringField('Subscription / Expense Description', validators=[DataRequired(), Length(min=2, max=255)])
    amount = DecimalField('Amount', places=2, validators=[
        DataRequired(),
        NumberRange(min=0.01, message='Amount must be greater than zero.')
    ])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    frequency = SelectField('Billing Frequency', choices=FREQUENCY_CHOICES, default='monthly', validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=PAYMENT_METHODS, default='Credit Card', validators=[DataRequired()])
    next_due_date = DateField('Next Billing / Due Date', default=date.today, validators=[DataRequired()])
    submit = SubmitField('Save Recurring Template')
