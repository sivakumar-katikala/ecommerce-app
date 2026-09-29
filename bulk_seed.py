"""
bulk_seed.py

Populate the existing Flask e-commerce PostgreSQL database with up to
3,000 rows in each table while preserving the model relationships.

Run this file from the folder that contains app.py:

    python bulk_seed.py

The script DOES NOT delete existing data.
It keeps the existing owner account/products and adds rows until each
table reaches 3,000 rows.
"""

import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

# Importing app initializes the database and creates the existing tables.
from app import app
from extensions import db
from models import User, Product, Order, OrderItem, Visit


TARGET = 3000
random.seed(42)

CATEGORIES = [
    "Electronics", "Apparel", "Home", "Fitness", "Books", "Beauty"
]

PRODUCT_NAMES = [
    "Wireless Headphones", "Smart Watch", "Bluetooth Speaker",
    "Power Bank", "Wireless Mouse", "Mechanical Keyboard",
    "USB-C Hub", "Phone Stand", "Action Camera", "Earbuds",
    "Cotton T-Shirt", "Denim Jacket", "Running Shoes", "Formal Shirt",
    "Woolen Sweater", "Leather Wallet", "Sports Cap", "Track Pants",
    "Coffee Mug", "Cookware Set", "LED Table Lamp", "Bedsheet Set",
    "Storage Organizer", "Wall Clock", "Yoga Mat", "Dumbbell Set",
    "Resistance Bands", "Skipping Rope", "Shaker Bottle", "Notebook"
]

PATHS = [
    "/", "/products", "/cart", "/checkout", "/orders",
    "/login", "/register"
]

USER_AGENTS = [
    "Mozilla/5.0 Chrome/153 Windows",
    "Mozilla/5.0 Edge/153 Windows",
    "Mozilla/5.0 Chrome/153 Android",
    "Mozilla/5.0 Safari iPhone"
]

PAYMENT_METHODS = [
    "STRIPE", "UPI", "NET_BANKING", "DEBIT_CARD",
    "CREDIT_CARD", "WALLET"
]

STATUSES = ["PAID", "PAID", "PAID", "PENDING", "CANCELLED", "FAILED"]


def random_date(days_back=730):
    return date.today() - timedelta(days=random.randint(0, days_back))


def random_datetime(days_back=730):
    return datetime.utcnow() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def add_users():
    current = User.query.count()
    needed = TARGET - current

    if needed <= 0:
        print(f"users: already {current}")
        return

    print(f"users: adding {needed} rows...")

    # One valid hash reused for test users. Their password is Test@123.
    test_password_hash = generate_password_hash("Test@123")

    rows = []
    start = current + 1

    for i in range(start, TARGET + 1):
        rows.append(
            User(
                username=f"user{i:04d}",
                email=f"user{i:04d}@example.com",
                password_hash=test_password_hash,
                is_owner=False,
                created_at=random_datetime(),
            )
        )

    db.session.add_all(rows)
    db.session.commit()
    print(f"users: {User.query.count()}")


def add_products():
    current = Product.query.count()
    needed = TARGET - current

    if needed <= 0:
        print(f"products: already {current}")
        return

    print(f"products: adding {needed} rows...")

    rows = []

    for i in range(current + 1, TARGET + 1):
        base_name = PRODUCT_NAMES[(i - 1) % len(PRODUCT_NAMES)]
        category = CATEGORIES[(i - 1) % len(CATEGORIES)]

        price = round(random.uniform(199, 15000), 2)
        has_discount = random.random() < 0.65
        discount_price = (
            round(price * random.uniform(0.60, 0.95), 2)
            if has_discount
            else None
        )

        rows.append(
            Product(
                sku=f"SKU-{700000 + i:06d}",
                name=f"{base_name} {i:04d}",
                description=f"Demo e-commerce product {i:04d} for ETL testing.",
                category=category,
                price=price,
                discount_price=discount_price,
                stock=random.randint(5, 250),
                image_url=f"https://example.com/images/product-{i:04d}.jpg",
                created_at=random_datetime(),
            )
        )

    db.session.add_all(rows)
    db.session.commit()
    print(f"products: {Product.query.count()}")


