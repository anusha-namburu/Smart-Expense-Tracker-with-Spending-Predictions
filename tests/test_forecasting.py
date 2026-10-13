from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
from app.extensions import db
from app.models import Transaction
from app.forecasting.features import build_daily_time_series, extract_time_series_features
from app.forecasting.service import ForecastService

def test_feature_engineering_anti_leakage():
    # Construct 10 days of synthetic daily spending
    dates = [date(2026, 1, i) for i in range(1, 11)]
    records = {d: float(i * 10) for i, d in enumerate(dates, start=1)}

    ts_df = build_daily_time_series(records)
    feat_df = extract_time_series_features(ts_df)

    assert 'lag_1' in feat_df.columns
    assert 'rolling_7_mean' in feat_df.columns
    assert 'day_of_week' in feat_df.columns

    # Verify shift: on day 2, lag_1 must equal day 1 expense (10.0), NOT day 2 expense (20.0)
    assert feat_df.iloc[1]['lag_1'] == 10.0
    assert feat_df.iloc[1]['expense'] == 20.0

def test_forecasting_fallback_when_sparse(app, user_a, food_category):
    with app.app_context():
        # Only 2 transactions (insufficient for ML threshold of 14)
        t1 = Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('30.00'), type='expense', transaction_date=date(2026, 5, 2))
        t2 = Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('40.00'), type='expense', transaction_date=date(2026, 5, 4))
        db.session.add_all([t1, t2])
        db.session.commit()

        target_date = date(2026, 5, 5)
        forecast = ForecastService.generate_spending_forecast(user_a.id, target_date=target_date)

        assert forecast['is_ml'] is False
        assert 'Baseline' in forecast['model_name']
        assert forecast['warning'] is not None
        assert forecast['actual_spent_so_far'] == 70.0
        assert forecast['predicted_month_end_total'] >= 70.0
        assert len(forecast['daily_timeline']) == 31  # May has 31 days

def test_forecasting_with_adequate_history(app, user_a, food_category):
    with app.app_context():
        target_date = date(2026, 5, 10)
        # Create 60 days of prior transactions spanning March and April 2026
        tx_list = []
        cur_d = date(2026, 3, 1)
        while cur_d < date(2026, 5, 1):
            amt = Decimal('25.00') if cur_d.weekday() < 5 else Decimal('60.00')
            tx_list.append(Transaction(
                user_id=user_a.id,
                category_id=food_category.id,
                amount=amt,
                type='expense',
                transaction_date=cur_d
            ))
            cur_d += timedelta(days=1)

        # A few transactions in May
        tx_list.append(Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('50.00'), type='expense', transaction_date=date(2026, 5, 2)))
        tx_list.append(Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('40.00'), type='expense', transaction_date=date(2026, 5, 6)))

        db.session.add_all(tx_list)
        db.session.commit()

        forecast = ForecastService.generate_spending_forecast(user_a.id, target_date=target_date)

        assert forecast['is_ml'] is True
        assert 'Random Forest' in forecast['model_name']
        assert forecast['mae'] is not None
        assert forecast['warning'] is None
        assert forecast['actual_spent_so_far'] == 90.0
        assert forecast['predicted_month_end_total'] > 90.0

def test_income_excluded_from_expense_forecast(app, user_a, food_category, salary_category):
    with app.app_context():
        target_date = date(2026, 5, 5)
        # $50 expense
        tx_exp = Transaction(user_id=user_a.id, category_id=food_category.id, amount=Decimal('50.00'), type='expense', transaction_date=date(2026, 5, 2))
        # $10,000 huge income
        tx_inc = Transaction(user_id=user_a.id, category_id=salary_category.id, amount=Decimal('10000.00'), type='income', transaction_date=date(2026, 5, 1))
        db.session.add_all([tx_exp, tx_inc])
        db.session.commit()

        forecast = ForecastService.generate_spending_forecast(user_a.id, target_date=target_date)
        # Expense so far must be exactly 50, strictly ignoring the 10000 income
        assert forecast['actual_spent_so_far'] == 50.0
        assert forecast['predicted_month_end_total'] < 1000.0
