from flask import Blueprint

bp = Blueprint('main', __name__)

from . import auth, core, gameplay, payment, social, economy, garage, developer, search, graveyard, racing, errors
