import calendar
import math
from datetime import date, datetime, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sqlalchemy import func
from app.extensions import db
from app.models import Transaction, Budget
from app.forecasting.features import (
    FEATURE_COLUMNS,
    build_daily_time_series,
    extract_time_series_features
)

class ForecastService:
    @staticmethod
    def get_user_expense_transactions(user_id, up_to_date=None):
        """Returns all expense transactions for the user up to a given date."""
        query = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense'
        )
        if up_to_date:
            query = query.filter(Transaction.transaction_date <= up_to_date)
        return query.order_by(Transaction.transaction_date.asc()).all()

    @classmethod
    def generate_spending_forecast(cls, user_id, target_date=None):
        """
        Generates month-end forecast using RandomForestRegressor when sufficient
        data exists, or falls back transparently to a daily average baseline.
        """
        if target_date is None:
            target_date = date.today()

        year = target_date.year
        month = target_date.month
        month_start = date(year, month, 1)
        total_days_in_month = calendar.monthrange(year, month)[1]
        month_end = date(year, month, total_days_in_month)

        days_passed = target_date.day
        days_remaining = total_days_in_month - days_passed

        # Fetch all user expense transactions up to target_date
        all_txs = cls.get_user_expense_transactions(user_id, up_to_date=target_date)

        # 1. Calculate actual spending so far this month
        actual_txs_this_month = [t for t in all_txs if t.transaction_date >= month_start]
        actual_spent_so_far = sum(float(t.amount) for t in actual_txs_this_month)
        current_daily_pace = (actual_spent_so_far / days_passed) if days_passed > 0 else 0.0

        # Query active overall monthly budget
        overall_budget = Budget.query.filter_by(
            user_id=user_id,
            category_id=None,
            month=month,
            year=year
        ).first()
        budget_limit = float(overall_budget.monthly_limit) if overall_budget else None

        # Build daily history map
        daily_map = {}
        for t in all_txs:
            d = t.transaction_date
            daily_map[d] = daily_map.get(d, 0.0) + float(t.amount)

        # Count active historical days with transactions strictly prior to current month
        historical_days_count = len([d for d, val in daily_map.items() if d < month_start and val > 0])

        # Historical monthly comparison (last 6 months)
        historical_monthly_data = cls._get_historical_monthly_totals(user_id, current_year=year, current_month=month)

        # Daily timeline array for the entire current month (actuals up to today, predictions thereafter)
        daily_timeline = []
        for day_num in range(1, days_passed + 1):
            curr_d = date(year, month, day_num)
            spent_on_day = daily_map.get(curr_d, 0.0)
            daily_timeline.append({
                'date': curr_d.strftime('%Y-%m-%d'),
                'day': day_num,
                'amount': round(spent_on_day, 2),
                'type': 'actual'
            })

        # Threshold check: requires at least 14 active spending days
        min_required_days = 14
        if historical_days_count < min_required_days:
            # Fallback baseline
            return cls._generate_fallback_forecast(
                user_id=user_id,
                actual_spent_so_far=actual_spent_so_far,
                current_daily_pace=current_daily_pace,
                days_passed=days_passed,
                days_remaining=days_remaining,
                total_days_in_month=total_days_in_month,
                target_date=target_date,
                budget_limit=budget_limit,
                daily_timeline=daily_timeline,
                historical_monthly_data=historical_monthly_data,
                historical_days_count=historical_days_count,
                min_required_days=min_required_days
            )

        # Sufficient historical observations exist: Train Machine Learning Model
        return cls._train_and_forecast_ml(
            all_txs=all_txs,
            daily_map=daily_map,
            actual_spent_so_far=actual_spent_so_far,
            current_daily_pace=current_daily_pace,
            days_passed=days_passed,
            days_remaining=days_remaining,
            total_days_in_month=total_days_in_month,
            target_date=target_date,
            month_start=month_start,
            month_end=month_end,
            budget_limit=budget_limit,
            daily_timeline=daily_timeline,
            historical_monthly_data=historical_monthly_data
        )

    @classmethod
    def _generate_fallback_forecast(cls, user_id, actual_spent_so_far, current_daily_pace,
                                     days_passed, days_remaining, total_days_in_month,
                                     target_date, budget_limit, daily_timeline,
                                     historical_monthly_data, historical_days_count, min_required_days):
        """Generates transparent daily-average baseline forecast."""
        projected_daily = current_daily_pace

        # If zero spend so far, look at historical average across any available transactions
        if projected_daily == 0.0:
            prior_txs = Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.type == 'expense',
                Transaction.transaction_date < target_date
            ).all()
            if prior_txs:
                total_prior = sum(float(t.amount) for t in prior_txs)
                num_days_active = len(set(t.transaction_date for t in prior_txs))
                projected_daily = (total_prior / num_days_active) if num_days_active > 0 else 25.0
            else:
                projected_daily = 30.0  # reasonable default starting projection

        forecast_remaining = projected_daily * days_remaining
        predicted_total = actual_spent_so_far + forecast_remaining

        # Complete daily timeline with baseline projections
        for d_rem in range(days_passed + 1, total_days_in_month + 1):
            curr_d = date(target_date.year, target_date.month, d_rem)
            daily_timeline.append({
                'date': curr_d.strftime('%Y-%m-%d'),
                'day': d_rem,
                'amount': round(projected_daily, 2),
                'type': 'forecast'
            })

        # Uncertainty: +/- 15% on remaining baseline projection
        uncertainty_margin = forecast_remaining * 0.15
        lower_bound = max(actual_spent_so_far, predicted_total - uncertainty_margin)
        upper_bound = predicted_total + uncertainty_margin

        warning_msg = (
            f"Notice: You have {historical_days_count} historical expense days recorded. "
            f"The Machine Learning forecasting engine activates automatically once at least {min_required_days} "
            f"active expense days are recorded. Currently using a transparent daily-average baseline."
        )
        explanation = (
            f"Baseline projection calculated from your month-to-date pace of ${current_daily_pace:,.2f}/day "
            f"multiplied across the remaining {days_remaining} days in the month."
        )

        return {
            'is_ml': False,
            'model_name': 'Daily Average Baseline',
            'actual_spent_so_far': round(actual_spent_so_far, 2),
            'forecast_remaining': round(forecast_remaining, 2),
            'predicted_month_end_total': round(predicted_total, 2),
            'current_daily_pace': round(current_daily_pace, 2),
            'days_passed': days_passed,
            'days_remaining': days_remaining,
            'total_days_in_month': total_days_in_month,
            'mae': None,
            'baseline_mae': None,
            'uncertainty_lower': round(lower_bound, 2),
            'uncertainty_upper': round(upper_bound, 2),
            'budget_limit': budget_limit,
            'budget_difference': round(budget_limit - predicted_total, 2) if budget_limit else None,
            'budget_status': ('exceeded' if predicted_total > budget_limit else 'within') if budget_limit else None,
            'warning': warning_msg,
            'explanation': explanation,
            'daily_timeline': daily_timeline,
            'historical_monthly_data': historical_monthly_data
        }

    @classmethod
    def _train_and_forecast_ml(cls, all_txs, daily_map, actual_spent_so_far, current_daily_pace,
                               days_passed, days_remaining, total_days_in_month, target_date,
                               month_start, month_end, budget_limit, daily_timeline, historical_monthly_data):
        """Trains RandomForestRegressor chronologically and forecasts remaining days."""
        # 1. Build continuous historical daily DataFrame
        earliest_date = min(daily_map.keys())
        time_series_df = build_daily_time_series(daily_map, start_date=earliest_date, end_date=target_date)

        # 2. Extract features
        featured_df = extract_time_series_features(time_series_df)

        # 3. Chronological Train / Validation Split:
        # Use strictly completed historical data prior to current month
        hist_df = featured_df[featured_df['date'].dt.date < month_start].copy()

        # Holdout validation on the most recent completed month
        last_hist_month = hist_df['date'].dt.to_period('M').max()
        train_mask = hist_df['date'].dt.to_period('M') < last_hist_month
        val_mask = hist_df['date'].dt.to_period('M') == last_hist_month

        train_set = hist_df[train_mask]
        val_set = hist_df[val_mask]

        if len(train_set) < 7 or len(val_set) < 5:
            # If historical period only spans one prior month, use chronological 75/25 split
            split_idx = int(len(hist_df) * 0.75)
            train_set = hist_df.iloc[:split_idx]
            val_set = hist_df.iloc[split_idx:]

        X_train = train_set[FEATURE_COLUMNS]
        y_train = train_set['expense']
        X_val = val_set[FEATURE_COLUMNS]
        y_val = val_set['expense']

        # Train Random Forest Regressor
        rf_model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42, min_samples_leaf=2)
        rf_model.fit(X_train, y_train)
        val_preds_rf = rf_model.predict(X_val)
        val_mae_rf = float(mean_absolute_error(y_val, val_preds_rf))

        # Train simple Ridge baseline on validation set to compare
        ridge_model = Ridge()
        ridge_model.fit(X_train, y_train)
        val_preds_ridge = ridge_model.predict(X_val)
        val_mae_baseline = float(mean_absolute_error(y_val, val_preds_ridge))

        # Fit final model on all data strictly prior to target_date
        full_X = hist_df[FEATURE_COLUMNS]
        full_y = hist_df['expense']
        final_model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42, min_samples_leaf=2)
        final_model.fit(full_X, full_y)

        # 4. Multi-step forecasting for remaining days of the current month
        forecast_expenses = []
        running_df = featured_df.copy()

        for day_num in range(days_passed + 1, total_days_in_month + 1):
            next_date = date(target_date.year, target_date.month, day_num)

            # Construct row for next_date with anti-leakage lags
            last_date_val = running_df.iloc[-1]['expense']
            lag7_idx = len(running_df) - 7
            lag7_val = running_df.iloc[lag7_idx]['expense'] if lag7_idx >= 0 else 0.0

            roll7_val = running_df['expense'].iloc[-7:].mean() if len(running_df) >= 7 else running_df['expense'].mean()
            roll14_val = running_df['expense'].iloc[-14:].mean() if len(running_df) >= 14 else running_df['expense'].mean()

            next_dow = next_date.weekday()
            next_is_weekend = 1 if next_dow in [5, 6] else 0
            next_days_rem = total_days_in_month - day_num

            features_row = pd.DataFrame([{
                'day_of_week': next_dow,
                'is_weekend': next_is_weekend,
                'day_of_month': day_num,
                'month': target_date.month,
                'days_remaining': next_days_rem,
                'lag_1': last_date_val,
                'lag_7': lag7_val,
                'rolling_7_mean': roll7_val,
                'rolling_14_mean': roll14_val
            }])[FEATURE_COLUMNS]

            pred_spend = float(final_model.predict(features_row)[0])
            pred_spend = max(0.0, round(pred_spend, 2))
            forecast_expenses.append(pred_spend)

            # Append to running dataframe for iterative lag updating
            new_row = pd.DataFrame([{
                'date': pd.to_datetime(next_date),
                'expense': pred_spend,
                'day_of_week': next_dow,
                'is_weekend': next_is_weekend,
                'day_of_month': day_num,
                'month': target_date.month,
                'days_remaining': next_days_rem,
                'lag_1': last_date_val,
                'lag_7': lag7_val,
                'rolling_7_mean': roll7_val,
                'rolling_14_mean': roll14_val
            }])
            running_df = pd.concat([running_df, new_row], ignore_index=True)

            daily_timeline.append({
                'date': next_date.strftime('%Y-%m-%d'),
                'day': day_num,
                'amount': pred_spend,
                'type': 'forecast'
            })

        forecast_remaining = sum(forecast_expenses)
        predicted_total = actual_spent_so_far + forecast_remaining

        # 5. Uncertainty bounds (based on validation MAE and horizon square root)
        uncertainty_margin = (val_mae_rf * math.sqrt(max(1, days_remaining))) * 1.5
        lower_bound = max(actual_spent_so_far, predicted_total - uncertainty_margin)
        upper_bound = predicted_total + uncertainty_margin

        explanation = (
            f"Forecast generated using RandomForestRegressor (100 estimators, max depth 6) "
            f"trained on {len(hist_df)} historical daily observations with rolling averages and lag features. "
            f"Holdout validation MAE: ${val_mae_rf:.2f} (compared with Ridge baseline MAE: ${val_mae_baseline:.2f})."
        )

        return {
            'is_ml': True,
            'model_name': 'Random Forest Regressor (Time-Series)',
            'actual_spent_so_far': round(actual_spent_so_far, 2),
            'forecast_remaining': round(forecast_remaining, 2),
            'predicted_month_end_total': round(predicted_total, 2),
            'current_daily_pace': round(current_daily_pace, 2),
            'days_passed': days_passed,
            'days_remaining': days_remaining,
            'total_days_in_month': total_days_in_month,
            'mae': round(val_mae_rf, 2),
            'baseline_mae': round(val_mae_baseline, 2),
            'uncertainty_lower': round(lower_bound, 2),
            'uncertainty_upper': round(upper_bound, 2),
            'budget_limit': budget_limit,
            'budget_difference': round(budget_limit - predicted_total, 2) if budget_limit else None,
            'budget_status': ('exceeded' if predicted_total > budget_limit else 'within') if budget_limit else None,
            'warning': None,
            'explanation': explanation,
            'daily_timeline': daily_timeline,
            'historical_monthly_data': historical_monthly_data
        }

    @staticmethod
    def _get_historical_monthly_totals(user_id, current_year, current_month, num_months=6):
        """Returns historical monthly spending totals for the past N months."""
        results = []
        cur_date = date(current_year, current_month, 1)

        for i in range(num_months, 0, -1):
            m_date = cur_date - timedelta(days=i * 28)
            # Find start and end of that month
            y = m_date.year
            m = m_date.month
            m_start = date(y, m, 1)
            m_end = date(y, m, calendar.monthrange(y, m)[1])

            total = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'expense',
                Transaction.transaction_date >= m_start,
                Transaction.transaction_date <= m_end
            ).scalar()

            results.append({
                'label': f"{calendar.month_abbr[m]} {y}",
                'month': m,
                'year': y,
                'amount': round(float(total), 2)
            })

        return results
