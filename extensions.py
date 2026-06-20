import os
import platform
import sys

from flask_sqlalchemy import SQLAlchemy
try:
    from flask_migrate import Migrate
except Exception:
    class Migrate:
        def __init__(self, *args, **kwargs):
            return None

        def init_app(self, *args, **kwargs):
            return None
from flask_login import LoginManager, current_user
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.theme import Bootstrap4Theme
from flask_babel import Babel
from flask_wtf.csrf import CSRFProtect
from flask import redirect, url_for, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_mail import Mail
from flask_caching import Cache
from utils.seo import SEOManager


def _patch_platform_for_restricted_windows():
    if sys.platform != "win32":
        return

    def _safe_win32_ver(release="", version="", csd="", ptype=""):
        try:
            v = sys.getwindowsversion()
            release = f"{v.major}.{v.minor}"
            version = str(getattr(v, "build", ""))
            csd = getattr(v, "service_pack", "") or ""
            return release, version, csd, ptype
        except Exception:
            return "", "", "", ""

    platform.win32_ver = _safe_win32_ver

    uname_result = getattr(platform, "uname_result", None)
    if uname_result is None:
        return

    def _safe_uname():
        v = getattr(sys, "getwindowsversion", lambda: None)()
        system = "Windows"
        import socket
        try:
            node = socket.gethostname()
        except Exception:
            node = "Unknown"
        release = (
            f"{getattr(v, 'major', '')}.{getattr(v, 'minor', '')}"
            if v else "")
        version = str(getattr(v, "build", "")) if v else ""
        machine = os.environ.get("PROCESSOR_ARCHITECTURE", "") or ""
        processor = os.environ.get("PROCESSOR_IDENTIFIER", "") or ""
        try:
            return uname_result(
                system,
                node,
                release,
                version,
                machine,
                processor)
        except TypeError:
            return uname_result(system, node, release, version, machine)

    platform.uname = _safe_uname
    platform.machine = lambda: (
        os.environ.get("PROCESSOR_ARCHITECTURE", "") or "")


_patch_platform_for_restricted_windows()

try:
    from flask_socketio import SocketIO
    try:
        socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')
    except Exception:
        socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
except Exception:
    socketio = None

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'main.login'  # Corrected blueprint name
login.login_message = 'Please log in to access this page.'


@login.unauthorized_handler
def _handle_unauthorized():
    try:
        next_url = request.full_path
        if next_url and next_url.endswith('?'):
            next_url = next_url[:-1]
        return redirect(url_for('main.login', next=next_url))
    except Exception:
        return redirect('/login')


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"])
talisman = Talisman()
mail = Mail()
cache = Cache(config={
    'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})
seo_manager = SEOManager()


class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('main.login'))

    @expose('/')
    def index(self):
        from models import User, Gang, Crime, Item, GameLog, PaymentTransaction
        from sqlalchemy import func

        stats = {
            'user_count': User.query.count(),
            'gang_count': Gang.query.count(),
            'total_money': (
                db.session.query(func.sum(User.money)).scalar() or 0),
            'total_diamonds': (
                db.session.query(func.sum(User.diamonds)).scalar() or 0),
            'crime_count': Crime.query.count(),
            'item_count': Item.query.count(),
            'pending_payments': PaymentTransaction.query.filter_by(
                status='pending').count()
        }

        recent_users = User.query.order_by(User.id.desc()).limit(5).all()
        recent_logs = GameLog.query.order_by(
            GameLog.timestamp.desc()).limit(5).all()
        pending_transactions = PaymentTransaction.query.filter_by(
            status='pending').order_by(
                PaymentTransaction.created_at.desc()).limit(5).all()

        return self.render(
            'admin/index.html', stats=stats, recent_users=recent_users,
            recent_logs=recent_logs, pending_transactions=pending_transactions)


admin = Admin(
    name='Gangs of Palestine',
    index_view=MyAdminIndexView(),
    theme=Bootstrap4Theme())
babel = Babel()
csrf = CSRFProtect()
