"""Order confirmation email delivery.

This module never raises out of send_order_confirmation_email — a failed or
unconfigured email should never break the checkout/webhook flow. Every
attempt (success or failure, with the specific reason) is written onto the
Order row itself (email_sent, email_sent_at, email_error) so the owner can
see delivery status and resend later from the dashboard.
"""
import smtplib
import ssl
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from flask import current_app, render_template, url_for

from services.invoice_service import build_invoice_pdf


def _store_context():
    return {
        'name': current_app.config.get('STORE_NAME', 'ShopEasy'),
        'logo_url': current_app.config.get('STORE_LOGO_URL', ''),
        'website': current_app.config.get('STORE_WEBSITE', ''),
        'support_email': current_app.config.get('SUPPORT_EMAIL', ''),
        'support_phone': current_app.config.get('SUPPORT_PHONE', ''),
        'social_facebook': current_app.config.get('SOCIAL_FACEBOOK', ''),
        'social_instagram': current_app.config.get('SOCIAL_INSTAGRAM', ''),
        'social_twitter': current_app.config.get('SOCIAL_TWITTER', ''),
    }


def _plain_text_fallback(order, items, store):
    lines = [
        f"Hi {order.customer_name or 'there'},",
        '',
        'Thank you for your purchase! Your order has been confirmed.',
        '',
        f'Order ID: #{order.id}',
        f'Invoice Number: {order.invoice_number}',
        f'Order Date: {order.order_date.strftime("%d %b %Y")}',
        f'Payment Status: {order.status}',
        '',
        'Ordered Items:',
    ]
    for entry in items:
        lines.append(f'  - {entry["product"].name}  x{entry["quantity"]}  =  Rs. {entry["line_total"]:.2f}')
    lines += [
        '',
        f'Subtotal:  Rs. {order.subtotal_amount:.2f}',
        f'Discount:  - Rs. {order.discount_amount:.2f}',
        f'Tax:       Rs. {order.tax_amount:.2f}',
        f'Shipping:  {"FREE" if order.shipping_amount == 0 else f"Rs. {order.shipping_amount:.2f}"}',
        f'Grand Total: Rs. {order.total_amount:.2f}',
        '',
        f'Payment Method: {order.payment_method.replace("_", " ").title()}',
        f'Transaction Reference: {order.stripe_payment_intent_id or order.payment_reference or "N/A"}',
        '',
        'Shipping Address:',
        order.delivery_address or '',
        '',
        f'Thanks for shopping with {store["name"]}!',
        f'Support: {store["support_email"]} | {store["support_phone"]}',
    ]
    return '\n'.join(lines)


def build_sample_order_and_items(recipient_email):
    """Builds a realistic, fully-populated Order (NOT persisted to the DB) plus
    sample line items, for testing email/invoice delivery without a real
    purchase. This is the single source of truth for "what does a sample
    order look like" — used by both the owner's browser Email Settings page
    and the test_email.py CLI script — specifically so sample data can never
    silently drift out of sync with the real Order model as it evolves (that
    exact drift caused a crash here before)."""
    from models import Order  # local import: keeps this module import-order-safe

    class _SampleProduct:
        def __init__(self, name, image_url=None):
            self.name = name
            self.image_url = image_url

    today = date.today()
    order = Order(
        id=0,
        order_date=today,
        created_at=datetime.utcnow(),
        status='PAID',
        payment_method='STRIPE',
        payment_reference='TEST-REFERENCE',
        stripe_payment_intent_id='pi_test_sample_1234567890',
        subtotal_amount=4198.0,
        discount_amount=800.0,
        tax_amount=611.64,
        shipping_amount=0.0,
        total_amount=4009.64,
        contact_email=recipient_email,
        contact_phone='9876543210',
        customer_name='Test Customer',
        delivery_address='221B Sample Street, Test City, 500001',
        invoice_number=f'INV-{today.strftime("%Y%m")}-00000',
        estimated_delivery_date=today + timedelta(days=5),
    )

    items = [
        {
            'product': _SampleProduct('Wireless Headphones', 'https://loremflickr.com/500/400/headphones'),
            'quantity': 1, 'price_at_purchase': 2199.0, 'line_total': 2199.0,
        },
        {
            'product': _SampleProduct('Yoga Mat', 'https://loremflickr.com/500/400/yoga,mat'),
            'quantity': 2, 'price_at_purchase': 999.0, 'line_total': 1998.0,
        },
    ]
    return order, items


