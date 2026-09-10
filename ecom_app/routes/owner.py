from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models import Product, Order, OrderItem, Visit
from forms import ProductForm
from services.email_service import send_order_confirmation_email, build_sample_order_and_items

owner_bp = Blueprint('owner', __name__, url_prefix='/owner')


def owner_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_owner:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


@owner_bp.route('/dashboard')
@login_required
@owner_required
def dashboard():
    # Aggregate: sales count, items sold and income, grouped by date.
    daily_stats = (
        db.session.query(
            Order.order_date.label('order_date'),
            func.count(func.distinct(Order.id)).label('num_sales'),
            func.coalesce(func.sum(OrderItem.quantity), 0).label('num_items'),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.price_at_purchase), 0.0).label('income'),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(Order.status == 'PAID')
        .group_by(Order.order_date)
        .order_by(Order.order_date.desc())
        .all()
    )

    total_income = sum(row.income for row in daily_stats)
    total_items = sum(row.num_items for row in daily_stats)
    total_sales = sum(row.num_sales for row in daily_stats)

    recent_visits = Visit.query.order_by(Visit.timestamp.desc()).limit(25).all()
    products = Product.query.order_by(Product.created_at.desc()).all()

    # Units sold per product, computed live from actual orders — this is what
    # automatically keeps the owner page in sync with real sales, no manual entry.
    sold_by_product = dict(
        db.session.query(
            OrderItem.product_id,
            func.coalesce(func.sum(OrderItem.quantity), 0),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status == 'PAID')
        .group_by(OrderItem.product_id)
        .all()
    )

    # ---- Data for the sales trend graphs (Chart.js) ----
    # daily_stats is currently newest-first; charts read left-to-right chronologically.
    chronological = list(reversed(daily_stats))
    chart_labels = [row.order_date.strftime('%d %b') for row in chronological]
    chart_income = [row.income for row in chronological]
    chart_items = [row.num_items for row in chronological]

    top_products = sorted(products, key=lambda p: sold_by_product.get(p.id, 0), reverse=True)[:10]
    top_products = [p for p in top_products if sold_by_product.get(p.id, 0) > 0]
    top_product_labels = [p.name for p in top_products]
    top_product_sold = [sold_by_product.get(p.id, 0) for p in top_products]

    return render_template(
        'owner/dashboard.html',
        daily_stats=daily_stats,
        total_income=round(total_income, 2),
        total_items=total_items,
        total_sales=total_sales,
        recent_visits=recent_visits,
        products=products,
        sold_by_product=sold_by_product,
        chart_labels=chart_labels,
        chart_income=chart_income,
        chart_items=chart_items,
        top_product_labels=top_product_labels,
        top_product_sold=top_product_sold,
    )


@owner_bp.route('/products/new', methods=['GET', 'POST'])
@login_required
@owner_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(
            sku=form.sku.data.strip(),
            name=form.name.data.strip(),
            description=form.description.data or '',
            category=form.category.data.strip(),
            price=form.price.data,
            discount_price=form.discount_price.data,
            stock=form.stock.data,
            image_url=form.image_url.data.strip() if form.image_url.data else None,
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Product "{product.name}" added.', 'success')
        return redirect(url_for('owner.dashboard'))

    return render_template('owner/add_product.html', form=form)


@owner_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@owner_required
def edit_product(product_id):
    product = Product.query.get(product_id)
    if product is None:
        abort(404)

    form = ProductForm(obj=product)
    form.product_id = product.id  # used by validate_sku to allow keeping the same SKU

    if form.validate_on_submit():
        product.sku = form.sku.data.strip()
        product.name = form.name.data.strip()
        product.description = form.description.data or ''
        product.category = form.category.data.strip()
        product.price = form.price.data
        product.discount_price = form.discount_price.data
        product.stock = form.stock.data
        product.image_url = form.image_url.data.strip() if form.image_url.data else None
        db.session.commit()
        flash(f'Product "{product.name}" updated.', 'success')
        return redirect(url_for('owner.dashboard'))

    return render_template('owner/add_product.html', form=form, editing=True, product=product)


@owner_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
@owner_required
def delete_product(product_id):
    product = Product.query.get(product_id)
    if product is None:
        abort(404)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{name}" deleted.', 'info')
    return redirect(url_for('owner.dashboard'))


@owner_bp.route('/test-email', methods=['GET', 'POST'])
@login_required
@owner_required
def test_email():
    """Lets the store owner check email configuration and send a test email
    entirely from the browser — no terminal commands needed."""
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    mail_configured = bool(mail_username) and bool(mail_password)

    if request.method == 'POST':
        recipient = request.form.get('recipient', '').strip()
        if not recipient:
            flash('Please enter an email address to send the test to.', 'warning')
        else:
            sample_order, sample_items = build_sample_order_and_items(recipient)
            success = send_order_confirmation_email(sample_order, sample_items)
            if success:
                flash(f'✅ Test email sent successfully to {recipient}! Check that inbox (and spam folder).', 'success')
            else:
                flash(
                    f'❌ Test email FAILED to send: {sample_order.email_error or "unknown error"} '
                    'Check the terminal window running "python app.py" for more detail, or see the README "Email Setup" section.',
                    'danger',
                )
        return redirect(url_for('owner.test_email'))

    return render_template(
        'owner/test_email.html',
        mail_configured=mail_configured,
        mail_username=mail_username,
    )


@owner_bp.route('/orders')
@login_required
@owner_required
def orders_list():
    """All orders, with per-order email delivery status and a resend action —
    lets the owner recover from a failed confirmation email without needing
    the customer to do anything."""
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('owner/orders.html', orders=orders)


@owner_bp.route('/orders/<int:order_id>/resend-email', methods=['POST'])
@login_required
@owner_required
def resend_order_email(order_id):
    order = Order.query.get(order_id)
    if order is None:
        abort(404)

    if order.status != 'PAID':
        flash(f'Order #{order.id} is not PAID yet ({order.status}) — nothing to email.', 'warning')
        return redirect(url_for('owner.orders_list'))

    items = [
        {
            'product': item.product,
            'quantity': item.quantity,
            'price_at_purchase': item.price_at_purchase,
            'line_total': item.line_total,
        }
        for item in order.items
    ]

    success = send_order_confirmation_email(order, items)
    db.session.commit()  # persist email_sent / email_sent_at / email_error

    if success:
        flash(f'✅ Confirmation email resent to {order.contact_email} for order #{order.id}.', 'success')
    else:
        flash(f'❌ Resend failed for order #{order.id}: {order.email_error or "unknown error"}', 'danger')

    return redirect(url_for('owner.orders_list'))
