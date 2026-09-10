import re
from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, FloatField,
    IntegerField, SelectField, SubmitField, BooleanField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, NumberRange,
    Optional, Regexp, ValidationError
)
from models import User, Product


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), Length(min=3, max=50),
        Regexp(r'^[A-Za-z0-9_]+$', message='Only letters, numbers and underscores allowed.')
    ])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, message='Password must be at least 8 characters.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Create Account')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('That username is already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('An account with that email already exists.')


class LoginForm(FlaskForm):
    username = StringField('Username or Email', validators=[DataRequired(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Log In')


class ProductForm(FlaskForm):
    sku = StringField('SKU (unique code)', validators=[
        DataRequired(), Length(min=2, max=32),
        Regexp(r'^[A-Za-z0-9\-_]+$', message='Letters, numbers, hyphens and underscores only.')
    ])
    name = StringField('Product Name', validators=[DataRequired(), Length(max=150)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    category = StringField('Category', validators=[DataRequired(), Length(max=80)])
    price = FloatField('Price (₹)', validators=[DataRequired(), NumberRange(min=0.01)])
    discount_price = FloatField('Discount Price (₹, optional)', validators=[Optional(), NumberRange(min=0)])
    stock = IntegerField('Stock Quantity', validators=[DataRequired(), NumberRange(min=0)])
    image_url = StringField('Image URL', validators=[Optional(), Length(max=300)])
    submit = SubmitField('Save Product')

    def validate_sku(self, field):
        existing = Product.query.filter_by(sku=field.data).first()
        if existing and (not hasattr(self, 'product_id') or existing.id != self.product_id):
            raise ValidationError('A product with this SKU already exists.')

    def validate_discount_price(self, field):
        if field.data is not None and self.price.data is not None:
            if field.data >= self.price.data:
                raise ValidationError('Discount price must be lower than the regular price.')


class AddToCartForm(FlaskForm):
    quantity = IntegerField('Quantity', default=1, validators=[DataRequired(), NumberRange(min=1, max=99)])
    submit = SubmitField('Add to Cart')


class CheckoutForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    contact_email = StringField('Email (for order confirmation)', validators=[
        DataRequired(), Email(), Length(max=120)
    ])
    contact_phone = StringField('Mobile Number', validators=[
        DataRequired(),
        Regexp(r'^\+?\d{10,13}$', message='Enter a valid mobile number (10-13 digits, optional +country code).')
    ])
    address = TextAreaField('Delivery Address', validators=[DataRequired(), Length(max=500)])
    payment_method = SelectField('Payment Method', choices=[
        ('STRIPE', 'Card (Stripe Secure Checkout)'),
        ('UPI', 'UPI'),
        ('NET_BANKING', 'Net Banking'),
        ('DEBIT_CARD', 'Debit Card (demo)'),
        ('CREDIT_CARD', 'Credit Card (demo)'),
        ('WALLET', 'Wallet (Paytm / PhonePe / Amazon Pay)'),
    ], validators=[DataRequired()])

    upi_id = StringField('UPI ID', validators=[Optional(), Length(max=100)])
    bank_name = StringField('Bank Name', validators=[Optional(), Length(max=100)])

    card_number = StringField('Card Number', validators=[Optional(), Length(min=12, max=19)])
    card_expiry = StringField('Expiry Date (MM/YY)', validators=[Optional(), Length(max=5)])
    card_cvv = PasswordField('CVV', validators=[Optional(), Length(min=3, max=4)])

    wallet_provider = SelectField('Wallet Provider', choices=[
        ('', '-- Select Wallet --'),
        ('Paytm', 'Paytm'),
        ('PhonePe', 'PhonePe'),
        ('Amazon Pay', 'Amazon Pay'),
        ('Google Pay', 'Google Pay'),
    ], validators=[Optional()])

    submit = SubmitField('Pay Now')

    CARD_METHODS = ('DEBIT_CARD', 'CREDIT_CARD')

    def validate_upi_id(self, field):
        if self.payment_method.data == 'UPI':
            if not field.data:
                raise ValidationError('UPI ID is required for UPI payments.')
            if '@' not in field.data:
                raise ValidationError('Enter a valid UPI ID, e.g. name@bank.')

    def validate_bank_name(self, field):
        if self.payment_method.data == 'NET_BANKING' and not field.data:
            raise ValidationError('Bank name is required for Net Banking.')

    def validate_card_number(self, field):
        if self.payment_method.data in self.CARD_METHODS:
            if not field.data:
                raise ValidationError('Card number is required for card payments.')
            digits = field.data.replace(' ', '')
            if not digits.isdigit():
                raise ValidationError('Card number must contain digits only.')
            if not (12 <= len(digits) <= 19):
                raise ValidationError('Enter a valid card number.')

    def validate_card_expiry(self, field):
        if self.payment_method.data in self.CARD_METHODS:
            if not field.data:
                raise ValidationError('Expiry date is required for card payments.')
            match = re.match(r'^(0[1-9]|1[0-2])/(\d{2})$', field.data.strip())
            if not match:
                raise ValidationError('Enter expiry as MM/YY, e.g. 08/29.')
            month, year_two_digit = int(match.group(1)), int(match.group(2))
            expiry_year = 2000 + year_two_digit
            today = date.today()
            # Card is valid through the end of its expiry month.
            if (expiry_year, month) < (today.year, today.month):
                raise ValidationError('This card has expired.')

    def validate_card_cvv(self, field):
        if self.payment_method.data in self.CARD_METHODS:
            if not field.data:
                raise ValidationError('CVV is required for card payments.')
            if not field.data.isdigit() or not (3 <= len(field.data) <= 4):
                raise ValidationError('CVV must be 3 or 4 digits.')

    def validate_wallet_provider(self, field):
        if self.payment_method.data == 'WALLET' and not field.data:
            raise ValidationError('Please select a wallet provider.')
