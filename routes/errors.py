from flask import render_template, request, redirect, url_for, flash, jsonify
from . import bp
from extensions import db
from flask_wtf.csrf import CSRFError
from flask_babel import _


@bp.app_errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403


@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


@bp.app_errorhandler(429)
def ratelimit_error(error):
    return render_template('errors/429.html', error=error), 429


@bp.app_errorhandler(CSRFError)
def csrf_error(error):
    db.session.rollback()
    wants_json = request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
    is_api = request.path.startswith(
        '/api/') or request.path.startswith('/market/api/')
    if wants_json or is_api:
        return jsonify({'error': 'csrf', 'message': getattr(
            error, 'description', 'CSRF error')}), 400
    flash(
        _('انتهت صلاحية الجلسة أو رمز الحماية. حدّث الصفحة وحاول مرة أخرى.'),
        'warning')
    return redirect(request.referrer or url_for('main.index'))
