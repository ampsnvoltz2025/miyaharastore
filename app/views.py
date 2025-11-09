# app/views.py
import os
import time
import cv2
import numpy as np
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .models import Item, Cart, CartItem, Order, OrderItem, StoreSettings, db
from werkzeug.utils import secure_filename
from .utils.zbar_loader import ensure_zbar_loaded

views = Blueprint('views', __name__)

# Configure upload folder for barcode images
UPLOAD_FOLDER = os.path.join('app', 'static', 'barcode_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@views.route('/')
def home():
    from .models import StoreSettings
    # Only show items that have stock available
    items = Item.query.filter(Item.stock > 0).all()
    settings = StoreSettings.get_settings()
    return render_template('views/home.html', items=items, user=current_user, settings=settings)


@views.route('/freestore/')
def fs_home():
    from .models import StoreSettings
    # Only show items that have stock available (free store view)
    items = Item.query.filter(Item.stock > 0).all()
    settings = StoreSettings.get_settings()
    return render_template('fs/views/home.html', items=items, user=current_user, settings=settings)

@views.route('/item/<int:item_id>')
def item_detail(item_id):
    from .models import StoreSettings
    item = Item.query.get_or_404(item_id)
    settings = StoreSettings.get_settings()
    return render_template('views/item_detail.html', item=item, user=current_user, settings=settings)

@views.route('/add_to_cart/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    # CSRF token is automatically validated by Flask-WTF
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    def error_response(message, category='error'):
        if is_ajax:
            return jsonify({
                'success': False,
                'message': message,
                'category': category
            }), 400
        flash(message, category)
        return redirect(url_for('views.item_detail', item_id=item_id))
    
    # Get the item
    item = Item.query.get_or_404(item_id)
    
    # Get quantity from form, default to 1 if not provided or invalid
    try:
        quantity = int(request.form.get('quantity', 1))
        if quantity < 1:
            return error_response('Quantity must be at least 1', 'error')
    except (ValueError, TypeError):
        return error_response('Invalid quantity', 'error')
    
    if not current_user.cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    # Check if item already in cart
    cart_item = CartItem.query.filter_by(
        cart_id=current_user.cart.id,
        item_id=item_id
    ).first()
    
    # Calculate total requested quantity
    requested_quantity = (cart_item.quantity if cart_item else 0) + quantity
    
    # Apply maximum per customer limit if set
    if item.max_per_customer and requested_quantity > item.max_per_customer:
        adjusted_quantity = item.max_per_customer - (cart_item.quantity if cart_item else 0)
        if adjusted_quantity <= 0:
            return error_response(
                f'You can only order a maximum of {item.max_per_customer} of this item.',
                'warning'
            )
        quantity = adjusted_quantity
        if is_ajax:
            return jsonify({
                'success': True,
                'message': f'Adjusted quantity to maximum allowed ({item.max_per_customer}).',
                'category': 'info',
                'adjusted_quantity': quantity,
                'redirect': False
            })
        flash(f'Adjusted quantity to maximum allowed ({item.max_per_customer}).', 'info')
    
    # Check stock availability
    available_quantity = item.stock - (cart_item.quantity if cart_item else 0)
    if quantity > available_quantity:
        if available_quantity <= 0:
            return error_response('Sorry, this item is out of stock.', 'error')
        quantity = available_quantity
        if is_ajax:
            return jsonify({
                'success': True,
                'message': f'Adjusted quantity to available stock ({available_quantity}).',
                'category': 'info',
                'adjusted_quantity': quantity,
                'redirect': False
            })
        flash(f'Adjusted quantity to available stock ({available_quantity}).', 'info')
    
    if cart_item:
        # Update existing cart item quantity
        cart_item.quantity += quantity
    else:
        # Create new cart item with specified quantity
        cart_item = CartItem(
            cart_id=current_user.cart.id,
            item_id=item_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    if is_ajax:
        return jsonify({
            'success': True,
            'message': f'{quantity} item(s) added to cart!',
            'category': 'success',
            'redirect': url_for('views.cart')
        })
    
    flash(f'{quantity} item(s) added to cart!', 'success')
    return redirect(url_for('views.cart'))

@views.route('/update_cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    if not current_user.cart:
        return jsonify({'success': False, 'message': 'Cart not found'}), 400
    
    # Get data from form instead of JSON
    quantity = request.form.get('quantity', 1, type=int)
    
    try:
        quantity = int(quantity)
        if quantity < 1:
            return jsonify({'success': False, 'message': 'Quantity must be at least 1'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid quantity'}), 400
    
    # Get the cart item
    cart_item = CartItem.query.filter_by(
        cart_id=current_user.cart.id,
        item_id=item_id
    ).first()
    
    if not cart_item:
        return jsonify({'success': False, 'message': 'Item not found in cart'}), 404
    
    # Check max_per_customer limit
    if cart_item.item.max_per_customer:
        # Get total quantity of this item in all cart items
        total_quantity_in_cart = sum(
            ci.quantity 
            for ci in current_user.cart.items 
            if ci.item_id == item_id
        )
        
        # Calculate the new total quantity (current total - current item quantity + new quantity)
        new_total_quantity = total_quantity_in_cart - cart_item.quantity + quantity
        
        if new_total_quantity > cart_item.item.max_per_customer:
            max_additional = max(0, cart_item.item.max_per_customer - (total_quantity_in_cart - cart_item.quantity))
            return jsonify({
                'success': False, 
                'message': f'Maximum {cart_item.item.max_per_customer} per customer allowed for this item. You can add up to {max_additional} more.',
                'max_additional': max_additional
            }), 400
    
    # Check stock availability
    if quantity > (cart_item.item.stock + cart_item.quantity):
        return jsonify({
            'success': False,
            'message': f'Only {cart_item.item.stock + cart_item.quantity} available in stock'
        }), 400
    
    # Update quantity
    cart_item.quantity = quantity
    db.session.commit()
    
    return jsonify({'success': True})

@views.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    if not current_user.cart:
        return jsonify({'success': False, 'message': 'Cart not found'}), 400
    
    # CSRF token is automatically validated by Flask-WTF
    
    # Remove the item from cart
    cart_item = CartItem.query.filter_by(
        cart_id=current_user.cart.id,
        item_id=item_id
    ).first()
    
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Item not found in cart'}), 404

@views.route('/cart')
@login_required
def cart():
    if not current_user.cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    cart_items = current_user.cart.items
    total = sum(item.item.price * item.quantity for item in cart_items)
    settings = StoreSettings.get_settings()
    return render_template('views/cart.html', 
                         cart_items=cart_items, 
                         total=total, 
                         user=current_user,
                         settings=settings)

@views.route('/checkout', methods=['POST'])
@login_required
def checkout():
    if not current_user.cart or not current_user.cart.items:
        flash('Your cart is empty!', 'error')
        return redirect(url_for('views.cart'))
    
    cart_items = current_user.cart.items
    total = sum(item.item.price * item.quantity for item in cart_items)
    
    # Create order
    order = Order(user_id=current_user.id, total=total)
    db.session.add(order)
    db.session.flush()  # Get the order ID
    
    # Add items to order
    for cart_item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            item_id=cart_item.item_id,
            quantity=cart_item.quantity,
            price=cart_item.item.price
        )
        db.session.add(order_item)
        
        # Update stock
        cart_item.item.stock -= cart_item.quantity
        if cart_item.item.stock < 0:
            db.session.rollback()
            flash(f'Not enough stock for {cart_item.item.name}', 'error')
            return redirect(url_for('views.cart'))
    
    # Clear cart
    CartItem.query.filter_by(cart_id=current_user.cart.id).delete()
    db.session.commit()
    
    flash('Order placed successfully!', 'success')
    return redirect(url_for('views.orders'))

@views.route('/orders')
@login_required
def orders():
    from .models import StoreSettings
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.date_ordered.desc()).all()
    settings = StoreSettings.get_settings()
    return render_template('views/orders.html', orders=orders, user=current_user, settings=settings)

@views.route('/camera-test')
def camera_test():
    return render_template('camera_test.html')

@views.route('/scan-barcode', methods=['GET', 'POST'])
@login_required
def scan_barcode():
    if request.method == 'POST':
        # Ensure ZBar DLL is available before importing pyzbar
        if not ensure_zbar_loaded():
            flash('Barcode engine (ZBar) is not available on this system. Please reinstall or contact support.', 'error')
            return redirect(request.url)
        from pyzbar.pyzbar import decode
        if 'barcode_image' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
        
        file = request.files['barcode_image']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Save the uploaded file
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Read the image
            img = cv2.imread(filepath)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Decode barcodes
            barcodes = decode(gray)
            
            if barcodes:
                barcode_data = barcodes[0].data.decode('utf-8')
                # Try to find item by barcode in the database
                item = Item.query.filter_by(barcode=barcode_data).first()
                if item:
                    # Add to cart if item found
                    if not current_user.cart:
                        cart = Cart(user_id=current_user.id)
                        db.session.add(cart)
                        db.session.commit()
                    
                    cart_item = CartItem.query.filter_by(
                        cart_id=current_user.cart.id,
                        item_id=item.id
                    ).first()
                    
                    if cart_item:
                        cart_item.quantity += 1
                    else:
                        cart_item = CartItem(
                            cart_id=current_user.cart.id,
                            item_id=item.id,
                            quantity=1
                        )
                        db.session.add(cart_item)
                    
                    db.session.commit()
                    flash(f'Added {item.name} to cart!', 'success')
                    return redirect(url_for('views.item_detail', item_id=item.id))
                else:
                    flash(f'Item with barcode {barcode_data} not found in database.', 'warning')
                    return redirect(url_for('views.scan_barcode'))
            else:
                flash('No barcode detected in the image.', 'error')
                return redirect(url_for('views.scan_barcode'))
    
    return render_template('views/scan_barcode.html', user=current_user)

@views.route('/api/scan-barcode', methods=['POST'])
@login_required
def api_scan_barcode():
    try:
        print("Received barcode scan request")
        # Ensure ZBar DLL is available before importing pyzbar
        if not ensure_zbar_loaded():
            return jsonify({'success': False, 'error': 'Barcode engine (ZBar) is not available.'}), 500
        from pyzbar.pyzbar import decode
        
        if 'barcode_image' not in request.files:
            print("No file in request")
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['barcode_image']
        if file.filename == '':
            print("Empty filename")
            return jsonify({'success': False, 'error': 'No selected file'}), 400
        
        if not allowed_file(file.filename):
            print(f"File type not allowed: {file.filename}")
            return jsonify({'success': False, 'error': 'File type not allowed'}), 400
            
        # Read the image file
        try:
            file_data = file.read()
            if not file_data:
                print("Empty file data")
                return jsonify({'success': False, 'error': 'Empty file data'}), 400
                
            nparr = np.frombuffer(file_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                print("Failed to decode image")
                return jsonify({'success': False, 'error': 'Failed to process image'}), 400
                
            # Save the received image for debugging
            debug_dir = os.path.join('app', 'static', 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, f'scan_{int(time.time())}.jpg')
            cv2.imwrite(debug_path, img)
            print(f"Saved debug image to {debug_path}")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Try different barcode formats if needed
            barcodes = decode(gray)
            
            if not barcodes:
                # Try with different settings if no barcode found
                print("No barcode found with default settings, trying with different parameters...")
                # Try with different binarization
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                barcodes = decode(binary)
            
            print(f"Found {len(barcodes)} barcodes")
            
            if barcodes:
                barcode_data = barcodes[0].data.decode('utf-8')
                print(f"Decoded barcode: {barcode_data}")
                
                item = Item.query.filter_by(barcode=barcode_data).first()
                if item:
                    print(f"Found item in database: {item.name}")
                    return jsonify({
                        'success': True,
                        'barcode': barcode_data,
                        'item': {
                            'id': item.id,
                            'name': item.name,
                            'price': str(item.price),
                            'stock': item.stock,
                            'image_url': item.image_url or ''
                        }
                    })
                else:
                    print("Item not found in database")
                    return jsonify({
                        'success': True,
                        'barcode': barcode_data,
                        'item': None,
                        'message': 'Item not found in database.'
                    })
            else:
                print("No barcode detected in the image")
                return jsonify({
                    'success': False, 
                    'error': 'No barcode detected. Make sure the barcode is clear and well-lit.',
                    'debug': f'Saved debug image at: {debug_path}'
                }), 400
                
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False, 
                'error': f'Error processing image: {str(e)}'
            }), 500
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': f'An unexpected error occurred: {str(e)}'
        }), 500
    
    return jsonify({'success': False, 'error': 'Invalid file type'}), 400

@views.route('/order/<int:order_id>')
@login_required
def view_order(order_id):
    from .models import StoreSettings
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    settings = StoreSettings.get_settings()
    return render_template('views/order_detail.html', order=order, user=current_user, settings=settings)