from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import SavingsGoal, RecurringExpense, Category, Notification
from app.goals.forms import SavingsGoalForm, DepositGoalForm, RecurringExpenseForm
from app.utils import get_user_categories, process_recurring_expenses

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('/')
@login_required
def index():
    goals = SavingsGoal.query.filter_by(user_id=current_user.id).order_by(SavingsGoal.created_at.desc()).all()
    recurring_items = RecurringExpense.query.filter_by(user_id=current_user.id).order_by(RecurringExpense.next_due_date.asc()).all()

    goal_form = SavingsGoalForm()
    deposit_form = DepositGoalForm()

    categories = get_user_categories(current_user.id, cat_type='expense')
    recurring_form = RecurringExpenseForm()
    recurring_form.category_id.choices = [(c.id, c.name) for c in categories]

    return render_template(
        'goals/index.html',
        goals=goals,
        recurring_items=recurring_items,
        goal_form=goal_form,
        deposit_form=deposit_form,
        recurring_form=recurring_form
    )

@goals_bp.route('/add', methods=['POST'])
@login_required
def add():
    form = SavingsGoalForm()
    if form.validate_on_submit():
        goal = SavingsGoal(
            user_id=current_user.id,
            title=form.title.data.strip(),
            target_amount=form.target_amount.data,
            current_amount=form.current_amount.data or Decimal('0.00'),
            target_date=form.target_date.data,
            status='completed' if (form.current_amount.data or 0) >= form.target_amount.data else 'in_progress'
        )
        db.session.add(goal)
        db.session.commit()
        flash(f"Savings goal '{goal.title}' created!", 'success')
    else:
        for err in form.errors.values():
            flash(err[0], 'danger')

    return redirect(url_for('goals.index'))

@goals_bp.route('/<int:id>/deposit', methods=['POST'])
@login_required
def deposit(id):
    goal = SavingsGoal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        abort(403)

    form = DepositGoalForm()
    if form.validate_on_submit():
        added_amount = form.deposit_amount.data
        goal.current_amount = Decimal(str(float(goal.current_amount) + float(added_amount)))

        if float(goal.current_amount) >= float(goal.target_amount):
            goal.status = 'completed'
            dedup_key = f"goal_completed_{goal.id}"
            existing = Notification.query.filter_by(user_id=current_user.id, dedup_key=dedup_key).first()
            if not existing:
                notif = Notification(
                    user_id=current_user.id,
                    title=f"🎉 Goal Achieved: {goal.title}!",
                    message=f"Congratulations! You reached your savings target of ${float(goal.target_amount):,.2f}.",
                    type='goal_milestone',
                    dedup_key=dedup_key
                )
                db.session.add(notif)
            flash(f"🎉 Congratulations! You have fully achieved your goal '{goal.title}'!", 'success')
        else:
            flash(f"Added ${float(added_amount):,.2f} towards '{goal.title}'. Current progress: {goal.progress_pct}%.", 'success')

        db.session.commit()
    return redirect(url_for('goals.index'))

@goals_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    goal = SavingsGoal.query.get_or_404(id)
    if goal.user_id != current_user.id:
        abort(403)

    db.session.delete(goal)
    db.session.commit()
    flash(f"Goal '{goal.title}' deleted.", 'info')
    return redirect(url_for('goals.index'))

@goals_bp.route('/recurring/add', methods=['POST'])
@login_required
def add_recurring():
    categories = get_user_categories(current_user.id, cat_type='expense')
    form = RecurringExpenseForm()
    form.category_id.choices = [(c.id, c.name) for c in categories]

    if form.validate_on_submit():
        rec = RecurringExpense(
            user_id=current_user.id,
            category_id=form.category_id.data,
            amount=form.amount.data,
            description=form.description.data.strip(),
            payment_method=form.payment_method.data,
            frequency=form.frequency.data,
            next_due_date=form.next_due_date.data,
            is_active=True
        )
        db.session.add(rec)
        db.session.commit()
        flash(f"Recurring expense template '{rec.description}' added.", 'success')
    else:
        for err in form.errors.values():
            flash(err[0], 'danger')

    return redirect(url_for('goals.index'))

@goals_bp.route('/recurring/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_recurring(id):
    rec = RecurringExpense.query.get_or_404(id)
    if rec.user_id != current_user.id:
        abort(403)

    rec.is_active = not rec.is_active
    db.session.commit()
    state_str = "activated" if rec.is_active else "paused"
    flash(f"Recurring template '{rec.description}' is now {state_str}.", 'info')
    return redirect(url_for('goals.index'))

@goals_bp.route('/recurring/<int:id>/delete', methods=['POST'])
@login_required
def delete_recurring(id):
    rec = RecurringExpense.query.get_or_404(id)
    if rec.user_id != current_user.id:
        abort(403)

    db.session.delete(rec)
    db.session.commit()
    flash('Recurring expense template removed.', 'info')
    return redirect(url_for('goals.index'))

@goals_bp.route('/recurring/process-due', methods=['POST'])
@login_required
def process_due_recurring():
    created_count = process_recurring_expenses(current_user.id)
    if created_count > 0:
        flash(f"Successfully generated {created_count} due recurring transaction(s).", 'success')
    else:
        flash("All recurring expenses are up-to-date. No pending due transactions found.", 'info')
    return redirect(url_for('goals.index'))
