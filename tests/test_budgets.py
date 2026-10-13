from datetime import date
from decimal import Decimal
from app.extensions import db
from app.models import Budget, Transaction, Notification
from app.utils import check_and_create_budget_alerts

def test_create_overall_budget(auth_client_a, user_a):
    res = auth_client_a.post('/budgets/add', data={
        'category_id': 0,  # 0 indicates Overall
        'monthly_limit': '2500.00',
        'month': 10,
        'year': 2026
    }, follow_redirects=True)
    assert res.status_code == 200
    b = Budget.query.filter_by(user_id=user_a.id, category_id=None, month=10, year=2026).first()
    assert b is not None
    assert float(b.monthly_limit) == 2500.00
    assert b.is_overall is True

def test_prevent_duplicate_budget(auth_client_a, user_a, food_category):
    b1 = Budget(user_id=user_a.id, category_id=food_category.id, monthly_limit=Decimal('500.00'), month=10, year=2026)
    db.session.add(b1)
    db.session.commit()

    # Attempt to add same category, month, year
    res = auth_client_a.post('/budgets/add', data={
        'category_id': food_category.id,
        'monthly_limit': '600.00',
        'month': 10,
        'year': 2026
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'already have' in res.data
    assert Budget.query.filter_by(user_id=user_a.id, category_id=food_category.id, month=10, year=2026).count() == 1

def test_budget_threshold_alerts_and_deduplication(app, user_a, food_category):
    with app.app_context():
        # Set $100 budget for Food in May 2026
        target_date = date(2026, 5, 15)
        b = Budget(user_id=user_a.id, category_id=food_category.id, monthly_limit=Decimal('100.00'), month=5, year=2026)
        db.session.add(b)
        db.session.commit()

        # Step 1: Spend $55 (55% utilization -> triggers 50% threshold)
        tx1 = Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('55.00'), type='expense', transaction_date=target_date)
        db.session.add(tx1)
        db.session.commit()

        created_1 = check_and_create_budget_alerts(user_a.id, target_date=target_date)
        assert created_1 == 1
        notif_50 = Notification.query.filter_by(user_id=user_a.id, dedup_key=f"budget_{b.id}_2026_5_50").first()
        assert notif_50 is not None
        assert 'Budget Notice' in notif_50.title

        # Step 2: Running check again without changes must NOT create duplicate notification!
        created_dup = check_and_create_budget_alerts(user_a.id, target_date=target_date)
        assert created_dup == 0
        assert Notification.query.filter_by(user_id=user_a.id).count() == 1

        # Step 3: Spend more to cross 85% ($30 more -> $85 total)
        tx2 = Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('30.00'), type='expense', transaction_date=target_date)
        db.session.add(tx2)
        db.session.commit()

        created_2 = check_and_create_budget_alerts(user_a.id, target_date=target_date)
        assert created_2 == 1
        notif_80 = Notification.query.filter_by(user_id=user_a.id, dedup_key=f"budget_{b.id}_2026_5_80").first()
        assert notif_80 is not None
        assert 'Budget Warning' in notif_80.title

        # Step 4: Exceed 100% ($25 more -> $110 total)
        tx3 = Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('25.00'), type='expense', transaction_date=target_date)
        db.session.add(tx3)
        db.session.commit()

        created_3 = check_and_create_budget_alerts(user_a.id, target_date=target_date)
        assert created_3 == 1
        notif_100 = Notification.query.filter_by(user_id=user_a.id, dedup_key=f"budget_{b.id}_2026_5_100").first()
        assert notif_100 is not None
        assert 'Budget Exceeded' in notif_100.title
