from flask import render_template, request, redirect, url_for, flash, Response
import csv
from io import StringIO
from . import admin
from ..models import Item, Order, StoreSettings, User, db
from werkzeug.utils import secure_filename
import os

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
    settings = StoreSettings.get_settings()
    return render_template('admin/items.html', 
                         items=all_items,
                         store_settings=settings)

@admin.route('/items/new', methods=['GET', 'POST'])
def new_item():
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price', 0))
        description = request.form.get('description', '')
        stock = int(request.form.get('stock', 0))
        barcode = request.form.get('barcode', '')
        
        # Handle file upload
        image = request.files.get('image')
        image_path = None
        if image and image.filename:
            # filename = secure_filename(image.filename)
            filename = image.filename
            upload_folder = os.path.join('app', 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            # Save the image file with proper path formatting
            relative_path = os.path.join('uploads', filename).replace('\\', '/')
            image.save(os.path.join('miyaharastore/app', 'static', relative_path))
            # Format the URL with a leading slash for web access
            image_path = f'{os.path.join('miyaharastore/app', 'static', relative_path)}'
        
        try:
            item = Item(
                name=name,
                price=price,
                description=description,
                stock=stock,
                barcode=barcode,
                image_url=image_path
            )
            db.session.add(item)
            db.session.commit()
            flash(f'Item added successfully! {image_path}', 'success')
            return redirect(url_for('admin.items'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding item: {str(e)}', 'error')
    
    return render_template('admin/new_item.html')

@admin.route('/items/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    
    if request.method == 'POST':
        item.name = request.form.get('name', item.name)
        item.price = float(request.form.get('price', item.price))
        item.description = request.form.get('description', item.description)
        item.stock = int(request.form.get('stock', item.stock))
        item.barcode = request.form.get('barcode', item.barcode)
        
        # Handle file upload
        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            upload_folder = os.path.join('app', 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            # Save the image file with proper path formatting
            relative_path = os.path.join('uploads', filename).replace('\\', '/')
            image.save(os.path.join('app', 'static', relative_path))
            # Format the URL with a leading slash for web access
            item.image_url = f'/static/{relative_path}'
        
        try:
            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('admin.items'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating item: {str(e)}', 'error')
    
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
def settings():
    settings = StoreSettings.get_settings()
    
    if request.method == 'POST':
        try:
            db.session.commit()
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('admin.settings'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating settings: {str(e)}', 'error')
    
    return render_template('admin/settings.html', settings=settings)

@admin.route('/export/products')
def export_products():
    # Create CSV in memory
    si = StringIO()
    cw = csv.writer(si)
    
    # Write header
    cw.writerow(['ID', 'Name', 'Description', 'Price', 'Stock', 'Barcode', 'Image Path', 'Date Added'])
    
    # Write data
    products = Item.query.all()
    for product in products:
        cw.writerow([
            product.id,
            product.name,
            product.description or '',
            str(product.price),
            product.stock,
            product.barcode or '',
            product.image_url or '',
            product.date_added.strftime('%Y-%m-%d %H:%M:%S') if product.date_added else ''
        ])
    
    # Create response
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=products_export.csv"}
    )

@admin.route('/export/orders')
def export_orders():
    # Create CSV in memory
    si = StringIO()
    cw = csv.writer(si)
    
    # Write header
    cw.writerow(['Order ID', 'Customer Name', 'Email', 'Phone', 'Status', 'Total Amount', 'Order Date'])
    
    # Write data
    orders = Order.query.all()
    for order in orders:
        cw.writerow([
            order.id,
            order.user.first_name or 'Guest',
            order.user.email or 'No email',
            '',  # Phone number not stored in the model
            order.status,
            str(order.total) if hasattr(order, 'total') else '0.00',
            order.date_ordered.strftime('%Y-%m-%d %H:%M:%S') if order.date_ordered else ''
        ])
    
    # Create response
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=orders_export.csv"}
    )

@admin.route('/export/customers')
def export_customers():
    # Create CSV in memory
    si = StringIO()
    cw = csv.writer(si)
    
    # Write header
    cw.writerow(['Name', 'Email', 'Phone', 'Total Orders', 'Total Spent', 'Last Order Date'])
    
    # Get unique customers from orders
    from sqlalchemy import func, desc
    from sqlalchemy.sql import label
    
    # Get all users who have placed orders
    customer_data = db.session.query(
        User.id,
        User.first_name,
        User.email,
        label('order_count', func.count(Order.id)),
        label('total_spent', func.coalesce(func.sum(Order.total), 0.0)),
        func.max(Order.date_ordered)
    ).join(Order, User.id == Order.user_id)\
     .group_by(User.id, User.first_name, User.email)\
     .order_by(desc(func.count(Order.id)))\
     .all()
    
    # Write data
    for customer in customer_data:
        cw.writerow([
            customer.first_name or 'Guest',
            customer.email or 'No email',
            '',  # Phone number not stored in the model
            customer.order_count,
            f"{customer.total_spent:.2f}",
            customer[5].strftime('%Y-%m-%d %H:%M:%S') if customer[5] else 'N/A'
        ])
    
    # Create response
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=customers_export.csv"}
    )
