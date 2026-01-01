from flask import render_template
from . import bp
from extensions import db

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
