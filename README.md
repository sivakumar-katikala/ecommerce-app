# ShopEasy — Flask E-commerce Application

A full-featured e-commerce web app built with **Flask**, **Flask-SQLAlchemy**, **Flask-WTF**, **Flask-Login**, and **Stripe**.

## Features

- **Product catalog** with unique SKUs, categories, stock, and images. Discounted products show the original price struck through in **red** and the sale price in **green**.
- **Live price/stock updates** — the catalog and product pages poll the server every few seconds and update in place, no reload, so shoppers see owner changes automatically.
- **Cart & checkout** with five payment methods: real **Stripe Checkout** (card, PCI-compliant, hosted by Stripe), plus UI-only demo methods (UPI, Net Banking, Debit/Credit Card, Wallet) with no real gateway integrated.
- **Webhook-driven order fulfillment** — Stripe orders are created `PENDING` immediately, then only marked `PAID` (and only then does stock get decremented) once Stripe's webhook independently confirms payment via `checkout.session.completed` / `payment_intent.succeeded`. A customer can never fake a paid order just by visiting a URL.
- **Professional order success page** (Bootstrap 5) — animated checkmark, full order/customer/payment details, itemized products with images, order summary breakdown (subtotal/discount/tax/shipping/total), and Continue Shopping / View Orders / Download Invoice buttons. Auto-refreshes while a Stripe payment is still confirming.
- **Automatic order confirmation email** — sent immediately once an order is confirmed `PAID` (by the webhook, or synchronously for the demo methods). Professional HTML email (inline CSS, renders correctly in Gmail) with itemized products, pricing breakdown, shipping address, payment info, and Track Order / Download Invoice buttons — plus a **PDF invoice attached**.
- **PDF invoice generation** (ReportLab) — invoice number, line items, tax/shipping/discount breakdown, billing/shipping details, and payment info. Downloadable anytime from the order success page, order history, or the email attachment.
- **Owner dashboard** (`/owner/dashboard`) — sales trend graphs (Chart.js), daily sales table, live Units Sold / Stock Remaining per product, recent visitor log, an **Orders** page with per-order email delivery status and a **Resend Email** button, and a browser-based **Email Settings** page to check SMTP config and send test emails without touching a terminal.
- **Race-safe stock control** — stock is decremented atomically at the database level, so overselling under concurrent checkouts is impossible.
- **Security** — CSRF protection everywhere, Werkzeug password hashing, security headers (CSP, X-Frame-Options, etc.), server-side validation, custom error pages, open-redirect protection. Card CVV/expiry (for the demo card methods) are validated but **never stored**.

## Project Structure

```
ecom_app/
├── app.py                       # App factory, blueprint registration, security headers
├── config.py                    # All environment-driven configuration
├── extensions.py                # db, csrf, login_manager instances
├── forms.py                     # WTForms: Registration, Login, Product, Checkout
├── seed.py                      # Creates a default owner + sample products
├── test_email.py                # CLI tool to test/resend confirmation emails
├── requirements.txt
├── models/
│   ├── user.py                  # User (auth)
│   ├── product.py                # Product (catalog)
│   ├── order.py                   # Order + OrderItem (pricing, Stripe IDs, invoice, email status)
│   └── visit.py                    # Visit (page-view tracking)
├── routes/
│   ├── auth.py                  # signup / login / logout
│   ├── products.py               # product listing, detail, live-status JSON API
│   ├── orders.py                  # cart, checkout (demo methods), order history, invoice download
│   ├── payment.py                  # Stripe: checkout session, success redirect, webhook
│   └── owner.py                    # dashboard, product CRUD, orders list + resend, email settings
├── services/
│   ├── pricing_service.py       # subtotal/discount/tax/shipping/total calculation
│   ├── email_service.py          # renders + sends the confirmation email (with invoice attached)
│   └── invoice_service.py         # wraps utils/pdf_generator with order/store data
├── utils/
│   └── pdf_generator.py         # low-level ReportLab invoice PDF builder
├── templates/
│   ├── base.html, index.html, product_detail.html, login.html, register.html,
│   │   cart.html, checkout.html, order_success.html, my_orders.html
│   ├── emails/order_confirmation.html   # HTML email template (inline CSS)
│   ├── owner/dashboard.html, orders.html, test_email.html, add_product.html
│   └── errors/403.html, 404.html, 500.html
├── static/css/style.css
└── instance/                    # SQLite DB is created here at runtime
```

## Setup

