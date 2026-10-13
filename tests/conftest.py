import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models import User, Category, Transaction, Budget, Notification, SavingsGoal, RecurringExpense
from app.utils import init_default_categories

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        init_default_categories()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def user_a(app):
    user = User(username='Alice User', email='alice@example.com', currency='$')
    user.set_password('Password123!')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def user_b(app):
    user = User(username='Bob Hacker', email='bob@example.com', currency='$')
    user.set_password('SecretPassword!')
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def auth_client_a(client, user_a):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_a.id)
        sess['_fresh'] = True
    return client

@pytest.fixture
def auth_client_b(client, user_b):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_b.id)
        sess['_fresh'] = True
    return client

@pytest.fixture
def food_category(app):
    cat = Category.query.filter_by(name='Food', type='expense').first()
    if not cat:
        cat = Category(name='Food', type='expense', icon='bi-cup-hot', color='#e74a3b', is_default=True)
        db.session.add(cat)
        db.session.commit()
    return cat

@pytest.fixture
def salary_category(app):
    cat = Category.query.filter_by(name='Salary', type='income').first()
    if not cat:
        cat = Category(name='Salary', type='income', icon='bi-cash-stack', color='#1cc88a', is_default=True)
        db.session.add(cat)
        db.session.commit()
    return cat
