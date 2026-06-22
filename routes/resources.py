from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from models.log import UserLog, MoneySinkLog
from models.user import UserRole, User
from services.budget_service import BudgetService
from routes.utils import track_academy_visit

bp = Blueprint('resources', __name__, url_prefix='/resources')


def _parse_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


@bp.route('/ledger')
@login_required
def my_ledger():
    track_academy_visit(current_user, 'ledger_visit')
    return _ledger_view(current_user.id)


@bp.route('/ledger/<int:user_id>')
@login_required
def ledger(user_id):
    if current_user.id != user_id and current_user.role.value < UserRole.MODERATOR.value:
        abort(403)
    return _ledger_view(user_id)


def _ledger_view(user_id: int):
    user = User.query.get_or_404(user_id)
    page = _parse_int(request.args.get('page', 1), 1)
    per_page = min(
        max(_parse_int(request.args.get('per_page', 50), 50), 10), 200)

    q = UserLog.query.filter(UserLog.user_id == user_id).filter(
        or_(
            UserLog.details.ilike("%money%"),
            UserLog.details.ilike("%bank_balance%"),
            UserLog.details.ilike("%diamonds%"),
            UserLog.before_state.isnot(None),
            UserLog.after_state.isnot(None),
        )
    ).order_by(UserLog.timestamp.desc())

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    entries = []
    for log in pagination.items:
        deltas = BudgetService.extract_deltas(log)

        entries.append(
            {
                "id": log.id,
                "timestamp": log.timestamp,
                "action": log.action,
                "scenario": BudgetService.scenario_for_action(
                    log.action),
                "result": log.result,
                "deltas": deltas,
                "before": log.before_state if isinstance(
                    log.before_state,
                    dict) else None,
                "after": log.after_state if isinstance(
                    log.after_state,
                    dict) else None,
                "ip": log.ip_address,
            })

    sink_entries = MoneySinkLog.query.filter(
        MoneySinkLog.user_id == user_id).order_by(
        MoneySinkLog.timestamp.desc()).limit(80).all()

    return render_template(
        'resources/ledger.html',
        user=user,
        entries=entries,
        sink_entries=sink_entries,
        pagination=pagination,
        per_page=per_page,
    )