```bash
cd ecom_app
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The app runs at **http://127.0.0.1:5000**. On first run it creates the SQLite database and seeds:
- An **owner account**: username `owner`, password `OwnerPass123` (change this before any real deployment).
- 33 sample products across 6 categories, several with discounts.

If you update the code later and the database already exists, the app will print a clear warning at startup if the schema is out of date — just delete `instance/ecom.db` and restart.

## Environment Variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask session/CSRF signing key |
| `DATABASE_URL` | e.g. `postgresql://user:pass@host/dbname` for production |
| `SESSION_COOKIE_SECURE` | `True` when serving over HTTPS |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | Your store's Gmail address + **App Password** — enables order confirmation emails |
| `MAIL_DEFAULT_SENDER`, `MAIL_SERVER`, `MAIL_PORT` | Optional overrides |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` | Stripe test (or live) API keys — enables real Stripe Checkout |
| `STRIPE_WEBHOOK_SECRET` | Verifies that webhook requests genuinely came from Stripe — **required before production** |
| `STRIPE_CURRENCY` | Optional, defaults to `inr` |
| `TAX_RATE` | Optional, defaults to `0.18` (18%) |
| `SHIPPING_FLAT_FEE` / `FREE_SHIPPING_THRESHOLD` | Optional, default `49` / `999` |
| `STORE_NAME`, `STORE_LOGO_URL`, `STORE_WEBSITE`, `SUPPORT_EMAIL`, `SUPPORT_PHONE`, `SOCIAL_FACEBOOK`, `SOCIAL_INSTAGRAM`, `SOCIAL_TWITTER` | Branding shown in the email/invoice/footer |

Emails send **automatically** whenever `MAIL_USERNAME`/`MAIL_PASSWORD` are set — there's no separate on/off flag. If they're not set, orders still complete normally; the email step is just skipped and logged.

## Email Setup (Gmail)

```powershell
$env:MAIL_USERNAME = "yourstore@gmail.com"
$env:MAIL_PASSWORD = "your16charapppassword"
python app.py
```

Gmail requires an **App Password** (not your normal login password):
1. Enable 2-Step Verification: https://myaccount.google.com/security
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use that 16-character password as `MAIL_PASSWORD`.

**Testing your email setup — three ways, no manual typing required:**
1. **Browser** (easiest): log in as owner → Dashboard → "✉️ Email Settings" → shows configured status, and has a "Send Test Email" box.
2. **CLI, auto-resend**: `python test_email.py` — finds the most recent real PAID order and resends its actual confirmation (real buyer email, real items) to that buyer.
3. **CLI, sample**: `python test_email.py someone@gmail.com` — sends a realistic sample confirmation (with sample items and a sample invoice) to any address.

If an email fails to send for a real order, the reason is stored on that order and visible on the owner's **Orders** page (`/owner/orders`), with a **Resend Email** button to retry once the issue is fixed.

## Stripe Setup

### 1. API keys (test mode — no real money)

```powershell
$env:STRIPE_SECRET_KEY = "sk_test_..."
$env:STRIPE_PUBLISHABLE_KEY = "pk_test_..."
python app.py
```
Get test keys free at https://dashboard.stripe.com/test/apikeys (sign up if needed).

### 2. Webhook setup (required for orders to ever complete)

Stripe orders only become `PAID` when Stripe's webhook confirms payment — **without a working webhook, Stripe orders stay `PENDING` forever**, even after you successfully pay on Stripe's page. For local testing, use the [Stripe CLI](https://stripe.com/docs/stripe-cli):

```bash
stripe login
stripe listen --forward-to localhost:5000/payment/webhook
```

This prints a webhook signing secret like `whsec_...` — set it:
```powershell
$env:STRIPE_WEBHOOK_SECRET = "whsec_..."
```
Restart `python app.py` after setting this. Keep `stripe listen` running in a separate terminal the whole time you're testing — it's what actually delivers Stripe's events to your local server.

**Without `STRIPE_WEBHOOK_SECRET` set**, the webhook endpoint still works but logs a warning that signatures aren't being verified — fine for a first quick test, but treat this as required before anything resembling production, since without it anyone could POST a fake "payment succeeded" event to your server.

### 3. Test the full flow

1. Add something to your cart, go to checkout, choose **"Card (Stripe Secure Checkout)"**.
2. You'll land on Stripe's real hosted payment page. Use a test card:

| Field | Value |
|---|---|
| Card number | `4242 4242 4242 4242` |
| Expiry | any future date, e.g. `12/34` |
| CVC | any 3 digits |
| ZIP | any 5 digits |

3. After paying, you're redirected back — the order page shows a spinner ("Confirming your payment...") for a moment while the webhook arrives, then automatically shows the full success page once `stripe listen` delivers the event to your server.
4. Check the terminal running `stripe listen` — you should see the `checkout.session.completed` event logged there and forwarded successfully (`200`) to your app.

### Production readiness checklist
- Use **live** keys (`sk_live_...` / `pk_live_...`) instead of test keys.
- Register a real webhook endpoint in the Stripe Dashboard (Developers → Webhooks) pointing at your real domain, instead of `stripe listen`, and set `STRIPE_WEBHOOK_SECRET` to that endpoint's signing secret.
- Set `SESSION_COOKIE_SECURE=True` once served over HTTPS.

## Notes

- Only **"Card (Stripe Secure Checkout)"** is a real payment gateway. UPI / Net Banking / Debit-Credit Card (demo) / Wallet are UI-only demos with no real processor — useful for showing the checkout UX, but nothing is actually charged. Demo-card CVV/expiry are validated then immediately discarded; only a masked reference (e.g. `Debit Card:****1234`) is stored.
- Tax and shipping use simple demo rules (`TAX_RATE`, `SHIPPING_FLAT_FEE`, `FREE_SHIPPING_THRESHOLD`) — swap in real logic for production.
- The invoice PDF and email both regenerate on demand from the database rather than being stored as files — there's no stale-file cleanup to worry about.
- To make a user an owner, set `is_owner=True` on their row in the `users` table.
