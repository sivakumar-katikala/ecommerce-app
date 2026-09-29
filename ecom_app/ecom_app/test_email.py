"""
Test / resend the order confirmation email (with invoice PDF attached).

TWO MODES:

1) No arguments — automatically finds the MOST RECENT real PAID order and
   re-sends its ACTUAL confirmation (real buyer email, real items, real
   total, real invoice) to that same buyer. No typing required.

       python test_email.py

2) One argument — sends a realistic SAMPLE email (with sample purchased
   items and a sample invoice) to whichever address you pass in. Useful
   before any real orders exist yet.

       python test_email.py someone@gmail.com

Either way, make sure MAIL_USERNAME and MAIL_PASSWORD are set as environment
variables first (see README.md "Email Setup" for how to generate a Gmail
App Password), or use the Owner Dashboard -> Email Settings page in the
browser instead of this script.
"""
import sys

from app import create_app
from models import Order
from services.email_service import send_order_confirmation_email, build_sample_order_and_items


def _report_result(success, recipient, error=None):
    print('-' * 60)
    if success:
        print(f'SUCCESS: check the inbox (and spam folder) for {recipient}.')
    else:
        print(f'FAILED: {error or "see the warning above for the specific reason"}')


def resend_latest_real_order(app):
    with app.app_context():
        order = Order.query.filter_by(status='PAID').order_by(Order.created_at.desc()).first()

        if order is None:
            print('No PAID orders exist yet in this database.')
            print('Either place a test order through the site first, or send a sample email instead:')
            print('    python test_email.py someone@gmail.com')
            sys.exit(1)

        if not order.contact_email:
            print(f'Order #{order.id} has no contact email on file — cannot resend.')
            sys.exit(1)

        items = [
            {
                'product': order_item.product,
                'quantity': order_item.quantity,
                'price_at_purchase': order_item.price_at_purchase,
                'line_total': order_item.line_total,
            }
            for order_item in order.items
        ]

        print(f'Found most recent PAID order: #{order.id}')
        print(f'  Buyer email:  {order.contact_email}')
        print(f'  Buyer phone:  {order.contact_phone or "(not provided)"}')
        print(f'  Items:        {", ".join(entry["product"].name for entry in items) or "(none found)"}')
        print(f'  Total paid:   Rs. {order.total_amount:.2f}')
        print(f'  Payment:      {order.payment_method}')
        print('-' * 60)

        success = send_order_confirmation_email(order, items)
        from extensions import db
        db.session.commit()  # persist email_sent / email_error
        _report_result(success, order.contact_email, order.email_error)


def send_sample_to(app, recipient):
    with app.app_context():
        print(f'MAIL_USERNAME configured as: {app.config.get("MAIL_USERNAME")!r}')
        print(f'MAIL_SERVER / PORT:          {app.config.get("MAIL_SERVER")}:{app.config.get("MAIL_PORT")}')
        print(f'Sending a SAMPLE test email to: {recipient}')
        print('-' * 60)

        sample_order, sample_items = build_sample_order_and_items(recipient)
        with app.test_request_context(base_url="https://ecommerce-app-3-7bjw.onrender.com"):
         success = send_order_confirmation_email(sample_order, sample_items)
        _report_result(success, recipient, sample_order.email_error)


def main():
    app = create_app()

    if len(sys.argv) == 1:
        resend_latest_real_order(app)
    elif len(sys.argv) == 2:
        send_sample_to(app, sys.argv[1])
    else:
        print('Usage:')
        print('  python test_email.py                     # resend the latest real PAID order to its buyer')
        print('  python test_email.py someone@gmail.com   # send a sample email to this address')
        sys.exit(1)


if __name__ == '__main__':
    main()
