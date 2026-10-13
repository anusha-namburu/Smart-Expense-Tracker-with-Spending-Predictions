import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-fallback-insecure-key-2026-expense-tracker'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'smart_expense_tracker.db')
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    ITEMS_PER_PAGE = 15
    ML_MIN_TRAINING_DAYS = int(os.environ.get('ML_MIN_TRAINING_DAYS', 14))
    ML_MODEL_CACHE_DIR = os.path.join(basedir, 'instance', 'ml_models')
    DEFAULT_CURRENCY = os.environ.get('DEFAULT_CURRENCY', '$')

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    ML_MIN_TRAINING_DAYS = 10

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
