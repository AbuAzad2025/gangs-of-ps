from flask import Blueprint

bp = Blueprint('hostesses', __name__)

from . import jasmin, layla, ruby, sarah

def register_hostess_blueprints(app):
    app.register_blueprint(jasmin.bp)
    app.register_blueprint(layla.bp)
    app.register_blueprint(ruby.bp)
    app.register_blueprint(sarah.bp)

