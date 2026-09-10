import json
from datetime import date

import stripe
from flask import Blueprint, redirect, url_for, flash, request, session, current_app, abort
from flask_login import login_required, current_user

from extensions import db, csrf
from models import Product, Order, OrderItem
from services.pricing_service import calculate_pricing
from services.email_service import send_order_confirmation_email

payment_bp = Blueprint('payment', __name__, url_prefix='/payment')


def start_stripe_checkout(form, items):
    """Creates a PENDING Order + OrderItems (stock is NOT touched yet), then a
    Stripe Checkout Session tied to that order via metadata, and redirects the
    browser there. This function never marks anything PAID — only the webhook
    below does that, once Stripe actually confirms the payment."""
    if not current_app.config.get('STRIPE_SECRET_KEY'):
        flash(
            'Card payment via Stripe is not set up on this server yet. '
            'Please choose a different payment method, or see the README "Stripe Setup" section.',
            'danger',
        )
        return redirect(url_for('orders.checkout'))

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    pricing = calculate_pricing(items)  # enriches each entry + returns the breakdown

    order = Order(
        user_id=current_user.id,
        order_date=date.today(),
        status='PENDING',
        payment_method='STRIPE',
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
    db.session.flush()  # assign order.id

    for entry in items:
        db.session.add(OrderItem(
            order_id=order.id,
            product_id=entry['product'].id,
            quantity=entry['quantity'],
            price_at_purchase=entry['price_at_purchase'],
            original_price_at_purchase=entry['original_price_at_purchase'],
        ))
    db.session.commit()

    # One Stripe line item per product, priced at what we're actually charging
    # (post product-level discount) — plus a single combined line for tax +
    # shipping so the Stripe-charged total matches order.total_amount exactly.
    line_items = [
        {
            'price_data': {
                'currency': current_app.config.get('STRIPE_CURRENCY', 'inr'),
                'product_data': {'name': entry['product'].name},
                'unit_amount': int(round(entry['price_at_purchase'] * 100)),
            },
            'quantity': entry['quantity'],
        }
        for entry in items
    ]
    extra_amount = pricing['tax'] + pricing['shipping']
    if extra_amount > 0:
        line_items.append({
            'price_data': {
                'currency': current_app.config.get('STRIPE_CURRENCY', 'inr'),
                'product_data': {'name': 'Tax & Shipping'},
                'unit_amount': int(round(extra_amount * 100)),
            },
            'quantity': 1,
        })

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            customer_email=order.contact_email or None,
            metadata={'order_id': str(order.id)},
            success_url=url_for('payment.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payment.cancel', order_id=order.id, _external=True),
        )
    except Exception as exc:
        current_app.logger.warning(f'Stripe checkout session creation failed: {exc}')
        db.session.delete(order)  # nothing was ever charged; discard the pending order
        db.session.commit()
        flash('Could not open the Stripe payment page right now. Please try again or choose another payment method.', 'danger')
        return redirect(url_for('orders.checkout'))

    order.stripe_checkout_session_id = checkout_session.id
    db.session.commit()

    return redirect(checkout_session.url, code=303)


@payment_bp.route('/success')
@login_required
def success():
    """Stripe redirects the browser here right after payment. Finalizing the
    order (stock decrement + email) is still driven by _finalize_paid_order —
    the SAME function the webhook calls — so there is exactly one code path
    that marks an order PAID; a customer still can't fake a successful order
    just by visiting this URL with a made-up session_id, since finalization
    only proceeds if Stripe itself confirms that exact session was paid.

    Why call it from here at all, then? In local/dev setups the webhook often
    never arrives (no `stripe listen` running, no public URL configured), and
    without this fallback the order would sit in PENDING forever while the
    success page spins. So: try to finalize immediately by asking Stripe
    directly whether this session was paid. If the webhook already beat us to
    it, _finalize_paid_order just no-ops (order.status is already PAID)."""
    session_id = request.args.get('session_id')
    if not session_id:
        abort(400)

    order = Order.query.filter_by(stripe_checkout_session_id=session_id).first()
    if order is None or order.user_id != current_user.id:
        abort(404)

    session['cart'] = {}
    session.modified = True

    if order.status == 'PENDING' and current_app.config.get('STRIPE_SECRET_KEY'):
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            if checkout_session.get('payment_status') == 'paid':
                _finalize_paid_order('checkout.session.completed', checkout_session)
        except Exception as exc:
            # Don't fail the redirect over this — the webhook (or the next
            # refresh of the success page) can still finalize it later.
            current_app.logger.warning(f'Fallback finalize check failed for order #{order.id}: {exc}')

    return redirect(url_for('orders.order_success', order_id=order.id))


