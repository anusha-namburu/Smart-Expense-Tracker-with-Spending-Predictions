from datetime import date
from decimal import Decimal
from app.extensions import db
from app.models import Transaction, Budget, SavingsGoal, RecurringExpense, Notification

def test_user_cannot_access_other_user_transaction(auth_client_b, user_a, food_category):
    # Transaction belonging to User A
    tx_a = Transaction(
        user_id=user_a.id,
        category_id=food_category.id,
        amount=Decimal('99.00'),
        type='expense',
        transaction_date=date.today(),
        description="User A's Secret Purchase"
    )
    db.session.add(tx_a)
    db.session.commit()

    # User B attempts to edit User A's transaction
    res_edit = auth_client_b.post(f'/transactions/{tx_a.id}/edit', data={
        'type': 'expense',
        'amount': '1.00',
        'category_id': food_category.id,
        'transaction_date': date.today().isoformat(),
        'payment_method': 'Cash'
    })
    assert res_edit.status_code in [403, 404]

    # User B attempts to delete User A's transaction
    res_delete = auth_client_b.post(f'/transactions/{tx_a.id}/delete')
    assert res_delete.status_code in [403, 404]
    # Ensure User A's transaction was not deleted
    assert db.session.get(Transaction, tx_a.id) is not None

def test_user_cannot_view_other_user_transaction_in_list_or_csv(auth_client_b, user_a, food_category):
    tx_a = Transaction(
        user_id=user_a.id,
        category_id=food_category.id,
        amount=Decimal('500.00'),
        type='expense',
        transaction_date=date.today(),
        description="AliceConfidentialItem"
    )
    db.session.add(tx_a)
    db.session.commit()

    # User B list
    res_list = auth_client_b.get('/transactions/')
    assert b'AliceConfidentialItem' not in res_list.data

    # User B CSV export
    res_csv = auth_client_b.get('/transactions/export-csv')
    assert b'AliceConfidentialItem' not in res_csv.data

def test_user_cannot_delete_other_user_budget(auth_client_b, user_a):
    b_a = Budget(user_id=user_a.id, category_id=None, monthly_limit=Decimal('1000.00'), month=10, year=2026)
    db.session.add(b_a)
    db.session.commit()

    res = auth_client_b.post(f'/budgets/{b_a.id}/delete')
    assert res.status_code in [403, 404]
    assert db.session.get(Budget, b_a.id) is not None

def test_user_cannot_delete_other_user_goal_or_recurring(auth_client_b, user_a, food_category):
    goal_a = SavingsGoal(user_id=user_a.id, title="Alice Goal", target_amount=Decimal('500'), target_date=date.today())
    rec_a = RecurringExpense(user_id=user_a.id, category_id=food_category.id, amount=Decimal('50'), description="Alice Sub", frequency='monthly', next_due_date=date.today())
    notif_a = Notification(user_id=user_a.id, title="Alice Alert", message="Test", type='info')
    db.session.add_all([goal_a, rec_a, notif_a])
    db.session.commit()

    # User B attempts actions on User A resources
    assert auth_client_b.post(f'/goals/{goal_a.id}/delete').status_code in [403, 404]
    assert auth_client_b.post(f'/goals/recurring/{rec_a.id}/delete').status_code in [403, 404]
    assert auth_client_b.post(f'/notifications/{notif_a.id}/read').status_code in [403, 404]
    assert auth_client_b.post(f'/notifications/{notif_a.id}/delete').status_code in [403, 404]
