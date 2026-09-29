from datetime import datetime

from extensions import db


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
