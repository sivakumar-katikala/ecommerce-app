import logging
from datetime import datetime

from flask import Flask, render_template, request
from flask_login import current_user

from config import Config
from extensions import db, csrf, login_manager

# Make INFO/WARNING logs (including email send attempts) visible in the console
# when running `python app.py` — without this, Flask's default logger level
# hides them and it looks like nothing happened.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ---- Initialize extensions ----
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    from models import User, Visit

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ---- Register blueprints ----
    from routes.auth import auth_bp
    from routes.products import products_bp
    from routes.orders import orders_bp
    from routes.owner import owner_bp
    from routes.payment import payment_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(payment_bp)

    # ---- Track visits (who visits the app, and which pages) ----
    @app.before_request
    def log_visit():
        if request.method != 'GET' or request.path.startswith('/static'):
            return
        try:
            visit = Visit(
                user_id=current_user.id if current_user.is_authenticated else None,
                path=request.path,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:255],
            )
            db.session.add(visit)
            db.session.commit()
        except Exception:
            db.session.rollback()

    # ---- Security headers (basic CSP and related hardening) ----
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "font-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response

    # ---- Error handlers ----
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # ---- Template globals ----
    @app.context_processor
    def inject_globals():
        return {'current_year': datetime.utcnow().year}

    # ---- DB init + seed data ----
    with app.app_context():
        db.create_all()
        _check_schema_matches_models(app)
        from seed import seed_data
        seed_data()

    return app


def _check_schema_matches_models(app):
    """db.create_all() only creates NEW tables — it never adds columns to a
    table that already exists. If the code changes and adds a column, an old
    instance/ecom.db file will be missing it, which otherwise fails deep inside
    a request with a confusing traceback. Catch that here at startup instead,
    with a clear, actionable message."""
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(db.engine)
    problems = []

    for table in db.metadata.sorted_tables:
        if table.name not in inspector.get_table_names():
            continue
        existing_columns = {col['name'] for col in inspector.get_columns(table.name)}
        expected_columns = {col.name for col in table.columns}
        missing = expected_columns - existing_columns
        if missing:
            problems.append(f'  - table "{table.name}" is missing column(s): {", ".join(sorted(missing))}')

    if problems:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        db_path = db_uri.replace('sqlite:///', '') if db_uri.startswith('sqlite:///') else db_uri
        app.logger.warning(
            '\n' + '=' * 70 +
            '\n⚠️  DATABASE SCHEMA IS OUT OF DATE\n' +
            'Your database file is missing columns the app now expects:\n' +
            '\n'.join(problems) +
            '\n\nThis happens when the code is updated after the database was\n'
            'already created. Fix it by deleting the database file and letting\n'
            'the app recreate it (this clears existing data):\n\n'
            f'  Windows (PowerShell):  Remove-Item "{db_path}"\n'
            f'  macOS/Linux:           rm "{db_path}"\n\n'
            'Then restart the app.\n' +
            '=' * 70
        )


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
