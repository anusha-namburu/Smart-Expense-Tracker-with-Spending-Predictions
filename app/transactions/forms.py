from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Length

PAYMENT_METHODS = [
    ('Cash', 'Cash'),
    ('Credit Card', 'Credit Card'),
    ('Debit Card', 'Debit Card'),
    ('Bank Transfer', 'Bank Transfer'),
    ('UPI', 'UPI / Instant Payment'),
    ('Digital Wallet', 'Digital Wallet'),
    ('Other', 'Other'),
]

class TransactionForm(FlaskForm):
    type = SelectField('Type', choices=[('expense', 'Expense'), ('income', 'Income')], default='expense', validators=[DataRequired()])
    amount = DecimalField('Amount', places=2, validators=[
        DataRequired(message='Please enter an amount.'),
        NumberRange(min=0.01, message='Amount must be greater than zero.')
    ])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired(message='Please choose a category.')])
    transaction_date = DateField('Transaction Date', default=date.today, validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=PAYMENT_METHODS, default='Credit Card', validators=[DataRequired()])
    description = StringField('Description / Notes', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Save Transaction')

class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(min=2, max=64)])
    type = SelectField('Type', choices=[('expense', 'Expense'), ('income', 'Income')], default='expense', validators=[DataRequired()])
    icon = SelectField('Icon', choices=[
        ('bi-tag', 'Tag'),
        ('bi-cup-hot', 'Coffee / Dining'),
        ('bi-cart', 'Shopping Cart'),
        ('bi-car-front', 'Vehicle / Transit'),
        ('bi-fuel-pump', 'Fuel'),
        ('bi-house-door', 'Home / Rent'),
        ('bi-receipt', 'Bills / Utilities'),
        ('bi-heart-pulse', 'Healthcare'),
        ('bi-controller', 'Entertainment / Games'),
        ('bi-airplane', 'Travel'),
        ('bi-book', 'Education'),
        ('bi-gift', 'Gifts'),
        ('bi-cash-stack', 'Cash / Salary'),
        ('bi-laptop', 'Freelance / Tech'),
        ('bi-graph-up-arrow', 'Investments'),
    ], default='bi-tag', validators=[DataRequired()])
    color = StringField('Color (Hex)', default='#4e73df', validators=[DataRequired(), Length(min=4, max=7)])
    submit = SubmitField('Create Category')
