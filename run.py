import os
from dotenv import load_dotenv
from app import create_app
from app.extensions import db
from app.utils import init_default_categories

# Load environment variables from .env if present
load_dotenv()

app = create_app(os.environ.get('FLASK_ENV', 'development'))

# Auto-initialise the database when the app module is loaded.
# This runs for both `python run.py` (dev) and `gunicorn run:app` (production).
with app.app_context():
    db.create_all()
    init_default_categories()

@app.cli.command("init-db")
def init_db_command():
    """Initializes the database schema and default categories."""
    with app.app_context():
        db.create_all()
        init_default_categories()
        print("Database schema and default categories initialized successfully.")

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)

