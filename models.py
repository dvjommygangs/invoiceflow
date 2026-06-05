import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    business_name = db.Column(db.String(200), default="")
    currency = db.Column(db.String(3), default="USD")
    plan = db.Column(db.String(20), default="free")
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    invoices = db.relationship('Invoice', backref='owner', lazy=True)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), nullable=False)
    client_name = db.Column(db.String(200), nullable=False)
    client_email = db.Column(db.String(120))
    client_address = db.Column(db.Text, default="")
    items = db.Column(db.Text, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="draft")
    due_date = db.Column(db.String(20))
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
