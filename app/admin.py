# app/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user
from .models import Item, Order, StoreSettings, db
from werkzeug.utils import secure_filename
from functools import wraps
import os

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

admin = Blueprint('admin', __name__)

# Apply admin_required to all routes in this blueprint
@admin.before_request
@login_required
@admin_required
def require_admin():
    pass  # The actual check is done in the decorator

# Import routes after the admin_required decorator is defined
from . import routes

@admin.route('/')
def dashboard():
    total_items = Item.query.count()
    total_orders = Order.query.count()
    recent_orders = Order.query.order_by(Order.date_ordered.desc()).limit(5).all()
    settings = StoreSettings.get_settings()
    return render_template('admin/dashboard.html', 
                         total_items=total_items,
                         total_orders=total_orders,
                         recent_orders=recent_orders,
                         settings=settings)

@admin.route('/items')
def items():
    all_items = Item.query.all()
    return render_template('admin/items.html', items=all_items)

@admin.route('/items/new', methods=['GET', 'POST'])
def new_item():
    if request.method == 'POST':
        image_path = ''
        name = request.form.get('name')
        price = float(request.form.get('price'))
        description = request.form.get('description')
        stock = int(request.form.get('stock', 0))
        max_per_customer = int(request.form.get('max_per_customer', 1))
        barcode = request.form.get('barcode', '').strip() or None
        
        # Check if barcode already exists
        if barcode and Item.query.filter_by(barcode=barcode).first():
            flash('A product with this barcode already exists!', 'error')
            return render_template('admin/new_item.html')
        
        # Handle file upload
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                # filename = secure_filename(image.filename)
                filename = image.filename
                image_path = os.path.join('static/uploads', filename)
                image.save(os.path.join('miyaharastore/app', image_path))
                image_url = url_for('app/static', filename=f'uploads/{filename}')
            else:
                image_url = None
        else:
            image_url = None
        
        new_item = Item(
            name=name,
            price=price,
            description=description,
            stock=stock,
            max_per_customer=max_per_customer,
            barcode=barcode,
            image_url=image_url
        )
        
        db.session.add(new_item)
        db.session.commit()
        
        flash(f'Item added successfully! {image_path}', 'success')
        return redirect(url_for('admin.items'))
    
    return render_template('admin/new_item.html')

@admin.route('/items/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.price = float(request.form.get('price'))
        item.description = request.form.get('description')
        item.stock = int(request.form.get('stock', 0))
        item.max_per_customer = int(request.form.get('max_per_customer', 1))
        
        # Update barcode if provided and not in use
        new_barcode = request.form.get('barcode', '').strip() or None
        if new_barcode and new_barcode != item.barcode:
            if Item.query.filter(Item.id != item.id, Item.barcode == new_barcode).first():
                flash('A product with this barcode already exists!', 'error')
                return redirect(url_for('admin.edit_item', item_id=item.id))
            item.barcode = new_barcode
        
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                # filename = secure_filename(image.filename)
                filename = image.filename
                image_path = os.path.join('static/uploads', filename)
                image.save(os.path.join('miyaharastore/app', image_path))
                item.image_url = url_for('app/static', filename=f'uploads/{filename}')
        
        db.session.commit()
        flash(f'Item updated successfully! {os.path.join('app', image_path)}', 'success')
        return redirect(url_for('admin.items'))
    
    return render_template('admin/edit_item.html', item=item)

@admin.route('/items/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted successfully!', 'success')
    return redirect(url_for('admin.items'))

@admin.route('/orders')
def orders():
    all_orders = Order.query.order_by(Order.date_ordered.desc()).all()
    settings = StoreSettings.get_settings()
    return render_template('admin/orders.html', orders=all_orders, settings=settings)

@admin.route('/order/<int:order_id>')
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    settings = StoreSettings.get_settings()
    return render_template('admin/view_order.html', order=order, settings=settings)

@admin.route('/order/update_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['Processing', 'Shipped', 'Delivered', 'Cancelled']:
        order.status = new_status
        db.session.commit()
        flash('Order status updated successfully!', 'success')
    else:
        flash('Invalid status!', 'error')
    
    return redirect(url_for('admin.view_order', order_id=order_id))

@admin.route('/settings', methods=['GET', 'POST'])
@login_required
@require_admin
def settings():
    settings = StoreSettings.get_settings()
    
    if request.method == 'POST':
        try:
            # Validate currency symbol (1-3 characters)
            currency = request.form.get('currency', '$').strip()
            if not 1 <= len(currency) <= 3:
                flash('Currency symbol must be 1-3 characters long', 'error')
                return redirect(url_for('admin.settings'))
                
            settings.currency = currency
            settings.currency_position = request.form.get('currency_position', 'left')
            settings.show_addresses = 'show_addresses' in request.form
            settings.show_prices = 'show_prices' in request.form
            settings.prices_as_free = 'prices_as_free' in request.form
            
            # If prices are hidden, ensure prices_as_free is False
            if not settings.show_prices:
                settings.prices_as_free = False
            
            db.session.commit()
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('admin.settings'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating settings: {str(e)}', 'error')
            return redirect(url_for('admin.settings'))
        
    return render_template('admin/settings.html', settings=settings)