import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from app.extensions import db
from app.models import Category, Transaction, Budget, Notification, RecurringExpense

DEFAULT_EXPENSE_CATEGORIES = [
    ('Food', 'bi-cup-hot', '#e74a3b'),
    ('Transport', 'bi-car-front', '#36b9cc'),
    ('Shopping', 'bi-bag', '#f6c23e'),
    ('Education', 'bi-book', '#4e73df'),
    ('Healthcare', 'bi-heart-pulse', '#e83e8c'),
    ('Housing', 'bi-house-door', '#1cc88a'),
    ('Bills', 'bi-receipt', '#6f42c1'),
    ('Entertainment', 'bi-controller', '#fd7e14'),
    ('Travel', 'bi-airplane', '#20c997'),
    ('Personal Care', 'bi-person-badge', '#0dcaf0'),
    ('Other', 'bi-three-dots', '#6c757d'),
]

DEFAULT_INCOME_CATEGORIES = [
    ('Salary', 'bi-cash-stack', '#1cc88a'),
    ('Freelancing', 'bi-laptop', '#4e73df'),
    ('Investment Income', 'bi-graph-up-arrow', '#36b9cc'),
    ('Other', 'bi-piggy-bank', '#6c757d'),
]

def init_default_categories():
    """Initializes system default categories if not already present."""
    for name, icon, color in DEFAULT_EXPENSE_CATEGORIES:
        exists = Category.query.filter_by(user_id=None, name=name, type='expense').first()
        if not exists:
            cat = Category(user_id=None, name=name, type='expense', icon=icon, color=color, is_default=True)
            db.session.add(cat)

    for name, icon, color in DEFAULT_INCOME_CATEGORIES:
        exists = Category.query.filter_by(user_id=None, name=name, type='income').first()
        if not exists:
            cat = Category(user_id=None, name=name, type='income', icon=icon, color=color, is_default=True)
            db.session.add(cat)

    db.session.commit()

def get_user_categories(user_id, cat_type=None):
    """Gets categories available to the user (global defaults + user custom)."""
    query = Category.query.filter(
        db.or_(Category.user_id == None, Category.user_id == user_id)
    )
    if cat_type:
        query = query.filter(Category.type == cat_type)
    return query.order_by(Category.name.asc()).all()

def format_currency(value, symbol='$'):
    """Formats a numeric value as a currency string."""
    try:
        val = float(value or 0)
        return f"{symbol}{val:,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"

def calculate_savings_rate(total_income, total_expenses):
    """
    Calculates savings rate as ((Total Income - Total Expenses) / Total Income) * 100.
    Handles zero income without division-by-zero errors.
    """
    inc = float(total_income or 0)
    exp = float(total_expenses or 0)
    if inc <= 0:
        return 0.0
    rate = ((inc - exp) / inc) * 100.0
    return round(rate, 2)

def advance_date_by_frequency(start_date, frequency):
    """Calculates next due date based on frequency."""
    if frequency == 'weekly':
        return start_date + timedelta(days=7)
    elif frequency == 'monthly':
        year = start_date.year
        month = start_date.month + 1
        if month > 12:
            month = 1
            year += 1
        max_day = calendar.monthrange(year, month)[1]
        day = min(start_date.day, max_day)
        return date(year, month, day)
    elif frequency == 'yearly':
        year = start_date.year + 1
        month = start_date.month
        max_day = calendar.monthrange(year, month)[1]
        day = min(start_date.day, max_day)
        return date(year, month, day)
    return start_date + timedelta(days=30)

def process_recurring_expenses(user_id):
    """
    Idempotent recurring transaction processor.
    Running multiple times does not produce duplicate transactions for the same due date.
    """
    today = date.today()
    recurring_list = RecurringExpense.query.filter_by(user_id=user_id, is_active=True).all()
    created_count = 0

    for item in recurring_list:
        while item.next_due_date <= today:
            if item.last_generated_date == item.next_due_date:
                item.next_due_date = advance_date_by_frequency(item.next_due_date, item.frequency)
                continue

            tx = Transaction(
                user_id=item.user_id,
                category_id=item.category_id,
                amount=item.amount,
                type='expense',
                description=f"{item.description} (Recurring {item.frequency.capitalize()})",
                transaction_date=item.next_due_date,
                payment_method=item.payment_method
            )
            db.session.add(tx)
            item.last_generated_date = item.next_due_date
            item.next_due_date = advance_date_by_frequency(item.next_due_date, item.frequency)
            created_count += 1

    if created_count > 0:
        db.session.commit()
    return created_count

def check_and_create_budget_alerts(user_id, target_date=None):
    """
    Evaluates current month budgets and creates deduplicated alerts at 50%, 80%, 100%.
    Does not produce duplicate notifications on repeated runs.
    """
    if target_date is None:
        target_date = date.today()
    month = target_date.month
    year = target_date.year

    budgets = Budget.query.filter_by(user_id=user_id, month=month, year=year).all()
    created_alerts = 0

    start_date = date(year, month, 1)
    end_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, end_day)

    for b in budgets:
        limit_val = float(b.monthly_limit)
        if limit_val <= 0:
            continue

        if b.is_overall:
            total_spent = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'expense',
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).scalar()
            cat_name = 'Overall Monthly Budget'
        else:
            total_spent = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.user_id == user_id,
                Transaction.category_id == b.category_id,
                Transaction.type == 'expense',
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).scalar()
            cat_name = f"{b.category.name} Budget" if b.category else 'Category Budget'

        spent_val = float(total_spent)
        utilization = (spent_val / limit_val) * 100.0

        if utilization >= 100.0:
            dedup_key = f"budget_{b.id}_{year}_{month}_100"
            existing = Notification.query.filter_by(user_id=user_id, dedup_key=dedup_key).first()
            if not existing:
                notif = Notification(
                    user_id=user_id,
                    title=f"Budget Exceeded: {cat_name}",
                    message=f"You have spent {format_currency(spent_val)} of your {format_currency(limit_val)} limit ({utilization:.1f}%).",
                    type='budget_exceeded',
                    dedup_key=dedup_key
                )
                db.session.add(notif)
                created_alerts += 1
        elif utilization >= 80.0:
            dedup_key = f"budget_{b.id}_{year}_{month}_80"
            existing = Notification.query.filter_by(user_id=user_id, dedup_key=dedup_key).first()
            if not existing:
                notif = Notification(
                    user_id=user_id,
                    title=f"Budget Warning: {cat_name}",
                    message=f"You have reached {utilization:.1f}% of your {format_currency(limit_val)} limit ({format_currency(spent_val)} spent).",
                    type='budget_warning',
                    dedup_key=dedup_key
                )
                db.session.add(notif)
                created_alerts += 1
        elif utilization >= 50.0:
            dedup_key = f"budget_{b.id}_{year}_{month}_50"
            existing = Notification.query.filter_by(user_id=user_id, dedup_key=dedup_key).first()
            if not existing:
                notif = Notification(
                    user_id=user_id,
                    title=f"Budget Notice: {cat_name}",
                    message=f"You have used {utilization:.1f}% of your {format_currency(limit_val)} limit.",
                    type='budget_warning',
                    dedup_key=dedup_key
                )
                db.session.add(notif)
                created_alerts += 1

    if created_alerts > 0:
        db.session.commit()
    return created_alerts
