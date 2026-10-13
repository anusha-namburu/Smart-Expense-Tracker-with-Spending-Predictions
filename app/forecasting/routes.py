from datetime import date
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.forecasting.service import ForecastService

forecasting_bp = Blueprint('forecasting', __name__)

@forecasting_bp.route('/')
@login_required
def index():
    today = date.today()
    forecast = ForecastService.generate_spending_forecast(current_user.id, target_date=today)
    return render_template('forecasting/index.html', forecast=forecast, today=today)

@forecasting_bp.route('/api')
@login_required
def api():
    today = date.today()
    forecast = ForecastService.generate_spending_forecast(current_user.id, target_date=today)
    return jsonify(forecast)
