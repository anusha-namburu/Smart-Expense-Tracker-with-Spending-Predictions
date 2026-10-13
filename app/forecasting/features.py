import calendar
from datetime import date, timedelta
import pandas as pd
import numpy as np

FEATURE_COLUMNS = [
    'day_of_week',
    'is_weekend',
    'day_of_month',
    'month',
    'days_remaining',
    'lag_1',
    'lag_7',
    'rolling_7_mean',
    'rolling_14_mean'
]

def build_daily_time_series(daily_records, start_date=None, end_date=None):
    """
    Takes a dictionary or sequence of (date, expense_amount) and returns
    a complete, continuous daily pandas DataFrame with missing days filled with 0.0.
    """
    if not daily_records:
        if start_date is None or end_date is None:
            return pd.DataFrame()
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        return pd.DataFrame({'expense': 0.0}, index=pd.Index(dates.date, name='date'))

    df = pd.DataFrame(list(daily_records.items()), columns=['date', 'expense'])
    df['date'] = pd.to_datetime(df['date']).dt.date
    df = df.groupby('date')['expense'].sum().reset_index()

    min_date = start_date if start_date else df['date'].min()
    max_date = end_date if end_date else df['date'].max()

    full_dates = pd.date_range(start=min_date, end=max_date, freq='D').date
    full_df = pd.DataFrame({'date': full_dates})
    merged = pd.merge(full_df, df, on='date', how='left').fillna({'expense': 0.0})
    merged.sort_values('date', inplace=True)
    merged.reset_index(drop=True, inplace=True)
    return merged

def extract_time_series_features(df):
    """
    Extracts time-series features with strict anti-leakage shifts.
    Lags and rolling metrics only use prior days (shift=1).
    """
    if df.empty or len(df) == 0:
        return df

    data = df.copy()
    data['date'] = pd.to_datetime(data['date'])
    data['day_of_week'] = data['date'].dt.dayofweek
    data['is_weekend'] = data['day_of_week'].isin([5, 6]).astype(int)
    data['day_of_month'] = data['date'].dt.day
    data['month'] = data['date'].dt.month

    # Days remaining in month
    def get_days_remaining(dt):
        num_days = calendar.monthrange(dt.year, dt.month)[1]
        return num_days - dt.day

    data['days_remaining'] = data['date'].apply(get_days_remaining)

    # Shift by 1 to prevent target data leakage
    shifted = data['expense'].shift(1).fillna(0.0)
    data['lag_1'] = shifted
    data['lag_7'] = data['expense'].shift(7).fillna(0.0)
    data['rolling_7_mean'] = shifted.rolling(window=7, min_periods=1).mean().fillna(0.0)
    data['rolling_14_mean'] = shifted.rolling(window=14, min_periods=1).mean().fillna(0.0)

    return data
