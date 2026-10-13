from datetime import datetime, date
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, Index
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    currency = db.Column(db.String(10), default='$', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    transactions = db.relationship('Transaction', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    custom_categories = db.relationship('Category', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    savings_goals = db.relationship('SavingsGoal', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    recurring_expenses = db.relationship('RecurringExpense', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.email})>'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    name = db.Column(db.String(64), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'expense' or 'income'
    icon = db.Column(db.String(64), default='bi-tag', nullable=False)
    color = db.Column(db.String(16), default='#6c757d', nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    transactions = db.relationship('Transaction', backref='category', lazy='dynamic')
    budgets = db.relationship('Budget', backref='category', lazy='dynamic')
    recurring_expenses = db.relationship('RecurringExpense', backref='category', lazy='dynamic')

    __table_args__ = (
        UniqueConstraint('user_id', 'name', 'type', name='uq_user_category_name_type'),
    )

    def __repr__(self):
        return f'<Category {self.name} ({self.type})>'


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='RESTRICT'), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2, asdecimal=True), nullable=False)
    type = db.Column(db.String(10), nullable=False, index=True)  # 'income' or 'expense'
    description = db.Column(db.String(255), nullable=True)
    transaction_date = db.Column(db.Date, nullable=False, index=True)
    payment_method = db.Column(db.String(50), default='Cash', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_user_transaction_date', 'user_id', 'transaction_date'),
        Index('idx_user_type_date', 'user_id', 'type', 'transaction_date'),
    )

    @property
    def amount_float(self):
        return float(self.amount) if self.amount is not None else 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'amount': float(self.amount),
            'type': self.type,
            'category': self.category.name if self.category else 'Uncategorized',
            'category_color': self.category.color if self.category else '#6c757d',
            'category_icon': self.category.icon if self.category else 'bi-tag',
            'description': self.description or '',
            'transaction_date': self.transaction_date.isoformat(),
            'payment_method': self.payment_method,
            'created_at': self.created_at.isoformat()
        }

    def __repr__(self):
        return f'<Transaction {self.id}: {self.type} {self.amount} on {self.transaction_date}>'


class Budget(db.Model):
    __tablename__ = 'budgets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True, index=True)
    monthly_limit = db.Column(db.Numeric(12, 2, asdecimal=True), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1 to 12
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'category_id', 'month', 'year', name='uq_user_cat_month_year'),
    )

    @property
    def is_overall(self):
        return self.category_id is None

    @property
    def limit_float(self):
        return float(self.monthly_limit) if self.monthly_limit is not None else 0.0

    def __repr__(self):
        cat_str = self.category.name if self.category else 'Overall'
        return f'<Budget {cat_str} {self.year}-{self.month:02d}: {self.monthly_limit}>'


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(32), default='info', nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    dedup_key = db.Column(db.String(128), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'dedup_key', name='uq_user_dedup_key'),
    )

    def __repr__(self):
        return f'<Notification {self.title} (read={self.is_read})>'


class SavingsGoal(db.Model):
    __tablename__ = 'savings_goals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(128), nullable=False)
    target_amount = db.Column(db.Numeric(12, 2, asdecimal=True), nullable=False)
    current_amount = db.Column(db.Numeric(12, 2, asdecimal=True), default=Decimal('0.00'), nullable=False)
    target_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='in_progress', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def target_float(self):
        return float(self.target_amount) if self.target_amount is not None else 0.0

    @property
    def current_float(self):
        return float(self.current_amount) if self.current_amount is not None else 0.0

    @property
    def progress_pct(self):
        t = self.target_float
        c = self.current_float
        if t <= 0:
            return 100.0 if c >= t else 0.0
        pct = (c / t) * 100.0
        return min(100.0, round(pct, 1))

    @property
    def remaining_float(self):
        return max(0.0, self.target_float - self.current_float)

    def __repr__(self):
        return f'<SavingsGoal {self.title}: {self.current_amount}/{self.target_amount}>'


class RecurringExpense(db.Model):
    __tablename__ = 'recurring_expenses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='RESTRICT'), nullable=False)
    amount = db.Column(db.Numeric(12, 2, asdecimal=True), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    payment_method = db.Column(db.String(50), default='Cash', nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # 'weekly', 'monthly', 'yearly'
    next_due_date = db.Column(db.Date, nullable=False, index=True)
    last_generated_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def amount_float(self):
        return float(self.amount) if self.amount is not None else 0.0

    def __repr__(self):
        return f'<RecurringExpense {self.description}: {self.amount} ({self.frequency})>'
