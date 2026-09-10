from flask import current_app


def calculate_pricing(items):
    """items: list of dicts with 'product' and 'quantity'. Mutates each entry
    in place to add price_at_purchase / original_price_at_purchase / line_total,
    and returns the order-level breakdown: subtotal, discount, tax, shipping, total.

    These are DEMO pricing rules (flat tax rate, flat shipping fee above a
    free-shipping threshold) — swap in real tax/shipping logic for production."""
    subtotal = 0.0
    discount = 0.0

    for entry in items:
        product = entry['product']
        qty = entry['quantity']
        original_line = product.price * qty
        final_line = product.final_price * qty
        subtotal += original_line
        discount += (original_line - final_line)
        entry['price_at_purchase'] = product.final_price
        entry['original_price_at_purchase'] = product.price
        entry['line_total'] = round(final_line, 2)

    taxable_amount = subtotal - discount
    tax_rate = current_app.config.get('TAX_RATE', 0.18)
    tax = round(taxable_amount * tax_rate, 2)

    free_shipping_threshold = current_app.config.get('FREE_SHIPPING_THRESHOLD', 999)
    shipping_flat_fee = current_app.config.get('SHIPPING_FLAT_FEE', 49)
    shipping = 0.0 if taxable_amount >= free_shipping_threshold else shipping_flat_fee

    total = round(taxable_amount + tax + shipping, 2)

    return {
        'subtotal': round(subtotal, 2),
        'discount': round(discount, 2),
        'tax': tax,
        'shipping': shipping,
        'total': total,
    }
