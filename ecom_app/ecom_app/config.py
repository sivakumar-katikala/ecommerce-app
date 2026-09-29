import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # In production, ALWAYS set SECRET_KEY via environment variable.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-8f42a1c9')
    SERVER_NAME = os.getenv("SERVER_NAME")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'instance', 'ecom.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # SESSION_COOKIE_SECURE should be True when served over HTTPS in production.
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'

    PERMANENT_SESSION_LIFETIME = 3600

    # ---- Order confirmation email (Gmail SMTP by default) ----
    # MAIL_USERNAME must be a full Gmail address, and MAIL_PASSWORD must be a
    # 16-character Gmail "App Password" (not your normal Gmail login password —
    # Google requires this for SMTP sign-in). Generate one at:
    # https://myaccount.google.com/apppasswords  (requires 2-Step Verification enabled)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
    
    # Emails send automatically whenever MAIL_USERNAME/MAIL_PASSWORD are set —
    # no separate opt-in flag. This matches "send automatically after payment".  

    # ---- Stripe (real card payment gateway) ----
    # Get test-mode keys from https://dashboard.stripe.com/test/apikeys
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_CURRENCY = os.environ.get('STRIPE_CURRENCY', 'inr')
    # Get this from the Stripe CLI (`stripe listen`) or your webhook endpoint
    # settings in the Stripe Dashboard. Required to verify webhook authenticity.
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # ---- Order pricing (demo values — adjust to your actual business rules) ----
    TAX_RATE = float(os.environ.get('TAX_RATE', '0.18'))               # 18% demo GST-style rate
    SHIPPING_FLAT_FEE = float(os.environ.get('SHIPPING_FLAT_FEE', '49'))
    FREE_SHIPPING_THRESHOLD = float(os.environ.get('FREE_SHIPPING_THRESHOLD', '999'))

    # ---- Store branding (used in the email template, invoice, and footer) ----
    STORE_NAME = os.environ.get('STORE_NAME', 'ShopEasy')
    STORE_LOGO_URL = os.environ.get('STORE_LOGO_URL', '')  # empty -> falls back to a text logo
    STORE_WEBSITE = os.environ.get('STORE_WEBSITE', 'https://example.com')
    SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', MAIL_USERNAME or 'support@example.com')
    SUPPORT_PHONE = os.environ.get('SUPPORT_PHONE', '+91 90000 00000')
    SOCIAL_FACEBOOK = os.environ.get('SOCIAL_FACEBOOK', '')
    SOCIAL_INSTAGRAM = os.environ.get('SOCIAL_INSTAGRAM', '')
    SOCIAL_TWITTER = os.environ.get('SOCIAL_TWITTER', '')
