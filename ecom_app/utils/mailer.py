"""Sends order confirmation emails via SMTP (works with Gmail out of the box).

This module never raises out of send_order_confirmation_email — a failed or
unconfigured email should never break the checkout flow. If MAIL_USERNAME /
MAIL_PASSWORD aren't set, sending is silently skipped and logged.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def send_order_confirmation_email(recipient_email, order, cart_items):
    """
    recipient_email: the email address to send the confirmation to (entered at checkout)
    order: the committed Order (needs .id, .total_amount, .payment_method, .order_date)
    cart_items: list of dicts like {'product': Product, 'quantity': int, 'line_total': float}
    Returns True if the email was sent, False if skipped or failed.
    """
    mail_username = (current_app.config.get('MAIL_USERNAME') or '').strip()
    # Google displays App Passwords with spaces for readability (e.g. "abcd efgh ijkl mnop") —
    # people commonly copy them exactly like that, which breaks SMTP login. Strip them here.
    mail_password = (current_app.config.get('MAIL_PASSWORD') or '').replace(' ', '').strip()
    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or mail_username

    if not recipient_email:
        current_app.logger.info('Email not sent: no recipient email address was provided.')
        return False

    if not mail_username or not mail_password:
        current_app.logger.warning(
            'Email not sent: MAIL_USERNAME / MAIL_PASSWORD are not configured. '
            'Set these environment variables (see README "Email Setup") to enable order confirmation emails.'
        )
        return False

    subject = f'Your ShopEasy Order #{order.id} is Confirmed'

    greeting_name = order.customer_name or 'there'

    # ---- Plain-text fallback (shown by clients/screen readers that don't render HTML) ----
    text_lines = [
        f'Hi {greeting_name},',
        '',
        f'Thank you for your purchase. Your payment for Order #{order.id} has been verified successfully.',
        '',
    ]
    for entry in cart_items:
        text_lines.append(f'  - {entry["product"].name}  x{entry["quantity"]}  =  Rs. {entry["line_total"]:.2f}')
    text_lines += [
        '',
        f'Total Paid Amount: Rs. {order.total_amount:.2f}',
        f'Payment Method:    {order.payment_method.replace("_", " ").title()}',
        f'Order Date:        {order.order_date.strftime("%d %b %Y")}',
    ]
    if order.delivery_address:
        text_lines.append(f'Delivery Destination: {order.delivery_address}')
    text_lines += ['', 'Thanks for shopping with ShopEasy!']
    text_body = '\n'.join(text_lines)

    # ---- Styled HTML version ----
    rows_html = ''.join(
        f'''
        <tr>
            <td style="padding:10px 8px;border-bottom:1px solid #e2e6ea;">{entry["product"].name}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #e2e6ea;text-align:center;">{entry["quantity"]}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #e2e6ea;text-align:right;">₹{entry["product"].final_price:.0f}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #e2e6ea;text-align:right;">₹{entry["line_total"]:.0f}</td>
        </tr>'''
        for entry in cart_items
    )

    delivery_html = ''
    if order.delivery_address:
        delivery_html = f'''
        <p style="margin:22px 0 0 0;font-size:14px;color:#22303c;text-align:center;">
            <strong>Delivery Destination:</strong> {order.delivery_address}
        </p>'''

    html_body = f'''
    <html>
    <body style="margin:0;padding:0;background:#f7f8fa;font-family:Arial,Helvetica,sans-serif;color:#22303c;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f7f8fa;padding:30px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="600" cellpadding="0" cellspacing="0"
                           style="background:#ffffff;border-radius:10px;border:1px solid #e2e6ea;overflow:hidden;">
                        <tr>
                            <td style="padding:32px 32px 8px 32px;text-align:center;">
                                <h2 style="margin:0 0 18px 0;color:#1a5276;font-size:22px;">Payment Successful! 🎉</h2>
                                <p style="margin:0 0 4px 0;font-size:15px;">Hi {greeting_name},</p>
                                <p style="margin:0 0 20px 0;font-size:15px;">
                                    Thank you for your purchase. Your payment for
                                    <strong>Order #{order.id}</strong> has been verified successfully.
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:0 32px;">
                                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                                    <tr>
                                        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #1a5276;font-size:13px;color:#1a5276;">Item</th>
                                        <th style="padding:10px 8px;text-align:center;border-bottom:2px solid #1a5276;font-size:13px;color:#1a5276;">Qty</th>
                                        <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #1a5276;font-size:13px;color:#1a5276;">Price</th>
                                        <th style="padding:10px 8px;text-align:right;border-bottom:2px solid #1a5276;font-size:13px;color:#1a5276;">Total</th>
                                    </tr>
                                    {rows_html}
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:20px 32px 6px 32px;text-align:center;">
                                <p style="margin:0;font-size:17px;font-weight:bold;color:#1e8449;">
                                    Total Paid Amount: ₹{order.total_amount:.0f}
                                </p>
                                {delivery_html}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:26px 32px 32px 32px;text-align:center;">
                                <p style="margin:0;font-size:13px;color:#6b7885;">
                                    Payment Method: {order.payment_method.replace('_', ' ').title()} &nbsp;|&nbsp;
                                    Order Date: {order.order_date.strftime('%d %b %Y')}
                                </p>
                                <p style="margin:14px 0 0 0;font-size:13px;color:#6b7885;">
                                    Thanks for shopping with ShopEasy!
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''

    msg = MIMEMultipart('alternative')
    msg['From'] = sender
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
            server.starttls(context=context)
            server.login(mail_username, mail_password)
            server.sendmail(sender, recipient_email, msg.as_string())
        current_app.logger.info(f'✅ Order confirmation email sent to {recipient_email} for order #{order.id}.')
        return True
    except smtplib.SMTPAuthenticationError as exc:
        current_app.logger.warning(
            f'❌ Gmail rejected the login for {mail_username}: {exc}. '
            'This almost always means MAIL_PASSWORD is not a valid Gmail App Password '
            '(your normal Gmail password will NOT work — see README "Email Setup").'
        )
        return False
    except (smtplib.SMTPException, OSError) as exc:
        current_app.logger.warning(
            f'❌ Could not connect to {mail_server}:{mail_port} to send the confirmation email: {exc}. '
            'Check your internet connection and firewall settings.'
        )
        return False
    except Exception as exc:
        current_app.logger.warning(f'❌ Unexpected error sending order confirmation email for order #{order.id}: {exc}')
        return False
