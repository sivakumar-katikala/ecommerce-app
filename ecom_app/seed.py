from urllib.parse import quote
from extensions import db
from models import User, Product


# (sku, name, category, description, price, discount_price, stock, image_keywords)
# image_keywords -> used to fetch a REAL matching photo (not a random placeholder)
PRODUCT_DATA = [
    # ---- Electronics ----
    ('SKU-1001', 'Wireless Headphones', 'Electronics',
     'Over-ear wireless headphones with active noise cancellation.', 2999.0, 2199.0, 25, 'headphones'),
    ('SKU-1002', 'Smart Watch', 'Electronics',
     'Fitness tracking smart watch with heart-rate monitor.', 4999.0, None, 15, 'smartwatch'),
    ('SKU-1003', 'Bluetooth Speaker', 'Electronics',
     'Portable waterproof speaker with 12-hour battery life.', 1999.0, 1499.0, 30, 'bluetooth,speaker'),
    ('SKU-1004', 'Power Bank 20000mAh', 'Electronics',
     'Fast-charging power bank with dual USB output.', 1499.0, 1099.0, 50, 'powerbank,charger'),
    ('SKU-1005', 'Wireless Mouse', 'Electronics',
     'Ergonomic wireless mouse with silent clicks.', 699.0, None, 80, 'computer,mouse'),
    ('SKU-1006', 'Mechanical Keyboard', 'Electronics',
     'RGB backlit mechanical keyboard, blue switches.', 3499.0, 2799.0, 20, 'mechanical,keyboard'),
    ('SKU-1007', 'USB-C Hub', 'Electronics',
     '7-in-1 USB-C hub with HDMI, SD card and USB 3.0 ports.', 1299.0, None, 40, 'usb,hub'),
    ('SKU-1008', 'Smartphone Stand', 'Electronics',
     'Adjustable aluminium stand for phones and tablets.', 399.0, 299.0, 100, 'phone,stand'),
    ('SKU-1009', 'Action Camera', 'Electronics',
     '4K waterproof action camera with mounting kit.', 6999.0, 5499.0, 12, 'action,camera'),
    ('SKU-1010', 'Noise Cancelling Earbuds', 'Electronics',
     'True wireless earbuds with active noise cancellation.', 3999.0, 2999.0, 35, 'earbuds,wireless'),

    # ---- Apparel ----
    ('SKU-2001', 'Cotton T-Shirt', 'Apparel',
     'Soft, breathable 100% cotton t-shirt.', 799.0, 549.0, 100, 'cotton,tshirt'),
    ('SKU-2002', 'Denim Jacket', 'Apparel',
     'Classic fit denim jacket, unisex.', 2499.0, 1899.0, 25, 'denim,jacket'),
    ('SKU-2003', 'Running Shoes', 'Apparel',
     'Lightweight running shoes with cushioned sole.', 3299.0, 2649.0, 40, 'running,shoes'),
    ('SKU-2004', 'Formal Shirt', 'Apparel',
     'Slim-fit formal shirt, easy-iron fabric.', 1399.0, None, 60, 'formal,shirt'),
    ('SKU-2005', 'Woolen Sweater', 'Apparel',
     'Warm woolen pullover sweater for winter.', 1799.0, 1349.0, 30, 'wool,sweater'),
    ('SKU-2006', 'Leather Wallet', 'Apparel',
     'Genuine leather bi-fold wallet with card slots.', 999.0, 749.0, 70, 'leather,wallet'),
    ('SKU-2007', 'Sports Cap', 'Apparel',
     'Adjustable cotton sports cap, UV protection.', 449.0, None, 90, 'baseball,cap'),
    ('SKU-2008', 'Track Pants', 'Apparel',
     'Comfortable stretch-fit track pants for workouts.', 999.0, 799.0, 55, 'track,pants'),

    # ---- Home ----
    ('SKU-3001', 'Ceramic Coffee Mug', 'Home',
     '350ml ceramic mug, dishwasher safe.', 349.0, None, 60, 'ceramic,mug'),
    ('SKU-3002', 'Non-Stick Cookware Set', 'Home',
     '5-piece non-stick cookware set with lids.', 2999.0, 2399.0, 18, 'cookware,kitchen'),
    ('SKU-3003', 'LED Table Lamp', 'Home',
     'Dimmable LED desk lamp with USB charging port.', 1199.0, 899.0, 45, 'led,lamp'),
    ('SKU-3004', 'Cotton Bedsheet Set', 'Home',
     'King-size cotton bedsheet with 2 pillow covers.', 1599.0, 1199.0, 35, 'bedsheet,bedroom'),
    ('SKU-3005', 'Storage Organizer Box', 'Home',
     'Foldable fabric storage box, set of 3.', 899.0, None, 50, 'storage,box'),
    ('SKU-3006', 'Wall Clock', 'Home',
     'Minimalist silent-sweep wall clock, 12 inch.', 799.0, 599.0, 40, 'wall,clock'),

    # ---- Fitness ----
    ('SKU-4001', 'Yoga Mat', 'Fitness',
     'Non-slip 6mm yoga mat with carry strap.', 1299.0, 999.0, 40, 'yoga,mat'),
    ('SKU-4002', 'Adjustable Dumbbell Set', 'Fitness',
     'Pair of adjustable dumbbells, 2-10kg each.', 3999.0, 3199.0, 15, 'dumbbell,gym'),
    ('SKU-4003', 'Resistance Bands Set', 'Fitness',
     'Set of 5 resistance bands with varying strengths.', 799.0, None, 65, 'resistance,band'),
    ('SKU-4004', 'Skipping Rope', 'Fitness',
     'Speed skipping rope with ball-bearing handles.', 349.0, 249.0, 90, 'jump,rope'),
    ('SKU-4005', 'Gym Shaker Bottle', 'Fitness',
     '700ml protein shaker bottle with mixer ball.', 299.0, None, 100, 'shaker,bottle'),

    # ---- Books & Stationery ----
    ('SKU-5001', 'Notebook Set', 'Books',
     'Pack of 3 ruled A5 notebooks, 200 pages each.', 399.0, 299.0, 80, 'notebook,stationery'),
    ('SKU-5002', 'Fountain Pen', 'Books',
     'Classic stainless-steel nib fountain pen.', 599.0, None, 40, 'fountain,pen'),

    # ---- Beauty ----
    ('SKU-6001', 'Herbal Face Wash', 'Beauty',
     'Gentle herbal face wash for daily use, 100ml.', 249.0, 179.0, 70, 'skincare,facewash'),
    ('SKU-6002', 'Hair Dryer', 'Beauty',
     'Compact 1200W hair dryer with 2 heat settings.', 1099.0, 849.0, 30, 'hair,dryer'),
]


def _image_url(keywords):
    """Fetch a real photo matching the given keywords (free, no API key required)."""
    return f'https://loremflickr.com/500/400/{quote(keywords)}'


def seed_data():
    """Create a default owner account and sample products, only if empty."""
    if User.query.filter_by(is_owner=True).first() is None:
        owner = User(username='owner', email='owner@example.com', is_owner=True)
        owner.set_password('OwnerPass123')
        db.session.add(owner)

    if Product.query.count() == 0:
        products = [
            Product(
                sku=sku, name=name, category=category, description=description,
                price=price, discount_price=discount_price, stock=stock,
                image_url=_image_url(image_keywords),
            )
            for sku, name, category, description, price, discount_price, stock, image_keywords in PRODUCT_DATA
        ]
        db.session.add_all(products)

    db.session.commit()