@payment_bp.route('/cancel/<int:order_id>')
@login_required
def cancel(order_id):
    order = Order.query.get(order_id)
    if order and order.user_id == current_user.id and order.status == 'PENDING':
        order.status = 'CANCELLED'
        db.session.commit()
    flash('Payment was cancelled. Your cart has been kept so you can try again.', 'info')
    return redirect(url_for('orders.view_cart'))


@payment_bp.route('/webhook', methods=['POST'])
@csrf.exempt  # Stripe posts here directly — it can't send our CSRF token
def webhook():
    """The SOURCE OF TRUTH for order fulfillment. Only fires stock decrement +
    confirmation email once Stripe has verifiably confirmed payment via
    'checkout.session.completed' or 'payment_intent.succeeded'."""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            # No webhook secret configured: signature is NOT verified. Fine for
            # quick local testing, but see README "Stripe Webhook Setup" —
            # this must be set before going anywhere near production.
            current_app.logger.warning('STRIPE_WEBHOOK_SECRET is not set — webhook signature is NOT being verified.')
            event = json.loads(payload)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        current_app.logger.warning(f'Stripe webhook rejected: {exc}')
        return '', 400

    event_type = event['type']
    data_object = event['data']['object']

    if event_type in ('checkout.session.completed', 'payment_intent.succeeded'):
        _finalize_paid_order(event_type, data_object)

    return '', 200


def _finalize_paid_order(event_type, data_object):
    if event_type == 'checkout.session.completed':
        order = Order.query.filter_by(stripe_checkout_session_id=data_object.get('id')).first()
        payment_intent_id = data_object.get('payment_intent')
    else:  # payment_intent.succeeded
        payment_intent_id = data_object.get('id')
        order = Order.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
        if order is None:
            metadata = data_object.get('metadata') or {}
            order_id = metadata.get('order_id')
            if order_id:
                order = Order.query.get(int(order_id))

    if order is None:
        current_app.logger.warning(f'Webhook {event_type}: no matching order found.')
        return

    if order.status == 'PAID':
        return  # already finalized — webhooks can legitimately fire more than once
    if order.status != 'PENDING':
        return  # CANCELLED / FAILED — don't resurrect it

    order.stripe_payment_intent_id = payment_intent_id or order.stripe_payment_intent_id

    items = [
        {
            'product': item.product,
            'quantity': item.quantity,
            'price_at_purchase': item.price_at_purchase,
            'line_total': item.line_total,
        }
        for item in order.items
    ]

    # Atomically decrement stock — only now, at confirmed payment, not at
    # PENDING creation. Guards against overselling under concurrent checkouts.
    for entry in items:
        product = entry['product']
        qty = entry['quantity']
        result = db.session.execute(
            db.update(Product)
            .where(Product.id == product.id, Product.stock >= qty)
            .values(stock=Product.stock - qty)
        )
        if result.rowcount == 0:
            order.status = 'FAILED'
            db.session.commit()
            current_app.logger.warning(
                f'Order #{order.id} FAILED at fulfillment: insufficient stock for "{product.name}". '
                f'Payment was captured by Stripe — a manual refund via the Stripe Dashboard is needed.'
            )
            return

    order.status = 'PAID'
    order.generate_invoice_number()
    db.session.commit()

    try:
        send_order_confirmation_email(order, items)
    except Exception:
        current_app.logger.exception(f'Unexpected error sending confirmation email for order #{order.id}.')
    db.session.commit()  # persist email_sent / email_error set on the order by the email service
