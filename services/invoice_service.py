from flask import current_app

from utils.pdf_generator import generate_invoice_pdf


def _store_info():
    return {
        'name': current_app.config.get('STORE_NAME', 'ShopEasy'),
        'website': current_app.config.get('STORE_WEBSITE', ''),
        'support_email': current_app.config.get('SUPPORT_EMAIL', ''),
        'support_phone': current_app.config.get('SUPPORT_PHONE', ''),
    }


def build_invoice_pdf(order, items):
    """Ensures the order has an invoice number, then generates the PDF bytes.
    Does NOT commit the invoice_number to the DB — the caller is responsible
    for that, since this may be called from a read-only context (e.g. a
    Download Invoice request) as well as the order-finalization flow."""
    if not order.invoice_number:
        order.generate_invoice_number()

    return generate_invoice_pdf(order, items, _store_info())