def add_orders():
    current = Order.query.count()
    needed = TARGET - current

    if needed <= 0:
        print(f"orders: already {current}")
        return

    print(f"orders: adding {needed} rows...")

    user_ids = [x[0] for x in db.session.query(User.id).all()]
    rows = []

    for i in range(needed):
        order_date = random_date()
        status = random.choice(STATUSES)
        subtotal = round(random.uniform(300, 25000), 2)
        discount = round(subtotal * random.uniform(0, 0.25), 2)
        taxable = max(subtotal - discount, 0)
        tax = round(taxable * 0.18, 2)
        shipping = 0.0 if taxable >= 999 else 49.0
        total = round(taxable + tax + shipping, 2)

        rows.append(
            Order(
                user_id=random.choice(user_ids),
                order_date=order_date,
                created_at=random_datetime(),
                status=status,
                payment_method=random.choice(PAYMENT_METHODS),
                payment_reference=f"PAY-{random.randint(10000000, 99999999)}",
                subtotal_amount=subtotal,
                discount_amount=discount,
                tax_amount=tax,
                shipping_amount=shipping,
                total_amount=total,
                estimated_delivery_date=order_date + timedelta(days=5),
                contact_email=f"customer{random.randint(1, TARGET):04d}@example.com",
                contact_phone=f"9{random.randint(100000000, 999999999)}",
                customer_name=f"Customer {random.randint(1, TARGET):04d}",
                delivery_address=f"{random.randint(1, 999)}, Demo Street, Hyderabad, India",
                email_sent=(status == "PAID"),
            )
        )

    db.session.add_all(rows)
    db.session.commit()

    # Give newly-created orders unique invoice numbers.
    # We only update rows where invoice_number is currently NULL.
    pending = (
        Order.query
        .filter(Order.invoice_number.is_(None))
        .order_by(Order.id)
        .all()
    )

    for order in pending:
        order.invoice_number = f"INV-{order.order_date.strftime('%Y%m')}-{order.id:05d}"

    db.session.commit()
    print(f"orders: {Order.query.count()}")


def add_order_items():
    current = OrderItem.query.count()
    needed = TARGET - current

    if needed <= 0:
        print(f"order_items: already {current}")
        return

    print(f"order_items: adding {needed} rows...")

    order_ids = [x[0] for x in db.session.query(Order.id).all()]
    products = Product.query.all()

    rows = []

    for i in range(needed):
        order_id = random.choice(order_ids)
        product = random.choice(products)
        quantity = random.randint(1, 5)

        original_price = product.price
        purchase_price = product.final_price

        rows.append(
            OrderItem(
                order_id=order_id,
                product_id=product.id,
                quantity=quantity,
                price_at_purchase=purchase_price,
                original_price_at_purchase=original_price,
            )
        )

    db.session.add_all(rows)
    db.session.commit()
    print(f"order_items: {OrderItem.query.count()}")


def add_visits():
    current = Visit.query.count()
    needed = TARGET - current

    if needed <= 0:
        print(f"visits: already {current}")
        return

    print(f"visits: adding {needed} rows...")

    user_ids = [x[0] for x in db.session.query(User.id).all()]
    rows = []

    for _ in range(needed):
        # Some anonymous visits, some logged-in visits.
        user_id = random.choice(user_ids) if random.random() < 0.75 else None

        rows.append(
            Visit(
                user_id=user_id,
                path=random.choice(PATHS),
                ip_address=f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}",
                user_agent=random.choice(USER_AGENTS),
                timestamp=random_datetime(),
            )
        )

    db.session.add_all(rows)
    db.session.commit()
    print(f"visits: {Visit.query.count()}")


def show_counts():
    print("\n========== FINAL COUNTS ==========")
    print(f"users       : {User.query.count()}")
    print(f"products    : {Product.query.count()}")
    print(f"orders      : {Order.query.count()}")
    print(f"order_items : {OrderItem.query.count()}")
    print(f"visits      : {Visit.query.count()}")
    print("==================================")
    print("Done.")


if __name__ == "__main__":
    with app.app_context():
        print("Connected application database:")
        print(app.config["SQLALCHEMY_DATABASE_URI"])
        print()

        add_users()
        add_products()
        add_orders()
        add_order_items()
        add_visits()
        show_counts()

