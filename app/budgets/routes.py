import calendar
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.models import Budget, Category, Transaction
from app.budgets.forms import BudgetForm
from app.utils import get_user_categories, check_and_create_budget_alerts

budgets_bp = Blueprint('budgets', __name__)

def build_budget_choices(user_id):
    expense_categories = get_user_categories(user_id, cat_type='expense')
    choices = [(0, '🌐 Overall Monthly Budget (All Categories)')]
    choices.extend([(c.id, f"🏷️ {c.name}") for c in expense_categories])
    return choices

def calculate_budget_progress(budget, user_id):
    start_date = date(budget.year, budget.month, 1)
    end_day = calendar.monthrange(budget.year, budget.month)[1]
    end_date = date(budget.year, budget.month, end_day)

    if budget.is_overall:
        spent = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar()
    else:
        spent = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.category_id == budget.category_id,
            Transaction.type == 'expense',
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar()

    spent_val = float(spent)
    limit_val = float(budget.monthly_limit)
    remaining_val = limit_val - spent_val
    utilization = (spent_val / limit_val * 100.0) if limit_val > 0 else 0.0

    if utilization >= 100.0:
        status = 'exceeded'
        color = 'danger'
    elif utilization >= 80.0:
        status = 'warning'
        color = 'warning'
    elif utilization >= 50.0:
        status = 'notice'
        color = 'info'
    else:
        status = 'healthy'
        color = 'success'

    return {
        'budget': budget,
        'limit': limit_val,
        'spent': spent_val,
        'remaining': remaining_val,
        'utilization': round(utilization, 1),
        'status': status,
        'color': color,
        'month_name': calendar.month_name[budget.month]
    }

@budgets_bp.route('/')
@login_required
def index():
    today = date.today()
    selected_month = request.args.get('month', today.month, type=int)
    selected_year = request.args.get('year', today.year, type=int)

    # Trigger alert check for current viewing period
    check_and_create_budget_alerts(current_user.id, target_date=date(selected_year, selected_month, 1))

    user_budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=selected_month,
        year=selected_year
    ).all()

    # Split overall vs category budgets to avoid confusion and double-counting
    overall_progress = None
    category_progresses = []

    for b in user_budgets:
        progress = calculate_budget_progress(b, current_user.id)
        if b.is_overall:
            overall_progress = progress
        else:
            category_progresses.append(progress)

    # Sort category budgets by utilization desc
    category_progresses.sort(key=lambda x: x['utilization'], reverse=True)

    form = BudgetForm()
    form.category_id.choices = build_budget_choices(current_user.id)
    form.month.data = selected_month
    form.year.data = selected_year

    return render_template(
        'budgets/index.html',
        overall_progress=overall_progress,
        category_progresses=category_progresses,
        selected_month=selected_month,
        selected_year=selected_year,
        month_name=calendar.month_name[selected_month],
        form=form
    )

@budgets_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    form = BudgetForm()
    form.category_id.choices = build_budget_choices(current_user.id)

    if form.validate_on_submit():
        cat_id = None if form.category_id.data == 0 else form.category_id.data

        # Check duplicate
        exists = Budget.query.filter_by(
            user_id=current_user.id,
            category_id=cat_id,
            month=form.month.data,
            year=form.year.data
        ).first()

        if exists:
            scope_str = "an overall budget" if cat_id is None else f"a budget for {exists.category.name}"
            flash(f"You already have {scope_str} for {calendar.month_name[form.month.data]} {form.year.data}. You can edit it instead.", 'warning')
            return redirect(url_for('budgets.index', month=form.month.data, year=form.year.data))

        budget = Budget(
            user_id=current_user.id,
            category_id=cat_id,
            monthly_limit=form.monthly_limit.data,
            month=form.month.data,
            year=form.year.data
        )
        db.session.add(budget)
        db.session.commit()

        check_and_create_budget_alerts(current_user.id, target_date=date(budget.year, budget.month, 1))
        flash('Budget created successfully!', 'success')
        return redirect(url_for('budgets.index', month=budget.month, year=budget.year))

    return render_template('budgets/form.html', form=form, title='Set Monthly Budget')

@budgets_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    budget = Budget.query.get_or_404(id)
    if budget.user_id != current_user.id:
        abort(403)

    form = BudgetForm(obj=budget)
    form.category_id.choices = build_budget_choices(current_user.id)

    if request.method == 'GET':
        form.category_id.data = 0 if budget.category_id is None else budget.category_id

    if form.validate_on_submit():
        cat_id = None if form.category_id.data == 0 else form.category_id.data

        # Check duplicate if changed
        duplicate = Budget.query.filter(
            Budget.id != budget.id,
            Budget.user_id == current_user.id,
            Budget.category_id == cat_id,
            Budget.month == form.month.data,
            Budget.year == form.year.data
        ).first()

        if duplicate:
            flash(f"Another budget already exists for this scope and month.", 'warning')
            return render_template('budgets/form.html', form=form, title='Edit Budget', budget=budget)

        budget.category_id = cat_id
        budget.monthly_limit = form.monthly_limit.data
        budget.month = form.month.data
        budget.year = form.year.data
        db.session.commit()

        check_and_create_budget_alerts(current_user.id, target_date=date(budget.year, budget.month, 1))
        flash('Budget updated successfully.', 'success')
        return redirect(url_for('budgets.index', month=budget.month, year=budget.year))

    return render_template('budgets/form.html', form=form, title='Edit Budget', budget=budget)

@budgets_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    budget = Budget.query.get_or_404(id)
    if budget.user_id != current_user.id:
        abort(403)

    m = budget.month
    y = budget.year
    db.session.delete(budget)
    db.session.commit()

    flash('Budget removed.', 'info')
    return redirect(url_for('budgets.index', month=m, year=y))

@budgets_bp.route('/summary-api')
@login_required
def summary_api():
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year = request.args.get('year', today.year, type=int)

    budgets = Budget.query.filter_by(user_id=current_user.id, month=month, year=year).all()
    results = [calculate_budget_progress(b, current_user.id) for b in budgets]

    return jsonify({
        'month': month,
        'year': year,
        'budgets': [{
            'id': r['budget'].id,
            'is_overall': r['budget'].is_overall,
            'category': r['budget'].category.name if r['budget'].category else 'Overall',
            'limit': r['limit'],
            'spent': r['spent'],
            'remaining': r['remaining'],
            'utilization': r['utilization'],
            'status': r['status'],
            'color': r['color']
        } for r in results]
    })
