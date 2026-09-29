from flask import Blueprint, render_template, request, abort, jsonify

from models import Product

products_bp = Blueprint('products', __name__)


@products_bp.route('/')
def index():
    category = request.args.get('category', '').strip()
    query = Product.query

    if category:
        query = query.filter_by(category=category)

    products = query.order_by(Product.created_at.desc()).all()
    categories = sorted({p.category for p in Product.query.all()})

    return render_template('index.html', products=products, categories=categories, active_category=category)


@products_bp.route('/product/<int:product_id>')
def detail(product_id):
    product = Product.query.get(product_id)
    if product is None:
        abort(404)
    return render_template('product_detail.html', product=product)


def _product_status_payload(product):
    return {
        'id': product.id,
        'price': product.price,
        'discount_price': product.discount_price,
        'is_on_offer': product.is_on_offer,
        'discount_percent': product.discount_percent,
        'final_price': product.final_price,
        'stock': product.stock,
        'in_stock': product.in_stock,
    }


@products_bp.route('/api/products/status')
def api_products_status():
    """Live price/discount/stock for every product — polled by the catalog page
    so shoppers see owner updates without reloading."""
    products = Product.query.all()
    return jsonify({str(p.id): _product_status_payload(p) for p in products})


@products_bp.route('/api/product/<int:product_id>/status')
def api_product_status(product_id):
    """Live price/discount/stock for a single product — polled by the product detail page."""
    product = Product.query.get(product_id)
    if product is None:
        abort(404)
    return jsonify(_product_status_payload(product))
