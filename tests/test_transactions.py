from datetime import date
from decimal import Decimal
from app.extensions import db
from app.models import Transaction

def test_add_expense_transaction(auth_client_a, user_a, food_category):
    res = auth_client_a.post('/transactions/add', data={
        'type': 'expense',
        'amount': '45.50',
        'category_id': food_category.id,
        'transaction_date': date.today().isoformat(),
        'payment_method': 'Credit Card',
        'description': 'Weekly Grocery Haul'
    }, follow_redirects=True)
    assert res.status_code == 200
    tx = Transaction.query.filter_by(user_id=user_a.id, description='Weekly Grocery Haul').first()
    assert tx is not None
    assert float(tx.amount) == 45.50
    assert tx.type == 'expense'
    assert tx.category_id == food_category.id

def test_add_income_transaction(auth_client_a, user_a, salary_category):
    res = auth_client_a.post('/transactions/add', data={
        'type': 'income',
        'amount': '3000.00',
        'category_id': salary_category.id,
        'transaction_date': date.today().isoformat(),
        'payment_method': 'Bank Transfer',
        'description': 'Bi-weekly Salary'
    }, follow_redirects=True)
    assert res.status_code == 200
    tx = Transaction.query.filter_by(user_id=user_a.id, type='income').first()
    assert tx is not None
    assert float(tx.amount) == 3000.00

def test_invalid_negative_amount_rejected(auth_client_a, food_category):
    res = auth_client_a.post('/transactions/add', data={
        'type': 'expense',
        'amount': '-15.00',
        'category_id': food_category.id,
        'transaction_date': date.today().isoformat(),
        'payment_method': 'Cash',
        'description': 'Negative test'
    }, follow_redirects=True)
    assert res.status_code == 200
    tx = Transaction.query.filter_by(description='Negative test').first()
    assert tx is None

def test_edit_transaction(auth_client_a, user_a, food_category):
    tx = Transaction(
        user_id=user_a.id,
        category_id=food_category.id,
        amount=Decimal('20.00'),
        type='expense',
        transaction_date=date.today(),
        payment_method='Cash',
        description='Lunch'
    )
    db.session.add(tx)
    db.session.commit()

    res = auth_client_a.post(f'/transactions/{tx.id}/edit', data={
        'type': 'expense',
        'amount': '25.00',
        'category_id': food_category.id,
        'transaction_date': date.today().isoformat(),
        'payment_method': 'Cash',
        'description': 'Lunch Buffet'
    }, follow_redirects=True)
    assert res.status_code == 200
    updated_tx = db.session.get(Transaction, tx.id)
    assert float(updated_tx.amount) == 25.00
    assert updated_tx.description == 'Lunch Buffet'

def test_delete_transaction(auth_client_a, user_a, food_category):
    tx = Transaction(
        user_id=user_a.id,
        category_id=food_category.id,
        amount=Decimal('10.00'),
        type='expense',
        transaction_date=date.today(),
        payment_method='Cash',
        description='Delete me'
    )
    db.session.add(tx)
    db.session.commit()

    res = auth_client_a.post(f'/transactions/{tx.id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert db.session.get(Transaction, tx.id) is None

def test_transaction_search_and_filter(auth_client_a, user_a, food_category, salary_category):
    t1 = Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('50'), type='expense', transaction_date=date(2026, 5, 1), description='Supermarket')
    t2 = Transaction(user_id=user_a.id, category_id=salary_category.id, amount=Decimal('1000'), type='income', transaction_date=date(2026, 5, 2), description='Consulting')
    db.session.add_all([t1, t2])
    db.session.commit()

    # Search keyword
    res_search = auth_client_a.get('/transactions/?q=Supermarket')
    assert b'Supermarket' in res_search.data
    assert b'Consulting' not in res_search.data

    # Filter type
    res_type = auth_client_a.get('/transactions/?type=income')
    assert b'Consulting' in res_type.data
    assert b'Supermarket' not in res_type.data

def test_csv_export(auth_client_a, user_a, food_category):
    tx = Transaction(
        user_id=user_a.id,
        category_id=food_category.id,
        amount=Decimal('42.00'),
        type='expense',
        transaction_date=date(2026, 6, 15),
        payment_method='Credit Card',
        description='Dinner with friends'
    )
    db.session.add(tx)
    db.session.commit()

    res = auth_client_a.get('/transactions/export-csv')
    assert res.status_code == 200
    assert res.mimetype == 'text/csv'
    csv_text = res.data.decode('utf-8')
    assert 'Transaction ID,Date,Type,Category,Amount,Currency,Payment Method,Description,Created Timestamp' in csv_text
    assert 'Dinner with friends' in csv_text
    assert '42.00' in csv_text
