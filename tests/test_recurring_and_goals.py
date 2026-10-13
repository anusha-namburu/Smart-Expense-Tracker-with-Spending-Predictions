from datetime import date, timedelta
from decimal import Decimal
from app.extensions import db
from app.models import RecurringExpense, Transaction, SavingsGoal, Notification
from app.utils import process_recurring_expenses

def test_recurring_expense_idempotency(app, user_a, food_category):
    with app.app_context():
        today = date.today()
        # Create an active recurring expense due today
        rec = RecurringExpense(
            user_id=user_a.id,
            category_id=food_category.id,
            amount=Decimal('49.99'),
            description='Fiber Internet Subscription',
            frequency='monthly',
            next_due_date=today,
            is_active=True
        )
        db.session.add(rec)
        db.session.commit()

        # Run processor first time: must generate exactly 1 transaction
        count_first = process_recurring_expenses(user_a.id)
        assert count_first == 1

        tx = Transaction.query.filter_by(user_id=user_a.id, type='expense').first()
        assert tx is not None
        assert float(tx.amount) == 49.99
        assert 'Recurring Monthly' in tx.description

        # Due date must have advanced into the future
        rec_updated = db.session.get(RecurringExpense, rec.id)
        assert rec_updated.next_due_date > today

        # Run processor second time: MUST NOT generate duplicate transactions (Idempotency)
        count_second = process_recurring_expenses(user_a.id)
        assert count_second == 0
        assert Transaction.query.filter_by(user_id=user_a.id).count() == 1

def test_savings_goal_completion_and_milestone(app, auth_client_a, user_a):
    with app.app_context():
        goal = SavingsGoal(
            user_id=user_a.id,
            title="Gaming Console",
            target_amount=Decimal('500.00'),
            current_amount=Decimal('450.00'),
            target_date=date.today() + timedelta(days=30),
            status='in_progress'
        )
        db.session.add(goal)
        db.session.commit()

        # Add $100 deposit (crosses target of 500)
        res = auth_client_a.post(f'/goals/{goal.id}/deposit', data={
            'deposit_amount': '100.00'
        }, follow_redirects=True)
        assert res.status_code == 200

        updated_goal = db.session.get(SavingsGoal, goal.id)
        assert updated_goal.status == 'completed'
        assert float(updated_goal.current_amount) == 550.00
        assert updated_goal.progress_pct == 100.0

        # Verify milestone notification created
        notif = Notification.query.filter_by(user_id=user_a.id, dedup_key=f"goal_completed_{goal.id}").first()
        assert notif is not None
        assert 'Goal Achieved' in notif.title
