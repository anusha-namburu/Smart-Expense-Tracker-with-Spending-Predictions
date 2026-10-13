import calendar
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from app.extensions import db
from app.models import Transaction, Budget, Category
from app.forecasting.service import ForecastService
from app.analytics.service import AnalyticsService
from app.utils import calculate_savings_rate, format_currency, check_and_create_budget_alerts

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    today = date.today()
    month = today.month
    year = today.year

    start_date = date(year, month, 1)
    end_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, end_day)

    # Trigger budget threshold alert check
    check_and_create_budget_alerts(current_user.id, target_date=today)

    # 1. Total income this month
    income_val = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'income',
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).scalar()
    total_income = float(income_val)

    # 2. Total expenses this month
    expense_val = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).scalar()
    total_expenses = float(expense_val)

    # 3. Balance
    balance = total_income - total_expenses

    # 4. Savings rate
    savings_rate = calculate_savings_rate(total_income, total_expenses)

    # 5. Budget utilization
    overall_budget = Budget.query.filter_by(
        user_id=current_user.id,
        category_id=None,
        month=month,
        year=year
    ).first()

    budget_limit = float(overall_budget.monthly_limit) if overall_budget else None
    if budget_limit and budget_limit > 0:
        budget_utilization = round((total_expenses / budget_limit) * 100.0, 1)
        budget_remaining = round(budget_limit - total_expenses, 2)
    else:
        budget_utilization = None
        budget_remaining = None

    # 6. ML Forecast
    forecast = ForecastService.generate_spending_forecast(current_user.id, target_date=today)

    # Recent transactions
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Transaction.transaction_date), desc(Transaction.created_at)).limit(8).all()

    # Category breakdown for doughnut chart
    cat_breakdown = AnalyticsService.get_category_breakdown(current_user.id, month=month, year=year)

    return render_template(
        'dashboard/index.html',
        today=today,
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        savings_rate=savings_rate,
        budget_limit=budget_limit,
        budget_utilization=budget_utilization,
        budget_remaining=budget_remaining,
        forecast=forecast,
        recent_transactions=recent_transactions,
        cat_breakdown=cat_breakdown
    )

@dashboard_bp.route('/charts-api')
@login_required
def charts_api():
    today = date.today()
    month = today.month
    year = today.year

    start_date = date(year, month, 1)
    end_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, end_day)

    # 1. Category Doughnut Chart Data
    cat_data = AnalyticsService.get_category_breakdown(current_user.id, month=month, year=year)

    # 2. Daily Spending Trend (Current Month)
    daily_txs = db.session.query(
        Transaction.transaction_date,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    ).group_by(Transaction.transaction_date).all()

    daily_dict = {t.transaction_date.day: float(t.total) for t in daily_txs}
    daily_labels = [f"Day {d}" for d in range(1, end_day + 1)]
    daily_values = [daily_dict.get(d, 0.0) for d in range(1, end_day + 1)]

    # 3. Income vs Expenses by Month (Last 6 Months)
    monthly_labels = []
    monthly_income = []
    monthly_expense = []

    for i in range(5, -1, -1):
        m_offset_date = today.replace(day=1) - timedelta(days=i * 28)
        y = m_offset_date.year
        m = m_offset_date.month
        m_start = date(y, m, 1)
        m_end = date(y, m, calendar.monthrange(y, m)[1])

        inc = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'income',
            Transaction.transaction_date >= m_start,
            Transaction.transaction_date <= m_end
        ).scalar()

        exp = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            Transaction.transaction_date >= m_start,
            Transaction.transaction_date <= m_end
        ).scalar()

        monthly_labels.append(f"{calendar.month_abbr[m]} {y}")
        monthly_income.append(round(float(inc), 2))
        monthly_expense.append(round(float(exp), 2))

    # 4. Budget vs Actual (Active Budgets in Current Month)
    budgets = Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    budget_labels = []
    budget_limits = []
    budget_actuals = []

    for b in budgets:
        limit_val = float(b.monthly_limit)
        if b.is_overall:
            label = "Overall Budget"
            spent = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.user_id == current_user.id,
                Transaction.type == 'expense',
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).scalar()
        else:
            label = b.category.name if b.category else "Category"
            spent = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.user_id == current_user.id,
                Transaction.category_id == b.category_id,
                Transaction.type == 'expense',
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).scalar()

        budget_labels.append(label)
        budget_limits.append(limit_val)
        budget_actuals.append(round(float(spent), 2))

    return jsonify({
        'category_chart': {
            'labels': cat_data['chart_labels'],
            'data': cat_data['chart_data'],
            'colors': cat_data['chart_colors']
        },
        'daily_chart': {
            'labels': daily_labels,
            'data': daily_values
        },
        'monthly_chart': {
            'labels': monthly_labels,
            'income': monthly_income,
            'expense': monthly_expense
        },
        'budget_chart': {
            'labels': budget_labels,
            'limits': budget_limits,
            'actuals': budget_actuals
        }
    })
