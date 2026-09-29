from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_owner = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='user', lazy=True)
    visits = db.relationship('Visit', backref='user', lazy=True)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f'<User {self.username}>'


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    category = db.Column(db.String(80), nullable=False, default='General')
    price = db.Column(db.Float, nullable=False)                # original price
    discount_price = db.Column(db.Float, nullable=True)        # sale price, if on offer
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    @property
    def is_on_offer(self):
        return self.discount_price is not None and self.discount_price < self.price

    @property
    def discount_percent(self):
        if self.is_on_offer:
            return round((1 - (self.discount_price / self.price)) * 100)
        return 0

    @property
    def final_price(self):
        return self.discount_price if self.is_on_offer else self.price

    @property
    def in_stock(self):
        return self.stock > 0

    def __repr__(self):
        return f'<Product {self.sku} {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(30), nullable=False)   # UPI / NET_BANKING / CARD
    payment_reference = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='PAID')  # PAID / FAILED / PENDING

    # Contact details captured at checkout — the confirmation email goes here,
    # and this is what the owner sees for delivery/contact purposes.
    contact_email = db.Column(db.String(120), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    customer_name = db.Column(db.String(120), nullable=True)
    delivery_address = db.Column(db.Text, nullable=True)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Order #{self.id} {self.status}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_purchase = db.Column(db.Float, nullable=False)  # price actually charged per unit

    @property
    def line_total(self):
        return round(self.quantity * self.price_at_purchase, 2)


class Visit(db.Model):
    """Tracks who visits the application and which pages, for the owner's info."""
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # nullable: anonymous visitors
    path = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
