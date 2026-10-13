import calendar
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func
from app.extensions import db
from app.models import Transaction, Category, Budget
from app.utils import calculate_savings_rate, format_currency

class AnalyticsService:
    @staticmethod
    def get_category_breakdown(user_id, month=None, year=None):
        """Returns spending grouped by category for the specified month and year."""
        if month is None or year is None:
            today = date.today()
            month = today.month
            year = today.year

        start_date = date(year, month, 1)
        end_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, end_day)

        results = db.session.query(
            Category.name,
            Category.color,
            Category.icon,
            func.coalesce(func.sum(Transaction.amount), 0).label('total_amount'),
            func.count(Transaction.id).label('tx_count')
        ).join(
            Transaction, Transaction.category_id == Category.id
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

        total_expenses = sum(float(r.total_amount) for r in results)

        categories = []
        for r in results:
            amt = float(r.total_amount)
            pct = (amt / total_expenses * 100.0) if total_expenses > 0 else 0.0
            categories.append({
                'name': r.name,
                'color': r.color,
                'icon': r.icon,
                'amount': round(amt, 2),
                'count': r.tx_count,
                'percentage': round(pct, 1)
            })

        return {
            'month': month,
            'year': year,
            'total_expenses': round(total_expenses, 2),
            'categories': categories,
            'chart_labels': [c['name'] for c in categories],
            'chart_data': [c['amount'] for c in categories],
            'chart_colors': [c['color'] for c in categories]
        }

    @staticmethod
    def get_mom_comparison(user_id, current_date=None):
        """Calculates Month-over-Month spending comparisons safely handling zeros."""
        if current_date is None:
            current_date = date.today()

        cur_year = current_date.year
        cur_month = current_date.month

        # Determine previous month
        if cur_month == 1:
            prev_month = 12
            prev_year = cur_year - 1
        else:
            prev_month = cur_month - 1
            prev_year = cur_year

        cur_start = date(cur_year, cur_month, 1)
        cur_end = date(cur_year, cur_month, calendar.monthrange(cur_year, cur_month)[1])

        prev_start = date(prev_year, prev_month, 1)
        prev_end = date(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])

        # Current month total
        cur_total = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.transaction_date >= cur_start,
            Transaction.transaction_date <= cur_end
        ).scalar()
        cur_total = float(cur_total)

        # Previous month total
        prev_total = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.transaction_date >= prev_start,
            Transaction.transaction_date <= prev_end
        ).scalar()
        prev_total = float(prev_total)

        if prev_total > 0:
            diff = cur_total - prev_total
            pct_change = (diff / prev_total) * 100.0
        else:
            diff = cur_total
            pct_change = None

        return {
            'current_month_name': calendar.month_name[cur_month],
            'current_year': cur_year,
            'previous_month_name': calendar.month_name[prev_month],
            'previous_year': prev_year,
            'current_total': round(cur_total, 2),
            'previous_total': round(prev_total, 2),
            'difference': round(diff, 2),
            'pct_change': round(pct_change, 1) if pct_change is not None else None
        }

    @classmethod
    def generate_personalized_insights(cls, user_id, current_date=None):
        """
        Rule-based deterministic insights engine.
        Produces explainable, data-driven financial insights with actionable tips.
        """
        if current_date is None:
            current_date = date.today()

        insights = []
        recommendations = []

        # 1. Month-over-month total change
        mom = cls.get_mom_comparison(user_id, current_date)
        if mom['previous_total'] > 0:
            if mom['pct_change'] is not None and mom['pct_change'] > 5.0:
                insights.append({
                    'type': 'warning',
                    'icon': 'bi-arrow-up-right-circle',
                    'title': 'Spending Spike Compared to Last Month',
                    'text': f"Your total expenses so far are {abs(mom['pct_change'])}% higher than the entirety of {mom['previous_month_name']} (${mom['current_total']:,.2f} vs ${mom['previous_total']:,.2f}).",
                    'period': f"{mom['previous_month_name']} vs {mom['current_month_name']}"
                })
            elif mom['pct_change'] is not None and mom['pct_change'] < -5.0:
                insights.append({
                    'type': 'success',
                    'icon': 'bi-arrow-down-right-circle',
                    'title': 'Reduced Spending Trajectory',
                    'text': f"Your total expenses are currently {abs(mom['pct_change'])}% lower than {mom['previous_month_name']}.",
                    'period': f"{mom['previous_month_name']} vs {mom['current_month_name']}"
                })
        elif mom['current_total'] > 0 and mom['previous_total'] == 0:
            insights.append({
                'type': 'info',
                'icon': 'bi-info-circle',
                'title': 'New Spending Activity',
                'text': f"You have recorded ${mom['current_total']:,.2f} in expenses this month (no transactions recorded in {mom['previous_month_name']}).",
                'period': f"{mom['current_month_name']}"
            })

        # 2. Category Breakdown analysis
        breakdown = cls.get_category_breakdown(user_id, current_date.month, current_date.year)
        if breakdown['categories']:
            top_cat = breakdown['categories'][0]
            if top_cat['percentage'] >= 30.0:
                insights.append({
                    'type': 'primary',
                    'icon': 'bi-pie-chart',
                    'title': f"{top_cat['name']} Dominates Your Budget",
                    'text': f"{top_cat['name']} represents {top_cat['percentage']}% (${top_cat['amount']:,.2f}) of your total expenses this month.",
                    'period': f"{calendar.month_name[current_date.month]} {current_date.year}"
                })
                if top_cat['name'].lower() in ['shopping', 'entertainment', 'food']:
                    recommendations.append(
                        f"Consider setting a tighter budget cap on {top_cat['name']} to balance discretionary spending."
                    )

        # 3. Income vs Expense Cash-Flow & Savings Rate
        cur_start = date(current_date.year, current_date.month, 1)
        cur_end = date(current_date.year, current_date.month, calendar.monthrange(current_date.year, current_date.month)[1])

        month_income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'income',
            Transaction.transaction_date >= cur_start,
            Transaction.transaction_date <= cur_end
        ).scalar()
        month_income = float(month_income)

        if month_income > 0:
            savings_rate = calculate_savings_rate(month_income, breakdown['total_expenses'])
            if savings_rate >= 20.0:
                insights.append({
                    'type': 'success',
                    'icon': 'bi-shield-check',
                    'title': 'Healthy Savings Rate',
                    'text': f"Your savings rate for {calendar.month_name[current_date.month]} is {savings_rate}%, well above the recommended 20% benchmark.",
                    'period': 'Current Month'
                })
            elif savings_rate < 0:
                insights.append({
                    'type': 'danger',
                    'icon': 'bi-exclamation-triangle',
                    'title': 'Cash-Flow Deficit',
                    'text': f"Expenses exceed income by ${abs(month_income - breakdown['total_expenses']):,.2f} this month.",
                    'period': 'Current Month'
                })
                recommendations.append("Review non-essential subscription and dining expenses to bring monthly cash flow into positive balance.")

        # 4. Active Budget Pace Alerts
        active_budgets = Budget.query.filter_by(
            user_id=user_id,
            month=current_date.month,
            year=current_date.year
        ).all()

        days_passed = current_date.day
        total_days = calendar.monthrange(current_date.year, current_date.month)[1]

        for b in active_budgets:
            limit_val = float(b.monthly_limit)
            if limit_val <= 0:
                continue

            if b.is_overall:
                spent = breakdown['total_expenses']
                label = "Overall Monthly Budget"
            else:
                cat_match = next((c for c in breakdown['categories'] if c['name'] == (b.category.name if b.category else '')), None)
                spent = cat_match['amount'] if cat_match else 0.0
                label = f"{b.category.name} Budget" if b.category else "Category Budget"

            util = (spent / limit_val) * 100.0
            if days_passed > 0:
                daily_pace = spent / days_passed
                projected_end = daily_pace * total_days
                if projected_end > limit_val and util < 100.0:
                    insights.append({
                        'type': 'warning',
                        'icon': 'bi-speedometer2',
                        'title': f"Projected Budget Overrun: {label}",
                        'text': f"At your current pace of ${daily_pace:,.2f}/day, spending will reach ${projected_end:,.2f} by month-end, exceeding your ${limit_val:,.2f} limit.",
                        'period': 'Current Month Projection'
                    })

        # Default recommendation if none
        if not recommendations:
            recommendations.append("Keep logging daily transactions to maintain high ML prediction accuracy.")
            recommendations.append("Establish monthly budget limits for your top 3 expense categories.")

        disclaimer = "These automated insights are calculated algorithmically for informational budgeting assistance and do not constitute certified professional financial advice."

        return {
            'insights': insights,
            'recommendations': recommendations,
            'disclaimer': disclaimer,
            'category_breakdown': breakdown,
            'mom_comparison': mom
        }
