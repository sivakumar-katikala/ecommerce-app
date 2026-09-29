import io
from datetime import date

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, session,
    abort, current_app, send_file
)
from flask_login import login_required, current_user

from extensions import db
from models import Product, Order, OrderItem
from forms import AddToCartForm, CheckoutForm
from services.pricing_service import calculate_pricing
from services.email_service import send_order_confirmation_email
from services.invoice_service import build_invoice_pdf

orders_bp = Blueprint('orders', __name__)


def _get_cart():
    """Cart is stored in the session as {product_id(str): quantity}."""
    return session.setdefault('cart', {})


def _build_cart_items():
    """Turns the session cart into a list of {'product', 'quantity'} dicts.
    Pricing (price_at_purchase / line_total / discount / tax / shipping) is
    computed separately by services.pricing_service.calculate_pricing, since
    that's shared with the Stripe flow in routes/payment.py."""
    cart = _get_cart()
    items = []
    for pid_str, qty in cart.items():
        product = Product.query.get(int(pid_str))
        if product is None:
            continue
        items.append({'product': product, 'quantity': qty})
    return items


@orders_bp.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if product is None:
        abort(404)

    form = AddToCartForm()
    if not form.validate_on_submit():
        flash('Could not add item to cart. Please try again.', 'danger')
        return redirect(url_for('products.detail', product_id=product_id))

    if not product.in_stock:
        flash(f'"{product.name}" is currently out of stock.', 'warning')
        return redirect(url_for('products.detail', product_id=product_id))

    cart = _get_cart()
    key = str(product_id)
    cart[key] = min(product.stock, cart.get(key, 0) + form.quantity.data)
    session.modified = True

    flash(f'Added "{product.name}" to your cart.', 'success')
    return redirect(url_for('orders.view_cart'))


@orders_bp.route('/cart')
@login_required
def view_cart():
    items = _build_cart_items()
    pricing = calculate_pricing(items) if items else {'subtotal': 0, 'discount': 0, 'tax': 0, 'shipping': 0, 'total': 0}
    return render_template('cart.html', items=items, pricing=pricing)


@orders_bp.route('/cart/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_cart(product_id):
    cart = _get_cart()
    cart.pop(str(product_id), None)
    session.modified = True
    flash('Item removed from cart.', 'info')
    return redirect(url_for('orders.view_cart'))


@orders_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = _build_cart_items()
    if not items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('products.index'))

    pricing = calculate_pricing([dict(entry) for entry in items])  # preview copy; doesn't mutate cart items

    form = CheckoutForm()
    if request.method == 'GET' and not form.contact_email.data:
        form.contact_email.data = current_user.email

    if form.validate_on_submit():
        if form.payment_method.data == 'STRIPE':
            from routes.payment import start_stripe_checkout
            return start_stripe_checkout(form, items)

        order = _finalize_demo_order(form, items)
        if order is None:
            return redirect(url_for('orders.view_cart'))
        return redirect(url_for('orders.order_success', order_id=order.id))

    return render_template(
        'checkout.html',
        form=form,
        items=items,
        pricing=pricing,
        stripe_configured=bool(current_app.config.get('STRIPE_SECRET_KEY')),
    )


def _build_payment_reference(form):
    """Builds a safe, non-sensitive reference to store against the order.
    NEVER include the CVV, full card number, or expiry date here — those are
    used only to validate the form and are discarded immediately after."""
    method = form.payment_method.data
    if method == 'UPI':
        return f'UPI:{form.upi_id.data}'
    if method == 'NET_BANKING':
        return f'BANK:{form.bank_name.data}'
    if method in ('DEBIT_CARD', 'CREDIT_CARD'):
        last4 = form.card_number.data.replace(' ', '')[-4:]
        label = 'Debit Card' if method == 'DEBIT_CARD' else 'Credit Card'
        return f'{label}:****{last4}'
    if method == 'WALLET':
        return f'Wallet:{form.wallet_provider.data}'
    return None


def _finalize_demo_order(form, items):
    """For the UI-only demo payment methods (UPI/Net Banking/demo cards/Wallet)
    there's no external gateway to wait on, so — unlike Stripe — these finalize
    immediately: stock decrement, invoice, and email all happen synchronously
    here rather than via a webhook."""
    pricing = calculate_pricing(items)  # enriches each entry in place

    order = Order(
        user_id=current_user.id,
        order_date=date.today(),
        status='PAID',
        payment_method=form.payment_method.data,
        payment_reference=_build_payment_reference(form),
        subtotal_amount=pricing['subtotal'],
        discount_amount=pricing['discount'],
        tax_amount=pricing['tax'],
        shipping_amount=pricing['shipping'],
        total_amount=pricing['total'],
        contact_email=form.contact_email.data.strip(),
        contact_phone=form.contact_phone.data.strip(),
        customer_name=form.full_name.data.strip(),
        delivery_address=form.address.data.strip(),
    )
    order.set_estimated_delivery()
    db.session.add(order)
    db.session.flush()  # get order.id

    for entry in items:
        product = entry['product']
        qty = entry['quantity']

        result = db.session.execute(
            db.update(Product)
            .where(Product.id == product.id, Product.stock >= qty)
            .values(stock=Product.stock - qty)
        )
        if result.rowcount == 0:
            db.session.rollback()
            flash(f'Sorry, "{product.name}" no longer has enough stock. Please update your cart.', 'danger')
            return None

        db.session.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=qty,
            price_at_purchase=entry['price_at_purchase'],
            original_price_at_purchase=entry['original_price_at_purchase'],
        ))

    order.generate_invoice_number()
    db.session.commit()

    session['cart'] = {}
    session.modified = True

    try:
        send_order_confirmation_email(order, items)
    except Exception:
        current_app.logger.exception(f'Unexpected error sending confirmation email for order #{order.id}.')
    db.session.commit()  # persist email_sent / email_error set by the email service

    return order


@orders_bp.route('/order/<int:order_id>/success')
@login_required
def order_success(order_id):
    order = Order.query.get(order_id)
    if order is None or order.user_id != current_user.id:
        abort(404)
    return render_template('order_success.html', order=order)


@orders_bp.route('/order/<int:order_id>/invoice')
@login_required
def download_invoice(order_id):
    order = Order.query.get(order_id)
    if order is None or order.user_id != current_user.id:
        abort(404)
    if order.status != 'PAID':
        flash('The invoice is available once payment is confirmed.', 'warning')
        return redirect(url_for('orders.order_success', order_id=order.id))

    items = [
        {
            'product': item.product,
            'quantity': item.quantity,
            'price_at_purchase': item.price_at_purchase,
            'line_total': item.line_total,
        }
        for item in order.items
    ]
    pdf_bytes = build_invoice_pdf(order, items)
    db.session.commit()  # persist invoice_number if it was just assigned

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{order.invoice_number}.pdf',
    )


@orders_bp.route('/my-orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)
