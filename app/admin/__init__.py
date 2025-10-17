from flask import Blueprint
from flask_login import login_required, current_user
from functools import wraps

def admin_required(f):
    """Decorator to ensure user is logged in and is an admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('views.home'))
        return f(*args, **kwargs)
    return decorated_function

# Create admin blueprint
admin = Blueprint('admin', __name__)

# Import routes after creating the blueprint to avoid circular imports
from . import routes
