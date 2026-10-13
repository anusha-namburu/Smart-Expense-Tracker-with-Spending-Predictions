from urllib.parse import urlsplit
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app.extensions import db
from app.models import User, Notification
from app.auth.forms import LoginForm, RegisterForm, ProfileForm, ChangePasswordForm
from app.utils import init_default_categories, process_recurring_expenses, check_and_create_budget_alerts

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            currency=form.currency.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        # Ensure global default categories exist
        init_default_categories()

        # Send welcome notification
        welcome_notif = Notification(
            user_id=user.id,
            title="Welcome to Smart Expense Tracker!",
            message="Your account is set up. Start recording transactions or setting budgets to unlock AI spending predictions.",
            type="info",
            dedup_key=f"welcome_{user.id}"
        )
        db.session.add(welcome_notif)
        db.session.commit()

        login_user(user)
        flash('Registration successful! Welcome to your Smart Expense Tracker.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password. Please verify your credentials.', 'danger')
            return render_template('auth/login.html', form=form)

        login_user(user, remember=form.remember_me.data)

        # Idempotently check recurring expenses and budget alerts upon login
        process_recurring_expenses(user.id)
        check_and_create_budget_alerts(user.id)

        flash(f'Welcome back, {user.username}!', 'success')
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('dashboard.index')
        return redirect(next_page)

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been safely signed out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_form = ProfileForm(prefix='profile')
    password_form = ChangePasswordForm(prefix='password')

    if profile_form.validate_on_submit() and 'profile-submit' in request.form:
        current_user.username = profile_form.username.data.strip()
        current_user.currency = profile_form.currency.data
        db.session.commit()
        flash('Your profile settings have been updated.', 'success')
        return redirect(url_for('auth.profile'))

    if password_form.validate_on_submit() and 'password-submit' in request.form:
        if not current_user.check_password(password_form.old_password.data):
            flash('Your current password was entered incorrectly.', 'danger')
        else:
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash('Your password has been successfully updated.', 'success')
            return redirect(url_for('auth.profile'))

    if request.method == 'GET':
        profile_form.username.data = current_user.username
        profile_form.currency.data = current_user.currency

    return render_template('auth/profile.html', profile_form=profile_form, password_form=password_form)
