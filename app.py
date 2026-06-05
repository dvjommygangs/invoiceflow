import os
import json
import hashlib
from datetime import datetime
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import login_user, login_required, logout_user, current_user, LoginManager
from models import db, User, Invoice
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import json
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-to-a-random-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invoiceflow.db'
app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_test_xxx')
app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_xxx')

@app.template_filter('fromjson')
def fromjson_filter(value):
    return json.loads(value)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_invoice_number(user_id):
    count = Invoice.query.filter_by(user_id=user_id).count() + 1
    return f"INV-{datetime.utcnow().strftime('%Y%m')}-{count:04d}"

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('business_name', '')
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        user = User(email=email, password_hash=hash_password(password), business_name=name)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Account created! Welcome to InvoiceFlow.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.password_hash == hash_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).all()
    total_sent = sum(i.total for i in invoices if i.status == 'sent' or i.status == 'paid')
    total_paid = sum(i.total for i in invoices if i.status == 'paid')
    invoice_count = len(invoices)
    return render_template('dashboard.html', invoices=invoices, total_sent=total_sent,
                           total_paid=total_paid, invoice_count=invoice_count)

@app.route('/invoices')
@login_required
def invoices():
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).all()
    return render_template('invoices.html', invoices=invoices)

@app.route('/invoices/new', methods=['GET', 'POST'])
@login_required
def invoice_new():
    if request.method == 'POST':
        items_data = []
        descriptions = request.form.getlist('description[]')
        quantities = request.form.getlist('quantity[]')
        rates = request.form.getlist('rate[]')
        for desc, qty, rate in zip(descriptions, quantities, rates):
            if desc.strip():
                items_data.append({
                    'description': desc,
                    'quantity': float(qty or 1),
                    'rate': float(rate or 0)
                })
        if not items_data:
            flash('Add at least one line item', 'error')
            return render_template('invoice_form.html', invoice=None)
        subtotal = sum(item['quantity'] * item['rate'] for item in items_data)
        tax_rate = float(request.form.get('tax_rate', 0))
        tax_amount = subtotal * (tax_rate / 100)
        total = subtotal + tax_amount
        invoice = Invoice(
            invoice_number=generate_invoice_number(current_user.id),
            client_name=request.form.get('client_name'),
            client_email=request.form.get('client_email'),
            client_address=request.form.get('client_address', ''),
            items=json.dumps(items_data),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total,
            due_date=request.form.get('due_date'),
            notes=request.form.get('notes', ''),
            status='draft',
            user_id=current_user.id
        )
        db.session.add(invoice)
        db.session.commit()
        flash(f'Invoice {invoice.invoice_number} created!', 'success')
        return redirect(url_for('invoices'))
    return render_template('invoice_form.html', invoice=None)

