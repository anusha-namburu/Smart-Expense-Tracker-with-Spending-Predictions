from datetime import date
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.analytics.service import AnalyticsService

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/')
@login_required
def index():
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year = request.args.get('year', today.year, type=int)

    insights_data = AnalyticsService.generate_personalized_insights(current_user.id, current_date=today)
    breakdown = AnalyticsService.get_category_breakdown(current_user.id, month=month, year=year)

    return render_template(
        'analytics/index.html',
        insights_data=insights_data,
        breakdown=breakdown,
        selected_month=month,
        selected_year=year
    )

@analytics_bp.route('/api')
@login_required
def api():
    today = date.today()
    month = request.args.get('month', today.month, type=int)
    year = request.args.get('year', today.year, type=int)

    breakdown = AnalyticsService.get_category_breakdown(current_user.id, month=month, year=year)
    insights_data = AnalyticsService.generate_personalized_insights(current_user.id, current_date=today)

    return jsonify({
        'breakdown': breakdown,
        'insights': insights_data['insights'],
        'recommendations': insights_data['recommendations']
    })
