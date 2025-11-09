# app/models.py
from . import db
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    is_admin = db.Column(db.Boolean, default=False)
    cart = db.relationship('Cart', backref='user', lazy=True, uselist=False)
    orders = db.relationship('Order', backref='user', lazy=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    stock = db.Column(db.Integer, default=0)
    max_per_customer = db.Column(db.Integer, nullable=True, 
                               doc='Maximum quantity allowed per customer. None means no limit.')
    barcode = db.Column(db.String(100), unique=True, index=True)
    image_url = db.Column(db.String(500))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    items = db.relationship('CartItem', backref='cart', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    quantity = db.Column(db.Integer, default=1)
    item = db.relationship('Item')

from datetime import datetime

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    items = db.relationship('OrderItem', backref='order', lazy=True)
    total = db.Column(db.Float, nullable=False)
    date_ordered = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(50), default='Processing')
    # Shipping address fields
    shipping_first_name = db.Column(db.String(100), nullable=True)
    shipping_last_name = db.Column(db.String(100), nullable=True)
    shipping_address1 = db.Column(db.String(200), nullable=True)
    shipping_address2 = db.Column(db.String(200), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_state = db.Column(db.String(100), nullable=True)
    shipping_zip_code = db.Column(db.String(20), nullable=True)
    shipping_country = db.Column(db.String(100), nullable=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    item = db.relationship('Item')

class StoreSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(10), default='¥')
    currency_position = db.Column(db.String(10), default='left')  # 'left' or 'right'
    show_addresses = db.Column(db.Boolean, default=True)
    show_prices = db.Column(db.Boolean, default=True)
    prices_as_free = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_settings(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def format_price(self, amount):
        if self.prices_as_free:
            return 'Free'
        if self.currency_position == 'left':
            return f"{self.currency}{amount:,.2f}"
        else:
            return f"{amount:,.2f}{self.currency}"