import os
from datetime import date
from flask import Flask, render_template, redirect, url_for
from flask_login import current_user
from config import config
from app.extensions import db, login_manager, csrf
from app.utils import format_currency

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Ensure instance directory exists
    os.makedirs(app.instance_path, exist_ok=True)
    if 'ML_MODEL_CACHE_DIR' in app.config:
        os.makedirs(app.config['ML_MODEL_CACHE_DIR'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register Blueprints
    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.transactions.routes import transactions_bp
    from app.budgets.routes import budgets_bp
    from app.forecasting.routes import forecasting_bp
    from app.analytics.routes import analytics_bp
    from app.notifications.routes import notifications_bp
    from app.errors.handlers import errors_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(transactions_bp, url_prefix='/transactions')
    app.register_blueprint(budgets_bp, url_prefix='/budgets')
    app.register_blueprint(forecasting_bp, url_prefix='/forecasting')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(errors_bp)

    # Landing page route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return render_template('index.html')

    # Global Jinja Context Processors
    @app.context_processor
    def inject_global_data():
        unread_count = 0
        if current_user.is_authenticated:
            from app.models import Notification
            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()

        return {
            'current_year': date.today().year,
            'unread_notifications_count': unread_count,
            'format_currency': format_currency
        }

    # Global Jinja Filters
    @app.template_filter('currency')
    def currency_filter(value, symbol=None):
        if symbol is None:
            symbol = current_user.currency if (current_user and current_user.is_authenticated) else '$'
        return format_currency(value, symbol)

    @app.template_filter('pct')
    def pct_filter(value):
        try:
            return f"{float(value):.1f}%"
        except (ValueError, TypeError):
            return "0.0%"

    return app
