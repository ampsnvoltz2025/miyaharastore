# run.py
from app import create_app, db
from app.models import User, Item, Cart, Order
import os
import ssl
from OpenSSL import crypto
import sys

app = create_app()

def init_db():
    with app.app_context():
        # Always ensure tables exist
        db.create_all()
        # When running as a packaged EXE (PyInstaller onefile), skip Alembic operations.
        if getattr(sys, 'frozen', False):
            return
        # Optionally run migrations only in a developer environment where migrations are editable
        try:
            from flask_migrate import upgrade as upgrade_db
            upgrade_db()
        except Exception:
            # If migrations are not available or another issue occurs, continue without failing
            pass

if __name__ == '__main__':
    # Set the environment
    os.environ['FLASK_ENV'] = 'production'
    
    # Initialize database and migrations
    init_db()
    
    with app.app_context():
        # Create admin user if not exists
        admin = User.query.filter_by(email='admin@example.com').first()
        if not admin:
            from werkzeug.security import generate_password_hash
            admin = User(
                email='admin@example.com',
                first_name='Admin',
                password=generate_password_hash('admin123', method='sha256'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
    
    # Run the app with HTTPS
    print("Starting server with HTTPS...")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    
    # Force HTTPS redirects
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=context)