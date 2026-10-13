import logging
from flask import Blueprint, render_template
from app.extensions import db

errors_bp = Blueprint('errors', __name__)
logger = logging.getLogger(__name__)

@errors_bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@errors_bp.app_errorhandler(403)
def forbidden_error(error):
    return render_template('errors/404.html', message="You do not have permission to view or modify this resource."), 403

@errors_bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal server error: {error}")
    return render_template('errors/500.html'), 500