def send_order_confirmation_email(order, items):
    """
    order: an Order instance with status already set to PAID, with an
           invoice_number assigned (or this function will assign one).
    items: list of dicts like {'product': Product, 'quantity': int,
           'price_at_purchase': float, 'line_total': float}
    Returns True if sent, False otherwise. Also updates order.email_sent /
    order.email_sent_at / order.email_error in place (caller must commit).
    """
    mail_username = (current_app.config.get('MAIL_USERNAME') or '').strip()
    mail_password = (current_app.config.get('MAIL_PASSWORD') or '').replace(' ', '').strip()
    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or mail_username

    recipient_email = order.contact_email

    if not recipient_email:
        order.email_error = 'No recipient email address was provided at checkout.'
        current_app.logger.info(f'Email not sent for order #{order.id}: {order.email_error}')
        return False

    if not mail_username or not mail_password:
        order.email_error = (
            'MAIL_USERNAME / MAIL_PASSWORD are not configured on the server. '
            'See README "Email Setup", or Owner Dashboard -> Email Settings.'
        )
        current_app.logger.warning(f'Email not sent for order #{order.id}: {order.email_error}')
        return False

    store = _store_context()

    try:
        invoice_pdf_bytes = build_invoice_pdf(order, items)
    except Exception as exc:
        order.email_error = f'Invoice PDF generation failed: {exc}'
        current_app.logger.exception(f'Invoice generation failed for order #{order.id}')
        return False

    track_order_url = url_for('orders.my_orders', _external=True)
    invoice_url = url_for('orders.download_invoice', order_id=order.id, _external=True)

    html_body = render_template(
        'emails/order_confirmation.html',
        order=order,
        items=items,
        store=store,
        current_year=datetime.utcnow().year,
        track_order_url=track_order_url,
        invoice_url=invoice_url,
    )
    text_body = _plain_text_fallback(order, items, store)

    msg = MIMEMultipart('mixed')
    msg['From'] = sender
    msg['To'] = recipient_email
    msg['Subject'] = 'Your Order has been Confirmed \u2705'

    alt_part = MIMEMultipart('alternative')
    alt_part.attach(MIMEText(text_body, 'plain'))
    alt_part.attach(MIMEText(html_body, 'html'))
    msg.attach(alt_part)

    pdf_attachment = MIMEApplication(invoice_pdf_bytes, _subtype='pdf')
    pdf_attachment.add_header('Content-Disposition', 'attachment', filename=f'{order.invoice_number}.pdf')
    msg.attach(pdf_attachment)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(mail_server, mail_port, timeout=15) as server:
            server.starttls(context=context)
            server.login(mail_username, mail_password)
            server.sendmail(sender, recipient_email, msg.as_string())

        order.email_sent = True
        order.email_sent_at = datetime.utcnow()
        order.email_error = None
        current_app.logger.info(f'\u2705 Order confirmation email (with invoice) sent to {recipient_email} for order #{order.id}.')
        return True

    except smtplib.SMTPAuthenticationError as exc:
        order.email_error = (
            f'Gmail rejected the login for {mail_username}. This almost always means MAIL_PASSWORD is '
            'not a valid Gmail App Password (your normal Gmail password will NOT work).'
        )
        current_app.logger.warning(f'\u274c Email auth failed for order #{order.id}: {exc}')
        return False
    except (smtplib.SMTPException, OSError) as exc:
        order.email_error = f'Could not connect to {mail_server}:{mail_port}: {exc}'
        current_app.logger.warning(f'\u274c Email connection failed for order #{order.id}: {exc}')
        return False
    except Exception as exc:
        order.email_error = f'Unexpected error: {exc}'
        current_app.logger.exception(f'\u274c Unexpected error sending email for order #{order.id}')
        return False
