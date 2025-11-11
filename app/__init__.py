# app/__init__.py
from flask import Flask, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os, json
from .config import Config
import shutil, platform

db = SQLAlchemy()

def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    if isinstance(value, datetime):
        return value.strftime(format)
    return value

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Only set defaults if not already set in config.py
    app.config.setdefault('SECRET_KEY', 'your_secret_key')
    app.config.setdefault('SQLALCHEMY_DATABASE_URI',
                          'mysql+pymysql://dor_pi:T0m3r!970S@172.234.160.57/dor_pi')
    app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {'pool_pre_ping': True})

    # OpenAI Key from Environment
    app.config["OPENAI_KEY"] = os.getenv("OPENAI_API_KEY")

    # wkhtmltopdf (legacy)
    app.config.setdefault(
        'WKHTMLTOPDF_CMD',
        os.getenv('WKHTMLTOPDF_CMD')  # allow override
        or shutil.which('wkhtmltopdf')  # Linux/most
        or (r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"  # Windows fallback
            if platform.system() == "Windows" else "/usr/bin/wkhtmltopdf")
    )

    # Ensure instance folders exist (for generated files etc.)
    os.makedirs(app.instance_path, exist_ok=True)
    gen_dir = os.path.join(app.instance_path, "generated_reports")
    os.makedirs(gen_dir, exist_ok=True)

    # Public URL for generated .docx files
    @app.route("/static/generated/<path:filename>")
    def generated_reports(filename):
        return send_from_directory(gen_dir, filename)

    # Initialize DB
    db.init_app(app)

    # Register custom filters
    app.jinja_env.filters['datetimeformat'] = datetimeformat

    # ---- Global context: user, shop, roles (safe defaults) ----
    @app.context_processor
    def inject_user_shop_and_roles():
        try:
            user_data = session.get('user')
            shop_data = session.get('shop')
            user = json.loads(user_data) if user_data else {}
            shop = json.loads(shop_data) if shop_data else {}
        except Exception:
            user, shop = {}, {}

        roles = []
        try:
            from .models import TocRole
            rows = db.session.query(TocRole).all()
            roles = [{'role': r.role, 'exclusions': r.exclusions} for r in rows]
        except Exception:
            roles = []

        return dict(user=user, shop=shop, roles=roles)

    # ---- Blueprints ----
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .reports_ui import reports_ui_bp
    app.register_blueprint(reports_ui_bp)

    # DOCX/reporting endpoints (/reports/<id>/preview, /render-docx, etc.)
    from .reports_docx import reports_docx_bp
    app.register_blueprint(reports_docx_bp)

    return app
