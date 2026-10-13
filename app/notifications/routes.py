from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Notification

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/')
@login_required
def index():
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()

    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()

    return render_template(
        'notifications/index.html',
        notifications=notifications,
        unread_count=unread_count
    )

@notifications_bp.route('/<int:id>/read', methods=['POST'])
@login_required
def mark_read(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id != current_user.id:
        abort(403)

    notif.is_read = True
    db.session.commit()
    return redirect(url_for('notifications.index'))

@notifications_bp.route('/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications.index'))

@notifications_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id != current_user.id:
        abort(403)

    db.session.delete(notif)
    db.session.commit()
    flash('Notification dismissed.', 'info')
    return redirect(url_for('notifications.index'))
