import csv
import io
from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import desc, asc
from app.extensions import db
from app.models import Transaction, Category
from app.transactions.forms import TransactionForm, CategoryForm
from app.utils import get_user_categories, check_and_create_budget_alerts

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search_q = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '')
    category_filter = request.args.get('category', type=int)
    payment_method = request.args.get('payment_method', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    sort_by = request.args.get('sort_by', 'date')
    order = request.args.get('order', 'desc')

    # Base query restricted strictly to current authenticated user
    query = Transaction.query.filter_by(user_id=current_user.id)

    # Search filter
    if search_q:
        query = query.filter(Transaction.description.ilike(f'%{search_q}%'))

    # Type filter
    if type_filter in ['income', 'expense']:
        query = query.filter(Transaction.type == type_filter)

    # Category filter
    if category_filter:
        query = query.filter(Transaction.category_id == category_filter)

    # Payment method filter
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)

    # Date range filters
    if start_date_str:
        try:
            start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date >= start_d)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date <= end_d)
        except ValueError:
            pass

    # Sorting
    if sort_by == 'amount':
        order_col = desc(Transaction.amount) if order == 'desc' else asc(Transaction.amount)
    else:
        order_col = desc(Transaction.transaction_date) if order == 'desc' else asc(Transaction.transaction_date)

    query = query.order_by(order_col, desc(Transaction.created_at))

    # Pagination
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    transactions = pagination.items

    # Categories for filter dropdown
    categories = get_user_categories(current_user.id)

    # Modal add form
    form = TransactionForm()
    form.category_id.choices = [(c.id, f"{c.name} ({c.type.capitalize()})") for c in categories]

    # Category creation form
    cat_form = CategoryForm()

    return render_template(
        'transactions/index.html',
        transactions=transactions,
        pagination=pagination,
        categories=categories,
        form=form,
        cat_form=cat_form,
        search_q=search_q,
        type_filter=type_filter,
        category_filter=category_filter,
        payment_method=payment_method,
        start_date=start_date_str,
        end_date=end_date_str,
        sort_by=sort_by,
        order=order
    )

@transactions_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    categories = get_user_categories(current_user.id)
    form = TransactionForm()
    form.category_id.choices = [(c.id, f"{c.name} ({c.type.capitalize()})") for c in categories]

    if form.validate_on_submit():
        category = Category.query.get(form.category_id.data)
        if not category:
            flash('Invalid category selected.', 'danger')
            return redirect(url_for('transactions.index'))

        tx = Transaction(
            user_id=current_user.id,
            category_id=category.id,
            amount=form.amount.data,
            type=form.type.data,
            description=form.description.data.strip() if form.description.data else '',
            transaction_date=form.transaction_date.data,
            payment_method=form.payment_method.data
        )
        db.session.add(tx)
        db.session.commit()

        # Recalculate alerts if this was an expense
        if tx.type == 'expense':
            check_and_create_budget_alerts(current_user.id, tx.transaction_date)

        flash('Transaction recorded successfully!', 'success')
        return redirect(url_for('transactions.index'))

    return render_template('transactions/form.html', form=form, title='Add Transaction')

@transactions_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    tx = Transaction.query.get_or_404(id)
    # Authorization check - prevent IDOR
    if tx.user_id != current_user.id:
        abort(403)

    categories = get_user_categories(current_user.id)
    form = TransactionForm(obj=tx)
    form.category_id.choices = [(c.id, f"{c.name} ({c.type.capitalize()})") for c in categories]

    if form.validate_on_submit():
        category = Category.query.get(form.category_id.data)
        if not category:
            flash('Invalid category selected.', 'danger')
            return redirect(url_for('transactions.index'))

        tx.category_id = category.id
        tx.type = form.type.data
        tx.amount = form.amount.data
        tx.transaction_date = form.transaction_date.data
        tx.payment_method = form.payment_method.data
        tx.description = form.description.data.strip() if form.description.data else ''
        db.session.commit()

        check_and_create_budget_alerts(current_user.id, tx.transaction_date)
        flash('Transaction updated successfully.', 'success')
        return redirect(url_for('transactions.index'))

    return render_template('transactions/form.html', form=form, title='Edit Transaction', transaction=tx)

@transactions_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    tx = Transaction.query.get_or_404(id)
    if tx.user_id != current_user.id:
        abort(403)

    tx_date = tx.transaction_date
    db.session.delete(tx)
    db.session.commit()

    check_and_create_budget_alerts(current_user.id, tx_date)
    flash('Transaction deleted.', 'info')
    return redirect(url_for('transactions.index'))

@transactions_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        # Check duplicate
        exists = Category.query.filter(
            Category.user_id == current_user.id,
            Category.name == form.name.data.strip(),
            Category.type == form.type.data
        ).first()
        if exists:
            flash(f"Category '{form.name.data}' already exists for {form.type.data}.", 'warning')
        else:
            cat = Category(
                user_id=current_user.id,
                name=form.name.data.strip(),
                type=form.type.data,
                icon=form.icon.data,
                color=form.color.data,
                is_default=False
            )
            db.session.add(cat)
            db.session.commit()
            flash(f"Custom category '{cat.name}' added successfully!", 'success')
    else:
        for err in form.errors.values():
            flash(err[0], 'danger')

    return redirect(url_for('transactions.index'))

@transactions_bp.route('/export-csv')
@login_required
def export_csv():
    # Filter identical to index query
    search_q = request.args.get('q', '').strip()
    type_filter = request.args.get('type', '')
    category_filter = request.args.get('category', type=int)
    payment_method = request.args.get('payment_method', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    query = Transaction.query.filter_by(user_id=current_user.id)

    if search_q:
        query = query.filter(Transaction.description.ilike(f'%{search_q}%'))
    if type_filter in ['income', 'expense']:
        query = query.filter(Transaction.type == type_filter)
    if category_filter:
        query = query.filter(Transaction.category_id == category_filter)
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)
    if start_date_str:
        try:
            start_d = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date >= start_d)
        except ValueError:
            pass
    if end_date_str:
        try:
            end_d = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(Transaction.transaction_date <= end_d)
        except ValueError:
            pass

    records = query.order_by(desc(Transaction.transaction_date)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Transaction ID',
        'Date',
        'Type',
        'Category',
        'Amount',
        'Currency',
        'Payment Method',
        'Description',
        'Created Timestamp'
    ])

    for t in records:
        writer.writerow([
            t.id,
            t.transaction_date.isoformat(),
            t.type.capitalize(),
            t.category.name if t.category else 'N/A',
            f"{float(t.amount):.2f}",
            current_user.currency,
            t.payment_method,
            t.description or '',
            t.created_at.isoformat()
        ])

    csv_data = output.getvalue()
    filename = f"transactions_{current_user.username.lower()}_{date.today().isoformat()}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