@app.route('/invoices/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def invoice_edit(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('invoices'))
    if request.method == 'POST':
        items_data = []
        descriptions = request.form.getlist('description[]')
        quantities = request.form.getlist('quantity[]')
        rates = request.form.getlist('rate[]')
        for desc, qty, rate in zip(descriptions, quantities, rates):
            if desc.strip():
                items_data.append({
                    'description': desc,
                    'quantity': float(qty or 1),
                    'rate': float(rate or 0)
                })
        if not items_data:
            flash('Add at least one line item', 'error')
            return render_template('invoice_form.html', invoice=invoice)
        subtotal = sum(item['quantity'] * item['rate'] for item in items_data)
        tax_rate = float(request.form.get('tax_rate', 0))
        tax_amount = subtotal * (tax_rate / 100)
        invoice.client_name = request.form.get('client_name')
        invoice.client_email = request.form.get('client_email')
        invoice.client_address = request.form.get('client_address', '')
        invoice.items = json.dumps(items_data)
        invoice.subtotal = subtotal
        invoice.tax_rate = tax_rate
        invoice.tax_amount = tax_amount
        invoice.total = subtotal + tax_amount
        invoice.due_date = request.form.get('due_date')
        invoice.notes = request.form.get('notes', '')
        db.session.commit()
        flash(f'Invoice {invoice.invoice_number} updated!', 'success')
        return redirect(url_for('invoices'))
    return render_template('invoice_form.html', invoice=invoice)

@app.route('/invoices/<int:id>/view')
@login_required
def invoice_view(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('invoices'))
    items = json.loads(invoice.items)
    return render_template('invoice_view.html', invoice=invoice, items=items)

@app.route('/invoices/<int:id>/pdf')
@login_required
def invoice_pdf(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('invoices'))
    items = json.loads(invoice.items)
    buf = BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    p.setFont("Helvetica-Bold", 20)
    p.drawString(40, height - 50, current_user.business_name or current_user.email)
    p.setFont("Helvetica", 10)
    p.drawString(40, height - 70, f"Invoice: {invoice.invoice_number}")
    p.drawString(40, height - 85, f"Date: {invoice.created_at.strftime('%Y-%m-%d')}")
    p.drawString(40, height - 100, f"Due: {invoice.due_date or 'N/A'}")
    p.drawString(40, height - 115, f"Status: {invoice.status.upper()}")
    p.drawString(350, height - 70, "Bill To:")
    p.drawString(350, height - 85, invoice.client_name)
    p.drawString(350, height - 100, invoice.client_email or "")
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, height - 145, "Description")
    p.drawString(350, height - 145, "Qty")
    p.drawString(400, height - 145, "Rate")
    p.drawString(470, height - 145, "Amount")
    p.line(40, height - 150, 560, height - 150)
    y = height - 170
    p.setFont("Helvetica", 10)
    for item in items:
        p.drawString(40, y, item['description'][:45])
        p.drawString(350, y, str(item['quantity']))
        p.drawString(400, y, f"${item['rate']:.2f}")
        p.drawString(470, y, f"${item['quantity'] * item['rate']:.2f}")
        y -= 20
    p.line(40, y - 5, 560, y - 5)
    y -= 25
    p.drawString(400, y, f"Subtotal: ${invoice.subtotal:.2f}")
    y -= 15
    p.drawString(400, y, f"Tax ({invoice.tax_rate}%): ${invoice.tax_amount:.2f}")
    y -= 15
    p.setFont("Helvetica-Bold", 12)
    p.drawString(400, y, f"Total: ${invoice.total:.2f}")
    if invoice.notes:
        y -= 30
        p.setFont("Helvetica", 9)
        p.drawString(40, y, f"Notes: {invoice.notes}")
    p.showPage()
    p.save()
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"{invoice.invoice_number}.pdf",
                     mimetype='application/pdf')

@app.route('/invoices/<int:id>/send')
@login_required
def invoice_send(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('invoices'))
    invoice.status = 'sent'
    db.session.commit()
    flash(f'Invoice {invoice.invoice_number} marked as sent!', 'success')
    return redirect(url_for('invoices'))

@app.route('/invoices/<int:id>/paid')
@login_required
def invoice_paid(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('invoices'))
    invoice.status = 'paid'
    db.session.commit()
    flash(f'Invoice {invoice.invoice_number} marked as paid!', 'success')
    return redirect(url_for('invoices'))

@app.route('/invoices/<int:id>/delete')
@login_required
def invoice_delete(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('invoices'))
    db.session.delete(invoice)
    db.session.commit()
    flash(f'Invoice deleted!', 'success')
    return redirect(url_for('invoices'))

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

import stripe
@app.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    stripe.api_key = app.config['STRIPE_SECRET_KEY']
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{
                'price': os.environ.get('STRIPE_PRICE_ID', 'price_pro_monthly'),
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.host_url + 'dashboard?subscribed=true',
            cancel_url=request.host_url + 'pricing',
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        flash(f'Payment error: {str(e)}', 'error')
        return redirect(url_for('pricing'))

@app.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    stripe.api_key = app.config['STRIPE_SECRET_KEY']
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET', ''))
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        email = session.get('customer_email') or session.get('customer_details', {}).get('email')
        if email:
            user = User.query.filter_by(email=email).first()
            if user:
                user.plan = 'pro'
                user.stripe_customer_id = customer_id
                user.stripe_subscription_id = subscription_id
                db.session.commit()
    return '', 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
