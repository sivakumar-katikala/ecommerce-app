from datetime import datetime, date, timedelta

from extensions import db


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- Status lifecycle ----
    # PENDING: Stripe checkout session created, payment not yet confirmed (stock NOT reserved yet)
    # PAID: payment confirmed (by webhook, or immediately for the non-Stripe demo methods)
    # FAILED: payment attempt did not complete / stock ran out at confirmation time
    # CANCELLED: customer abandoned the Stripe checkout page
    status = db.Column(db.String(20), nullable=False, default='PENDING', index=True)

    payment_method = db.Column(db.String(30), nullable=False)   # STRIPE / UPI / NET_BANKING / DEBIT_CARD / CREDIT_CARD / WALLET
    payment_reference = db.Column(db.String(120), nullable=True)  # masked reference shown to the customer

    # ---- Stripe-specific identifiers (used to match the webhook back to this order) ----
    stripe_checkout_session_id = db.Column(db.String(120), nullable=True, unique=True, index=True)
    stripe_payment_intent_id = db.Column(db.String(120), nullable=True, index=True)

    # ---- Pricing breakdown (Order Summary: Subtotal / Discount / Tax / Shipping / Grand Total) ----
    subtotal_amount = db.Column(db.Float, nullable=False, default=0.0)   # sum of original prices x qty
    discount_amount = db.Column(db.Float, nullable=False, default=0.0)   # total saved from per-product offers
    tax_amount = db.Column(db.Float, nullable=False, default=0.0)
    shipping_amount = db.Column(db.Float, nullable=False, default=0.0)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)      # grand total actually charged

    estimated_delivery_date = db.Column(db.Date, nullable=True)

    # ---- Contact / delivery details captured at checkout ----
    contact_email = db.Column(db.String(120), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    customer_name = db.Column(db.String(120), nullable=True)
    delivery_address = db.Column(db.Text, nullable=True)

    # ---- Invoice + email delivery tracking ----
    invoice_number = db.Column(db.String(40), nullable=True, unique=True)
    email_sent = db.Column(db.Boolean, nullable=False, default=False)
    email_sent_at = db.Column(db.DateTime, nullable=True)
    email_error = db.Column(db.Text, nullable=True)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    def generate_invoice_number(self):
        """Called once the order is PAID and given a real id."""
        if not self.invoice_number:
            self.invoice_number = f'INV-{self.order_date.strftime("%Y%m")}-{self.id:05d}'
        return self.invoice_number

    def set_estimated_delivery(self, business_days=5):
        self.estimated_delivery_date = date.today() + timedelta(days=business_days)
        return self.estimated_delivery_date

    def __repr__(self):
        return f'<Order #{self.id} {self.status}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_purchase = db.Column(db.Float, nullable=False)  # final (post-discount) price actually charged per unit
    original_price_at_purchase = db.Column(db.Float, nullable=True)  # pre-discount price, for invoice line detail

    @property
    def line_total(self):
        return round(self.quantity * self.price_at_purchase, 2)
