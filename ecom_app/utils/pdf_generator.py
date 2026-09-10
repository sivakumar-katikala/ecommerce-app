"""Generates a professional PDF invoice for an order, entirely in memory
(returns bytes) — nothing is written to disk, so there's no stale-file
management to worry about; it's simply regenerated on demand."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


def generate_invoice_pdf(order, items, store_info):
    """
    order: Order instance (needs invoice_number, id, order_date, customer_name,
           contact_email, delivery_address, payment_method, stripe_payment_intent_id
           or payment_reference, subtotal_amount, discount_amount, tax_amount,
           shipping_amount, total_amount, status)
    items: list of dicts like {'product': Product, 'quantity': int,
           'price_at_purchase': float, 'line_total': float}
    store_info: dict with 'name', 'website', 'support_email', 'support_phone'
    Returns: PDF file content as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('InvoiceTitle', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#1a5276'))
    heading_style = ParagraphStyle('InvoiceHeading', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1a5276'), spaceBefore=14, spaceAfter=6)
    normal = styles['Normal']
    small_muted = ParagraphStyle('SmallMuted', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#6b7885'))

    story = []

    # ---- Header: store name + invoice meta ----
    header_table = Table(
        [[
            Paragraph(f"<b>{store_info['name']}</b>", title_style),
            Paragraph(
                f"<b>Invoice #:</b> {order.invoice_number}<br/>"
                f"<b>Invoice Date:</b> {order.order_date.strftime('%d %b %Y')}<br/>"
                f"<b>Order ID:</b> #{order.id}",
                normal,
            ),
        ]],
        colWidths=[100 * mm, 72 * mm],
    )
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width='100%', color=colors.HexColor('#e2e6ea')))
    story.append(Spacer(1, 12))

    # ---- Customer / Shipping / Billing details ----
    details_table = Table(
        [[
            Paragraph(
                f"<b>Bill To</b><br/>{order.customer_name or ''}<br/>{order.contact_email or ''}<br/>{order.contact_phone or ''}",
                normal,
            ),
            Paragraph(
                f"<b>Ship To</b><br/>{(order.delivery_address or '').replace(chr(10), '<br/>')}",
                normal,
            ),
        ]],
        colWidths=[86 * mm, 86 * mm],
    )
    details_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(details_table)
    story.append(Spacer(1, 16))

    # ---- Line items table ----
    story.append(Paragraph('Purchased Products', heading_style))

    item_rows = [['Product', 'Qty', 'Unit Price', 'Total']]
    for entry in items:
        item_rows.append([
            Paragraph(entry['product'].name, normal),
            str(entry['quantity']),
            f"Rs. {entry['price_at_purchase']:.2f}",
            f"Rs. {entry['line_total']:.2f}",
        ])

    items_table = Table(item_rows, colWidths=[86 * mm, 20 * mm, 33 * mm, 33 * mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e6ea')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f8fa')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # ---- Order summary (subtotal / discount / tax / shipping / grand total) ----
    summary_rows = [
        ['Subtotal', f"Rs. {order.subtotal_amount:.2f}"],
        ['Discount', f"- Rs. {order.discount_amount:.2f}"],
        ['Tax', f"Rs. {order.tax_amount:.2f}"],
        ['Shipping', 'FREE' if order.shipping_amount == 0 else f"Rs. {order.shipping_amount:.2f}"],
        ['Grand Total', f"Rs. {order.total_amount:.2f}"],
    ]
    summary_table = Table(summary_rows, colWidths=[142 * mm, 30 * mm], hAlign='RIGHT')
    summary_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1a5276')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1e8449')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # ---- Payment information ----
    story.append(Paragraph('Payment Information', heading_style))
    payment_intent = order.stripe_payment_intent_id or order.payment_reference or 'N/A'
    story.append(Paragraph(
        f"<b>Payment Method:</b> {order.payment_method.replace('_', ' ').title()}<br/>"
        f"<b>Transaction / Payment Intent ID:</b> {payment_intent}<br/>"
        f"<b>Payment Status:</b> {order.status}",
        normal,
    ))
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width='100%', color=colors.HexColor('#e2e6ea')))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Thank you for shopping with {store_info['name']}! "
        f"Questions about this invoice? Contact {store_info['support_email']} "
        f"or {store_info['support_phone']}.",
        small_muted,
    ))

    doc.build(story)
    return buffer.getvalue()
