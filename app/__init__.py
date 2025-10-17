# app/__init__.py
from flask import Flask, request, redirect, current_app, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
import os
import ssl
import sys

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
DB_NAME = "store.db"

# Ensure the migrations directory exists
def ensure_migrations_dir():
    from app import app
    migrations_dir = os.path.join(app.root_path, '..', 'migrations')
    os.makedirs(migrations_dir, exist_ok=True)
    return migrations_dir

def create_app():
    app = Flask(__name__)
    
    # Secret key configuration
    app.config['SECRET_KEY'] = 'your-secret-key'  # In production, use a strong, unique secret key
    
    # CSRF Configuration
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_SECRET_KEY'] = 'a-different-secret-key'  # Different from SECRET_KEY
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour CSRF token lifetime
    app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken']
    app.config['WTF_CSRF_SSL_STRICT'] = False  # Set to True in production with HTTPS
    
    # Database Configuration
    # Use a user-writable data directory when packaged (PyInstaller) or
    # when overridden via STOREAPP_DATA_DIR env var.
    data_dir = os.environ.get('STOREAPP_DATA_DIR')
    if not data_dir:
        if getattr(sys, 'frozen', False):
            # Prefer %LOCALAPPDATA%\StoreApp for installed EXE
            local_appdata = os.environ.get('LOCALAPPDATA', os.getcwd())
            data_dir = os.path.join(local_appdata, 'StoreApp')
        else:
            # In development, keep data next to the project root
            data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    try:
        os.makedirs(data_dir, exist_ok=True)
    except Exception:
        pass
    db_path = os.path.join(data_dir, DB_NAME)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Session Configuration
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Configure server name and proxy settings
    app.config['PREFERRED_URL_SCHEME'] = 'http'
    
    # Only set SERVER_NAME in production with a proper domain
    if os.environ.get('FLASK_ENV') == 'production':
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
        app.config['PREFERRED_URL_SCHEME'] = 'https'
        # Set your production domain here
        # app.config['SERVER_NAME'] = 'yourdomain.com'
    
    # Configure session cookie settings
    app.config.update(
        SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        # Use a proper domain with at least one dot for production
        # SESSION_COOKIE_DOMAIN='.yourdomain.com'  # Note the leading dot
    )
    
    # Initialize extensions with app
    db.init_app(app)
    # Migrate will be initialized once below with the migrations directory
    
    # Initialize CSRF protection after all other extensions
    csrf.init_app(app)
    
    # Import models after db is initialized to avoid circular imports
    from . import models
    
    # Initialize the database
    with app.app_context():
        db.create_all()
        # Create default settings if they don't exist
        if not models.StoreSettings.query.first():
            default_settings = models.StoreSettings()
            db.session.add(default_settings)
            db.session.commit()
    
    # Import blueprints after CSRF is initialized to avoid circular imports
    from .views import views, api_scan_barcode
    from .admin import admin as admin_blueprint
    from .auth import auth
    
    # Register blueprints
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    
    # Exempt the API endpoint from CSRF protection
    csrf.exempt(api_scan_barcode)  # Exempt the API endpoint function
    
    # Make store settings available in all templates
    @app.context_processor
    def inject_settings():
        from .models import StoreSettings
        settings = StoreSettings.get_settings()
        return dict(store_settings=settings)
    
    # Make store settings available in request context
    @app.before_request
    def before_request():
        from .models import StoreSettings
        g.store_settings = StoreSettings.get_settings()
    
    # Ensure CSRF token is available in all templates
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token_value=generate_csrf())
    
    # Set CSRF token in cookie for JavaScript
    @app.after_request
    def set_csrf_cookie(response):
        if response.status_code == 200 and 'text/html' in response.content_type:
            csrf_token = generate_csrf()
            response.set_cookie('csrf_token', csrf_token, 
                             httponly=False,  # Allow JavaScript to read the cookie
                             samesite='Lax',
                             secure=app.config.get('PREFERRED_URL_SCHEME') == 'https')
        return response
    
    # Configure migrations directory (robust for PyInstaller onefile)
    base_path = getattr(sys, '_MEIPASS', None)
    if base_path:
        migrations_dir = os.path.join(base_path, 'migrations')
    else:
        migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
    migrate.init_app(app, db, directory=migrations_dir)
    
    # Ensure migrations directory exists (no-op in onefile if read-only)
    try:
        os.makedirs(migrations_dir, exist_ok=True)
    except Exception:
        pass
    
    from .models import User, Item, Cart, Order
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    
    # Add HTTPS redirect middleware
    @app.before_request
    def redirect_to_https():
        # Skip for local development without HTTPS
        if request.url.startswith('http://') and not request.is_secure:
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)
    
    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    return app
